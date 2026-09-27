"""A camada de chamada ao modelo, com o SDK substituído: sem chave, sem rede, sem espera.

O que se prova é o contorno de cada tipo de falha (ADR 0013, item 6): rede retenta, esquema
ganha uma segunda chance, conferência de conteúdo não volta ao modelo. E que o rastro sai com
um span por chamada e um filho por tentativa.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import BaseModel
from tenacity import wait_none

from arco_ia import config
from arco_ia.chamada import ForaDoEsquema, chamar, transitorio


class Saida(BaseModel):
    valor: int


class _Uso:
    total_input_tokens = 10
    total_output_tokens = 3


class _Resposta:
    def __init__(self, texto: str) -> None:
        self.output_text = texto
        self.usage = _Uso()


class _ErroDeStatus(Exception):
    """Como os erros de resposta do SDK: carregam `status_code`."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class _Interactions:
    """Devolve, em ordem, o que recebeu: exceção é levantada, texto vira resposta."""

    def __init__(self, roteiro: list[Exception | str]) -> None:
        self._roteiro = list(roteiro)
        self.chamadas: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _Resposta:
        self.chamadas.append(kwargs)
        proximo = self._roteiro.pop(0)
        if isinstance(proximo, Exception):
            raise proximo
        return _Resposta(proximo)


class _Cliente:
    def __init__(self, roteiro: list[Exception | str]) -> None:
        self.interactions = _Interactions(roteiro)


VALIDA = json.dumps({"valor": 7})
FORA = json.dumps({"valor": "sete"})


@pytest.fixture
def exportador() -> Iterator[InMemorySpanExporter]:
    exportador = InMemorySpanExporter()
    yield exportador
    exportador.clear()


def _chamar(cliente: _Cliente, exportador: InMemorySpanExporter | None = None, **kw: Any) -> Any:
    provedor = TracerProvider()
    if exportador is not None:
        provedor.add_span_processor(SimpleSpanProcessor(exportador))
    return chamar(
        "analista",
        "instrução",
        "entrada",
        Saida,
        cliente=cliente,
        rastreador=provedor.get_tracer("teste"),
        espera=wait_none(),
        **kw,
    )


def test_resposta_valida_na_primeira_devolve_a_saida_e_o_registro() -> None:
    cliente = _Cliente([VALIDA])
    resposta = _chamar(cliente)
    assert resposta.saida == Saida(valor=7)
    papel = config.PAPEIS["analista"]
    registro = resposta.registro
    assert (registro.papel, registro.modelo, registro.versao_prompt) == (
        "analista",
        papel.modelo,
        papel.versao_prompt,
    )
    assert (registro.tentativas, registro.validacao) == (1, "aceita")
    assert (registro.tokens_entrada, registro.tokens_saida) == (10, 3)
    assert registro.latencia_s >= 0


def test_a_chamada_leva_modelo_esforco_instrucao_e_esquema_do_papel() -> None:
    cliente = _Cliente([VALIDA])
    _chamar(cliente)
    enviada = cliente.interactions.chamadas[0]
    papel = config.PAPEIS["analista"]
    assert enviada["model"] == papel.modelo
    assert enviada["generation_config"] == {"thinking_level": papel.esforco}
    assert enviada["system_instruction"] == "instrução"
    assert enviada["input"] == "entrada"
    assert enviada["response_format"]["schema"] == Saida.model_json_schema()


def test_duas_falhas_de_rede_e_resposta_na_terceira_passa() -> None:
    cliente = _Cliente([httpx.ConnectError("caiu"), httpx.ReadTimeout("demorou"), VALIDA])
    resposta = _chamar(cliente)
    assert resposta.saida.valor == 7
    assert resposta.registro.tentativas == 3
    assert len(cliente.interactions.chamadas) == 3


def test_429_e_5xx_retentam() -> None:
    cliente = _Cliente([_ErroDeStatus(429), _ErroDeStatus(503), VALIDA])
    assert _chamar(cliente).registro.tentativas == 3


def test_rede_que_nao_volta_desiste_depois_de_tres_retentativas() -> None:
    cliente = _Cliente([httpx.ConnectError("caiu")] * 5)
    with pytest.raises(httpx.ConnectError):
        _chamar(cliente)
    assert len(cliente.interactions.chamadas) == 4


