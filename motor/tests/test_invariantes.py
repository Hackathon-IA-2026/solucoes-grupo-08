"""Invariantes do motor e casos de ouro, implementados na feature 01.

Os marcadores xfail saíram quando o motor passou a calcular. Nunca afrouxe um invariante:
se um deles falha, o erro está no cálculo, não no teste.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings

from arco_motor import METODO_VERSAO
from arco_motor.premissas import PREMISSAS_PADRAO, StatusPremissa
from arco_motor.simular import simular
from arco_motor.tipos import PASSO_HORAS, SerieRestricao
from sinteticos import (
    config_bateria,
    config_combinada,
    config_equipamento,
    configs_combinadas,
    serie_sintetica,
    series,
)

TOLERANCIA = 1e-6


@settings(max_examples=50, deadline=None)
@given(serie=series(), config=configs_combinadas())
def test_evitado_nunca_excede_cortado_em_nenhum_intervalo(serie: SerieRestricao, config) -> None:
    resultado = simular(serie, config)
    tecnico = resultado.tecnico
    for cortado, equipamento, bateria in zip(
        tecnico.cortado_mw,
        tecnico.evitado_equipamento_mw,
        tecnico.absorvido_bateria_mw,
        strict=True,
    ):
        assert equipamento + bateria <= cortado + TOLERANCIA


@settings(max_examples=50, deadline=None)
@given(serie=series(), config=configs_combinadas())
def test_energia_recuperada_total_limitada_pela_cortada(serie: SerieRestricao, config) -> None:
    resultado = simular(serie, config)
    assert resultado.tecnico.energia_recuperada_mwh <= serie.energia_cortada_mwh + TOLERANCIA
    assert 0 <= resultado.tecnico.fracao_recuperada <= 1


@settings(max_examples=50, deadline=None)
@given(serie=series(), config=configs_combinadas())
def test_estado_de_carga_dentro_dos_limites(serie: SerieRestricao, config) -> None:
    resultado = simular(serie, config)
    bateria = config.bateria
    assert bateria is not None
    piso = bateria.soc_min * bateria.capacidade_mwh - TOLERANCIA
    teto = bateria.soc_max * bateria.capacidade_mwh + TOLERANCIA
    assert all(piso <= soc <= teto for soc in resultado.tecnico.soc_mwh)


def test_mais_limite_nunca_recupera_menos() -> None:
    serie = serie_sintetica()
    anteriores = -1.0
    for ganho in (0.0, 25.0, 50.0, 100.0, 200.0):
        recuperado = simular(serie, config_equipamento(ganho)).tecnico.energia_recuperada_mwh
        assert recuperado >= anteriores - TOLERANCIA
        anteriores = recuperado


def test_combinada_nao_recupera_menos_que_equipamento_sozinho() -> None:
    serie = serie_sintetica()
    so_equipamento = simular(serie, config_equipamento(50.0)).tecnico.energia_recuperada_mwh
    combinada = simular(serie, config_combinada(50.0, 20.0, 80.0)).tecnico.energia_recuperada_mwh
    assert combinada >= so_equipamento - TOLERANCIA


def test_caso_de_ouro_aumento_de_limite() -> None:
    """Série sintética: 100 MW cortados por 18 h em 2 dias = 1.800 MWh.

    Com +40 MW de limite e sensibilidade 1, cada meia hora de corte evita 40 MW:
    36 intervalos x 40 MW x 0,5 h = 720 MWh, fração 0,4.
    """
    serie = serie_sintetica()
    assert serie.energia_cortada_mwh == pytest.approx(1800.0)
    resultado = simular(serie, config_equipamento(40.0))
    assert resultado.tecnico.energia_recuperada_mwh == pytest.approx(36 * 40 * PASSO_HORAS)
    assert resultado.tecnico.fracao_recuperada == pytest.approx(0.4)


def test_caso_de_ouro_bateria_pequena() -> None:
    """Bateria de 10 MW e 20 MWh, eficiência 0,85, sobre a série sintética.

    Corrigido em 2026-09-17: a versão anterior contava quatro blocos de corte e esperava 80
    MWh absorvidos. São **três**, porque a noite do dia 1 (20h–23h30) e a madrugada do dia 2
    (0h–4h30) são meias horas consecutivas, e formam um bloco só de 18 intervalos.

    Blocos: madrugada 1 (10 intervalos), noite 1 mais madrugada 2 (18), noite 2 (8).
    A bateria carrega 5 MWh por meia hora (10 MW x 0,5 h) e enche em 4 intervalos, então
    absorve 20 MWh em cada bloco: 3 x 20 = **60 MWh**.

    Entre os blocos há 30 meias horas sem corte, tempo de sobra para esvaziar: ela devolve
    20 x 0,85 = 17 MWh depois do primeiro bloco e outros 17 depois do segundo. A carga do
    terceiro bloco fica na bateria quando a série acaba, sem tempo de descarregar, então o
    devolvido é 2 x 17 = **34 MWh**. A energia recuperada conta o que foi absorvido.
    """
    serie = serie_sintetica()
    resultado = simular(serie, config_bateria(10.0, 20.0))
    assert resultado.tecnico.energia_absorvida_bateria_mwh == pytest.approx(60.0)
    assert resultado.tecnico.energia_devolvida_bateria_mwh == pytest.approx(34.0)


def test_vpl_zero_sem_capex_e_sem_fluxo() -> None:
    serie = serie_sintetica(corte_noturno_mw=0.0)
    config = config_equipamento(100.0)
    config.financeira.capex_reais = 0.0
    resultado = simular(serie, config)
    assert resultado.financeiro.vpl_reais == pytest.approx(0.0)
    assert resultado.tecnico.energia_recuperada_mwh == pytest.approx(0.0)


def test_resultado_carimba_metodo_snapshot_local_e_premissas() -> None:
    serie = serie_sintetica()
    resultado = simular(serie, config_equipamento(10.0))
    assert resultado.metodo_versao == METODO_VERSAO
    assert resultado.snapshot_id == serie.snapshot_id
    assert resultado.restricao_id == serie.restricao_id
    assert "sensibilidade_equipamento" in resultado.premissas_usadas


def test_resultado_carimba_a_fonte_sem_mudar_o_calculo() -> None:
    """O motor carimba `fonte_geracao` e não a lê: quem filtra a série pela fonte é quem a monta.

    O carimbo existe porque a fonte é entrada do cálculo — a mesma configuração sobre eólica e
    sobre ambas dá números diferentes, e sem ele a revisão salva não se refaz.
    """
    serie = serie_sintetica()
    config = config_equipamento(40.0)

    padrao = simular(serie, config)
    assert padrao.premissas_usadas["fonte_geracao"].valor == "eolica"
    assert padrao.premissas_usadas["fonte_geracao"].status is StatusPremissa.PROPOSTA

    ambas = simular(serie, config, PREMISSAS_PADRAO.com(fonte_geracao="ambas"))
    assert ambas.premissas_usadas["fonte_geracao"].valor == "ambas"
    # Mesma série entrando, **todo** o resto do resultado igual saindo. Comparar só a energia
    # recuperada deixaria passar a regressão que este teste existe para pegar: bastaria alguém
    # fazer a conta econômica ler `fonte_geracao` para o VPL mudar com o teste verde.
    so_o_carimbo = {"premissas_usadas"}
    assert ambas.model_dump(exclude=so_o_carimbo) == padrao.model_dump(exclude=so_o_carimbo)
