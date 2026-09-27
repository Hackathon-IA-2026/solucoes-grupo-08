"""Parte calculada do relatório da simulação: o que o código deriva entre revisões.

Feature 17, marco 0 ([spec](../../../docs/features/agentes/17-relatorio-da-simulacao.md),
[contrato](../../../docs/features/agentes/17-relatorio-contrato.md)). A regra é a da
[ADR 0012](../../../docs/adr/0012-relatorio-compila-evidencia-nao-recomenda.md): o que é tabela é
código, o que é prosa é modelo, e todo número da prosa tem de existir aqui. Ordenar é evidência;
escolher é recomendação, e não entra. Nada aqui interpola: toda afirmação é "entre as revisões
cobertas".

Puro como o resto do motor: as revisões entram prontas, com a data de criação e a frase de
"o que mudou" que a API já monta, e os rótulos dos campos vêm por parâmetro, porque a tabela
deles mora na API, que o motor não importa. Nenhum resultado existente muda: é cálculo novo ao
lado do que havia.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any, Literal, TypeIs

from pydantic import BaseModel, Field

from arco_motor.premissas import METODO, StatusPremissa
from arco_motor.tipos import Configuracao, Modalidade, Resultado
from arco_motor.versao import MUDAM_RESULTADO


class RevisaoCoberta(BaseModel):
    """Uma revisão salva que o relatório cobre, como a API a lê do banco."""

    revisao_id: int
    posicao: int = Field(ge=1, description="Posição da revisão na simulação, a partir de 1.")
    criada_em: datetime
    configuracao: Configuracao
    resultado: Resultado
    o_que_mudou: str = Field(description="A frase da coluna de mesmo nome, montada pela API.")
    revisao_anterior_id: int | None = Field(
        default=None,
        description="A revisão de onde esta nasceu ([ADR 0014]). É contra ela que as diferenças "
        '"vs anterior" e a sensibilidade se medem, e não contra a vizinha na ordem de gravação: '
        "numa simulação com ramos, duas variações irmãs nasceram da mesma revisão.",
    )


Metrica = Literal["vpl", "fracao_recuperada", "payback_descontado", "custo_por_mwh"]


class PosicaoOrdenada(BaseModel):
    posicao: int = Field(description="Lugar na ordenação, a partir de 1. Empate repete o lugar.")
    revisao_id: int
    posicao_da_revisao: int
    valor: float | None
    empate_com: list[int] = Field(description="`revisao_id` das revisões com o mesmo valor.")


class RevisaoBase(BaseModel):
    """A primeira revisão coberta, contra a qual as diferenças se medem."""

    revisao_id: int
    posicao: int


class Diferenca(BaseModel):
    """Uma revisão contra a base, que é a primeira coberta, e contra a de origem.

    "Anterior" nos nomes dos campos é a revisão de onde esta nasceu (`revisao_anterior_id`),
    como na revisão desde a [ADR 0014]; o nome ficou para os relatórios já gravados continuarem
    abrindo. Numa cadeia sem ramos, a de origem é a vizinha, e nada muda."""

    revisao_id: int
    o_que_mudou: str
    anterior_revisao_id: int | None = Field(
        default=None,
        description='A revisão de origem, contra a qual os deltas "vs anterior" se medem.',
    )
    delta_vpl_vs_base_reais: float
    delta_vpl_vs_anterior_reais: float = Field(description="Contra a revisão de origem.")
    delta_energia_vs_base_mwh: float
    delta_energia_vs_anterior_mwh: float = Field(description="Contra a revisão de origem.")
    delta_fracao_vs_base: float
    delta_payback_simples_vs_base_anos: float | None = Field(
        description="Nulo quando o payback não ocorre numa das duas."
    )


TipoSensibilidade = Literal["numerica", "categorica", "sem_par"]


class Sensibilidade(BaseModel):
    """O efeito observado entre uma revisão e a de onde ela nasceu, quando só uma coisa mudou
    entre elas.

    `sem_par` quando mudou mais de uma coisa, ou nenhuma: aí não há como atribuir o efeito a um
    campo, e o relatório não atribui.
    """

    de_revisao_id: int
    para_revisao_id: int
    tipo: TipoSensibilidade
    campo: str | None = Field(description="Caminho em `Configuracao`. Nulo em `sem_par`.")
    rotulo: str | None
    de: str | None
    para: str | None
    delta_vpl_por_unidade_reais: float | None = Field(
        description="ΔVPL dividido pela variação do campo. Só em `numerica`."
    )
    delta_energia_por_unidade_mwh: float | None = Field(
        description="Δenergia recuperada dividida pela variação do campo. Só em `numerica`."
    )
    delta_vpl_reais: float | None = Field(description="ΔVPL do par. Nulo em `sem_par`.")
    campos_que_mudaram: list[str] = Field(
        description="Em `sem_par`, tudo o que mudou entre as duas: campos, premissas, snapshot "
        "e versão do método."
    )
    condicao: str = Field(description="O que ficou fixo no par, em texto.")


class FronteiraPayback(BaseModel):
    revisao_id: int
    alavanca: str
    payback_anos: float
    horizonte_anos: int


class FronteiraFracao(BaseModel):
    revisao_id: int
    fracao: float
    custo_por_mwh_reais: float | None


class FronteiraTir(BaseModel):
    revisao_id: int
    tir_aa: float
    taxa_desconto_aa: float


class Fronteiras(BaseModel):
    """Onde algo acontece entre as revisões cobertas. Nulo é "não atingida entre elas"."""

    menor_alavanca_com_payback_no_horizonte: FronteiraPayback | None = Field(
        description="Entre as revisões com payback simples dentro do horizonte, a de menor "
        "alavanca: o tamanho do que se instalou, se todas são da mesma modalidade, com o "
        "investimento inicial desempatando; só o investimento, se não são."
    )
    maior_fracao_recuperada: FronteiraFracao | None = Field(
        description="A revisão de maior fração recuperada, e a que custo. Nula se nenhuma recupera."
    )
    tir_passa_taxa: FronteiraTir | None = Field(
        description="Entre as revisões com TIR acima da taxa de desconto, a de menor alavanca, "
        "pelo mesmo critério."
    )


class CampoEValor(BaseModel):
    campo: str
    rotulo: str
    valores: list[str] = Field(
        default_factory=list, description="Em `variou`: os valores distintos, na ordem."
    )
    valor: str | None = Field(default=None, description="Em `ficou_parado`: o valor único.")


class PremissaExposta(BaseModel):
    id: str
    descricao: str
    valor: str = Field(description="Os valores usados nas revisões cobertas, distintos.")
    unidade: str | None
    faixa: tuple[float, float] | None
    fonte: str = Field(description="De onde o valor vem, como no registro de premissas.")
    status: Literal["proposta", "nao_verificada"]
    de_metodo: bool


class Derivados(BaseModel):
    """Tudo o que o código deriva sobre as revisões cobertas. É contra isto que a prosa é
    conferida."""

    ordenacoes: dict[Metrica, list[PosicaoOrdenada]] = Field(
        description="VPL decrescente, fração decrescente, payback descontado crescente só onde "
        "ocorre, custo por MWh crescente só onde existe. Vazias com menos de duas revisões."
    )
    base: RevisaoBase
    diferencas: list[Diferenca]
    sensibilidades: list[Sensibilidade]
    fronteiras: Fronteiras
    variou: list[CampoEValor]
    ficou_parado: list[CampoEValor]
    premissas_expostas: list[PremissaExposta]


def derivar(
    revisoes: Sequence[RevisaoCoberta], rotulos: Mapping[str, str] | None = None
) -> Derivados:
    """A parte calculada do relatório, sobre as revisões cobertas em qualquer ordem."""
    if not revisoes:
        raise ValueError("relatório sem revisão coberta")
    rotulos = rotulos or {}
    ordem = sorted(revisoes, key=lambda r: r.posicao)
    base = ordem[0]
    pares = _pares(ordem)
    return Derivados(
        ordenacoes=_ordenacoes(ordem),
        base=RevisaoBase(revisao_id=base.revisao_id, posicao=base.posicao),
        diferencas=[_diferenca(r, origem, base) for origem, r in pares],
        sensibilidades=[_sensibilidade(origem, r, rotulos) for origem, r in pares],
        fronteiras=_fronteiras(ordem),
        **_variou_e_parado(ordem, rotulos),
        premissas_expostas=_premissas_expostas(ordem),
    )


# Ordenações --------------------------------------------------------------------------------


def _ordenacoes(ordem: list[RevisaoCoberta]) -> dict[Metrica, list[PosicaoOrdenada]]:
    criterios: dict[Metrica, tuple[Callable[[Resultado], float | None], bool]] = {
        "vpl": (lambda r: r.financeiro.vpl_reais, True),
        "fracao_recuperada": (lambda r: r.tecnico.fracao_recuperada, True),
        "payback_descontado": (lambda r: r.financeiro.payback_descontado_anos, False),
        "custo_por_mwh": (lambda r: r.financeiro.custo_por_mwh_reais, False),
    }
    if len(ordem) < 2:
        return {metrica: [] for metrica in criterios}
    return {
        metrica: _ordenar(ordem, ler, decrescente)
        for metrica, (ler, decrescente) in criterios.items()
    }


def _ordenar(
    ordem: list[RevisaoCoberta], ler: Callable[[Resultado], float | None], decrescente: bool
) -> list[PosicaoOrdenada]:
    """Classificação com empate: dois valores iguais dividem o lugar, e o seguinte pula."""
    com_valor = [(r, v) for r in ordem if (v := ler(r.resultado)) is not None]
    com_valor.sort(key=lambda par: (-par[1] if decrescente else par[1], par[0].posicao))
    grupos: list[list[tuple[RevisaoCoberta, float]]] = []
    for par in com_valor:
        if grupos and _iguais(grupos[-1][0][1], par[1]):
            grupos[-1].append(par)
        else:
            grupos.append([par])
    saida: list[PosicaoOrdenada] = []
    for grupo in grupos:
        lugar = len(saida) + 1
        ids = [r.revisao_id for r, _ in grupo]
        saida += [
            PosicaoOrdenada(
                posicao=lugar,
                revisao_id=r.revisao_id,
                posicao_da_revisao=r.posicao,
                valor=v,
                empate_com=[i for i in ids if i != r.revisao_id],
            )
            for r, v in grupo
        ]
    return saida


def _iguais(a: float, b: float) -> bool:
    """Empate é igualdade até o ruído de ponto flutuante, não até o arredondamento da tela."""
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6)


# Diferenças --------------------------------------------------------------------------------


def _pares(ordem: list[RevisaoCoberta]) -> list[tuple[RevisaoCoberta, RevisaoCoberta]]:
    """Cada revisão com a de onde ela nasceu, na ordem de gravação.

    Revisão sem origem entre as cobertas não forma par: é a base, ou uma origem que o relatório
    não cobre. Sem `revisao_anterior_id` em nenhuma — revisão lida de antes do campo —, o par é
    a vizinha na ordem, que era a origem enquanto a simulação não tinha ramos.
    """
    if all(r.revisao_anterior_id is None for r in ordem):
        return list(itertools.pairwise(ordem))
    por_id = {r.revisao_id: r for r in ordem}
    return [
        (por_id[r.revisao_anterior_id], r)
        for r in ordem
        if r.revisao_anterior_id is not None and r.revisao_anterior_id in por_id
    ]


def _diferenca(r: RevisaoCoberta, anterior: RevisaoCoberta, base: RevisaoCoberta) -> Diferenca:
    fin, tec = r.resultado.financeiro, r.resultado.tecnico
    payback, payback_base = (
        fin.payback_simples_anos,
        base.resultado.financeiro.payback_simples_anos,
    )
    return Diferenca(
        revisao_id=r.revisao_id,
        o_que_mudou=r.o_que_mudou,
        anterior_revisao_id=anterior.revisao_id,
        delta_vpl_vs_base_reais=fin.vpl_reais - base.resultado.financeiro.vpl_reais,
        delta_vpl_vs_anterior_reais=fin.vpl_reais - anterior.resultado.financeiro.vpl_reais,
        delta_energia_vs_base_mwh=tec.energia_recuperada_mwh
        - base.resultado.tecnico.energia_recuperada_mwh,
        delta_energia_vs_anterior_mwh=tec.energia_recuperada_mwh
        - anterior.resultado.tecnico.energia_recuperada_mwh,
        delta_fracao_vs_base=tec.fracao_recuperada - base.resultado.tecnico.fracao_recuperada,
        delta_payback_simples_vs_base_anos=(
            None if payback is None or payback_base is None else payback - payback_base
        ),
    )


# Sensibilidade observada -------------------------------------------------------------------

ALAVANCAS = (
    "modalidade",
    "bateria.potencia_mw",
    "bateria.capacidade_mwh",
    "bateria.subestacao",
    "equipamento.cod_equipamento",
    "equipamento.ganho_limite_mw",
    "financeira.cenario",
)
"""Os campos que dizem o que se instalou e sob que cenário. São eles que a condição de uma
sensibilidade nomeia como fixos; os demais cabem em "demais campos iguais"."""

POTENCIA = "bateria.potencia_mw"
CAPACIDADE = "bateria.capacidade_mwh"
TAMANHOS = (POTENCIA, CAPACIDADE, "equipamento.ganho_limite_mw")
"""O tamanho da alavanca: o que se mede em MW ou MWh e tem custo por unidade."""


def _mesma_duracao(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Capacidade sobre potência igual nas duas: a potência mudou e a duração ficou."""
    try:
        return math.isclose(
            float(a[CAPACIDADE]) / float(a[POTENCIA]),
            float(b[CAPACIDADE]) / float(b[POTENCIA]),
            rel_tol=1e-9,
        )
    except KeyError, TypeError, ValueError, ZeroDivisionError:
        return False