def test_erro_do_cliente_nao_retenta() -> None:
    """400 é pedido malformado: repetir o mesmo pedido dá o mesmo 400."""
    cliente = _Cliente([_ErroDeStatus(400), VALIDA])
    with pytest.raises(_ErroDeStatus):
        _chamar(cliente)
    assert len(cliente.interactions.chamadas) == 1


def test_fora_do_esquema_seguida_de_valida_passa_com_duas_chamadas() -> None:
    cliente = _Cliente([FORA, VALIDA])
    resposta = _chamar(cliente)
    assert resposta.saida.valor == 7
    assert len(cliente.interactions.chamadas) == 2
    segunda = cliente.interactions.chamadas[1]["input"]
    assert segunda.startswith("entrada")
    assert "não seguiu o esquema" in segunda


def test_texto_que_nao_e_json_tambem_ganha_a_segunda_chance() -> None:
    cliente = _Cliente(["isto não é json", VALIDA])
    assert _chamar(cliente).saida.valor == 7


def test_fora_do_esquema_duas_vezes_levanta() -> None:
    cliente = _Cliente([FORA, FORA, VALIDA])
    with pytest.raises(ForaDoEsquema):
        _chamar(cliente)
    assert len(cliente.interactions.chamadas) == 2


class _SemOrigem(ValueError):
    pass


def test_conferencia_que_falha_levanta_sem_segunda_chamada() -> None:
    def conferir(saida: Saida) -> None:
        raise _SemOrigem(f"{saida.valor} não está na entrada")

    cliente = _Cliente([VALIDA, VALIDA])
    with pytest.raises(_SemOrigem):
        _chamar(cliente, conferir=conferir)
    assert len(cliente.interactions.chamadas) == 1


def test_span_da_chamada_tem_os_spans_das_tentativas_dentro(
    exportador: InMemorySpanExporter,
) -> None:
    _chamar(_Cliente([httpx.ConnectError("caiu"), VALIDA]), exportador)
    spans = {s.name: s for s in exportador.get_finished_spans()}
    assert set(spans) == {"chamar analista", "tentativa 1", "tentativa 2"}
    pai = spans["chamar analista"]
    assert pai.context is not None
    for nome in ("tentativa 1", "tentativa 2"):
        filho = spans[nome]
        assert filho.parent is not None
        assert filho.parent.span_id == pai.context.span_id
    papel = config.PAPEIS["analista"]
    atributos = dict(pai.attributes or {})
    assert atributos["arco.papel"] == "analista"
    assert atributos["gen_ai.request.model"] == papel.modelo
    assert atributos["arco.versao_prompt"] == papel.versao_prompt
    assert atributos["arco.tentativas"] == 2
    assert atributos["arco.validacao"] == "aceita"


def test_span_da_chamada_marca_erro_quando_a_conferencia_falha(
    exportador: InMemorySpanExporter,
) -> None:
    def conferir(_: Saida) -> None:
        raise _SemOrigem("sem origem")

    with pytest.raises(_SemOrigem):
        _chamar(_Cliente([VALIDA]), exportador, conferir=conferir)
    (pai,) = [s for s in exportador.get_finished_spans() if s.name == "chamar analista"]
    assert not pai.status.is_ok
    assert dict(pai.attributes or {})["arco.validacao"] == "conferencia_falhou"


@pytest.mark.parametrize(
    ("erro", "retenta"),
    [
        (httpx.ConnectError("x"), True),
        (httpx.ReadTimeout("x"), True),
        (ConnectionResetError(), True),
        (_ErroDeStatus(429), True),
        (_ErroDeStatus(500), True),
        (_ErroDeStatus(400), False),
        (_ErroDeStatus(404), False),
        (ValueError("conteúdo"), False),
    ],
)
def test_so_rede_429_e_5xx_sao_transitorios(erro: Exception, retenta: bool) -> None:
    assert transitorio(erro) is retenta


