"""Relatório da simulação: montagem da parte calculada, geração em tarefa de fundo e rotas.

Feature 17, marco 0 ([spec](../../../docs/features/agentes/17-relatorio-da-simulacao.md),
[contrato](../../../docs/features/agentes/17-relatorio-contrato.md)). O que é tabela é código,
o que é prosa é modelo, e todo número da prosa existe na parte calculada
([ADR 0012](../../../docs/adr/0012-relatorio-compila-evidencia-nao-recomenda.md)):

1. o `POST` grava o relatório em `gerando` com as revisões que existem agora, e responde na hora;
2. a tarefa de fundo monta a parte calculada — cabeçalho a partir das rotas de restrição e de
   ocorrências, trilha por template, linha por revisão, derivados pelo motor —, pede a prosa ao
   analista de `ia` e passa pelo verificador;
3. grava `pronto`, `barrado` (a prosa recusada fica guardada e nunca volta como prosa) ou
   `falhou` (a geração não chegou ao fim, e o motivo fica em `erro`).

As rotas moram aqui, num router próprio, e não em `rotas.py`: este módulo lê pelas rotas de
restrição e de ocorrências, e registrá-las lá seria import circular.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException
from opentelemetry import trace
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from arco_api import modelos
from arco_api.banco import sessao
from arco_api.leitura import Fonte
from arco_api.modelos import (
    BARRADO,
    FALHOU,
    GERANDO,
    POR_AGENTE,
    PRONTO,
    Simulacao,
    SimulacaoRevisao,
)
from arco_api.mudancas import ROTULOS, descrever, resumir
from arco_api.rotas import (
    AvisoDaRestricao,
    EquipamentoNaTela,
    OcorrenciaNaTela,
    _cronologicas,
    ver_ocorrencias,
    ver_restricao,
    ver_snapshot,
)
from arco_ia import relatorio as analista
from arco_ia.chamada import contexto_do_rastro
from arco_ia.relatorio import Prosa, Verificacao
from arco_motor.relatorio import Derivados, RevisaoCoberta, alavanca, derivar
from arco_motor.tipos import Cenario, Configuracao, Modalidade, Resultado
from arco_motor.versao import METODO_VERSAO

rotas_relatorio = APIRouter(tags=["relatorios"])
_registro = logging.getLogger(__name__)

PERDIDO_DEPOIS_DE = timedelta(minutes=20)
"""`gerando` mais velho que isto é tarefa que morreu com o processo: a tarefa de fundo mora em
memória, e reiniciar a API no meio a perde. Sem este corte, o `409` travaria a simulação para
sempre. Uma geração de verdade leva segundos, e a pior que ainda termina fica abaixo disto: duas
chances de esquema, cada uma com até quatro tentativas de `TEMPO_LIMITE_S` no cliente do modelo
(`arco_ia.config`)."""

EstadoDoRelatorio = Literal["gerando", "pronto", "barrado", "falhou"]


# Esquemas do contrato ---------------------------------------------------------------------


class RevisaoNova(BaseModel):
    revisao_id: int
    posicao: int
    criada_em: datetime


class FatiaDaFonte(BaseModel):
    fonte: Fonte
    fatia: float = Field(description="Fração de 0 a 1 da energia do ranking daquela fonte.")


class OcorrenciasResumo(BaseModel):
    total: int
    energia_mwh: float
    maiores: list[OcorrenciaNaTela] = Field(description="As três de maior energia.")
    aviso: str = Field(description="O limite da contagem, o mesmo da rota de ocorrências.")


class Cabecalho(BaseModel):
    """A restrição e o período, lidos pelas mesmas rotas que a tela usa."""

    restricao_id: str
    nome_curto: str | None
    texto: str
    instrucao_operacao: str | None
    contingencia: str | None
    subestacoes: list[str]
    presente_no_snapshot: bool
    snapshot_id: str = Field(
        description="O snapshot de onde o cabeçalho foi lido: o ativo quando o relatório foi "
        "gerado. Pode ser outro que o das revisões, e é por isso que tem campo próprio."
    )
    periodo_inicio: datetime | None = Field(description="Janela de `snapshot_id`.")
    periodo_fim: datetime | None
    energia_cortada_mwh: float = Field(description="Em `snapshot_id`, na fonte da simulação.")
    fonte: Fonte = Field(description="A fonte da revisão mais nova coberta.")
    fatia_por_fonte: list[FatiaDaFonte] = Field(description="Uma por fonte com corte.")
    ocorrencias: OcorrenciasResumo
    equipamentos: list[EquipamentoNaTela]
    avisos: list[AvisoDaRestricao]


class PassoDaTrilha(BaseModel):
    revisao_id: int
    posicao: int
    criada_em: datetime
    procedencia: Literal["por_pessoa", "por_agente"] = Field(
        description="Como a revisão nasceu ([ADR 0011]). Não é autor."
    )
    texto: str = Field(min_length=1)
    origem_do_texto: Literal["nota_da_pessoa", "nota_do_agente", "resumo_da_configuracao"] = Field(
        description="Com nota, o texto é ela; sem nota, o resumo da configuração por template, e "
        'a tela mostra "sem nota". Número escrito numa nota não conta como origem de número '
        "da prosa: a nota diz o porquê, a conta está na parte calculada."
    )


class LinhaDaRevisao(BaseModel):
    revisao_id: int
    posicao: int
    criada_em: datetime
    procedencia: Literal["por_pessoa", "por_agente"]
    modalidade: Modalidade
    alavanca: str = Field(description='"50 MW · 100 MWh · AÇU III", ou a linha e o ganho.')
    cenario: Cenario
    energia_recuperada_mwh: float
    fracao_recuperada: float
    vpl_reais: float
    tir_aa: float | None
    payback_simples_anos: float | None
    payback_descontado_anos: float | None
    custo_por_mwh_reais: float | None
    avisos: int = Field(description="Quantos avisos a revisão tem. Eles estão na tela dela.")
    url: str = Field(description="Caminho da revisão na API: `/simulacoes/{revisao_id}`.")


class ItemFixo(BaseModel):
    titulo: str
    texto: str


class ParteCalculada(BaseModel):
    """O que o código monta e a prosa é conferida contra. É o que a coluna guarda."""

    cabecalho: Cabecalho
    trilha: list[PassoDaTrilha]
    derivados: Derivados
    por_revisao: list[LinhaDaRevisao]


class RelatorioCriado(BaseModel):
    id: int
    simulacao_id: int
    estado: EstadoDoRelatorio


class RelatorioNaLista(BaseModel):
    id: int
    estado: EstadoDoRelatorio
    gerado_em: datetime | None
    revisoes_cobertas: list[int] = Field(description="Posições das revisões cobertas, na ordem.")
    revisoes_novas: list[RevisaoNova] = Field(
        description="Revisões criadas depois do relatório. Calculado na leitura."
    )


class Relatorio(BaseModel):
    """O relatório inteiro, em qualquer estado.

    Em `gerando`, só o que o pedido já sabe: cabeçalho, derivados e prosa nulos, listas vazias.
    Em `barrado`, a parte calculada e a verificação com as falhas, e a prosa nula. Em `falhou`,
    o motivo em `erro`, e a parte calculada quando ela chegou a ser montada.
    """

    id: int
    simulacao_id: int
    nome: str
    pergunta: str | None
    estado: EstadoDoRelatorio
    gerado_em: datetime | None = Field(description="Nulo em `gerando`.")
    snapshot_id: str = Field(description="Da revisão mais nova coberta.")
    metodo_versao: str = Field(description="Da revisão mais nova coberta.")
    modelo: str | None = Field(description="Modelo que escreveu a prosa, gravado na geração.")
    versao_prompt: str | None
    revisoes_cobertas: list[int] = Field(description="Posições das revisões cobertas, na ordem.")
    revisoes_novas: list[RevisaoNova] = Field(
        description='Revisões criadas depois do relatório: "há 2 revisões novas". Calculado na '
        "leitura, não gravado."
    )
    verificacao: Verificacao
    cabecalho: Cabecalho | None
    trilha: list[PassoDaTrilha]
    prosa: Prosa | None = Field(description="Nula em `gerando`, `barrado` e `falhou`.")
    derivados: Derivados | None
    por_revisao: list[LinhaDaRevisao]
    nao_afirma: list[ItemFixo] = Field(description="Texto fixo, versionado com o método.")
    erro: str | None = Field(description="Por que a geração não chegou ao fim, em `falhou`.")


NAO_AFIRMA: list[ItemFixo] = [
    ItemFixo(
        titulo="Sensibilidade calculada",
        texto="O relatório só fala de sensibilidade observada entre revisões que existem. Saber "
        "o VPL com outro preço exige recalcular, e recalcular é revisão nova.",
    ),
    ItemFixo(
        titulo="Série por mês ou por hora do dia",
        texto="O resultado guarda a série por intervalo sem o instante, e não há como agregá-la "
        "por período até a rota devolvê-lo.",
    ),
    ItemFixo(
        titulo="Ordem não é indicação",
        texto="O relatório ordena as revisões por critério declarado e não indica nenhuma delas: "
        "ordenar é evidência, e a decisão fica com quem lê.",
    ),
    ItemFixo(
        titulo="O resultado é contrafactual",
        texto="Diz o que teria acontecido sob as hipóteses informadas se o passado se repetisse "
        "com a intervenção disponível. Não é previsão.",
    ),
    ItemFixo(
        titulo="Associação não é causalidade",
        texto="A associação histórica entre o texto da restrição e um equipamento não prova, "
        "sozinha, causalidade física nem sensibilidade unitária. A conversão entre reforço e "
        "corte recuperável é premissa visível e editável.",
    ),
    ItemFixo(
        titulo="O histórico pode não representar o futuro",
        texto="Rede, geração, carga, preços e regulação mudam. Vários gargalos têm obras "
        "previstas.",
    ),
    ItemFixo(
        titulo="Energia recuperável não é receita capturável",
        texto="O valor atribuído à energia é premissa, não contrato.",
    ),
    ItemFixo(
        titulo="A simulação apoia a decisão, não a substitui",
        texto="Não substitui estudo elétrico, regulatório nem de engenharia.",
    ),
]
"""Três itens da seção D de `17-relatorio-dados.md` — sensibilidade calculada, série por
período, vencedor — e os cinco limites de `limites.md`, com o texto de lá: o quarto item da
seção D é "os cinco limites aparecem no texto". Versionados com `METODO_VERSAO`: mudou o método,
este texto é reavaliado. Nenhum número e nenhuma forma proibida aqui: o analista lê este texto,
o verificador aceitaria como origem o número que estivesse nele, e o modelo reaproveita as
palavras."""


# Rotas ------------------------------------------------------------------------------------


@rotas_relatorio.post(
    "/simulacoes/{simulacao_id}/relatorios",
    status_code=202,
    operation_id="pedir_relatorio",
    responses={
        404: {"description": "Simulação não existe."},
        409: {"description": "Já há um relatório em `gerando` para esta simulação."},
    },
)
def pedir_relatorio(simulacao_id: int, tarefas: BackgroundTasks) -> RelatorioCriado:
    """Cria o relatório em `gerando`, sobre as revisões que existem agora, e responde na hora.

    A geração corre em tarefa de fundo: acompanhe pelo `GET` do relatório até `pronto`,
    `barrado` ou `falhou`. Pedir de novo, depois, cria outro relatório; nada se sobrescreve.
    """
    with sessao() as s:
        simulacao = s.get(Simulacao, simulacao_id)
        if simulacao is None:
            raise HTTPException(status_code=404, detail="simulação não existe")
        _encerrar_perdidos(s, simulacao_id)
        if _em_andamento(s, simulacao_id):
            raise HTTPException(status_code=409, detail="já há um relatório em geração")
        cronologicas = _cronologicas(s, [simulacao_id]).get(simulacao_id, [])
        if not cronologicas:
            raise HTTPException(status_code=409, detail="simulação sem revisão")
        mais_nova = cronologicas[-1]
        relatorio = modelos.Relatorio(
            simulacao_id=simulacao_id,
            estado=GERANDO,
            snapshot_id=mais_nova.snapshot_id,
            metodo_versao=mais_nova.metodo_versao,
            revisoes_cobertas=[r.id for r in cronologicas],
        )
        s.add(relatorio)
        try:
            s.commit()
        except IntegrityError as erro:
            raise HTTPException(status_code=409, detail="já há um relatório em geração") from erro
        criado = RelatorioCriado(id=relatorio.id, simulacao_id=simulacao_id, estado=GERANDO)
    tarefas.add_task(gerar, criado.id)
    return criado


@rotas_relatorio.get(
    "/simulacoes/{simulacao_id}/relatorios/{relatorio_id}",
    operation_id="ver_relatorio",
    responses={404: {"description": "Relatório não existe nesta simulação."}},
)
def ver_relatorio(simulacao_id: int, relatorio_id: int) -> Relatorio:
    """O relatório inteiro, em qualquer estado, com as revisões criadas depois dele."""
    with sessao() as s:
        relatorio = s.get(modelos.Relatorio, relatorio_id)
        if relatorio is None or relatorio.simulacao_id != simulacao_id:
            raise HTTPException(status_code=404, detail="relatório não existe")
        simulacao = s.get(Simulacao, simulacao_id)
        assert simulacao is not None
        cronologicas = _cronologicas(s, [simulacao_id]).get(simulacao_id, [])
    parte = (
        ParteCalculada.model_validate(relatorio.parte_calculada)
        if relatorio.parte_calculada
        else None
    )
    return Relatorio(
        id=relatorio.id,
        simulacao_id=simulacao_id,
        nome=simulacao.nome,
        pergunta=simulacao.pergunta,
        estado=relatorio.estado,  # type: ignore[arg-type]
        gerado_em=relatorio.gerado_em,
        snapshot_id=relatorio.snapshot_id,
        metodo_versao=relatorio.metodo_versao,
        modelo=relatorio.modelo,
        versao_prompt=relatorio.versao_prompt,
        revisoes_cobertas=_posicoes(relatorio, cronologicas),
        revisoes_novas=_novas(relatorio, cronologicas),
        verificacao=Verificacao.model_validate(relatorio.verificacao)
        if relatorio.verificacao
        else _sem_verificacao(),
        cabecalho=parte.cabecalho if parte else None,
        trilha=parte.trilha if parte else [],
        prosa=Prosa.model_validate(relatorio.prosa) if relatorio.prosa else None,
        derivados=parte.derivados if parte else None,
        por_revisao=parte.por_revisao if parte else [],
        nao_afirma=NAO_AFIRMA,
        erro=relatorio.erro,
    )


@rotas_relatorio.get(
    "/simulacoes/{simulacao_id}/relatorios",
    operation_id="listar_relatorios",
    responses={404: {"description": "Simulação não existe."}},
)
def listar_relatorios(simulacao_id: int) -> list[RelatorioNaLista]:
    """Os relatórios da simulação, do mais novo para o mais velho."""
    with sessao() as s:
        if s.get(Simulacao, simulacao_id) is None:
            raise HTTPException(status_code=404, detail="simulação não existe")
        cronologicas = _cronologicas(s, [simulacao_id]).get(simulacao_id, [])
        relatorios = s.scalars(
            select(modelos.Relatorio)
            .where(modelos.Relatorio.simulacao_id == simulacao_id)
            .order_by(modelos.Relatorio.id.desc())
        ).all()
        return [
            RelatorioNaLista(
                id=r.id,
                estado=r.estado,  # type: ignore[arg-type]
                gerado_em=r.gerado_em,
                revisoes_cobertas=_posicoes(r, cronologicas),
                revisoes_novas=_novas(r, cronologicas),
            )
            for r in relatorios
        ]


def _posicoes(relatorio: modelos.Relatorio, cronologicas: list[SimulacaoRevisao]) -> list[int]:
    posicao = {r.id: p for p, r in enumerate(cronologicas, start=1)}
    return [posicao[id] for id in relatorio.revisoes_cobertas if id in posicao]


def _novas(relatorio: modelos.Relatorio, cronologicas: list[SimulacaoRevisao]) -> list[RevisaoNova]:
    cobertas = set(relatorio.revisoes_cobertas)
    ultima = max(cobertas, default=0)
    return [
        RevisaoNova(revisao_id=r.id, posicao=p, criada_em=r.criada_em)
        for p, r in enumerate(cronologicas, start=1)
        if r.id not in cobertas and r.id > ultima
    ]


def _sem_verificacao() -> Verificacao:
    return Verificacao(resultado=None, numeros_na_prosa=0, encontrados=0)


def _em_andamento(s, simulacao_id: int) -> bool:  # type: ignore[no-untyped-def]
    return (
        s.scalars(
            select(modelos.Relatorio.id).where(
                modelos.Relatorio.simulacao_id == simulacao_id,
                modelos.Relatorio.estado == GERANDO,
            )
        ).first()
        is not None
    )


def _encerrar_perdidos(s, simulacao_id: int) -> None:  # type: ignore[no-untyped-def]
    """`gerando` velho demais vira `falhou`: a tarefa que o geraria morreu com o processo."""
    agora = datetime.now(UTC)
    for r in s.scalars(
        select(modelos.Relatorio).where(
            modelos.Relatorio.simulacao_id == simulacao_id,
            modelos.Relatorio.estado == GERANDO,
        )
    ):
        criado = r.criado_em if r.criado_em.tzinfo else r.criado_em.replace(tzinfo=UTC)
        if agora - criado > PERDIDO_DEPOIS_DE:
            r.estado = FALHOU
            r.erro = "a geração não terminou; o processo da API provavelmente reiniciou no meio"
    s.commit()


# Geração ----------------------------------------------------------------------------------


def gerar(relatorio_id: int) -> None:
    """A tarefa de fundo: monta, pede a prosa, verifica e grava o estado final. Nunca levanta:
    qualquer falha vira `falhou` com o motivo, porque não há quem a receba.

    No Langfuse, o relatório sai na sessão da simulação, com a tag `relatorio` e a versão do
    método, para filtrar ali todos os relatórios de uma simulação."""
    with sessao() as s:
        linha = s.get(modelos.Relatorio, relatorio_id)
        simulacao_id = linha.simulacao_id if linha else None
    with (
        contexto_do_rastro(
            sessao=f"simulacao-{simulacao_id}", tags=["relatorio"], release=METODO_VERSAO
        ),
        trace.get_tracer("arco_api").start_as_current_span("gerar relatorio") as span,
    ):
        span.set_attribute("arco.relatorio_id", relatorio_id)
        span.set_attribute(
            "langfuse.observation.input",
            json.dumps({"relatorio_id": relatorio_id, "simulacao_id": simulacao_id}),
        )
        etapa, guardada = "parte calculada", None
        try:
            parte, para_o_analista = montar(relatorio_id)
            guardada = parte.model_dump(mode="json")
            etapa = "analista"
            resposta = analista.escrever_prosa(para_o_analista)
            etapa = "verificador"
            verificacao = analista.verificar(resposta.saida, para_o_analista)
            passou = verificacao.resultado == "passou"
            prosa = resposta.saida.model_dump(mode="json")
            span.set_attribute("arco.verificacao", str(verificacao.resultado))
            span.set_attribute(
                "langfuse.observation.output",
                json.dumps(
                    {
                        "estado": PRONTO if passou else BARRADO,
                        "numeros_na_prosa": verificacao.numeros_na_prosa,
                        "encontrados": verificacao.encontrados,
                        "falhas": len(verificacao.falhas),
                    }
                ),
            )
            etapa = "gravação"
            _encerrar(
                relatorio_id,
                PRONTO if passou else BARRADO,
                parte_calculada=guardada,
                prosa=prosa if passou else None,
                prosa_barrada=None if passou else prosa,
                verificacao=verificacao.model_dump(mode="json"),
                modelo=resposta.registro.modelo,
                versao_prompt=resposta.registro.versao_prompt,
            )
        except Exception as erro:
            _registro.exception("relatório %s: %s falhou", relatorio_id, etapa)
            span.set_attribute(
                "langfuse.observation.output",
                json.dumps({"estado": FALHOU, "etapa": etapa, "erro": _motivo(erro)}),
            )
            try:
                _encerrar(
                    relatorio_id,
                    FALHOU,
                    parte_calculada=guardada,
                    erro=f"{etapa}: {_motivo(erro)}",
                )
            except Exception:
                # Nem o `falhou` gravou: sobra o corte de `PERDIDO_DEPOIS_DE`, que libera a
                # simulação. O registro acima diz o que aconteceu.
                _registro.exception("relatório %s: não gravou nem a falha", relatorio_id)


def _motivo(erro: Exception) -> str:
    return str(erro.detail) if isinstance(erro, HTTPException) else f"{type(erro).__name__}: {erro}"


def _encerrar(relatorio_id: int, estado: str, **campos: Any) -> None:
    """Grava o estado final, uma vez. Relatório que já saiu de `gerando` — declarado perdido por
    demorar demais — não é sobrescrito: quem pediu de novo já está vendo outro."""
    with sessao() as s:
        relatorio = s.get(modelos.Relatorio, relatorio_id)
        assert relatorio is not None
        if relatorio.estado != GERANDO:
            _registro.warning(
                "relatório %s terminou depois de encerrado como %s; resultado descartado",
                relatorio_id,
                relatorio.estado,
            )
            return
        relatorio.estado = estado
        relatorio.gerado_em = datetime.now(UTC)
        for campo, valor in campos.items():
            setattr(relatorio, campo, valor)
        s.commit()


def montar(relatorio_id: int) -> tuple[ParteCalculada, dict[str, Any]]:
    """A parte calculada, e a entrada do analista: ela mais a simulação e o texto fixo.

    O verificador confere a prosa contra a mesma entrada que o analista recebeu: um número que
    o modelo leu no nome da simulação existe, e pode ser citado.
    """
    with sessao() as s:
        relatorio = s.get(modelos.Relatorio, relatorio_id)
        assert relatorio is not None
        simulacao = s.get(Simulacao, relatorio.simulacao_id)
        assert simulacao is not None
        cronologicas = _cronologicas(s, [simulacao.id])[simulacao.id]
        cobertas_ids = set(relatorio.revisoes_cobertas)
        mais_nova = max((r for r in cronologicas if r.id in cobertas_ids), key=lambda r: r.id)

    posicoes = {r.id: p for p, r in enumerate(cronologicas, start=1)}
    por_id = {r.id: r for r in cronologicas}
    cobertas = [
        _coberta(r, posicoes, por_id.get(r.revisao_anterior_id or -1))
        for r in cronologicas
        if r.id in cobertas_ids
    ]
    salvas = {r.id: r for r in cronologicas if r.id in cobertas_ids}
    fonte = Fonte(
        ((mais_nova.premissas_usadas or {}).get("fonte_geracao") or {}).get("valor", "eolica")
    )
    parte = ParteCalculada(
        cabecalho=_cabecalho(simulacao.restricao_id, fonte),
        trilha=[_passo(c, salvas[c.revisao_id]) for c in cobertas],
        derivados=derivar(cobertas, ROTULOS),
        por_revisao=[_linha(c) for c in cobertas],
    )
    para_o_analista = {
        "simulacao": {"nome": simulacao.nome, "pergunta": simulacao.pergunta},
        **parte.model_dump(mode="json"),
        "nao_afirma": [item.model_dump() for item in NAO_AFIRMA],
    }
    return parte, para_o_analista


def _coberta(
    revisao: SimulacaoRevisao, posicoes: dict[int, int], anterior: SimulacaoRevisao | None
) -> RevisaoCoberta:
    return RevisaoCoberta(
        revisao_id=revisao.id,
        posicao=posicoes[revisao.id],
        criada_em=revisao.criada_em,
        configuracao=Configuracao.model_validate(revisao.configuracao),
        resultado=Resultado.model_validate(revisao.resultado),
        o_que_mudou=descrever(
            revisao.configuracao or {},
            anterior.configuracao if anterior else None,
            revisao.snapshot_id,
            anterior.snapshot_id if anterior else None,
            posicoes.get(anterior.id) if anterior else None,
            revisao.premissas_usadas or {},
            anterior.premissas_usadas if anterior else None,
        ),
        revisao_anterior_id=revisao.revisao_anterior_id,
    )


def _cabecalho(restricao_id: str, fonte: Fonte) -> Cabecalho:
    """Lido pelas rotas da tela, no snapshot ativo. As revisões podem ter sido calculadas sobre
    outro: por isso o cabeçalho diz o seu, e a janela é a dele, nunca a das revisões."""
    snapshot = ver_snapshot()
    detalhada = ver_restricao(restricao_id, fonte)
    fatias = [
        FatiaDaFonte(fonte=Fonte(f), fatia=ver_restricao(restricao_id, Fonte(f)).fatia_do_total)
        for f in detalhada.fontes
    ]
    ocorrencias = ver_ocorrencias(restricao_id, fonte)
    return Cabecalho(
        restricao_id=detalhada.id,
        nome_curto=detalhada.nome_curto,
        texto=detalhada.texto,
        instrucao_operacao=detalhada.instrucao_operacao,
        contingencia=detalhada.contingencia,
        subestacoes=detalhada.subestacoes,
        presente_no_snapshot=detalhada.presente_no_snapshot,
        snapshot_id=snapshot.id,
        periodo_inicio=snapshot.periodo_inicio,
        periodo_fim=snapshot.periodo_fim,
        energia_cortada_mwh=detalhada.energia_mwh,
        fonte=fonte,
        fatia_por_fonte=fatias,
        ocorrencias=OcorrenciasResumo(
            total=ocorrencias.total,
            energia_mwh=ocorrencias.energia_mwh,
            maiores=ocorrencias.itens[:3],
            aviso=ocorrencias.aviso,
        ),
        equipamentos=detalhada.equipamentos,
        avisos=detalhada.avisos,
    )


def _passo(c: RevisaoCoberta, salva: SimulacaoRevisao) -> PassoDaTrilha:
    """A nota de quem salvou, quando há; sem ela, o resumo da configuração por template.

    A nota é texto de pessoa ou de agente, e o verificador não aceita número dela como origem
    de número da prosa (`arco_ia.relatorio.valores`): ela diz o porquê, nunca a conta."""
    agente = salva.procedencia == POR_AGENTE
    if salva.nota:
        texto, origem = salva.nota, "nota_do_agente" if agente else "nota_da_pessoa"
    else:
        texto, origem = resumir(c.configuracao.model_dump(mode="json")), "resumo_da_configuracao"
    return PassoDaTrilha(
        revisao_id=c.revisao_id,
        posicao=c.posicao,
        criada_em=c.criada_em,
        procedencia="por_agente" if agente else "por_pessoa",
        texto=texto,
        origem_do_texto=origem,
    )


def _linha(c: RevisaoCoberta) -> LinhaDaRevisao:
    tec, fin = c.resultado.tecnico, c.resultado.financeiro
    return LinhaDaRevisao(
        revisao_id=c.revisao_id,
        posicao=c.posicao,
        criada_em=c.criada_em,
        procedencia="por_pessoa",
        modalidade=c.configuracao.modalidade,
        alavanca=alavanca(c.configuracao),
        cenario=c.configuracao.financeira.cenario,
        energia_recuperada_mwh=tec.energia_recuperada_mwh,
        fracao_recuperada=tec.fracao_recuperada,
        vpl_reais=fin.vpl_reais,
        tir_aa=fin.tir_aa,
        payback_simples_anos=fin.payback_simples_anos,
        payback_descontado_anos=fin.payback_descontado_anos,
        custo_por_mwh_reais=fin.custo_por_mwh_reais,
        avisos=len(c.resultado.avisos),
        url=f"/simulacoes/{c.revisao_id}",
    )