CUSTOS = (
    "financeira.capex_reais",
    "financeira.opex_fixo_reais_ano",
    "financeira.opex_variavel_reais_mwh",
    "financeira.reposicoes",
)
"""Os campos de custo que acompanham o tamanho da alavanca. Uma bateria de 100 MW custa mais que
uma de 50 MW, e a tela e o explorador montam o investimento pelo custo unitário: exigir que o
custo ficasse parado faria toda exploração de tamanho sair `sem_par`. Quando só o tamanho e o
custo mudam, o efeito é do tamanho **com o custo dele**, e a condição diz isso."""


def _sensibilidade(
    a: RevisaoCoberta, b: RevisaoCoberta, rotulos: Mapping[str, str]
) -> Sensibilidade:
    """Só atribui o efeito a um campo quando ele é a única diferença do par, ou quando é o
    tamanho da alavanca e o que mudou junto foi só o custo dela (`CUSTOS`).

    Diferença de premissa, de snapshot e de versão do método conta como mudança: trocar a fonte
    e a potência ao mesmo tempo e atribuir tudo à potência seria sensibilidade inventada.
    """
    folhas_a, folhas_b = folhas(a.configuracao), folhas(b.configuracao)
    campos = [
        c
        for c in dict.fromkeys([*folhas_a, *folhas_b])
        if folhas_a.get(c, _AUSENTE) != folhas_b.get(c, _AUSENTE)
    ]
    outros = _premissas_mudadas(a, b)
    if a.resultado.snapshot_id != b.resultado.snapshot_id:
        outros.append("snapshot_id")
    if _metodo_mudou_resultado(a.resultado.metodo_versao, b.resultado.metodo_versao):
        outros.append("metodo_versao")
    todos = campos + outros
    delta_vpl = b.resultado.financeiro.vpl_reais - a.resultado.financeiro.vpl_reais
    comum: dict[str, Any] = {"de_revisao_id": a.revisao_id, "para_revisao_id": b.revisao_id}
    tamanho = [c for c in campos if c in TAMANHOS]
    acompanham: set[str] = set(CUSTOS)
    if set(tamanho) == {POTENCIA, CAPACIDADE} and _mesma_duracao(folhas_a, folhas_b):
        # Potência na mesma duração: a capacidade acompanha, como o custo. É a alavanca
        # "potência" do explorador, e sem isto toda a grade de tamanhos sairia `sem_par`.
        tamanho = [POTENCIA]
        acompanham.add(CAPACIDADE)
    custo_acompanhou = (
        not outros
        and len(tamanho) == 1
        and len(campos) > 1
        and all(c in acompanham for c in campos if c != tamanho[0])
    )

    if custo_acompanhou:
        (campo,) = tamanho
        todos_de_custo = [c for c in campos if c != campo]
    elif len(todos) != 1 or not campos:
        if not todos:
            condicao = "nada mudou entre as duas"
        elif not campos:
            condicao = f"só mudou {todos[0]}, que não é campo da configuração"
        else:
            condicao = "mudou mais de uma coisa entre as duas"
        return Sensibilidade(
            **comum,
            tipo="sem_par",
            campo=None,
            rotulo=None,
            de=None,
            para=None,
            delta_vpl_por_unidade_reais=None,
            delta_energia_por_unidade_mwh=None,
            delta_vpl_reais=None,
            campos_que_mudaram=todos,
            condicao=condicao,
        )

    else:
        (campo,) = campos
        todos_de_custo = []
    de, para = folhas_a.get(campo), folhas_b.get(campo)
    variacao = float(para) - float(de) if _numero(de) and _numero(para) else None
    numerica = variacao is not None
    delta_energia = (
        b.resultado.tecnico.energia_recuperada_mwh - a.resultado.tecnico.energia_recuperada_mwh
    )
    return Sensibilidade(
        **comum,
        tipo="numerica" if numerica else "categorica",
        campo=campo,
        rotulo=rotulos.get(campo, campo),
        de=escrever(de, campo),
        para=escrever(para, campo),
        delta_vpl_por_unidade_reais=delta_vpl / variacao if variacao else None,
        delta_energia_por_unidade_mwh=delta_energia / variacao if variacao else None,
        delta_vpl_reais=delta_vpl,
        campos_que_mudaram=[campo, *todos_de_custo],
        condicao=_condicao(campo, folhas_a, rotulos, folhas_b, todos_de_custo),
    )


