"""Exploração de variações: a tarefa, os eventos dela, o streaming e a rota que salva variação.

Feature 17, marco 1, tasks 17.9 e 17.12
([spec](../../../docs/features/agentes/17-marco-1-mcp-e-explorador.md),
[regras do explorador](../../../docs/features/agentes/17-regras-do-explorador.md)).

Uma tarefa é uma exploração pedida no chat ou no painel. O agente decide rodadas de variações de
uma revisão de partida; cada variação passa pela rota de variação, que monta a configuração pelo
motor, calcula e grava a revisão `por_agente`. A tela Ver processamento acompanha pelo streaming.

**Quem põe o explorador para rodar.** A API, ao criar a tarefa: ela chama o processo de
`agentes` por HTTP, sem importá-lo (feature 17, marco 2,
[spec](../../../docs/features/agentes/17-marco-2-disparo-pela-api.md), ADR 0015). Assim painel,
chat e qualquer outro cliente disparam do mesmo jeito.

**Quem grava cada evento.** A rota de variação grava os da variação — `variacao_iniciada`,
`variacao_passo`, `revisao_pronta` e `variacao_recusada` —, e `revisao_pronta` sai na mesma
transação da revisão, com a tarefa travada. A contagem sai dos eventos, e só quem salva sabe o
que foi salvo: um trabalhador que morresse entre salvar e avisar deixaria a contagem errada, e
dez variações em paralelo passariam juntas pelo teto. `agentes` grava pela rota de eventos só o
que é dele: `rodada_decidida`, a recusa que ele mesmo fez antes de chamar a rota,
`relatorio_pedido`, `relatorio_pronto` e `tarefa_terminada`.

As rotas moram num router próprio, como as do relatório, porque leem pelas funções de
`rotas.py`.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

import anyio
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from arco_api import modelos
from arco_api.banco import sessao
from arco_api.config import configuracao
from arco_api.leitura import Fonte
from arco_api.modelos import (
    EM_ANDAMENTO,
    FALHOU,
    POR_AGENTE,
    Evento,
    Simulacao,
    SimulacaoRevisao,
    Tarefa,
)
from arco_api.rotas import (
    NOTA_MAXIMO,
    PedidoDeSimulacao,
    RevisaoSalva,
    _cadastro,
    _equipamentos,
    _premissas,
    _salva,
    _serie_do_motor,
)
from arco_motor.cenarios import CUSTOS_POR_CENARIO
from arco_motor.montar import custo_da_linha
from arco_motor.premissas import PREMISSAS_PADRAO, Premissa
from arco_motor.simular import simular as calcular
from arco_motor.tipos import Cenario, Configuracao
from arco_motor.variacao import (
    AlavancaFisica,
    FaixaPermitida,
    Variacao,
    estreitar,
    faixa_permitida,
    montar_variacao,
)
from arco_motor.versao import METODO_VERSAO

rotas_tarefas = APIRouter(tags=["tarefas"])

TETO_MAXIMO = 30
"""Revisões por exploração, teto duro da regra 5. A pessoa pode baixar ao confirmar."""

PERDIDA_DEPOIS_DE = timedelta(minutes=20)
"""Tarefa em andamento sem evento há mais que isto morreu com o processo de `agentes`: vira
`falhou`, como o relatório perdido. Uma rodada de verdade grava evento a cada variação."""

INTERVALO_DO_STREAMING_S = 0.5
"""De quanto em quanto o streaming procura evento novo no banco."""

BATIMENTO_S = 15.0
"""Comentário SSE mandado no silêncio, para túnel e proxy não fecharem a conexão parada."""

TEMPO_DO_DISPARO_S = 10.0
"""Quanto a API espera o processo de `agentes` aceitar a exploração. Ele só confere a tarefa e
responde: a exploração roda depois, em fundo."""


# Eventos ----------------------------------------------------------------------------------


class DecidindoRodada(BaseModel):
    """O agente começou a decidir a próxima rodada: lê os resultados e chama o modelo. Sem ele,
    a tela ficaria parada, sem saber se a exploração segue viva entre uma rodada e outra."""

    tipo: Literal["decidindo_rodada"] = "decidindo_rodada"
    rodada: int = Field(ge=1, description="A rodada que está sendo decidida.")


class VariacaoPlanejada(Variacao):
    variacao_id: str | None = Field(
        default=None,
        max_length=40,
        description="O identificador que a variação vai usar na rota de variação. Com ele, a tela "
        "liga a variação da fila aos eventos dela sem adivinhar.",
    )


class RodadaDecidida(BaseModel):
    tipo: Literal["rodada_decidida"] = "rodada_decidida"
    rodada: int = Field(ge=1)
    revisao_partida_id: int = Field(description="De onde as variações da rodada nascem.")
    porque: str = Field(min_length=1, max_length=NOTA_MAXIMO, description="Escrito pelo agente.")
    variacoes: list[VariacaoPlanejada] = Field(description="O que a rodada vai testar.")


class VariacaoIniciada(BaseModel):
    tipo: Literal["variacao_iniciada"] = "variacao_iniciada"
    variacao_id: str
    rodada: int | None
    revisao_partida_id: int
    alavanca: AlavancaFisica
    valor: float | str


class VariacaoPasso(BaseModel):
    tipo: Literal["variacao_passo"] = "variacao_passo"
    variacao_id: str
    passo: Literal["montando", "calculando", "salvando"]


class ResumoDaRevisao(BaseModel):
    """O bastante para a tela desenhar a revisão sem buscá-la: a revisão inteira traz a série de
    cada meia hora, pesada demais para uma exploração de 30 revisões."""

    energia_recuperada_mwh: float
    fracao_recuperada: float = Field(description="Fração de 0 a 1.")
    vpl_reais: float
    tir_aa: float | None
    payback_simples_anos: float | None
    custo_por_mwh_reais: float | None
    avisos: int = Field(description="Quantos avisos a revisão tem.")


class RevisaoPronta(BaseModel):
    tipo: Literal["revisao_pronta"] = "revisao_pronta"
    variacao_id: str
    revisao_id: int
    posicao: int | None = Field(default=None, description="Posição da revisão na simulação.")
    revisao_partida_id: int | None = Field(
        default=None, description="De onde nasceu: é a linha do grafo."
    )
    rodada: int | None = None
    alavanca: AlavancaFisica | None = None
    valor: float | str | None = None
    resumo: ResumoDaRevisao | None = None


class VariacaoRecusada(BaseModel):
    tipo: Literal["variacao_recusada"] = "variacao_recusada"
    variacao_id: str | None = Field(
        default=None,
        description="`null` na recusa que o agente fez antes de chamar a rota de variação.",
    )
    alavanca: AlavancaFisica | None = None
    valor: float | str | None = None
    status: int | None = Field(default=None, description="O código HTTP da recusa, se houve.")
    motivo: str = Field(min_length=1)


class RelatorioPedido(BaseModel):
    tipo: Literal["relatorio_pedido"] = "relatorio_pedido"
    relatorio_id: int


class RelatorioPronto(BaseModel):
    tipo: Literal["relatorio_pronto"] = "relatorio_pronto"
    relatorio_id: int
    estado: Literal["pronto", "barrado", "falhou"]


class TarefaTerminada(BaseModel):
    tipo: Literal["tarefa_terminada"] = "tarefa_terminada"
    estado: Literal["concluida", "falhou"]
    motivo: str = Field(min_length=1, max_length=NOTA_MAXIMO)


DadosDoEvento = Annotated[
    DecidindoRodada
    | RodadaDecidida
    | VariacaoIniciada
    | VariacaoPasso
    | RevisaoPronta
    | VariacaoRecusada
    | RelatorioPedido
    | RelatorioPronto
    | TarefaTerminada,
    Field(discriminator="tipo"),
]

EventoDoAgente = Annotated[
    DecidindoRodada
    | RodadaDecidida
    | VariacaoRecusada
    | RelatorioPedido
    | RelatorioPronto
    | TarefaTerminada,
    Field(discriminator="tipo"),
]
"""O que `agentes` grava pela rota de eventos. Os eventos da variação só a rota de variação
grava, e é por isso que a contagem vale."""

_LEITOR = TypeAdapter[Any](DadosDoEvento)


class EventoGravado(BaseModel):
    """Um evento como a trilha o guarda e o streaming o manda, no `data:` de cada mensagem."""

    id: int = Field(description="Crescente na tarefa. É o `id:` do SSE e o `Last-Event-ID`.")
    tarefa_id: int
    instante: datetime
    evento: DadosDoEvento


# Tarefa -----------------------------------------------------------------------------------


class Contagem(BaseModel):
    """Contada por código a partir dos eventos, por identificador de variação: a ordem em que
    os eventos chegam não muda o número."""

    rodadas: int
    disparadas: int = Field(description="Variações que chegaram à rota de variação.")
    trabalhando: int = Field(description="Disparadas sem desfecho. Zero em tarefa terminada.")
    prontas: int = Field(description="Revisões salvas. É o que conta para o teto.")
    recusadas: int = Field(description="Recusadas pela rota ou antes dela, pelo agente.")
    interrompidas: int = Field(description="Sem desfecho numa tarefa que já terminou.")


EstadoDaTarefa = Literal["em_andamento", "concluida", "falhou"]


class TarefaNaTela(BaseModel):
    id: int
    simulacao_id: int
    estado: EstadoDaTarefa
    teto: int = Field(description="Revisões que a exploração pode salvar.")
    pedido: str = Field(description="O que a pessoa pediu, como o chat entendeu.")
    revisao_partida_id: int = Field(description="De onde a exploração parte.")
    faixa: FaixaPermitida = Field(description="O que o agente pode variar, confirmado.")
    criada_em: datetime
    ultimo_evento_em: datetime | None
    terminada_em: datetime | None
    motivo: str | None = Field(description="Por que terminou, do evento `tarefa_terminada`.")
    erro: str | None = Field(description="Só em `falhou`.")
    relatorio_id: int | None
    contagem: Contagem
    revisoes: list[int] = Field(description="As revisões salvas, na ordem em que ficaram prontas.")


class DetalheDoConflito(BaseModel):
    mensagem: str
    tarefa_id: int


class ConflitoDeTarefa(BaseModel):
    detail: DetalheDoConflito


class DisparoRecusado(BaseModel):
    detail: DetalheDoConflito


class CondicoesFixas(BaseModel):
    """O que não varia na exploração: as condições da comparação (regra 2)."""

    cenario: Cenario
    taxa_desconto_aa: float
    preco_energia_reais_mwh: float = Field(description="O que o cálculo aplica.")
    preco_da_premissa: bool = Field(
        description="Verdadeiro quando a partida deixou o preço vazio e vale `preco_energia`."
    )
    custos_unitarios: list[Premissa] = Field(description="Do cenário da partida.")


class ResumoDaExploracao(BaseModel):
    """O que a pessoa confirma antes do disparo: de onde parte, o que varia e o que fica."""

    simulacao_id: int
    revisao_partida_id: int
    configuracao: Configuracao = Field(description="A configuração de partida, campo a campo.")
    faixa: FaixaPermitida
    condicoes_fixas: CondicoesFixas
    teto_maximo: int = Field(description=f"Revisões por exploração: {TETO_MAXIMO}.")


class PedidoDeTarefa(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pedido: str = Field(min_length=1, max_length=2000)
    teto: int = Field(default=TETO_MAXIMO, ge=1, le=TETO_MAXIMO)
    revisao_partida_id: int | None = Field(
        default=None, description="De onde a exploração parte. Vazio: a mais nova da simulação."
    )
    alavancas: list[AlavancaFisica] | None = Field(
        default=None,
        description='Estreita a faixa ("varia só a potência"). Vazio: todas as da modalidade.',
    )
    disparar: bool = Field(
        default=True,
        description="Põe o explorador para rodar ao criar. `false`: quem cria a tarefa roda o "
        "explorador por conta própria, como a CLI de `agentes` e o conjunto de avaliação.",
    )


class PedidoDeVariacao(BaseModel):
    """Uma variação: a alavanca e o valor. **Nenhum campo financeiro**: preço, taxa, cenário e
    custo unitário são os da revisão de partida, e campo a mais é `422`."""

    model_config = ConfigDict(extra="forbid")

    tarefa_id: int
    revisao_base_id: int = Field(description="A revisão de onde a variação nasce.")
    alavanca: AlavancaFisica
    valor: float | str = Field(description="MW, horas, MW, ou o nome da subestação.")
    nota: str = Field(min_length=1, max_length=NOTA_MAXIMO, description="O porquê, do agente.")
    variacao_id: str | None = Field(
        default=None,
        max_length=40,
        description="Identifica a variação nos eventos. Vazio: a rota sorteia um.",
    )
    rodada: int | None = Field(default=None, ge=1)


def _agora() -> datetime:
    return datetime.now(UTC)


def _com_fuso(instante: datetime) -> datetime:
    return instante if instante.tzinfo else instante.replace(tzinfo=UTC)


def _registrar(s, tarefa_id: int, evento: BaseModel) -> Evento:  # type: ignore[no-untyped-def]
    dados = evento.model_dump(mode="json")
    linha = Evento(tarefa_id=tarefa_id, instante=_agora(), tipo=dados["tipo"], dados=dados)
    s.add(linha)
    return linha


def _gravado(linha: Evento) -> EventoGravado:
    return EventoGravado(
        id=linha.id,
        tarefa_id=linha.tarefa_id,
        instante=linha.instante,
        evento=_LEITOR.validate_python(linha.dados),
    )


def _eventos(s, tarefa_id: int, depois_de: int = 0) -> list[Evento]:  # type: ignore[no-untyped-def]
    return list(
        s.scalars(
            select(Evento)
            .where(Evento.tarefa_id == tarefa_id, Evento.id > depois_de)
            .order_by(Evento.id)
        )
    )


def _falhar(s, tarefa: Tarefa, motivo: str) -> None:  # type: ignore[no-untyped-def]
    """Encerra em `falhou`, com o evento que fecha a trilha e o streaming."""
    tarefa.estado, tarefa.terminada_em, tarefa.erro = FALHOU, _agora(), motivo
    _registrar(s, tarefa.id, TarefaTerminada(estado="falhou", motivo=motivo))
    s.commit()


def _encerrar_se_perdida(s, tarefa: Tarefa) -> None:  # type: ignore[no-untyped-def]
    """Em andamento e sem evento há mais de `PERDIDA_DEPOIS_DE`: o processo de `agentes` parou."""
    if tarefa.estado != EM_ANDAMENTO:
        return
    ultimo = s.scalar(select(func.max(Evento.instante)).where(Evento.tarefa_id == tarefa.id))
    referencia = _com_fuso(ultimo or tarefa.criada_em)
    if _agora() - referencia <= PERDIDA_DEPOIS_DE:
        return
    _falhar(
        s,
        tarefa,
        f"sem evento há mais de {int(PERDIDA_DEPOIS_DE.total_seconds() // 60)} minutos: o "
        "processo de agentes provavelmente parou. As revisões salvas ficam; continuar é "
        "disparar de novo na mesma simulação.",
    )


# Disparo ----------------------------------------------------------------------------------


class ExploradorFora(Exception):
    """O processo de `agentes` não pôs a exploração para rodar. A mensagem diz por quê."""


Disparar = Callable[[int], None]
"""Põe para rodar a exploração da tarefa, ou levanta `ExploradorFora`."""


def _disparar_por_http(tarefa_id: int) -> None:
    url = f"{configuracao().arco_agentes_url.rstrip('/')}/exploracoes/{tarefa_id}"
    try:
        resposta = httpx.post(url, timeout=TEMPO_DO_DISPARO_S)
    except httpx.HTTPError as erro:
        raise ExploradorFora(
            f"o processo de agentes não respondeu em {url} ({type(erro).__name__})"
        ) from erro
    if resposta.status_code != 202:
        raise ExploradorFora(
            f"o processo de agentes recusou ({resposta.status_code}: {_detalhe(resposta)})"
        )


def _detalhe(resposta: httpx.Response) -> str:
    try:
        detalhe = resposta.json().get("detail")
    except ValueError, AttributeError:
        detalhe = None
    return str(detalhe or resposta.text or "sem corpo")[:300]


def disparador() -> Disparar:
    """A dependência que põe o explorador para rodar. Os testes a trocam."""
    return _disparar_por_http


def contar(eventos: list[EventoGravado], terminada: bool) -> Contagem:
    """A contagem por identificador de variação. Um `revisao_pronta` que chegue antes do
    `variacao_iniciada` da mesma variação conta igual."""
    iniciadas: set[str] = set()
    prontas: set[str] = set()
    recusadas: set[str] = set()
    recusadas_antes = rodadas = 0
    for gravado in eventos:
        e = gravado.evento
        if isinstance(e, RodadaDecidida):
            rodadas += 1
        elif isinstance(e, VariacaoIniciada | VariacaoPasso):
            iniciadas.add(e.variacao_id)
        elif isinstance(e, RevisaoPronta):
            iniciadas.add(e.variacao_id)
            prontas.add(e.variacao_id)
        elif isinstance(e, VariacaoRecusada):
            if e.variacao_id is None:
                recusadas_antes += 1
            else:
                iniciadas.add(e.variacao_id)
                recusadas.add(e.variacao_id)
    abertas = len(iniciadas - prontas - recusadas)
    return Contagem(
        rodadas=rodadas,
        disparadas=len(iniciadas),
        trabalhando=0 if terminada else abertas,
        prontas=len(prontas),
        recusadas=len(recusadas) + recusadas_antes,
        interrompidas=abertas if terminada else 0,
    )


def _na_tela(s, tarefa: Tarefa) -> TarefaNaTela:  # type: ignore[no-untyped-def]
    eventos = [_gravado(e) for e in _eventos(s, tarefa.id)]
    terminada = tarefa.estado != EM_ANDAMENTO
    fim = next((g.evento for g in reversed(eventos) if isinstance(g.evento, TarefaTerminada)), None)
    return TarefaNaTela(
        id=tarefa.id,
        simulacao_id=tarefa.simulacao_id,
        estado=tarefa.estado,  # type: ignore[arg-type]
        teto=tarefa.teto,
        pedido=tarefa.pedido,
        revisao_partida_id=tarefa.revisao_partida_id,
        faixa=FaixaPermitida.model_validate(tarefa.faixa),
        criada_em=tarefa.criada_em,
        ultimo_evento_em=eventos[-1].instante if eventos else None,
        terminada_em=tarefa.terminada_em,
        motivo=fim.motivo if isinstance(fim, TarefaTerminada) else None,
        erro=tarefa.erro,
        relatorio_id=tarefa.relatorio_id,
        contagem=contar(eventos, terminada),
        revisoes=[g.evento.revisao_id for g in eventos if isinstance(g.evento, RevisaoPronta)],
    )


def _revisao_da_simulacao(s, simulacao_id: int, revisao_id: int, papel: str) -> SimulacaoRevisao:  # type: ignore[no-untyped-def]
    revisao = s.get(SimulacaoRevisao, revisao_id)
    if revisao is None or revisao.simulacao_id != simulacao_id:
        raise HTTPException(
            status_code=422,
            detail=f"{papel} {revisao_id} não é revisão da simulação {simulacao_id}",
        )
    return revisao


def _fonte_e_correcao(revisao: SimulacaoRevisao) -> tuple[Fonte, bool]:
    """A fonte e a correção de minutos com que a partida foi calculada: são premissa, não campo
    da configuração, e a variação herda as duas para comparar o que é comparável."""
    usadas = revisao.premissas_usadas or {}
    fonte = (usadas.get("fonte_geracao") or {}).get("valor", Fonte.EOLICA.value)
    correcao = (usadas.get("correcao_minutos") or {}).get("valor", True)
    return Fonte(fonte), bool(correcao)


def _resumo(s, simulacao: Simulacao, partida: SimulacaoRevisao, alavancas) -> ResumoDaExploracao:  # type: ignore[no-untyped-def]
    configuracao = Configuracao.model_validate(partida.configuracao)
    financeira = configuracao.financeira
    custos = CUSTOS_POR_CENARIO[financeira.cenario]
    cadastro = _cadastro(_equipamentos(s, simulacao.restricao_id, partida.snapshot_id))
    faixa = faixa_permitida(configuracao, cadastro, PREMISSAS_PADRAO)
    if alavancas:
        try:
            faixa = estreitar(faixa, alavancas)
        except ValueError as erro:
            raise HTTPException(status_code=422, detail=str(erro)) from erro
    unitarios = [custos.obter("bateria_capex_kwh")] if configuracao.bateria else []
    for linha in cadastro:
        if (
            configuracao.equipamento
            and linha.cod_equipamento == configuracao.equipamento.cod_equipamento
        ):
            custo = custos.itens.get(custo_da_linha(linha.tensao_kv))
            unitarios += [custo] if custo else []
    preco = financeira.preco_energia_reais_mwh
    return ResumoDaExploracao(
        simulacao_id=simulacao.id,
        revisao_partida_id=partida.id,
        configuracao=configuracao,
        faixa=faixa,
        condicoes_fixas=CondicoesFixas(
            cenario=financeira.cenario,
            taxa_desconto_aa=financeira.taxa_desconto_aa,
            preco_energia_reais_mwh=preco
            if preco is not None
            else float(PREMISSAS_PADRAO.valor("preco_energia")),
            preco_da_premissa=preco is None,
            custos_unitarios=unitarios,
        ),
        teto_maximo=TETO_MAXIMO,
    )


def _partida(s, simulacao_id: int, revisao_partida_id: int | None) -> SimulacaoRevisao:  # type: ignore[no-untyped-def]
    if revisao_partida_id is not None:
        return _revisao_da_simulacao(s, simulacao_id, revisao_partida_id, "revisão de partida")
    mais_nova = s.scalars(
        select(SimulacaoRevisao)
        .where(SimulacaoRevisao.simulacao_id == simulacao_id)
        .order_by(SimulacaoRevisao.id.desc())
        .limit(1)
    ).first()
    if mais_nova is None:
        raise HTTPException(status_code=409, detail="simulação sem revisão")
    return mais_nova


# Rotas ------------------------------------------------------------------------------------


@rotas_tarefas.get(
    "/simulacoes/{simulacao_id}/exploracao",
    operation_id="ver_resumo_da_exploracao",
    responses={404: {"description": "Simulação não existe."}},
)
def ver_resumo_da_exploracao(
    simulacao_id: int,
    revisao_partida_id: int | None = Query(
        default=None, description="De onde a exploração partiria. Vazio: a mais nova."
    ),
    alavancas: Annotated[
        list[AlavancaFisica] | None,
        Query(description="Só estas alavancas. Vazio: todas as da modalidade."),
    ] = None,
) -> ResumoDaExploracao:
    """O que se confirma antes de disparar uma exploração, sem criar nada: a configuração de
    partida, a faixa permitida de cada alavanca e as condições que ficam fixas. `422` quando a
    revisão não é da simulação ou a alavanca não existe na modalidade."""
    with sessao() as s:
        simulacao = s.get(Simulacao, simulacao_id)
        if simulacao is None:
            raise HTTPException(status_code=404, detail="simulação não existe")
        return _resumo(s, simulacao, _partida(s, simulacao_id, revisao_partida_id), alavancas)


@rotas_tarefas.post(
    "/simulacoes/{simulacao_id}/tarefas",
    status_code=201,
    operation_id="criar_tarefa",
    responses={
        404: {"description": "Simulação não existe."},
        409: {"model": ConflitoDeTarefa, "description": "Já há exploração em andamento."},
        503: {
            "model": DisparoRecusado,
            "description": "O processo de `agentes` não pôs a exploração para rodar: fora do "
            "ar, ou sem explorador. A tarefa fica `falhou`, com o motivo, e não trava a "
            "simulação.",
        },
    },
)
def criar_tarefa(
    simulacao_id: int,
    pedido: PedidoDeTarefa,
    disparar: Annotated[Disparar, Depends(disparador)],
) -> TarefaNaTela:
    """Cria a exploração em andamento, com a faixa confirmada gravada, e põe o explorador para
    rodar, a menos que `disparar` seja `false`. Uma por simulação: a segunda responde `409` com o
    id da que está rodando. Simulações diferentes rodam em paralelo."""
    with sessao() as s:
        simulacao = s.get(Simulacao, simulacao_id)
        if simulacao is None:
            raise HTTPException(status_code=404, detail="simulação não existe")
        for aberta in s.scalars(
            select(Tarefa).where(Tarefa.simulacao_id == simulacao_id, Tarefa.estado == EM_ANDAMENTO)
        ):
            _encerrar_se_perdida(s, aberta)
            if aberta.estado == EM_ANDAMENTO:
                raise _conflito(aberta.id)
        partida = _partida(s, simulacao_id, pedido.revisao_partida_id)
        resumo = _resumo(s, simulacao, partida, pedido.alavancas)
        tarefa = Tarefa(
            simulacao_id=simulacao_id,
            estado=EM_ANDAMENTO,
            teto=pedido.teto,
            pedido=pedido.pedido,
            revisao_partida_id=partida.id,
            faixa=resumo.faixa.model_dump(mode="json"),
        )
        s.add(tarefa)
        try:
            s.commit()
        except IntegrityError as erro:
            s.rollback()
            aberta = s.scalars(
                select(Tarefa.id).where(
                    Tarefa.simulacao_id == simulacao_id, Tarefa.estado == EM_ANDAMENTO
                )
            ).first()
            raise _conflito(aberta or 0) from erro
        criada = _na_tela(s, tarefa)
    if pedido.disparar:
        try:
            disparar(criada.id)
        except ExploradorFora as erro:
            with sessao() as s:
                tarefa = s.get(Tarefa, criada.id, with_for_update=True)
                if tarefa is not None and tarefa.estado == EM_ANDAMENTO:
                    _falhar(s, tarefa, f"a exploração não começou: {erro}")
            # Só a causa: quem chama já diz que a exploração não começou.
            raise HTTPException(
                status_code=503, detail={"mensagem": str(erro), "tarefa_id": criada.id}
            ) from erro
    return criada


def _conflito(tarefa_id: int) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "mensagem": f"já há uma exploração em andamento nesta simulação, a tarefa {tarefa_id}",
            "tarefa_id": tarefa_id,
        },
    )


@rotas_tarefas.get(
    "/simulacoes/{simulacao_id}/tarefas",
    operation_id="listar_tarefas",
    responses={404: {"description": "Simulação não existe."}},
)
def listar_tarefas(simulacao_id: int) -> list[TarefaNaTela]:
    """As explorações da simulação, da mais nova para a mais velha. É por aqui que a tela acha a
    que está em andamento, que é no máximo uma."""
    with sessao() as s:
        if s.get(Simulacao, simulacao_id) is None:
            raise HTTPException(status_code=404, detail="simulação não existe")
        linhas = list(
            s.scalars(
                select(Tarefa).where(Tarefa.simulacao_id == simulacao_id).order_by(Tarefa.id.desc())
            )
        )
        for tarefa in linhas:
            _encerrar_se_perdida(s, tarefa)
        return [_na_tela(s, tarefa) for tarefa in linhas]


@rotas_tarefas.get(
    "/tarefas/{tarefa_id}",
    operation_id="ver_tarefa",
    responses={404: {"description": "Tarefa não existe."}},
)
def ver_tarefa(tarefa_id: int) -> TarefaNaTela:
    """A tarefa com a contagem, contada dos eventos. Parada há mais de 20 minutos vira
    `falhou` aqui."""
    with sessao() as s:
        tarefa = s.get(Tarefa, tarefa_id)
        if tarefa is None:
            raise HTTPException(status_code=404, detail="tarefa não existe")
        _encerrar_se_perdida(s, tarefa)
        return _na_tela(s, tarefa)


@rotas_tarefas.post(
    "/tarefas/{tarefa_id}/eventos",
    status_code=201,
    operation_id="registrar_evento",
    responses={
        404: {"description": "Tarefa não existe."},
        409: {"description": "Tarefa já terminou."},
    },
)
def registrar_evento(tarefa_id: int, evento: EventoDoAgente) -> EventoGravado:
    """Grava um evento de `agentes`. `tarefa_terminada` encerra a tarefa, e `relatorio_pedido`
    liga o relatório a ela; relatório e revisão citados têm de ser da simulação da tarefa
    (`422`). Os eventos de variação não entram por aqui: quem os grava é a rota de variação."""
    with sessao() as s:
        tarefa = s.get(Tarefa, tarefa_id, with_for_update=True)
        if tarefa is None:
            raise HTTPException(status_code=404, detail="tarefa não existe")
        if tarefa.estado != EM_ANDAMENTO:
            raise HTTPException(status_code=409, detail=f"a tarefa já terminou: {tarefa.estado}")
        if isinstance(evento, RodadaDecidida):
            _revisao_da_simulacao(
                s, tarefa.simulacao_id, evento.revisao_partida_id, "revisão de partida"
            )
        if isinstance(evento, RelatorioPedido | RelatorioPronto):
            relatorio = s.get(modelos.Relatorio, evento.relatorio_id)
            if relatorio is None or relatorio.simulacao_id != tarefa.simulacao_id:
                raise HTTPException(
                    status_code=422,
                    detail=f"relatório {evento.relatorio_id} não é da simulação da tarefa",
                )
            if isinstance(evento, RelatorioPedido):
                tarefa.relatorio_id = relatorio.id
        if isinstance(evento, TarefaTerminada):
            tarefa.estado, tarefa.terminada_em = evento.estado, _agora()
            tarefa.erro = evento.motivo if evento.estado == FALHOU else None
        linha = _registrar(s, tarefa.id, evento)
        s.commit()
        return _gravado(linha)


@rotas_tarefas.get(
    "/tarefas/{tarefa_id}/eventos",
    operation_id="seguir_eventos",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "`text/event-stream`. Cada mensagem traz `id:` (o do evento), "
            "`event:` (o tipo) e `data:` com um `EventoGravado` em JSON.",
            "content": {
                "text/event-stream": {"schema": {"$ref": "#/components/schemas/EventoGravado"}}
            },
        },
        404: {"description": "Tarefa não existe."},
    },
)
def seguir_eventos(
    tarefa_id: int,
    depois_de: int = Query(default=0, ge=0, description="Só eventos com `id` maior que este."),
    last_event_id: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    """Os eventos já gravados, na ordem, e os novos à medida que chegam. Fecha quando a tarefa
    termina e o último evento foi mandado. Reconecta de onde parou pelo `Last-Event-ID`, que o
    `EventSource` do navegador manda sozinho."""
    with sessao() as s:
        if s.get(Tarefa, tarefa_id) is None:
            raise HTTPException(status_code=404, detail="tarefa não existe")
    retomada = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0
    inicio = max(depois_de, retomada)
    return StreamingResponse(
        _fluxo(tarefa_id, inicio),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _ler_depois(tarefa_id: int, depois_de: int) -> tuple[list[EventoGravado], bool]:
    with sessao() as s:
        tarefa = s.get(Tarefa, tarefa_id)
        assert tarefa is not None
        _encerrar_se_perdida(s, tarefa)
        # Estado antes dos eventos: o `tarefa_terminada` grava junto com o estado, então quem vê
        # a tarefa terminada vê também o evento que a terminou.
        terminada = tarefa.estado != EM_ANDAMENTO
        return [_gravado(e) for e in _eventos(s, tarefa_id, depois_de)], terminada


async def _fluxo(tarefa_id: int, depois_de: int) -> AsyncIterator[str]:
    ultimo, silencio = depois_de, 0.0
    while True:
        novos, terminada = await anyio.to_thread.run_sync(_ler_depois, tarefa_id, ultimo)
        for gravado in novos:
            ultimo = gravado.id
            dados = json.dumps(gravado.model_dump(mode="json"), ensure_ascii=False)
            yield f"id: {gravado.id}\nevent: {gravado.evento.tipo}\ndata: {dados}\n\n"
        if terminada and not novos:
            return
        silencio = 0.0 if novos else silencio + INTERVALO_DO_STREAMING_S
        if silencio >= BATIMENTO_S:
            silencio = 0.0
            yield ": vivo\n\n"
        await anyio.sleep(INTERVALO_DO_STREAMING_S)


@rotas_tarefas.post(
    "/simulacoes/{simulacao_id}/variacoes",
    operation_id="salvar_variacao",
    responses={
        404: {"description": "Simulação não existe."},
        409: {
            "description": "Tarefa terminada, teto de revisões atingido, ou configuração igual à "
            "de uma revisão que já existe na simulação."
        },
        422: {
            "description": "Alavanca fora da faixa ou que a exploração não varia, revisão ou "
            "tarefa de outra simulação, linha contingenciada, teto da capacidade, ou campo que "
            "não é da variação (preço, taxa, cenário, configuração)."
        },
    },
)
def salvar_variacao(simulacao_id: int, pedido: PedidoDeVariacao) -> RevisaoSalva:
    """Monta a variação pelo motor a partir de `revisao_base_id`, calcula e salva como revisão
    `por_agente` com a nota. As condições da comparação (preço, taxa, cenário, custo unitário,
    fonte, correção de minutos e snapshot) são as da revisão de partida, e o pedido não tem
    campo para mudá-las.

    Grava os eventos da variação na tarefa: iniciada, cada passo, e pronta ou recusada. Com a
    tarefa travada, confere o teto e a repetição, e grava revisão e `revisao_pronta` juntos.
    """
    variacao_id = pedido.variacao_id or uuid.uuid4().hex[:8]
    variacao = Variacao(alavanca=pedido.alavanca, valor=pedido.valor)
    with sessao() as s:
        simulacao = s.get(Simulacao, simulacao_id)
        if simulacao is None:
            raise HTTPException(status_code=404, detail="simulação não existe")
        tarefa = s.get(Tarefa, pedido.tarefa_id)
        if tarefa is None or tarefa.simulacao_id != simulacao_id:
            raise HTTPException(
                status_code=422,
                detail=f"tarefa {pedido.tarefa_id} não é exploração da simulação {simulacao_id}",
            )
        _encerrar_se_perdida(s, tarefa)
        if tarefa.estado != EM_ANDAMENTO:
            raise HTTPException(status_code=409, detail=f"a tarefa já terminou: {tarefa.estado}")
        base = _revisao_da_simulacao(s, simulacao_id, pedido.revisao_base_id, "revisão de partida")
        _registrar(
            s,
            tarefa.id,
            VariacaoIniciada(
                variacao_id=variacao_id,
                rodada=pedido.rodada,
                revisao_partida_id=base.id,
                alavanca=pedido.alavanca,
                valor=pedido.valor,
            ),
        )
        _registrar(s, tarefa.id, VariacaoPasso(variacao_id=variacao_id, passo="montando"))
        s.commit()
        partida = Configuracao.model_validate(base.configuracao)
        fonte, correcao = _fonte_e_correcao(base)
        faixa = FaixaPermitida.model_validate(tarefa.faixa)
        restricao_id, snapshot_id = simulacao.restricao_id, base.snapshot_id

    recusar = _Recusa(tarefa.id, variacao_id, variacao)
    try:
        montada = montar_variacao(partida, variacao, PREMISSAS_PADRAO, faixa)
    except ValueError as erro:
        raise recusar(422, str(erro)) from erro
    configuracao = montada.configuracao
    calculo = PedidoDeSimulacao(
        restricao_id=restricao_id,
        configuracao=configuracao,
        fonte=fonte,
        correcao_minutos=correcao,
        snapshot_id=snapshot_id,
    )
    _passo(tarefa.id, variacao_id, "calculando")
    try:
        serie = _serie_do_motor(calculo)
        resultado = calcular(serie, configuracao, _premissas(calculo))
    except HTTPException as erro:
        raise recusar(erro.status_code, str(erro.detail)) from erro
    _passo(tarefa.id, variacao_id, "salvando")

    with sessao() as s:
        travada = s.get(Tarefa, tarefa.id, with_for_update=True)
        assert travada is not None
        if travada.estado != EM_ANDAMENTO:
            raise recusar(409, f"a tarefa terminou antes de salvar: {travada.estado}", s)
        prontas = s.scalar(
            select(func.count())
            .select_from(Evento)
            .where(Evento.tarefa_id == travada.id, Evento.tipo == "revisao_pronta")
        )
        if (prontas or 0) >= travada.teto:
            raise recusar(409, f"teto de {travada.teto} revisões da exploração atingido", s)
        igual = _repetida(s, simulacao_id, configuracao, fonte, correcao)
        if igual is not None:
            raise recusar(
                409,
                f"configuração igual à da revisão {igual}, que já existe na simulação: variação "
                "repetida não conta",
                s,
            )
        revisao = SimulacaoRevisao(
            simulacao_id=simulacao_id,
            revisao_anterior_id=base.id,
            procedencia=POR_AGENTE,
            nota=pedido.nota.strip(),
            snapshot_id=serie.snapshot_id,
            metodo_versao=METODO_VERSAO,
            configuracao=configuracao.model_dump(mode="json"),
            premissas_usadas={
                id: p.model_dump(mode="json") for id, p in resultado.premissas_usadas.items()
            },
            resultado=resultado.model_dump(mode="json"),
            # A conta do investimento vai junto: a revisão grava só o total, e a trilha de custo
            # unitário vezes quantidade (a pergunta 4 da feature 04) se perderia ao salvar.
            avisos=[a.model_dump(mode="json") for a in [*resultado.avisos, *montada.avisos]],
        )
        s.add(revisao)
        s.flush()
        posicao = s.scalar(
            select(func.count())
            .select_from(SimulacaoRevisao)
            .where(SimulacaoRevisao.simulacao_id == simulacao_id, SimulacaoRevisao.id <= revisao.id)
        )
        tec, fin = resultado.tecnico, resultado.financeiro
        _registrar(
            s,
            travada.id,
            RevisaoPronta(
                variacao_id=variacao_id,
                revisao_id=revisao.id,
                posicao=posicao,
                revisao_partida_id=base.id,
                rodada=pedido.rodada,
                alavanca=pedido.alavanca,
                valor=pedido.valor,
                resumo=ResumoDaRevisao(
                    energia_recuperada_mwh=tec.energia_recuperada_mwh,
                    fracao_recuperada=tec.fracao_recuperada,
                    vpl_reais=fin.vpl_reais,
                    tir_aa=fin.tir_aa,
                    payback_simples_anos=fin.payback_simples_anos,
                    custo_por_mwh_reais=fin.custo_por_mwh_reais,
                    avisos=len(resultado.avisos) + len(montada.avisos),
                ),
            ),
        )
        s.commit()
        simulacao = s.get(Simulacao, simulacao_id)
        assert simulacao is not None
        return RevisaoSalva.model_validate(_salva(revisao, simulacao))


def _passo(tarefa_id: int, variacao_id: str, passo: Literal["calculando", "salvando"]) -> None:
    with sessao() as s:
        if _aberta(s, tarefa_id):
            _registrar(s, tarefa_id, VariacaoPasso(variacao_id=variacao_id, passo=passo))
        s.commit()


def _aberta(s, tarefa_id: int) -> bool:  # type: ignore[no-untyped-def]
    """A tarefa ainda aceita evento. Trava a linha: `tarefa_terminada` é sempre o último evento,
    e o streaming fecha depois dele, então evento gravado depois não chegaria à tela."""
    tarefa = s.get(Tarefa, tarefa_id, with_for_update=True)
    return tarefa is not None and tarefa.estado == EM_ANDAMENTO


class _Recusa:
    """Grava `variacao_recusada` com o motivo e devolve o erro HTTP a levantar. Com sessão, o
    evento entra na transação dela, que ainda tem a tarefa travada."""

    def __init__(self, tarefa_id: int, variacao_id: str, variacao: Variacao) -> None:
        self.tarefa_id, self.variacao_id, self.variacao = tarefa_id, variacao_id, variacao

    def __call__(self, status: int, motivo: str, s=None) -> HTTPException:  # type: ignore[no-untyped-def]
        evento = VariacaoRecusada(
            variacao_id=self.variacao_id,
            alavanca=self.variacao.alavanca,
            valor=self.variacao.valor,
            status=status,
            motivo=motivo,
        )
        if s is not None:
            if _aberta(s, self.tarefa_id):
                _registrar(s, self.tarefa_id, evento)
            s.commit()
        else:
            with sessao() as nova:
                if _aberta(nova, self.tarefa_id):
                    _registrar(nova, self.tarefa_id, evento)
                nova.commit()
        return HTTPException(status_code=status, detail=motivo)


def _repetida(  # type: ignore[no-untyped-def]
    s, simulacao_id: int, configuracao: Configuracao, fonte: Fonte, correcao: bool
) -> int | None:
    """A revisão da simulação com a mesma configuração, fonte e correção de minutos, se houver.
    As duas premissas entram porque são entrada do cálculo que a configuração não carrega."""
    alvo = configuracao.model_dump(mode="json")
    for revisao in s.scalars(
        select(SimulacaoRevisao).where(SimulacaoRevisao.simulacao_id == simulacao_id)
    ):
        if Configuracao.model_validate(revisao.configuracao).model_dump(mode="json") != alvo:
            continue
        if _fonte_e_correcao(revisao) == (fonte, correcao):
            return revisao.id
    return None
