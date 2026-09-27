"""Diagnósticos do explorador: saturação da bateria, corte residual e cruzamentos.

A série sintética de dois dias corta 100 MW das 20h às 5h: 36 meias horas de 50 MWh, em três
episódios — 0h às 5h do dia 1 (10 meias horas), 20h do dia 1 às 5h do dia 2 (18) e 20h às 24h
do dia 2 (8) —, 1.800 MWh ao todo.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from arco_motor.bateria import teto_mwh
from arco_motor.diagnosticos import cruzamentos
from arco_motor.relatorio import RevisaoCoberta
from arco_motor.simular import simular
from arco_motor.tipos import Configuracao, Intervalo, SerieRestricao
from sinteticos import (
    INICIO,
    config_bateria,
    config_equipamento,
    configs_combinadas,
    serie_sintetica,
    series,
)


def test_bateria_pequena_cheia_em_tres_quartos_das_meias_horas() -> None:
    """10 MW e 20 MWh: absorve 5 MWh por meia hora e enche na 4ª de cada episódio. Ficam
    cheias as meias horas 4 em diante: 7 + 15 + 5 = 27 de 36, 0,75.

    Entre um episódio e outro há 15 horas sem corte, que a descarregam de 5 em 5 MWh: os três
    episódios começam vazios."""
    diagnosticos = simular(serie_sintetica(), config_bateria(10.0, 20.0)).diagnosticos

    assert diagnosticos is not None and diagnosticos.saturacao is not None
    saturacao = diagnosticos.saturacao
    assert (saturacao.meias_horas_com_corte, saturacao.meias_horas_cheia) == (36, 27)
    assert saturacao.fracao_cheia == pytest.approx(0.75)
    assert (saturacao.episodios, saturacao.episodios_comecaram_vazia) == (3, 3)
    assert saturacao.episodios_comecaram_com_carga == 0


def test_corte_residual_por_hora_do_dia() -> None:
    """Cada hora com corte (0 a 4 e 20 a 23) tem 4 meias horas de 50 MWh nos dois dias: 200
    MWh. A bateria de 10 MW e 20 MWh tira 5 MWh de cada uma das 4 primeiras meias horas de cada
    episódio: 10 MWh das horas 0 e 1 (episódio 1), e 20 MWh das horas 20 e 21 (episódios 2 e
    3). Sobra 1.800 - 60 = 1.740 MWh."""
    diagnosticos = simular(serie_sintetica(), config_bateria(10.0, 20.0)).diagnosticos

    assert diagnosticos is not None
    residual = diagnosticos.corte_residual
    assert residual.energia_mwh == pytest.approx(1740.0)
    esperado = [0.0] * 24
    for hora in (2, 3, 4, 22, 23):
        esperado[hora] = 200.0
    esperado[0] = esperado[1] = 190.0
    esperado[20] = esperado[21] = 180.0
    assert residual.por_hora_do_dia_mwh == pytest.approx(esperado)


def test_episodio_que_comeca_com_carga_do_anterior() -> None:
    """Série esparsa: 100 MW às 0h e às 0h30, e de novo à 1h30. A bateria de 10 MW e 20 MWh
    guarda 10 MWh nas duas primeiras; na folga de meia hora entre 1h e 1h30 devolve 5, e o
    segundo episódio começa com 5 MWh. Falta tempo para descarregar."""
    serie = SerieRestricao(
        restricao_id="curta",
        snapshot_id="teste",
        intervalos=[
            Intervalo(instante=INICIO + timedelta(minutes=minutos), corte_mw=100.0)
            for minutos in (0, 30, 90)
        ],
    )

    diagnosticos = simular(serie, config_bateria(10.0, 20.0)).diagnosticos

    assert diagnosticos is not None and diagnosticos.saturacao is not None
    saturacao = diagnosticos.saturacao
    assert (saturacao.episodios, saturacao.episodios_comecaram_vazia) == (2, 1)
    assert saturacao.episodios_comecaram_com_carga == 1
    assert saturacao.meias_horas_cheia == 0


def test_sem_bateria_nao_ha_saturacao() -> None:
    """Circuito de 40 MW: evita 40 dos 100 MW em cada meia hora, e sobram 60 MW x 0,5 h x 36 =
    1.080 MWh."""
    diagnosticos = simular(serie_sintetica(), config_equipamento(40.0)).diagnosticos

    assert diagnosticos is not None
    assert diagnosticos.saturacao is None
    assert diagnosticos.corte_residual.energia_mwh == pytest.approx(1080.0)


@settings(max_examples=50, deadline=None)
@given(serie=series(), config=configs_combinadas())
def test_corte_residual_fecha_com_cortado_menos_recuperado(
    serie: SerieRestricao, config: Configuracao
) -> None:
    resultado = simular(serie, config)
    diagnosticos = resultado.diagnosticos
    tecnico = resultado.tecnico

    assert diagnosticos is not None
    residual = diagnosticos.corte_residual
    esperado = tecnico.energia_cortada_mwh - tecnico.energia_recuperada_mwh
    assert residual.energia_mwh == pytest.approx(esperado, abs=1e-6)
    assert sum(residual.por_hora_do_dia_mwh) == pytest.approx(residual.energia_mwh, abs=1e-6)
    assert diagnosticos.saturacao is not None
    saturacao = diagnosticos.saturacao
    assert 0 <= saturacao.meias_horas_cheia <= saturacao.meias_horas_com_corte
    assert saturacao.episodios_comecaram_vazia + saturacao.episodios_comecaram_com_carga == (
        saturacao.episodios
    )


def _revisao(id: int, potencia_mw: float, payback: float | None, tir: float | None):  # type: ignore[no-untyped-def]
    """Uma revisão de bateria com payback e TIR postos à mão; o horizonte é 15 anos e a taxa,
    8 % (`sinteticos.financeira_padrao`)."""
    config = config_bateria(potencia_mw, potencia_mw * 4)
    resultado = simular(serie_sintetica(), config)
    financeiro = resultado.financeiro.model_copy(
        update={"payback_simples_anos": payback, "tir_aa": tir}
    )
    return RevisaoCoberta(
        revisao_id=id,
        posicao=id,
        criada_em=datetime(2026, 9, 23),
        configuracao=config,
        resultado=resultado.model_copy(update={"financeiro": financeiro}),
        o_que_mudou="",
    )


def test_cruzamento_fica_entre_as_duas_revisoes_vizinhas() -> None:
    """Gravadas fora de ordem de tamanho: 150, 50 e 100 MW. Payback de 12, 25 e 18 anos contra
    o horizonte de 15: cabe só na de 150, e o par é 100 (fora) e 150 (dentro). TIR de 9 %, 3 % e
    6 % contra a taxa de 8 %: o mesmo par."""
    revisoes = [
        _revisao(1, 150.0, 12.0, 0.09),
        _revisao(2, 50.0, 25.0, 0.03),
        _revisao(3, 100.0, 18.0, 0.06),
    ]

    resultado = cruzamentos(revisoes)

    assert resultado.payback_no_horizonte is not None
    assert (
        resultado.payback_no_horizonte.antes_revisao_id,
        resultado.payback_no_horizonte.depois_revisao_id,
    ) == (3, 1)
    assert resultado.tir_acima_da_taxa is not None
    assert resultado.tir_acima_da_taxa.depois_revisao_id == 1


@pytest.mark.parametrize("payback", [None, 12.0])
def test_sem_cruzamento_quando_nenhuma_muda_de_lado(payback: float | None) -> None:
    """Todas fora do horizonte, ou todas dentro: nenhuma revisão cruza."""
    revisoes = [_revisao(1, 50.0, payback, None), _revisao(2, 100.0, payback, None)]

    resultado = cruzamentos(revisoes)

    assert resultado.payback_no_horizonte is None
    assert resultado.tir_acima_da_taxa is None


@st.composite
def esparsas_com_bateria(draw: st.DrawFn) -> tuple[SerieRestricao, Configuracao]:
    """Série esparsa (folgas de 0 a 5 h entre carimbos), com minutos de corte, e bateria com
    degradação, carga mínima e inicial sorteadas: os caminhos em que "cheia" e a carga do início
    do episódio poderiam errar."""
    n = draw(st.integers(min_value=1, max_value=60))
    folgas = draw(st.lists(st.integers(min_value=0, max_value=10), min_size=n, max_size=n))
    instante = INICIO
    intervalos = []
    for folga in folgas:
        instante += timedelta(minutes=30 * (1 + folga))
        intervalos.append(
            Intervalo(
                instante=instante,
                corte_mw=draw(st.floats(min_value=0, max_value=500)),
                minutos_cnf=draw(st.none() | st.integers(min_value=1, max_value=30)),
            )
        )
    soc_min = draw(st.floats(min_value=0, max_value=0.3))
    config = config_bateria(
        draw(st.floats(min_value=1, max_value=200)), draw(st.floats(min_value=1, max_value=800))
    )
    assert config.bateria is not None
    config.bateria.soc_min = soc_min
    config.bateria.soc_max = draw(st.floats(min_value=soc_min, max_value=1))
    config.bateria.soc_inicial = soc_min
    config.bateria.degradacao_por_ciclo = draw(st.floats(min_value=0, max_value=0.01))
    serie = SerieRestricao(restricao_id="h", snapshot_id="teste", intervalos=intervalos)
    return serie, Configuracao.model_validate(config.model_dump())


@settings(max_examples=200, deadline=None)
@given(caso=esparsas_com_bateria())
def test_saturacao_bate_com_o_despacho(caso: tuple[SerieRestricao, Configuracao]) -> None:
    """Duas propriedades contra o despacho, calculadas por fora do diagnóstico:

    - a carga com que um episódio começa é a do fim da meia hora anterior menos o que a folga
      entre os carimbos descarregou (potência efetiva vezes a folga, até o piso), e a contagem
      de episódios que começam vazios bate com ela;
    - meia hora cheia seguida de outra, sem folga e com corte, não absorve nada: "cheia" é
      mesmo sem espaço, com a degradação acumulada."""
    serie, config = caso
    resultado = simular(serie, config)
    bateria, tecnico = config.bateria, resultado.tecnico
    assert bateria is not None and resultado.diagnosticos is not None
    saturacao = resultado.diagnosticos.saturacao
    assert saturacao is not None
    piso = bateria.soc_min * bateria.capacidade_mwh
    potencia = bateria.potencia_mw * bateria.disponibilidade
    meia_hora = timedelta(minutes=30)

    vazias = episodios = 0
    acumulado = 0.0
    cheia_antes = False
    for k, intervalo in enumerate(serie.intervalos):
        chega = tecnico.cortado_mw[k] - tecnico.evitado_equipamento_mw[k] > 0
        seguida = k > 0 and intervalo.instante - serie.intervalos[k - 1].instante == meia_hora
        if chega and cheia_antes and seguida:
            assert tecnico.absorvido_bateria_mw[k] <= 1e-9
        if chega and not (seguida and tecnico.cortado_mw[k - 1] > 0):
            episodios += 1
            anterior = (
                tecnico.soc_mwh[k - 1] if k > 0 else bateria.carga_inicial * bateria.capacidade_mwh
            )
            folga = (
                (intervalo.instante - serie.intervalos[k - 1].instante - meia_hora).total_seconds()
                / 3600
                if k > 0
                else 0.0
            )
            carga = anterior - min(potencia * folga, max(anterior - piso, 0.0))
            vazias += carga <= piso + 1e-6
        cheia_antes = chega and tecnico.soc_mwh[k] >= teto_mwh(bateria, acumulado) - 1e-6
        acumulado += tecnico.absorvido_bateria_mw[k] * 0.5

    assert (saturacao.episodios, saturacao.episodios_comecaram_vazia) == (episodios, vazias)