def _metodo_mudou_resultado(de: str, para: str) -> bool:
    """Entre as duas versões há alguma que muda resultado para a mesma entrada?

    Só essas tiram o par: uma versão que acrescenta campo, como a 0.7.0, não muda número, e
    tratá-la como mudança faria toda simulação perder a sensibilidade na virada. Versão que o
    histórico não conhece conta como mudança, pelo lado seguro.
    """
    if de == para:
        return False
    try:
        a, b = sorted((_versao(de), _versao(para)))
    except ValueError:
        return True
    return any(a < _versao(v) <= b for v in MUDAM_RESULTADO)


def _versao(texto: str) -> tuple[int, ...]:
    return tuple(int(parte) for parte in texto.split("."))


def _condicao(
    campo: str,
    fixas: dict[str, Any],
    rotulos: Mapping[str, str],
    depois: dict[str, Any],
    custos: list[str],
) -> str:
    partes = [
        f"{rotulos.get(c, c)}: {escrever(fixas[c], c)}"
        for c in ALAVANCAS
        if c != campo and c not in custos and c in fixas
    ]
    texto = "fixos: " + "; ".join([*partes, "demais campos iguais"])

    def de_para(c: str) -> str:
        return f"{rotulos.get(c, c)}: {escrever(fixas.get(c), c)} → {escrever(depois.get(c), c)}"

    so_custo = [c for c in custos if c != CAPACIDADE]
    if so_custo:
        texto = f"o custo acompanhou a alavanca ({'; '.join(map(de_para, so_custo))}); {texto}"
    if CAPACIDADE in custos:
        horas = float(fixas[CAPACIDADE]) / float(fixas[POTENCIA])
        texto = (
            f"a capacidade acompanhou a potência na mesma duração, {numero_br(horas)} h "
            f"({de_para(CAPACIDADE)}); {texto}"
        )
    return texto


