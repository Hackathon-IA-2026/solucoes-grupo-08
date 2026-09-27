"""O explorador por rodadas (feature 17, marco 1, task 17.14).

O agente escolhe o que testar; o código faz toda conta
([regras do explorador](../../../docs/features/agentes/17-regras-do-explorador.md), seção 1).
A cada rodada, **o código** grava `decidindo_rodada`, lê pelo MCP as revisões da simulação com
os diagnósticos e pede ao decisor uma decisão; **o decisor** responde com um lote de variações
a partir de uma revisão de partida, e o porquê, ou com o fim; **o código** executa a decisão
pelo MCP, com `disparar_lote` ou `encerrar`. Uma chamada ao modelo por rodada (regra 10).

Dois decisores usam o mesmo laço e as mesmas ferramentas: `DecisorDoModelo`, um agente Strands
com o Gemini do papel `explorador` ([ADR 0013](../../../docs/adr/0013-pilha-dos-agentes.md)), e
a árvore de referência, sem modelo (`referencia.py`), que o conjunto de avaliação compara.

As regras não dependem do decisor obedecer. `disparar_lote` confere faixa, repetição e teto, a
rota de variação monta a configuração pelo motor, e preço, taxa, cenário e custo unitário não
têm campo por onde entrar. O laço ainda para sozinho: teto atingido, duas rodadas seguidas sem
revisão nova, ou `MAXIMO_DE_RODADAS`.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from arco_agentes import resumos
from arco_agentes.api import ClienteDaApi, ErroDaApi

MAXIMO_DE_RODADAS = 12
"""Trava do laço. Com teto de 30 revisões e lotes de até 10, três rodadas bastam para gastar o
teto; doze deixam folga para lotes pequenos e recusados, sem deixar o laço infinito."""

RODADAS_SEM_REVISAO = 2
"""Rodadas seguidas sem revisão nova que encerram a exploração: o decisor está pedindo o que
não cabe, e insistir só gasta chamada."""

Alavanca = Literal[
    "bateria.potencia_mw",
    "bateria.duracao_horas",
    "bateria.subestacao",
    "equipamento.ganho_limite_mw",
]


class VariacaoDecidida(BaseModel):
    alavanca: Alavanca = Field(
        description="Uma alavanca física. Potência em MW (a duração fica), duração em horas de "
        "potência (a potência fica), subestação pelo nome, ganho de limite em MW."
    )
    valor: float | str = Field(description="Número, ou o nome da subestação.")


class Decisao(BaseModel):
    """O que o decisor responde a cada rodada. Não tem campo financeiro: não há como pedir
    outro preço, outra taxa ou outro cenário."""

    acao: Literal["disparar", "encerrar"]
    revisao_partida_id: int | None = Field(
        default=None, description="Em `disparar`: de qual revisão da simulação o lote nasce."
    )
    variacoes: list[VariacaoDecidida] = Field(
        default_factory=list, description="Em `disparar`: até 10, uma alavanca cada."
    )
    porque: str = Field(
        min_length=1,
        max_length=1000,
        description="Por que esta rodada, ou por que parar. Cite revisões pela posição (rev 3). "
        "Sem número de resultado: os números estão nas revisões.",
    )


class RevisaoNaSituacao(BaseModel):
    revisao_id: int
    posicao: int | None
    revisao_anterior_id: int | None
    procedencia: str | None
    da_exploracao: bool = Field(description="Salva por esta exploração.")
    alavanca: str
    configuracao: dict[str, Any]
    resultado: dict[str, Any]
    diagnosticos: dict[str, Any] | None
    nota: str | None


class Situacao(BaseModel):
    """O que o decisor lê para decidir a rodada, montado pelo código."""

    tarefa_id: int
    simulacao_id: int
    rodada: int
    pedido: str
    teto: int
    prontas: int
    revisao_partida_id: int = Field(description="De onde a exploração parte.")
    faixa: dict[str, Any] = Field(description="O que se pode variar, e entre que valores.")
    revisoes: list[RevisaoNaSituacao] = Field(description="Todas as da simulação, em ordem.")
    cruzamentos: dict[str, Any] | None
    ultimo_lote: dict[str, Any] | None = Field(description="Desfechos da rodada anterior.")


class Decisor(Protocol):
    async def decidir(self, situacao: Situacao) -> Decisao: ...


class FerramentaRecusou(Exception):
    """A ferramenta do MCP devolveu erro. A mensagem é a dela, com o status da API."""


class Ferramentas(Protocol):
    """As ferramentas do perfil do explorador, chamadas pelo MCP. Devolvem o dado estruturado."""

    async def chamar(self, nome: str, argumentos: dict[str, Any]) -> dict[str, Any]: ...


class FerramentasDoStrands:
    """O MCP do ARCO pelo cliente MCP do Strands, no caminho do explorador, por `localhost`: a
    mesma superfície que o cliente externo usa, com o mesmo registro (ADR 0013)."""

    def __init__(self, url: str) -> None:
        from strands.tools.mcp import MCPClient

        self._cliente = MCPClient(url=url, application_name="arco-explorador")
        self._contador = 0

    def __enter__(self) -> FerramentasDoStrands:
        self._cliente.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._cliente.stop(None, None, None)

    async def abrir(self) -> FerramentasDoStrands:
        """Conecta fora do laço de eventos: `start` espera o servidor responder, e o servidor
        pode ser este mesmo processo, que travaria esperando a si mesmo."""
        return await asyncio.to_thread(self.__enter__)

    async def fechar(self) -> None:
        await asyncio.to_thread(self.__exit__)

    def nomes(self) -> set[str]:
        return {ferramenta.tool_name for ferramenta in self._cliente.list_tools_sync()}

    async def chamar(self, nome: str, argumentos: dict[str, Any]) -> dict[str, Any]:
        self._contador += 1
        resultado = await self._cliente.call_tool_async(f"arco-{self._contador}", nome, argumentos)
        if resultado.get("status") == "error":
            texto = " ".join(c.get("text", "") for c in resultado.get("content", []))
            raise FerramentaRecusou(texto or f"{nome} falhou")
        return dict(resultado.get("structuredContent") or {})


INSTRUCAO = """\
Você é o explorador do ARCO. O ARCO refaz os cortes de geração renovável registrados pelo ONS com
uma intervenção hipotética e calcula o efeito. Você explora variações de uma simulação, em
rodadas, para responder ao pedido de uma pessoa. Você escolhe o que testar; o código calcula,
salva e compara. Você não faz conta e não recomenda.