def test_sem_chave_diz_o_que_o_papel_deixa_de_fazer(monkeypatch: pytest.MonkeyPatch) -> None:
    from arco_ia import IndisponivelSemChave

    monkeypatch.setattr(config, "chave", lambda: "")
    with pytest.raises(IndisponivelSemChave, match="relatório"):
        config.cliente("analista")


def test_com_as_chaves_do_langfuse_o_rastro_vai_para_la(monkeypatch: pytest.MonkeyPatch) -> None:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    from arco_ia.chamada import configurar_rastro

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-teste")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-teste")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com/")
    ligado: list[Any] = []
    monkeypatch.setattr(trace, "set_tracer_provider", ligado.append)
    configurar_rastro()
    (provedor,) = ligado
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    from arco_ia.chamada import _CopiaBaggage

    processadores = provedor._active_span_processor._span_processors
    assert isinstance(processadores[0], _CopiaBaggage), "sessão e tags antes de exportar"
    (processador,) = [p for p in processadores if isinstance(p, BatchSpanProcessor)]
    exportador = processador._batch_processor._exporter
    assert isinstance(exportador, OTLPSpanExporter)
    assert exportador._endpoint == "https://us.cloud.langfuse.com/api/public/otel/v1/traces"
    assert exportador._headers["Authorization"].startswith("Basic ")
    provedor.shutdown()


def test_langfuse_recebe_entrada_saida_e_parametros_e_tokens_uma_vez(
    exportador: InMemorySpanExporter,
) -> None:
    """Sem input e output o Langfuse mostra a chamada e o custo, mas não o que foi perguntado nem
    respondido. E os tokens só na geração: na tentativa também, a soma da tarefa sairia dobrada."""
    _chamar(_Cliente([VALIDA]), exportador)
    spans = {s.name: dict(s.attributes or {}) for s in exportador.get_finished_spans()}
    pai = spans["chamar analista"]
    mensagens = json.loads(str(pai["langfuse.observation.input"]))
    assert mensagens == [
        {"role": "system", "content": "instrução"},
        {"role": "user", "content": "entrada"},
    ]
    assert pai["langfuse.observation.output"] == VALIDA
    papel = config.PAPEIS["analista"]
    assert json.loads(str(pai["langfuse.observation.model.parameters"])) == {
        "thinking_level": papel.esforco
    }
    assert pai["langfuse.version"] == papel.versao_prompt
    assert pai["gen_ai.usage.input_tokens"] == 10
    assert "gen_ai.usage.input_tokens" not in spans["tentativa 1"]


def test_segunda_chance_mostra_o_pedido_com_o_erro(exportador: InMemorySpanExporter) -> None:
    _chamar(_Cliente([FORA, VALIDA]), exportador)
    (pai,) = [
        dict(s.attributes or {})
        for s in exportador.get_finished_spans()
        if s.name == "chamar analista"
    ]
    ultima = json.loads(str(pai["langfuse.observation.input"]))[-1]["content"]
    assert "não seguiu o esquema" in ultima


def test_sessao_tags_e_release_vao_para_todos_os_spans(exportador: InMemorySpanExporter) -> None:
    """O Langfuse filtra e soma por observação: sessão, tags e release têm de estar em cada span."""
    from opentelemetry.sdk.trace import TracerProvider as Provedor

    from arco_ia.chamada import _CopiaBaggage, contexto_do_rastro

    provedor = Provedor()
    provedor.add_span_processor(_CopiaBaggage())
    provedor.add_span_processor(SimpleSpanProcessor(exportador))
    with contexto_do_rastro(sessao="simulacao-3", tags=["relatorio"], release="0.7.0"):
        chamar(
            "analista",
            "instrução",
            "entrada",
            Saida,
            cliente=_Cliente([VALIDA]),
            rastreador=provedor.get_tracer("teste"),
            espera=wait_none(),
        )
    spans = exportador.get_finished_spans()
    assert {s.name for s in spans} == {"chamar analista", "tentativa 1"}
    for s in spans:
        atributos = dict(s.attributes or {})
        assert atributos["langfuse.session.id"] == "simulacao-3"
        assert list(atributos["langfuse.trace.tags"]) == ["relatorio"]  # type: ignore[arg-type]
        assert atributos["langfuse.release"] == "0.7.0"