def _premissas_mudadas(a: RevisaoCoberta, b: RevisaoCoberta) -> list[str]:
    """Premissas presentes nas duas com valor diferente. Premissa que só existe de um lado é
    consequência da modalidade ou da versão do método, não escolha: mesma regra de
    `mudancas.descrever`, na API."""
    antes, agora = a.resultado.premissas_usadas, b.resultado.premissas_usadas
    return [
        f"premissa.{id}"
        for id, premissa in agora.items()
        if id in antes and antes[id].valor != premissa.valor
    ]


# Fronteiras --------------------------------------------------------------------------------


def _fronteiras(ordem: list[RevisaoCoberta]) -> Fronteiras:
    menor = _menor_alavanca(ordem)
    no_horizonte = [
        r
        for r in ordem
        if (p := r.resultado.financeiro.payback_simples_anos) is not None
        and p <= r.configuracao.financeira.horizonte_anos
    ]
    payback = None
    if no_horizonte:
        r = min(no_horizonte, key=menor)
        payback = FronteiraPayback(
            revisao_id=r.revisao_id,
            alavanca=alavanca(r.configuracao),
            payback_anos=r.resultado.financeiro.payback_simples_anos or 0.0,
            horizonte_anos=r.configuracao.financeira.horizonte_anos,
        )

    maior = max(ordem, key=lambda r: (r.resultado.tecnico.fracao_recuperada, -r.posicao))
    fracao = None
    if maior.resultado.tecnico.fracao_recuperada > 0:
        fracao = FronteiraFracao(
            revisao_id=maior.revisao_id,
            fracao=maior.resultado.tecnico.fracao_recuperada,
            custo_por_mwh_reais=maior.resultado.financeiro.custo_por_mwh_reais,
        )

    acima = [
        r
        for r in ordem
        if (t := r.resultado.financeiro.tir_aa) is not None
        and t > r.configuracao.financeira.taxa_desconto_aa
    ]
    tir = None
    if acima:
        r = min(acima, key=menor)
        tir = FronteiraTir(
            revisao_id=r.revisao_id,
            tir_aa=r.resultado.financeiro.tir_aa or 0.0,
            taxa_desconto_aa=r.configuracao.financeira.taxa_desconto_aa,
        )
    return Fronteiras(
        menor_alavanca_com_payback_no_horizonte=payback,
        maior_fracao_recuperada=fracao,
        tir_passa_taxa=tir,
    )