A cada rodada, decida uma de duas coisas:
- disparar: um lote de variações, todas a partir da mesma revisão de partida da simulação;
- encerrar: quando o pedido estiver respondido entre as revisões feitas (por exemplo, o payback
  cruzou o horizonte, ou a fração recuperada passou do alvo), ou quando a última rodada inteira
  não mexeu na métrica que o pedido pede.

Regras:
1. Só a alavanca física varia: bateria.potencia_mw (MW; a duração fica a da partida),
   bateria.duracao_horas (horas de potência; a potência fica), bateria.subestacao (nome de uma
   das subestações permitidas) e equipamento.ganho_limite_mw (MW). Preço da energia, taxa de
   desconto, cenário e custo unitário são condições fixas e não variam.
2. Cada variação muda uma alavanca só em relação à revisão de partida.
3. Até 10 variações por rodada, sempre dentro da faixa permitida da situação, e nunca uma
   configuração que já existe entre as revisões: seria recusada.
4. O teto é de revisões salvas pela exploração; não passe dele.
5. Primeira rodada sugerida: a grade de tamanhos a partir da revisão de partida (1,5, 2, 3, 4, 6
   e 8 vezes a potência, dentro da faixa) e as outras subestações permitidas, a não ser que o
   pedido indique outra coisa.
6. Leia os diagnósticos. Bateria cheia com corte sobrando em muitas meias horas é falta de
   capacidade: vale testar duração maior. Episódios que começam com a bateria ainda carregada
   são falta de tempo para descarregar. O corte residual por hora diz quando sobra corte.
   Os cruzamentos dizem entre que revisões o payback passa a caber no horizonte e a TIR passa
   da taxa.
7. No porquê, diga o motivo da rodada em uma ou duas frases, citando revisões pela posição
   (rev 3). Não escreva números de resultado: eles estão nas revisões, calculados.
