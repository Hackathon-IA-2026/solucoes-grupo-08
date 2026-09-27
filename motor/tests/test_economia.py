"""Conta econômica: VPL, TIR, payback e o fluxo anual. Casos calculáveis à mão."""

from __future__ import annotations

import pytest

from arco_motor.economia import calcular, tir, vpl
from arco_motor.premissas import PREMISSAS_PADRAO
from arco_motor.tipos import Cenario, ConfigFinanceira, ResultadoTecnico


def tecnico_com(energia_recuperada_mwh: float) -> ResultadoTecnico:
    """Resultado técnico mínimo: só a energia importa para a conta econômica."""
    return ResultadoTecnico(
        cortado_mw=[],
        evitado_equipamento_mw=[],
        absorvido_bateria_mw=[],
        devolvido_bateria_mw=[],
        residual_mw=[],
        soc_mwh=[],
        energia_cortada_mwh=energia_recuperada_mwh,
        energia_evitada_equipamento_mwh=energia_recuperada_mwh,
        energia_absorvida_bateria_mwh=0.0,
        energia_devolvida_bateria_mwh=0.0,
        energia_recuperada_mwh=energia_recuperada_mwh,
        fracao_recuperada=1.0,
    )


def test_vpl_de_fluxo_conhecido() -> None:
    """-100 hoje e +110 daqui a um ano, a 10% ao ano, vale zero hoje."""
    assert vpl([-100.0, 110.0], 0.10) == pytest.approx(0.0)
    assert vpl([-100.0, 110.0], 0.0) == pytest.approx(10.0)


def test_tir_de_fluxo_conhecido() -> None:
    resultado = tir([-100.0, 110.0])
    assert resultado is not None
    assert resultado == pytest.approx(0.10, abs=1e-6)


def test_tir_e_none_sem_troca_de_sinal() -> None:
    assert tir([100.0, 110.0]) is None
    assert tir([-100.0, -110.0]) is None


def test_caso_de_ouro_fluxo_de_dois_anos() -> None:
    """1.000 MWh por ano a 150 reais, CAPEX de 100 mil, taxa zero, horizonte de 2 anos.

    Benefício anual = 1.000 x 150 = 150.000. Fluxos: -100.000, +150.000, +150.000.
    Com taxa zero o VPL é a soma: **200.000**. O payback simples cruza zero em 2/3 de ano.
    """
    config = ConfigFinanceira(
        cenario=Cenario.REFERENCIA,
        taxa_desconto_aa=0.0,
        horizonte_anos=2,
        capex_reais=100_000.0,
        preco_energia_reais_mwh=150.0,
    )
    resultado = calcular(tecnico_com(1000.0), config, 12.0, PREMISSAS_PADRAO)

    assert [f.fluxo_liquido_reais for f in resultado.fluxos] == pytest.approx(
        [-100_000.0, 150_000.0, 150_000.0]
    )
    assert resultado.vpl_reais == pytest.approx(200_000.0)
    assert resultado.payback_simples_anos == pytest.approx(2.0 / 3.0)
    assert resultado.custo_por_mwh_reais == pytest.approx(50.0)


def test_preco_sem_valor_na_configuracao_cai_na_premissa() -> None:
    """Preço vazio usa `preco_energia`, hoje 216 reais por MWh."""
    config = ConfigFinanceira(
        cenario=Cenario.REFERENCIA, taxa_desconto_aa=0.0, horizonte_anos=1, capex_reais=0.0
    )
    resultado = calcular(tecnico_com(1000.0), config, 12.0, PREMISSAS_PADRAO)
    assert resultado.fluxos[1].beneficio_bruto_reais == pytest.approx(216_000.0)


def test_periodo_menor_que_um_ano_e_anualizado() -> None:
    """Seis meses de histórico com 500 MWh recuperados valem 1.000 MWh por ano."""
    config = ConfigFinanceira(
        cenario=Cenario.REFERENCIA,
        taxa_desconto_aa=0.0,
        horizonte_anos=1,
        capex_reais=0.0,
        preco_energia_reais_mwh=100.0,
    )
    resultado = calcular(tecnico_com(500.0), config, 6.0, PREMISSAS_PADRAO)
    assert resultado.fluxos[1].beneficio_bruto_reais == pytest.approx(100_000.0)