def _menor_alavanca(
    ordem: list[RevisaoCoberta],
) -> Callable[[RevisaoCoberta], tuple[tuple[float, ...], float, int]]:
    """Critério de "menor alavanca": o tamanho do que se instalou, quando todas as revisões são
    da mesma modalidade; o investimento inicial desempata, e a posição depois dele.

    Entre modalidades diferentes o tamanho não se compara (MW de bateria não é MW de ganho de
    limite), e sobra o investimento. O investimento sozinho não serve de critério geral porque é
    digitado: duas baterias de tamanhos diferentes podem ter o mesmo.
    """
    mesma = len({r.configuracao.modalidade for r in ordem}) == 1

    def chave(r: RevisaoCoberta) -> tuple[tuple[float, ...], float, int]:
        return (
            _tamanho(r.configuracao) if mesma else (),
            r.configuracao.financeira.capex_reais,
            r.posicao,
        )

    return chave


def _tamanho(configuracao: Configuracao) -> tuple[float, ...]:
    """Ganho de limite primeiro, depois potência e capacidade da bateria."""
    partes: list[float] = []
    if configuracao.equipamento is not None:
        partes.append(configuracao.equipamento.ganho_limite_mw)
    if configuracao.bateria is not None:
        partes += [configuracao.bateria.potencia_mw, configuracao.bateria.capacidade_mwh]
    return tuple(partes)


