"""Uma porta só para o modelo: `chamar(papel, instrucao, entrada, esquema)`.

Três tipos de falha, três tratamentos ([ADR 0013](../../../docs/adr/0013-pilha-dos-agentes.md),
item 6):

- **Rede, 429 e 5xx** são do caminho, não da resposta: retenta com espera crescente, até
  `RETENTATIVAS_DE_REDE` vezes.
- **Resposta fora do esquema** é o modelo errando a forma: ganha **uma** segunda tentativa, com o
  erro anexado à entrada. Errou de novo, é erro.
- **Conferência de conteúdo que falha** (nome fora do texto, número sem origem) nunca é
  reenviada. Pedir de novo é pedir ao modelo que insista no erro; o padrão de `ia` é falhar
  alto.

Cada chamada abre um span OpenTelemetry com um filho por tentativa, com os atributos da
convenção `gen_ai.*`, que o Langfuse lê como geração, e registra papel, modelo, versão do
prompt, tokens, latência, tentativa e resultado da validação. Exceção que atravessa o span o
marca como erro, pelo próprio OpenTelemetry.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx
from opentelemetry import baggage, context, trace
from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.trace import Tracer
from pydantic import BaseModel, ValidationError
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential
from tenacity.wait import wait_base

from arco_ia import config

RETENTATIVAS_DE_REDE = 3
"""Quantas vezes se reenvia a mesma pergunta depois de erro de rede, 429 ou 5xx."""

ESPERA = wait_exponential(multiplier=1, min=1, max=8)
"""Entre retentativas de rede: 1 s, 2 s, 4 s, com teto de 8 s."""

NOME_DO_RASTREADOR = "arco_ia"

Validacao = Literal["aceita", "fora_do_esquema", "conferencia_falhou", "erro_na_chamada"]

_registro = logging.getLogger(__name__)


class Cliente(Protocol):
    """A fatia do SDK que a chamada usa, para o teste substituir sem chave nem rede."""

    @property
    def interactions(self) -> Any: ...


class ForaDoEsquema(ValueError):
    """O modelo respondeu duas vezes fora do esquema pedido. Erro, não achado."""


@dataclass(frozen=True)
class Registro:
    """O rastro de uma chamada: quem respondeu, com que prompt, a que custo e com que resultado."""

    papel: str
    modelo: str
    versao_prompt: str
    tokens_entrada: int
    tokens_saida: int
    latencia_s: float
    tentativas: int
    """Pedidos ao modelo, somando as retentativas de rede e a segunda chance de esquema."""
    validacao: Validacao


@dataclass(frozen=True)
class Resposta[M: BaseModel]:
    saida: M
    registro: Registro


def chamar[M: BaseModel](
    papel: config.NomeDoPapel,
    instrucao: str,
    entrada: str,
    esquema: type[M],
    *,
    conferir: Callable[[M], None] | None = None,
    cliente: Cliente | None = None,
    rastreador: Tracer | None = None,
    espera: wait_base = ESPERA,
) -> Resposta[M]:
    """Pergunta ao modelo do papel e devolve a saída validada no esquema, com o registro.

    `conferir` é a conferência de conteúdo de quem chama: roda depois do esquema, dentro do
    span, e o que ela levanta sobe sem nova chamada ao modelo.
    """
    do_papel = config.PAPEIS[papel]
    cli = cliente if cliente is not None else config.cliente(papel)
    rastro = rastreador if rastreador is not None else trace.get_tracer(NOME_DO_RASTREADOR)
    contagem = _Contagem()
    inicio = time.perf_counter()

    with rastro.start_as_current_span(f"chamar {papel}") as span:
        span.set_attributes(
            {
                "gen_ai.operation.name": "chat",
                "gen_ai.provider.name": "gcp.gemini",
                "gen_ai.request.model": do_papel.modelo,
                "arco.papel": papel,
                "arco.versao_prompt": do_papel.versao_prompt,
                "arco.esforco": do_papel.esforco,
                # O que o Langfuse mostra nas colunas próprias, e não só em metadados.
                "langfuse.observation.model.parameters": json.dumps(
                    {"thinking_level": do_papel.esforco}
                ),
                "langfuse.version": do_papel.versao_prompt,
            }
        )

        def registrar(validacao: Validacao) -> Registro:
            registro = Registro(
                papel=papel,
                modelo=do_papel.modelo,
                versao_prompt=do_papel.versao_prompt,
                tokens_entrada=contagem.entrada,
                tokens_saida=contagem.saida,
                latencia_s=round(time.perf_counter() - inicio, 3),
                tentativas=contagem.tentativas,
                validacao=validacao,
            )
            span.set_attributes(
                {
                    "gen_ai.usage.input_tokens": registro.tokens_entrada,
                    "gen_ai.usage.output_tokens": registro.tokens_saida,
                    "arco.tentativas": registro.tentativas,
                    "arco.validacao": validacao,
                }
            )
            _registro.info(
                "chamada ao modelo",
                extra={"chamada": registro.__dict__},
            )
            return registro

        pedido = entrada
        for chance in (1, 2):
            span.set_attribute("langfuse.observation.input", _mensagens(instrucao, pedido))
            try:
                texto = _pedir_com_retentativa(
                    cli, do_papel, instrucao, pedido, esquema, rastro, contagem, espera
                )
            except Exception:
                registrar("erro_na_chamada")
                raise
            span.set_attribute("langfuse.observation.output", texto or "")
            try:
                saida = esquema.model_validate(json.loads(texto or ""))
            except (json.JSONDecodeError, ValidationError) as erro:
                if chance == 2:
                    registrar("fora_do_esquema")
                    raise ForaDoEsquema(
                        f"{papel}: resposta fora do esquema duas vezes. Última: {erro}"
                    ) from erro
                pedido = _com_o_erro(entrada, texto, erro)
                continue
            if conferir is not None:
                try:
                    conferir(saida)
                except Exception:
                    registrar("conferencia_falhou")
                    raise
            return Resposta(saida=saida, registro=registrar("aceita"))
    raise AssertionError("inalcançável: o laço devolve ou levanta")  # pragma: no cover


class _Contagem:
    """Soma tokens e pedidos de todas as tentativas de uma chamada."""

    def __init__(self) -> None:
        self.entrada = 0
        self.saida = 0
        self.tentativas = 0


def _pedir_com_retentativa(
    cli: Cliente,
    papel: config.Papel,
    instrucao: str,
    pedido: str,
    esquema: type[BaseModel],
    rastro: Tracer,
    contagem: _Contagem,
    espera: wait_base,
) -> str:
    """Um pedido ao modelo, retentado só em erro transitório. Um span filho por tentativa."""
    for tentativa in Retrying(
        retry=retry_if_exception(transitorio),
        stop=stop_after_attempt(RETENTATIVAS_DE_REDE + 1),
        wait=espera,
        reraise=True,
    ):
        with tentativa:
            contagem.tentativas += 1
            with rastro.start_as_current_span(f"tentativa {contagem.tentativas}") as filho:
                filho.set_attribute("arco.tentativa", contagem.tentativas)
                interacao = cli.interactions.create(
                    model=papel.modelo,
                    system_instruction=instrucao,
                    input=pedido,
                    response_format={
                        "type": "text",
                        "mime_type": "application/json",
                        "schema": esquema.model_json_schema(),
                    },
                    generation_config={"thinking_level": papel.esforco},
                )
                uso = getattr(interacao, "usage", None)
                # Os tokens ficam só no span da chamada, que o Langfuse lê como geração: postos
                # também aqui, a soma da tarefa sairia dobrada.
                contagem.entrada += getattr(uso, "total_input_tokens", None) or 0
                contagem.saida += getattr(uso, "total_output_tokens", None) or 0
                return interacao.output_text
    raise AssertionError("inalcançável: o Retrying devolve ou relança")  # pragma: no cover


def transitorio(erro: BaseException) -> bool:
    """Erro de rede, 429 ou 5xx: vale retentar. Qualquer outro sobe na primeira.

    O SDK da Interactions API põe `status_code` nos erros de resposta e só exporta as classes
    num módulo privado; por isso a leitura é pelo atributo e pelo nome da classe, não por
    import. `APIConnectionError` é a falha de conexão e o tempo esgotado do SDK.
    """
    status = getattr(erro, "status_code", None)
    if isinstance(status, int):
        return status == 429 or 500 <= status < 600
    if isinstance(erro, ConnectionError | TimeoutError | httpx.TransportError):
        return True
    return any(classe.__name__ == "APIConnectionError" for classe in type(erro).__mro__)


def _mensagens(instrucao: str, pedido: str) -> str:
    """O que foi ao modelo, no formato de mensagens que o Langfuse mostra como conversa."""
    return json.dumps(
        [{"role": "system", "content": instrucao}, {"role": "user", "content": pedido}],
        ensure_ascii=False,
    )


BAGAGEM_DO_LANGFUSE = ("langfuse.session.id", "langfuse.trace.tags", "langfuse.release")
"""Atributos que o Langfuse quer em **todo** span do rastro, para filtrar e somar por eles. Vão
por baggage do OpenTelemetry e o `_CopiaBaggage` os põe em cada span que nasce, como a
[documentação](https://langfuse.com/integrations/native/opentelemetry#propagating-attributes)
recomenda."""


@contextmanager
def contexto_do_rastro(
    *, sessao: str, tags: list[str], release: str | None = None
) -> Iterator[None]:
    """Tudo o que rodar dentro sai no Langfuse com esta sessão, estas tags e este release."""
    valores = {
        "langfuse.session.id": sessao,
        "langfuse.trace.tags": json.dumps(tags, ensure_ascii=False),
    }
    if release:
        valores["langfuse.release"] = release
    ctx = context.get_current()
    for chave, valor in valores.items():
        ctx = baggage.set_baggage(chave, valor, context=ctx)
    token = context.attach(ctx)
    try:
        yield
    finally:
        context.detach(token)


class _CopiaBaggage(SpanProcessor):
    """Processador de span: copia do baggage os atributos do Langfuse para cada span."""

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        for chave in BAGAGEM_DO_LANGFUSE:
            valor = baggage.get_baggage(chave, context=parent_context)
            if valor is None:
                continue
            if chave == "langfuse.trace.tags":
                span.set_attribute(chave, json.loads(str(valor)))
            else:
                span.set_attribute(chave, str(valor))


def _com_o_erro(entrada: str, texto: str | None, erro: Exception) -> str:
    return (
        f"{entrada}\n\n"
        "Sua resposta anterior não seguiu o esquema JSON pedido e foi recusada.\n"
        f"Resposta anterior: {texto!r}\n"
        f"Erro: {erro}\n"
        "Responda de novo, só com o JSON no esquema."
    )


def configurar_rastro() -> None:
    """Liga o provedor global de rastro: Langfuse Cloud com as chaves, console sem elas.

    Chamada uma vez, por quem sobe o processo (a API na partida). Sem as chaves nada quebra: o
    rastro vai para o console. O Langfuse recebe OTLP por HTTP, com as chaves em Basic Auth,
    segundo a [documentação](https://langfuse.com/integrations/native/opentelemetry).
    """
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    lidas = config.Configuracao()
    provedor = TracerProvider(resource=Resource.create({"service.name": "arco"}))
    publica, secreta = lidas.langfuse_public_key.strip(), lidas.langfuse_secret_key.strip()
    if publica and secreta:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        credencial = base64.b64encode(f"{publica}:{secreta}".encode()).decode("ascii")
        exportador: Any = OTLPSpanExporter(
            endpoint=f"{lidas.langfuse_base_url.rstrip('/')}/api/public/otel/v1/traces",
            headers={
                "Authorization": f"Basic {credencial}",
                "x-langfuse-ingestion-version": "4",
            },
        )
    else:
        exportador = ConsoleSpanExporter()
    provedor.add_span_processor(_CopiaBaggage())
    provedor.add_span_processor(BatchSpanProcessor(exportador))
    trace.set_tracer_provider(provedor)
