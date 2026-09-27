"""Correção pela duração do corte dentro da meia hora. Premissa `correcao_minutos`, ligada.

De out/2024 a set/2025, entre 46% e 76% dos comandos eólicos de cada mês duraram menos de
30 minutos. A energia apurada é a média dos 30, então a média subestima o pico e superestima
o que cada alavanca captura.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from arco_motor.premissas import PREMISSAS_PADRAO
from arco_motor.simular import simular
from arco_motor.tipos import Intervalo, SerieRestricao
from sinteticos import config_bateria, config_equipamento


def serie_de_um_intervalo(corte_mw: float, minutos_cnf: int | None) -> SerieRestricao:
    return SerieRestricao(
        restricao_id="um-intervalo",
        snapshot_id="teste",
        intervalos=[
            Intervalo(instante=datetime(2026, 1, 1), corte_mw=corte_mw, minutos_cnf=minutos_cnf)
        ],
    )


def test_caso_de_ouro_correcao_de_minutos() -> None:
    """100 MW médios em 10 minutos de corte, com ganho de limite de 200 MW.

    A meia hora apurou 100 MW médios, ou seja 50 MWh. Se o corte durou 10 minutos, a potência
    naqueles minutos foi de 100 x 30 / 10 = **300 MW**. Um ganho de 200 MW captura 200 dos
    300, e só durante aqueles 10 minutos: 200 MW x 10/60 h = **33,33 MWh**.

    Sem a correção, a conta veria 100 MW médios, o ganho de 200 cobriria tudo, e o resultado
    seria os 50 MWh inteiros — 50% a mais do que a física permite.
    """
    serie = serie_de_um_intervalo(100.0, minutos_cnf=10)
    assert serie.energia_cortada_mwh == pytest.approx(50.0)

    com = simular(serie, config_equipamento(200.0))
    assert com.tecnico.energia_evitada_equipamento_mwh == pytest.approx(100.0 / 3.0)

    sem = simular(serie, config_equipamento(200.0), PREMISSAS_PADRAO.com(correcao_minutos=False))
    assert sem.tecnico.energia_evitada_equipamento_mwh == pytest.approx(50.0)


def test_correcao_nunca_muda_a_energia_cortada() -> None:
    """A correção mexe na potência que a alavanca captura, nunca na apuração oficial."""
    for minutos in (None, 5, 10, 30):
        serie = serie_de_um_intervalo(100.0, minutos_cnf=minutos)
        resultado = simular(serie, config_equipamento(200.0))
        assert resultado.tecnico.energia_cortada_mwh == pytest.approx(50.0)
        assert resultado.tecnico.energia_evitada_equipamento_mwh <= 50.0 + 1e-9


def test_campo_vazio_e_meia_hora_cheia_nao_corrigem() -> None:
    """Vazio é dado que não veio, não afirmação de que o corte durou os 30 minutos."""
    vazio = simular(serie_de_um_intervalo(100.0, None), config_equipamento(200.0))
    cheia = simular(serie_de_um_intervalo(100.0, 30), config_equipamento(200.0))
    assert vazio.tecnico.energia_evitada_equipamento_mwh == pytest.approx(50.0)
    assert cheia.tecnico.energia_evitada_equipamento_mwh == pytest.approx(50.0)


def test_aviso_quando_a_correcao_esta_ligada_e_nao_ha_minutos() -> None:
    resultado = simular(serie_de_um_intervalo(100.0, None), config_equipamento(200.0))
    codigos = [aviso.codigo for aviso in resultado.avisos]
    assert "correcao_minutos_sem_dado" in codigos


def test_a_bateria_tambem_enfrenta_o_pico() -> None:
    """Bateria de 50 MW contra 100 MW médios em 10 minutos, ou seja 300 MW de pico.

    Ela captura 50 dos 300 MW, durante 10 minutos: 50 x 10/60 = 8,33 MWh. Sem a correção
    ela veria 100 MW médios, capturaria 50 por meia hora e absorveria 25 MWh.
    """
    serie = serie_de_um_intervalo(100.0, minutos_cnf=10)
    com = simular(serie, config_bateria(50.0, 1000.0))
    assert com.tecnico.energia_absorvida_bateria_mwh == pytest.approx(50.0 / 6.0)

    sem = simular(serie, config_bateria(50.0, 1000.0), PREMISSAS_PADRAO.com(correcao_minutos=False))
    assert sem.tecnico.energia_absorvida_bateria_mwh == pytest.approx(25.0)