# O que variou e o que ficou parado ---------------------------------------------------------


def _variou_e_parado(
    ordem: list[RevisaoCoberta], rotulos: Mapping[str, str]
) -> dict[str, list[CampoEValor]]:
    """Particiona os campos da configuração: os que mudaram em alguma revisão e os iguais em
    todas. Campo que só existe em parte das revisões (a bateria numa revisão de equipamento)
    variou: numa ele tem valor, na outra está vazio."""
    todas = [folhas(r.configuracao) for r in ordem]
    campos = dict.fromkeys(c for f in todas for c in f)
    variou: list[CampoEValor] = []
    parado: list[CampoEValor] = []
    for campo in campos:
        valores = [f.get(campo, _AUSENTE) for f in todas]
        rotulo = rotulos.get(campo, campo)
        if all(v == valores[0] for v in valores):
            parado.append(
                CampoEValor(campo=campo, rotulo=rotulo, valor=escrever(valores[0], campo))
            )
        else:
            escritos = [escrever(None if v is _AUSENTE else v, campo) for v in valores]
            variou.append(
                CampoEValor(campo=campo, rotulo=rotulo, valores=list(dict.fromkeys(escritos)))
            )
    return {"variou": variou, "ficou_parado": parado}


# Premissas expostas ------------------------------------------------------------------------