"""


class DecisorDoModelo:
    """Um agente Strands com o Gemini do papel `explorador` (`arco_ia.config`). Uma chamada por
    rodada, com saída estruturada em `Decisao`; um agente novo a cada rodada, porque a situação
    inteira vai no prompt e o histórico não precisa crescer."""

    def __init__(self, modelo: Any | None = None) -> None:
        """`modelo` é um `strands.models.Model`; vazio, o Gemini do papel, que exige a chave."""
        if modelo is None:
            from strands.models.gemini import GeminiModel

            from arco_ia.config import PAPEIS, cliente

            papel = PAPEIS["explorador"]
            modelo = GeminiModel(
                client=cliente("explorador"),
                model_id=papel.modelo,
                params={"thinking_config": {"thinking_level": papel.esforco}},
            )
        self._modelo = modelo
        self.chamadas: list[dict[str, Any]] = []
        """Uma por rodada: tokens e tempo, para o conjunto de avaliação (17.16)."""

    async def decidir(self, situacao: Situacao) -> Decisao:
        from strands import Agent

        from arco_ia.config import PAPEIS

        agente = Agent(
            model=self._modelo,
            system_prompt=INSTRUCAO,
            callback_handler=None,
            trace_attributes={
                "arco.papel": "explorador",
                "arco.versao_prompt": PAPEIS["explorador"].versao_prompt,
                "arco.tarefa_id": situacao.tarefa_id,
                "arco.rodada": situacao.rodada,
            },
        )
        inicio = time.monotonic()
        resultado = await agente.invoke_async(
            f"Pedido: {situacao.pedido}\n\nSituação da exploração, calculada pelo ARCO:\n"
            f"{situacao.model_dump_json(indent=1)}\n\nDecida a rodada {situacao.rodada}.",
            structured_output_model=Decisao,
        )
        uso = agente.event_loop_metrics.accumulated_usage
        self.chamadas.append(
            {
                "rodada": situacao.rodada,
                "tokens_entrada": uso.get("inputTokens", 0),
                "tokens_saida": uso.get("outputTokens", 0),
                "latencia_s": time.monotonic() - inicio,
            }
        )
        decisao = resultado.structured_output
        if not isinstance(decisao, Decisao):
            raise ValueError("o modelo não devolveu uma decisão no formato pedido")
        return decisao


@dataclass
class Exploracao:
    """O que aconteceu, para a CLI e o conjunto de avaliação. A trilha oficial são os eventos."""

    tarefa_id: int
    decisoes: list[dict[str, Any]] = field(default_factory=list)
    fim: str | None = None
    erro: str | None = None


class Explorador:
    def __init__(self, api: ClienteDaApi, ferramentas: Ferramentas, decisor: Decisor) -> None:
        self.api, self.ferramentas, self.decisor = api, ferramentas, decisor
        self._revisoes: dict[int, dict[str, Any]] = {}

    async def explorar(self, tarefa_id: int) -> Exploracao:
        """Roda as rodadas até o fim. Nunca levanta: falha vira `tarefa_terminada` em `falhou`,
        com o motivo, e as revisões salvas até ali ficam."""
        exploracao = Exploracao(tarefa_id=tarefa_id)
        ultimo_lote: dict[str, Any] | None = None
        sem_revisao = 0
        try:
            while True:
                tarefa = await self.api.ver_tarefa(tarefa_id)
                if tarefa["estado"] != "em_andamento":
                    exploracao.fim = f"a exploração terminou por fora: {tarefa['estado']}"
                    break
                rodada = tarefa["contagem"]["rodadas"] + 1
                parada = self._parada(tarefa, rodada, sem_revisao)
                if parada:
                    await self._encerrar(tarefa_id, parada)
                    exploracao.fim = parada
                    break
                await self.api.registrar_evento(
                    tarefa_id, {"tipo": "decidindo_rodada", "rodada": rodada}
                )
                situacao = await self._situacao(tarefa, rodada, ultimo_lote)
                decisao = await self.decisor.decidir(situacao)
                exploracao.decisoes.append(decisao.model_dump())
                if decisao.acao == "encerrar" or not decisao.variacoes:
                    await self._encerrar(tarefa_id, decisao.porque)
                    exploracao.fim = decisao.porque
                    break
                ultimo_lote = await self.ferramentas.chamar(
                    "disparar_lote",
                    {
                        "tarefa_id": tarefa_id,
                        "revisao_partida_id": decisao.revisao_partida_id
                        or tarefa["revisao_partida_id"],
                        "variacoes": [v.model_dump() for v in decisao.variacoes],
                        "porque": decisao.porque,
                    },
                )
                novas = sum(1 for d in ultimo_lote["desfechos"] if d["estado"] == "pronta")
                sem_revisao = 0 if novas else sem_revisao + 1
        except Exception as erro:
            exploracao.erro = f"{type(erro).__name__}: {erro}"
            await self._falhar(tarefa_id, exploracao.erro)
        return exploracao

    def _parada(self, tarefa: dict[str, Any], rodada: int, sem_revisao: int) -> str | None:
        if tarefa["contagem"]["prontas"] >= tarefa["teto"]:
            return f"teto de {tarefa['teto']} revisões atingido"
        if sem_revisao >= RODADAS_SEM_REVISAO:
            return f"{RODADAS_SEM_REVISAO} rodadas seguidas sem revisão nova"
        if rodada > MAXIMO_DE_RODADAS:
            return f"limite de {MAXIMO_DE_RODADAS} rodadas"
        return None

    async def _encerrar(self, tarefa_id: int, motivo: str) -> None:
        await self.ferramentas.chamar("encerrar", {"tarefa_id": tarefa_id, "motivo": motivo})

    async def _falhar(self, tarefa_id: int, motivo: str) -> None:
        """A exploração não terminou. Se nem isso gravar, sobra o corte de 20 minutos da API."""
        with contextlib.suppress(ErroDaApi):
            await self.api.registrar_evento(
                tarefa_id, {"tipo": "tarefa_terminada", "estado": "falhou", "motivo": motivo[:1000]}
            )

    async def _situacao(
        self, tarefa: dict[str, Any], rodada: int, ultimo_lote: dict[str, Any] | None
    ) -> Situacao:
        """Lida pelo MCP. A revisão salva não muda, então cada uma é lida uma vez; a de
        partida é lida de novo a cada rodada, porque é ela que traz a lista atual de revisões
        da simulação e os cruzamentos entre elas."""
        partida = await self.ferramentas.chamar(
            "ver_revisao", {"revisao_id": tarefa["revisao_partida_id"]}
        )
        da_exploracao = set(tarefa.get("revisoes", []))
        revisoes = []
        for irma in sorted(partida["revisoes_da_simulacao"], key=lambda r: r["posicao"]):
            revisao_id = irma["revisao_id"]
            if revisao_id not in self._revisoes:
                self._revisoes[revisao_id] = await self.ferramentas.chamar(
                    "ver_revisao", {"revisao_id": revisao_id}
                )
            r = self._revisoes[revisao_id]
            revisoes.append(
                RevisaoNaSituacao(
                    revisao_id=revisao_id,
                    posicao=irma["posicao"],
                    revisao_anterior_id=r.get("revisao_anterior_id"),
                    procedencia=r.get("procedencia"),
                    da_exploracao=revisao_id in da_exploracao,
                    alavanca=resumos.alavanca(r["configuracao"]),
                    configuracao=r["configuracao"],
                    resultado=r["resultado"],
                    diagnosticos=r.get("diagnosticos"),
                    nota=r.get("nota"),
                )
            )
        return Situacao(
            tarefa_id=tarefa["id"],
            simulacao_id=tarefa["simulacao_id"],
            rodada=rodada,
            pedido=tarefa["pedido"],
            teto=tarefa["teto"],
            prontas=tarefa["contagem"]["prontas"],
            revisao_partida_id=tarefa["revisao_partida_id"],
            faixa=tarefa["faixa"],
            revisoes=revisoes,
            cruzamentos=partida.get("cruzamentos"),
            ultimo_lote={
                "rodada": ultimo_lote["rodada"],
                "desfechos": [
                    {k: d.get(k) for k in ("alavanca", "valor", "estado", "motivo")}
                    | {"revisao_id": (d.get("revisao") or {}).get("revisao_id")}
                    for d in ultimo_lote["desfechos"]
                ],
            }
            if ultimo_lote
            else None,
        )


async def explorar_com(
    api_url: str, url_do_mcp: str, tarefa_id: int, decisor: Decisor | None = None
) -> Exploracao:
    """Uma exploração inteira, com as próprias conexões: a API e o MCP do explorador. Sem
    decisor, o do modelo. Falha antes do laço — sem chave, MCP fora — também encerra a tarefa
    em `falhou`, para ela não ficar parada até o corte de 20 minutos."""
    api = ClienteDaApi(api_url)
    ferramentas = FerramentasDoStrands(url_do_mcp)
    try:
        await ferramentas.abrir()
        explorador = Explorador(api, ferramentas, decisor or DecisorDoModelo())
        return await explorador.explorar(tarefa_id)
    except Exception as erro:
        motivo = f"{type(erro).__name__}: {erro}"
        await Explorador(api, ferramentas, _SemDecisor())._falhar(tarefa_id, motivo)
        exploracao = Exploracao(tarefa_id=tarefa_id, erro=motivo)
        return exploracao
    finally:
        await ferramentas.fechar()
        await api.fechar()


class _SemDecisor:
    async def decidir(self, situacao: Situacao) -> Decisao:
        raise RuntimeError("sem decisor")
