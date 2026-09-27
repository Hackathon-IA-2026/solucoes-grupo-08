"""Séries e configurações sintéticas para testes: curtas, calculáveis à mão."""

from __future__ import annotations

from datetime import datetime, timedelta

from hypothesis import strategies as st

from arco_motor.tipos import (
    Cenario,
    ConfigBateria,
    ConfigEquipamento,
    ConfigFinanceira,
    Configuracao,
    Intervalo,
    Modalidade,
    SerieRestricao,
    TipoIntervencao,
)

INICIO = datetime(2026, 1, 1)


def serie_sintetica(dias: int = 2, corte_noturno_mw: float = 100.0) -> SerieRestricao:
    """Corte constante das 20h às 5h, zero no resto do dia.

    Com 2 dias e 100 MW: 18 horas de corte (5 h + 4 h por dia) = 1.800 MWh.
    """
    intervalos = []
    for k in range(dias * 48):
        instante = INICIO + timedelta(minutes=30 * k)
        noite = instante.hour >= 20 or instante.hour < 5
        intervalos.append(Intervalo(instante=instante, corte_mw=corte_noturno_mw if noite else 0.0))
    return SerieRestricao(restricao_id="sintetico", snapshot_id="teste", intervalos=intervalos)


def financeira_padrao(capex_reais: float = 1_000_000.0) -> ConfigFinanceira:
    return ConfigFinanceira(
        cenario=Cenario.REFERENCIA,
        taxa_desconto_aa=0.08,
        horizonte_anos=15,
        capex_reais=capex_reais,
        preco_energia_reais_mwh=150.0,
    )


COD_EQUIPAMENTO = "LT-TESTE-1"
"""Nas séries sintéticas o código não é conferido: quem confere contra o cadastro é a rota."""

SUBESTACAO = "SE TESTE"


def config_equipamento(ganho_limite_mw: float) -> Configuracao:
    return Configuracao(
        modalidade=Modalidade.EQUIPAMENTO,
        equipamento=ConfigEquipamento(
            tipo=TipoIntervencao.ADICAO_CIRCUITO,
            cod_equipamento=COD_EQUIPAMENTO,
            ganho_limite_mw=ganho_limite_mw,
        ),
        financeira=financeira_padrao(),
    )


def config_bateria(potencia_mw: float, capacidade_mwh: float) -> Configuracao:
    return Configuracao(
        modalidade=Modalidade.BATERIA,
        bateria=ConfigBateria(
            potencia_mw=potencia_mw, capacidade_mwh=capacidade_mwh, subestacao=SUBESTACAO
        ),
        financeira=financeira_padrao(),
    )


def config_combinada(
    ganho_limite_mw: float, potencia_mw: float, capacidade_mwh: float
) -> Configuracao:
    return Configuracao(
        modalidade=Modalidade.COMBINADA,
        equipamento=ConfigEquipamento(
            tipo=TipoIntervencao.ADICAO_CIRCUITO,
            cod_equipamento=COD_EQUIPAMENTO,
            ganho_limite_mw=ganho_limite_mw,
        ),
        bateria=ConfigBateria(
            potencia_mw=potencia_mw, capacidade_mwh=capacidade_mwh, subestacao=SUBESTACAO
        ),
        financeira=financeira_padrao(),
    )


@st.composite
def series(draw: st.DrawFn, max_intervalos: int = 96) -> SerieRestricao:
    """Série aleatória de até `max_intervalos` meias horas, cortes entre 0 e 2.000 MW."""
    n = draw(st.integers(min_value=1, max_value=max_intervalos))
    cortes = draw(
        st.lists(
            st.floats(min_value=0, max_value=2000, allow_nan=False, allow_infinity=False),
            min_size=n,
            max_size=n,
        )
    )
    intervalos = [
        Intervalo(instante=INICIO + timedelta(minutes=30 * k), corte_mw=corte)
        for k, corte in enumerate(cortes)
    ]
    return SerieRestricao(restricao_id="hipotese", snapshot_id="teste", intervalos=intervalos)


@st.composite
def configs_combinadas(draw: st.DrawFn) -> Configuracao:
    return config_combinada(
        ganho_limite_mw=draw(st.floats(min_value=0, max_value=1500, allow_nan=False)),
        potencia_mw=draw(st.floats(min_value=0.1, max_value=500, allow_nan=False)),
        capacidade_mwh=draw(st.floats(min_value=0.1, max_value=4000, allow_nan=False)),
    )