def _premissas_expostas(ordem: list[RevisaoCoberta]) -> list[PremissaExposta]:
    """As premissas que o resultado tocou e ninguém validou, com os valores das revisões.

    `premissas_usadas` carimba mais do que o cálculo lê, e por bom motivo, auditoria: a
    sensibilidade do equipamento aparece sempre, e o preço padrão aparece mesmo quando a
    configuração o sobrescreve. Expor essas duas quando não tocaram o resultado poria na prosa
    um número que não entrou em conta nenhuma.

    Com status diferente entre revisões, vale o menos validado: `nao_verificada` vence
    `proposta`.
    """
    vistas: dict[str, PremissaExposta] = {}
    valores: dict[str, list[str]] = {}
    for r in ordem:
        for id, p in r.resultado.premissas_usadas.items():
            if p.status is StatusPremissa.VALIDADA or not _tocou(id, r.configuracao):
                continue
            valores.setdefault(id, [])
            escrito = escrever(p.valor)
            if escrito not in valores[id]:
                valores[id].append(escrito)
            status = "proposta" if p.status is StatusPremissa.PROPOSTA else "nao_verificada"
            if id in vistas and vistas[id].status == "nao_verificada":
                status = "nao_verificada"
            vistas[id] = PremissaExposta(
                id=id,
                descricao=p.descricao,
                valor="; ".join(valores[id]),
                unidade=p.unidade,
                faixa=p.faixa,
                fonte=p.fonte,
                status=status,
                de_metodo=p.fonte == METODO,
            )
    return list(vistas.values())


