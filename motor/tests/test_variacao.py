"""`montar_variacao` e a faixa permitida: uma alavanca muda, as condições ficam.

Custo unitário `bateria_capex_kwh`: 1.375 R$/kWh na referência, 2.250 no conservador.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from arco_motor.cenarios import CUSTOS_POR_CENARIO
from arco_motor.montar import LinhaDoCadastro
from arco_motor.premissas import PREMISSAS_PADRAO
from arco_motor.tipos import (
    Cenario,
    ConfigBateria,
    ConfigEquipamento,
    ConfigFinanceira,
    Configuracao,
    Modalidade,
    Reposicao,
    TipoIntervencao,
)
from arco_motor.variacao import (
    AlavancaFisica,
    Variacao,
    VariacaoMontada,
    estreitar,
    faixa_permitida,
    montar_variacao,
)
from sinteticos import COD_EQUIPAMENTO, SUBESTACAO

PREMISSAS = PREMISSAS_PADRAO
CADASTRO = [
    LinhaDoCadastro(
        cod_equipamento=COD_EQUIPAMENTO,
        papel="monitorado",
        tensao_kv=500,
        comprimento_km=210.0,
        capacidade_longa_mva=3005.0,
        subestacao_de=SUBESTACAO,
        subestacao_para="SE OUTRA",
    )
]


def _partida(
    modalidade: Modalidade = Modalidade.BATERIA,
    potencia_mw: float = 50.0,
    capacidade_mwh: float = 200.0,
    ganho_limite_mw: float = 40.0,
    capex_reais: float = 275_000_000.0,
    cenario: Cenario = Cenario.REFERENCIA,
) -> Configuracao:
    """Bateria de 50 MW e 4 h, com custo fixo de 7 milhões e uma reposição de 100 milhões."""
    com_bateria = modalidade is not Modalidade.EQUIPAMENTO
    com_circuito = modalidade is not Modalidade.BATERIA
    return Configuracao(
        modalidade=modalidade,
        bateria=ConfigBateria(
            potencia_mw=potencia_mw, capacidade_mwh=capacidade_mwh, subestacao=SUBESTACAO
        )
        if com_bateria
        else None,
        equipamento=ConfigEquipamento(
            tipo=TipoIntervencao.ADICAO_CIRCUITO,
            cod_equipamento=COD_EQUIPAMENTO,
            ganho_limite_mw=ganho_limite_mw,
        )
        if com_circuito
        else None,
        financeira=ConfigFinanceira(
            cenario=cenario,
            taxa_desconto_aa=0.08,
            horizonte_anos=20,
            capex_reais=capex_reais,
            opex_fixo_reais_ano=7_000_000.0,
            opex_variavel_reais_mwh=3.0,
            reposicoes=[Reposicao(ano=10, valor_reais=100_000_000.0)],
            valor_residual_reais=5.0,
            preco_energia_reais_mwh=216.0,
            receitas_adicionais_reais_ano=11.0,
        ),
    )


def _montar(partida: Configuracao, alavanca: AlavancaFisica, valor: float | str) -> VariacaoMontada:
    faixa = faixa_permitida(partida, CADASTRO, PREMISSAS)
    return montar_variacao(partida, Variacao(alavanca=alavanca, valor=valor), PREMISSAS, faixa)


def _variar(partida: Configuracao, alavanca: AlavancaFisica, valor: float | str) -> Configuracao:
    return _montar(partida, alavanca, valor).configuracao


def test_potencia_de_50_para_100_mw_em_4_horas() -> None:
    """A duração fica em 4 h: 100 MW x 4 h = 400 MWh. A capacidade sobe 200 MWh = 200.000 kWh,
    que a 1.375 R$/kWh somam 275.000.000 R$ ao capex: 275 + 275 = 550 milhões. O capex dobrou,
    e custo fixo e reposição dobram junto: 14 milhões por ano e 200 milhões no ano 10."""
    montada = _montar(_partida(), AlavancaFisica.POTENCIA, 100.0)
    variada = montada.configuracao

    assert variada.bateria is not None
    assert variada.bateria.potencia_mw == 100
    assert variada.bateria.capacidade_mwh == pytest.approx(400)
    assert variada.financeira.capex_reais == pytest.approx(550_000_000)
    assert variada.financeira.opex_fixo_reais_ano == pytest.approx(14_000_000)
    assert variada.financeira.reposicoes[0].valor_reais == pytest.approx(200_000_000)
    assert variada.financeira.reposicoes[0].ano == 10
    (conta,) = montada.avisos
    assert conta.codigo == "investimento_por_custo_unitario"
    assert "275.000.000 reais da partida, mais 200.000 kWh vezes 1.375 R$/kWh" in conta.mensagem
    assert "550.000.000 reais" in conta.mensagem


def test_duracao_de_4_para_6_horas() -> None:
    """50 MW x 6 h = 300 MWh: 100.000 kWh a mais, 137.500.000 R$. Capex 412,5 milhões, 1,5 vez o
    da partida, e o custo fixo vai a 10,5 milhões."""
    variada = _variar(_partida(), AlavancaFisica.DURACAO, 6.0)

    assert variada.bateria is not None
    assert (variada.bateria.potencia_mw, variada.bateria.capacidade_mwh) == (50, 300)
    assert variada.financeira.capex_reais == pytest.approx(412_500_000)
    assert variada.financeira.opex_fixo_reais_ano == pytest.approx(10_500_000)


def test_custo_unitario_e_o_do_cenario_da_partida() -> None:
    """Partida no conservador: os 200.000 kWh a mais custam 2.250 R$/kWh, 450 milhões, e não o
    da referência. O cenário vem da partida, não de quem chama."""
    partida = _partida(cenario=Cenario.CONSERVADOR, capex_reais=450_000_000.0)
    variada = _variar(partida, AlavancaFisica.POTENCIA, 100.0)

    assert variada.financeira.capex_reais == pytest.approx(900_000_000)
    assert variada.financeira.cenario is Cenario.CONSERVADOR


def test_na_combinada_a_reposicao_acompanha_a_bateria_e_nao_a_linha() -> None:
    """Combinada de 50 MW e 4 h (275.000.000 R$ de bateria) mais 519.087.030 R$ de linha: capex
    de 794.087.030. Potência a 400 MW, 8 vezes: 1.400.000 kWh a mais, 1.925.000.000 R$; capex de
    2.719.087.030. O custo fixo acompanha o capex inteiro, 7 M x 2.719.087.030 / 794.087.030 =
    23.969.127 R$. A reposição, que é de módulo de bateria, acompanha a bateria: 275 M viram
    2.200 M, 8 vezes, e os 100 M da reposição viram 800 M."""
    partida = _partida(Modalidade.COMBINADA, capex_reais=794_087_030.0)
    variada = _variar(partida, AlavancaFisica.POTENCIA, 400.0)

    assert variada.financeira.capex_reais == pytest.approx(2_719_087_030)
    assert variada.financeira.opex_fixo_reais_ano == pytest.approx(
        7_000_000 * 2_719_087_030 / 794_087_030
    )
    assert variada.financeira.reposicoes[0].valor_reais == pytest.approx(800_000_000)


def test_subestacao_nao_muda_o_custo() -> None:
    partida = _partida()
    montada = _montar(partida, AlavancaFisica.SUBESTACAO, "SE OUTRA")

    assert montada.configuracao.bateria is not None
    assert montada.configuracao.bateria.subestacao == "SE OUTRA"
    assert montada.configuracao.financeira == partida.financeira
    assert montada.avisos == []


def test_ganho_de_limite_nao_muda_o_custo() -> None:
    """O circuito custa por km, não por MW de ganho."""
    partida = _partida(Modalidade.COMBINADA)
    variada = _variar(partida, AlavancaFisica.GANHO, 60.0)

    assert variada.equipamento is not None
    assert variada.equipamento.ganho_limite_mw == 60
    assert variada.financeira == partida.financeira
    assert variada.bateria == partida.bateria


def test_potencia_de_partida_fora_da_duracao_avisa() -> None:
    """Partida de 1 h: variar a potência mantém 1 h, e o custo por kWh de 4 h é extrapolado."""
    montada = _montar(
        _partida(capacidade_mwh=50.0, capex_reais=100_000_000.0), AlavancaFisica.POTENCIA, 100.0
    )

    assert [a.codigo for a in montada.avisos] == [
        "investimento_por_custo_unitario",
        "duracao_fora_da_calibracao",
    ]


@pytest.mark.parametrize(
    ("alavanca", "valor", "limite"),
    [
        (AlavancaFisica.POTENCIA, 401.0, "de 25 a 400 MW"),
        (AlavancaFisica.POTENCIA, 20.0, "de 25 a 400 MW"),
        (AlavancaFisica.DURACAO, 7.0, "de 2 a 6 h"),
        (AlavancaFisica.DURACAO, 1.5, "de 2 a 6 h"),
    ],
)
def test_fora_da_faixa_recusa_com_o_limite(
    alavanca: AlavancaFisica, valor: float, limite: str
) -> None:
    with pytest.raises(ValueError, match=limite):
        _variar(_partida(), alavanca, valor)


def test_subestacao_que_nao_e_terminal_recusa() -> None:
    with pytest.raises(ValueError, match="não é terminal"):
        _variar(_partida(), AlavancaFisica.SUBESTACAO, "SE DE OUTRA RESTRIÇÃO")


def test_alavanca_que_a_modalidade_nao_tem_recusa() -> None:
    with pytest.raises(ValueError, match="não tem circuito"):
        _variar(_partida(Modalidade.BATERIA), AlavancaFisica.GANHO, 60.0)
    with pytest.raises(ValueError, match="não tem bateria"):
        _variar(_partida(Modalidade.EQUIPAMENTO), AlavancaFisica.POTENCIA, 60.0)


def test_partida_de_graca_nao_varia_o_tamanho() -> None:
    """Sem investimento na partida não há custo que acompanhe o tamanho: variar daria ganho
    falso, porque o que se somaria seria só a diferença."""
    with pytest.raises(ValueError, match="investimento zero"):
        _variar(_partida(capex_reais=0.0), AlavancaFisica.POTENCIA, 100.0)


def test_reduzir_mais_do_que_a_partida_pagou_recusa() -> None:
    """Partida de 1.000 R$ para 200 MWh: tirar 100 MWh tira 137,5 milhões, e o capex ficaria
    negativo."""
    with pytest.raises(ValueError, match="investimento ficaria"):
        _variar(_partida(capex_reais=1000.0), AlavancaFisica.POTENCIA, 25.0)


def test_faixa_da_potencia_para_no_teto_do_cadastro() -> None:
    """Partida de 500 MW: 8 vezes seriam 4.000 MW, e a linha aguenta 3.005 MVA, lidos como MW
    a fator de potência 1, vezes `teto_alavanca_capacidade` = 1."""
    faixa = faixa_permitida(_partida(potencia_mw=500, capacidade_mwh=2000), CADASTRO, PREMISSAS)

    assert faixa.potencia_mw is not None
    assert (faixa.potencia_mw.minimo, faixa.potencia_mw.maximo) == (250, 3005)
    assert faixa.subestacoes == ["SE OUTRA", SUBESTACAO]
    assert faixa.ganho_limite_mw is None, "bateria só não tem circuito"


def test_partida_acima_do_teto_nao_varia_a_potencia() -> None:
    """7.000 MW com teto de 3.005: a faixa seria de 3.500 a 3.005, vazia. Sem faixa, com aviso,
    em vez de um ponto abaixo da metade da partida."""
    faixa = faixa_permitida(_partida(potencia_mw=7000, capacidade_mwh=28000), CADASTRO, PREMISSAS)

    assert faixa.potencia_mw is None
    assert [a.codigo for a in faixa.avisos] == ["potencia_da_partida_acima_do_teto"]
    assert faixa.duracao_horas is not None, "a duração continua variando"


def test_ganho_vai_da_partida_a_capacidade_da_linha() -> None:
    faixa = faixa_permitida(_partida(Modalidade.EQUIPAMENTO), CADASTRO, PREMISSAS)

    assert faixa.ganho_limite_mw is not None
    assert (faixa.ganho_limite_mw.minimo, faixa.ganho_limite_mw.maximo) == (40, 3005)
    assert faixa.potencia_mw is None


@pytest.mark.parametrize("capacidade", [None, 0.0])
def test_sem_capacidade_no_cadastro_o_ganho_nao_varia(capacidade: float | None) -> None:
    sem_capacidade = [CADASTRO[0].model_copy(update={"capacidade_longa_mva": capacidade})]
    faixa = faixa_permitida(_partida(Modalidade.EQUIPAMENTO), sem_capacidade, PREMISSAS)

    assert faixa.ganho_limite_mw is not None
    assert (faixa.ganho_limite_mw.minimo, faixa.ganho_limite_mw.maximo) == (40, 40)
    assert [a.codigo for a in faixa.avisos] == ["ganho_sem_capacidade_no_cadastro"]


def test_estreitar_deixa_so_as_alavancas_pedidas() -> None:
    """ "Varia só a potência": a duração e a subestação saem da faixa, e a variação delas passa a
    ser recusada como alavanca que a exploração não tem."""
    partida = _partida()
    faixa = estreitar(faixa_permitida(partida, CADASTRO, PREMISSAS), [AlavancaFisica.POTENCIA])

    assert faixa.potencia_mw is not None
    assert (faixa.duracao_horas, faixa.subestacoes) == (None, None)
    with pytest.raises(ValueError, match=r"não varia essa alavanca; varia bateria\.potencia_mw"):
        montar_variacao(
            partida, Variacao(alavanca=AlavancaFisica.DURACAO, valor=6), PREMISSAS, faixa
        )
    with pytest.raises(ValueError, match="não usa"):
        estreitar(faixa_permitida(partida, CADASTRO, PREMISSAS), [AlavancaFisica.GANHO])


CONDICOES = (
    "cenario",
    "taxa_desconto_aa",
    "horizonte_anos",
    "opex_variavel_reais_mwh",
    "valor_residual_reais",
    "preco_energia_reais_mwh",
    "receitas_adicionais_reais_ano",
)
"""O que nenhuma variação muda: as condições da comparação e os campos que não acompanham o
tamanho. O custo unitário nem está na configuração: vem do catálogo, pelo cenário da partida."""


@st.composite
def variacoes(draw: st.DrawFn) -> tuple[Configuracao, Variacao]:
    """Partidas com cenário, taxa, preço (vazio inclusive), horizonte e demais condições
    sorteados, para um código que trocasse qualquer uma delas por um padrão não passar."""
    cenario = draw(st.sampled_from(list(Cenario)))
    modalidade = draw(st.sampled_from([Modalidade.BATERIA, Modalidade.COMBINADA]))
    potencia = draw(st.floats(min_value=1, max_value=300))
    horas = draw(st.floats(min_value=2, max_value=6))
    por_kwh = float(CUSTOS_POR_CENARIO[cenario].valor("bateria_capex_kwh"))
    # A partida paga ao menos a própria bateria pelo custo unitário: reduzir até a metade
    # nunca leva o capex a zero, e o caso de capex insuficiente tem teste próprio.
    capex = potencia * horas * 1000 * por_kwh * draw(st.floats(min_value=1, max_value=3))
    partida = _partida(
        modalidade,
        potencia_mw=potencia,
        capacidade_mwh=potencia * horas,
        ganho_limite_mw=draw(st.floats(min_value=0, max_value=1000)),
        capex_reais=capex,
        cenario=cenario,
    )
    financeira = partida.financeira.model_copy(
        update={
            "taxa_desconto_aa": draw(st.floats(min_value=0, max_value=0.3)),
            "horizonte_anos": draw(st.integers(min_value=1, max_value=40)),
            "preco_energia_reais_mwh": draw(st.none() | st.floats(min_value=0, max_value=2000)),
            "valor_residual_reais": draw(st.floats(min_value=0, max_value=1e9)),
            "receitas_adicionais_reais_ano": draw(st.floats(min_value=0, max_value=1e8)),
            "opex_variavel_reais_mwh": draw(st.floats(min_value=0, max_value=100)),
        }
    )
    partida = partida.model_copy(update={"financeira": financeira})
    faixa = faixa_permitida(partida, CADASTRO, PREMISSAS)
    alavancas = [AlavancaFisica.POTENCIA, AlavancaFisica.DURACAO, AlavancaFisica.SUBESTACAO]
    if modalidade is Modalidade.COMBINADA:
        alavancas.append(AlavancaFisica.GANHO)
    alavanca = draw(st.sampled_from(alavancas))
    if alavanca is AlavancaFisica.SUBESTACAO:
        valor: float | str = draw(st.sampled_from(faixa.subestacoes or []))
    else:
        limites = {
            AlavancaFisica.POTENCIA: faixa.potencia_mw,
            AlavancaFisica.DURACAO: faixa.duracao_horas,
            AlavancaFisica.GANHO: faixa.ganho_limite_mw,
        }[alavanca]
        assert limites is not None
        valor = draw(st.floats(min_value=limites.minimo, max_value=limites.maximo))
    return partida, Variacao(alavanca=alavanca, valor=valor)


@settings(max_examples=300, deadline=None)
@given(caso=variacoes())
def test_variacao_nunca_muda_as_condicoes_nem_outra_alavanca(
    caso: tuple[Configuracao, Variacao],
) -> None:
    """Preço, taxa, cenário e o resto das condições ficam os da partida; da alavanca física só
    muda a pedida, com a capacidade junto quando a pedida é potência ou duração; e o capex é o
    da partida mais a diferença de kWh vezes o custo do cenário **da partida**."""
    partida, variacao = caso
    faixa = faixa_permitida(partida, CADASTRO, PREMISSAS)
    variada = montar_variacao(partida, variacao, PREMISSAS, faixa).configuracao

    for campo in CONDICOES:
        assert getattr(variada.financeira, campo) == getattr(partida.financeira, campo), campo
    assert variada.modalidade is partida.modalidade
    assert variada.bateria is not None and partida.bateria is not None

    mexidos = {
        AlavancaFisica.POTENCIA: {"potencia_mw", "capacidade_mwh"},
        AlavancaFisica.DURACAO: {"capacidade_mwh"},
        AlavancaFisica.SUBESTACAO: {"subestacao"},
        AlavancaFisica.GANHO: set(),
    }[variacao.alavanca]
    antes, depois = partida.bateria.model_dump(), variada.bateria.model_dump()
    assert {c for c in antes if antes[c] != depois[c]} <= mexidos
    if partida.equipamento is not None:
        assert variada.equipamento is not None
        antes, depois = partida.equipamento.model_dump(), variada.equipamento.model_dump()
        assert {c for c in antes if antes[c] != depois[c]} <= {"ganho_limite_mw"}

    por_kwh = float(CUSTOS_POR_CENARIO[partida.financeira.cenario].valor("bateria_capex_kwh"))
    delta_kwh = (variada.bateria.capacidade_mwh - partida.bateria.capacidade_mwh) * 1000
    assert variada.financeira.capex_reais == pytest.approx(
        partida.financeira.capex_reais + delta_kwh * por_kwh
    )
    if variacao.alavanca in (AlavancaFisica.SUBESTACAO, AlavancaFisica.GANHO):
        assert variada.financeira == partida.financeira
