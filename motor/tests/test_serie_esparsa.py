"""A série do ONS é esparsa: só a meia hora com corte existe. O motor precisa dar o mesmo
resultado para a mesma história, contada de forma densa ou esparsa.

Os dois defeitos que este arquivo tranca, achados em 2026-09-18 ao rodar contra o Postgres
com o dado de verdade:

1. **O período saía do número de linhas.** Um ano com 3.721 meias horas de corte parecia 2,5
   meses, e a anualização inflava a conta por cinco.
2. **A bateria não descarregava.** Ela só devolve quando o corte cessa, e as meias horas sem
   corte não existiam na série: enchia e travava cheia pelo resto da simulação.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from arco_motor.simular import meses_da_serie, simular
from arco_motor.tipos import Intervalo, SerieRestricao
from sinteticos import config_bateria, config_equipamento, serie_sintetica

INICIO = datetime(2026, 1, 1)


def esparsa(serie: SerieRestricao) -> SerieRestricao:
    """A mesma história sem as meias horas de corte zero, como o ONS entrega."""
    return SerieRestricao(
        restricao_id=serie.restricao_id,
        snapshot_id=serie.snapshot_id,
        intervalos=[i for i in serie.intervalos if i.corte_mw > 0],
        periodo_inicio=serie.intervalos[0].instante,
        periodo_fim=serie.intervalos[-1].instante,
    )


def test_o_periodo_vem_do_declarado_e_nao_do_numero_de_linhas() -> None:
    """Um ano com poucos cortes é um ano, não dois meses."""
    um_ano = SerieRestricao(
        restricao_id="r",
        snapshot_id="s",
        intervalos=[
            Intervalo(instante=INICIO + timedelta(days=30 * k), corte_mw=100.0) for k in range(12)
        ],
        periodo_inicio=INICIO,
        periodo_fim=INICIO + timedelta(days=365),
    )
    assert meses_da_serie(um_ano) == pytest.approx(12.0, abs=0.1)

    sem_declarar = SerieRestricao(restricao_id="r", snapshot_id="s", intervalos=um_ano.intervalos)
    # Sem período declarado o motor usa o que a série cobre: do primeiro ao último corte, que
    # aqui são 330 dias. O que ele nunca faz é contar linhas — 12 linhas de meia hora dariam
    # 0,008 mês, e a anualização multiplicaria a conta por mil e quinhentos.
    assert meses_da_serie(sem_declarar) == pytest.approx(10.8, abs=0.1)
    assert meses_da_serie(sem_declarar) > len(um_ano.intervalos) * 0.5 / 24 / 30.44


def test_energia_cortada_e_a_mesma_densa_ou_esparsa() -> None:
    densa = serie_sintetica()
    assert esparsa(densa).energia_cortada_mwh == pytest.approx(densa.energia_cortada_mwh)


def test_equipamento_recupera_o_mesmo_densa_ou_esparsa() -> None:
    densa = serie_sintetica()
    config = config_equipamento(40.0)
    assert simular(esparsa(densa), config).tecnico.energia_recuperada_mwh == pytest.approx(
        simular(densa, config).tecnico.energia_recuperada_mwh
    )


def test_a_bateria_descarrega_na_folga_que_a_serie_nao_materializa() -> None:
    """É o defeito 2. Na série densa a bateria devolve 34 MWh; na esparsa tem de devolver o mesmo.

    A série sintética tem três blocos de corte separados por 30 meias horas de folga. Na
    versão esparsa essas 30 meias horas somem, e sem olhar o relógio a bateria ficaria cheia
    depois do primeiro bloco: absorveria 20 MWh em vez de 60 e devolveria zero em vez de 34.
    """
    densa = serie_sintetica()
    config = config_bateria(10.0, 20.0)
    resultado_denso = simular(densa, config).tecnico
    resultado_esparso = simular(esparsa(densa), config).tecnico

    assert resultado_denso.energia_absorvida_bateria_mwh == pytest.approx(60.0)
    assert resultado_esparso.energia_absorvida_bateria_mwh == pytest.approx(60.0)
    assert resultado_esparso.energia_devolvida_bateria_mwh == pytest.approx(
        resultado_denso.energia_devolvida_bateria_mwh
    )


def test_uma_folga_longa_esvazia_a_bateria() -> None:
    """Duas meias horas de corte com 23 horas entre elas: dá tempo de devolver tudo."""
    serie = SerieRestricao(
        restricao_id="r",
        snapshot_id="s",
        intervalos=[
            Intervalo(instante=INICIO, corte_mw=1000.0),
            Intervalo(instante=INICIO + timedelta(hours=23, minutes=30), corte_mw=1000.0),
        ],
        periodo_inicio=INICIO,
        periodo_fim=INICIO + timedelta(days=1),
    )
    tecnico = simular(serie, config_bateria(10.0, 5.0)).tecnico
    # Enche no primeiro corte (5 MWh), esvazia nas 23 horas de folga, enche de novo no segundo.
    assert tecnico.energia_absorvida_bateria_mwh == pytest.approx(10.0)
    assert tecnico.energia_devolvida_bateria_mwh == pytest.approx(5.0 * 0.85)


def test_periodo_declarado_nao_pode_deixar_corte_de_fora() -> None:
    with pytest.raises(ValueError, match="periodo_fim antes do último corte"):
        SerieRestricao(
            restricao_id="r",
            snapshot_id="s",
            intervalos=[Intervalo(instante=INICIO + timedelta(days=10), corte_mw=1.0)],
            periodo_inicio=INICIO,
            periodo_fim=INICIO + timedelta(days=5),
        )