def _tocou(id: str, configuracao: Configuracao) -> bool:
    """A premissa entrou na conta desta configuração? As outras que `simular` carimba já são
    carimbadas só quando a modalidade as usa."""
    if id == "sensibilidade_equipamento":
        return configuracao.equipamento is not None
    if id == "preco_energia":
        return configuracao.financeira.preco_energia_reais_mwh is None
    return True


# Texto de valores --------------------------------------------------------------------------


class _Ausente:
    def __repr__(self) -> str:
        return "ausente"


_AUSENTE = _Ausente()


def folhas(configuracao: Configuracao) -> dict[str, Any]:
    """A configuração achatada em caminho pontuado. Bloco vazio não gera folha: a modalidade já
    diz que ele não existe. A lista de reposições fica inteira."""
    achatado: dict[str, Any] = {}

    def descer(valor: Any, prefixo: str) -> None:
        for chave, dentro in valor.items():
            caminho = f"{prefixo}.{chave}" if prefixo else chave
            if isinstance(dentro, dict):
                descer(dentro, caminho)
            elif dentro is None and not prefixo:
                continue
            else:
                achatado[caminho] = dentro

    descer(configuracao.model_dump(mode="json"), "")
    return achatado


def _numero(valor: Any) -> TypeIs[int | float]:
    return isinstance(valor, int | float) and not isinstance(valor, bool)


UNIDADES = (
    ("_reais_mwh", "R$ por MWh"),
    ("_reais_ano", "R$ por ano"),
    ("_reais", "R$"),
    ("_mwh", "MWh"),
    ("_mw", "MW"),
    ("_mva", "MVA"),
    ("_anos", "anos"),
    ("_aa", "ao ano"),
)
"""Unidade pelo sufixo do nome, a convenção do motor. Moeda vai sempre antes do número, como se
escreve em português e como o verificador da prosa lê: "R$ 216 por MWh", nunca "216 R$/MWh"."""


def escrever(valor: Any, campo: str = "") -> str:
    """Valor como texto de relatório, no formato brasileiro: 0.85 vira "0,85", 250000.0 vira
    "250.000", e o campo com sufixo de unidade leva a unidade."""
    if valor is None:
        return "vazio"
    if isinstance(valor, bool):
        return "sim" if valor else "não"
    if isinstance(valor, list):
        if not valor:
            return "nenhuma"
        return "; ".join(
            ", ".join(f"{k} {escrever(v, k)}" for k, v in item.items())
            if isinstance(item, dict)
            else escrever(item)
            for item in valor
        )
    if not _numero(valor):
        return str(valor)
    texto = numero_br(float(valor))
    unidade = next((u for sufixo, u in UNIDADES if campo.endswith(sufixo)), None)
    if unidade and unidade.startswith("R$"):
        return f"R$ {texto}{unidade.removeprefix('R$')}"
    return f"{texto} {unidade}" if unidade else texto


def numero_br(valor: float, casas: int = 6) -> str:
    """Número com milhar em ponto e decimal em vírgula, sem cauda de zeros."""
    inteiro, _, decimal = f"{valor:,.{casas}f}".partition(".")
    decimal = decimal.rstrip("0")
    inteiro = inteiro.replace(",", ".")
    return f"{inteiro},{decimal}" if decimal else inteiro


def alavanca(configuracao: Configuracao) -> str:
    """O que se instalou, em uma linha: "50 MW · 100 MWh · AÇU III", ou a linha que recebe o
    circuito com o ganho de limite, ou os dois na combinada."""
    partes: list[str] = []
    if configuracao.equipamento is not None:
        e = configuracao.equipamento
        partes.append(f"{e.cod_equipamento} · ganho {numero_br(e.ganho_limite_mw)} MW")
    if configuracao.bateria is not None:
        b = configuracao.bateria
        partes.append(
            f"{numero_br(b.potencia_mw)} MW · {numero_br(b.capacidade_mwh)} MWh · {b.subestacao}"
        )
    if configuracao.modalidade is Modalidade.COMBINADA:
        return " + ".join(partes)
    return partes[0]
