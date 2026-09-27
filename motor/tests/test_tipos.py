"""Contrato dos tipos: o que já vale desde a fundação."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

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
from sinteticos import serie_sintetica


def test_serie_sintetica_soma_1800_mwh() -> None:
    assert serie_sintetica().energia_cortada_mwh == pytest.approx(1800.0)


def test_serie_fora_de_ordem_e_rejeitada() -> None:
    a = Intervalo(instante=datetime(2026, 1, 1, 1, 0), corte_mw=1.0)
    b = Intervalo(instante=datetime(2026, 1, 1, 0, 30), corte_mw=1.0)
    with pytest.raises(ValidationError, match="fora de ordem"):
        SerieRestricao(restricao_id="x", snapshot_id="s", intervalos=[a, b])


def test_corte_negativo_e_rejeitado() -> None:
    with pytest.raises(ValidationError):
        Intervalo(instante=datetime(2026, 1, 1), corte_mw=-1.0)


def test_modalidade_exige_configuracao_coerente() -> None:
    financeira = ConfigFinanceira(
        cenario=Cenario.REFERENCIA, taxa_desconto_aa=0.08, horizonte_anos=10, capex_reais=1.0
    )
    with pytest.raises(ValidationError, match="exige bateria"):
        Configuracao(modalidade=Modalidade.BATERIA, financeira=financeira)
    with pytest.raises(ValidationError, match="não aceita equipamento"):
        Configuracao(
            modalidade=Modalidade.BATERIA,
            bateria=ConfigBateria(potencia_mw=1, capacidade_mwh=1, subestacao="SE TESTE"),
            equipamento=ConfigEquipamento(
                tipo=TipoIntervencao.ADICAO_CIRCUITO,
                cod_equipamento="LT-TESTE-1",
                ganho_limite_mw=1,
            ),
            financeira=financeira,
        )


def test_estado_de_carga_inicial_fora_dos_limites_e_rejeitado() -> None:
    with pytest.raises(ValidationError, match="soc_min <= soc_inicial <= soc_max"):
        ConfigBateria(
            potencia_mw=1,
            capacidade_mwh=1,
            subestacao="SE TESTE",
            soc_inicial=0.9,
            soc_max=0.8,
        )


def test_soc_inicial_vazio_assume_o_piso_e_nao_zero() -> None:
    """O payload que o front mandou em 2026-09-21 e tomou 422 sem ter escolhido nada.

    `soc_inicial` é opcional. Omitido, caía em zero — carga proibida sempre que `soc_min` for
    maior que zero. Agora assume `soc_min`, o piso que a operação permite.
    """
    config = ConfigBateria(
        subestacao="ACU III",
        potencia_mw=100.0,
        capacidade_mwh=400.0,
        soc_min=0.2,
        soc_max=0.5,
    )

    assert config.soc_inicial is None
    assert config.carga_inicial == 0.2


def test_soc_inicial_informado_continua_valendo() -> None:
    config = ConfigBateria(
        subestacao="ACU III",
        potencia_mw=100.0,
        capacidade_mwh=400.0,
        soc_min=0.2,
        soc_inicial=0.35,
        soc_max=0.5,
    )

    assert config.carga_inicial == 0.35


def test_soc_inicial_fora_da_faixa_continua_recusado() -> None:
    with pytest.raises(ValidationError, match="soc_min <= soc_inicial <= soc_max"):
        ConfigBateria(
            subestacao="ACU III",
            potencia_mw=100.0,
            capacidade_mwh=400.0,
            soc_min=0.2,
            soc_inicial=0.9,
            soc_max=0.5,
        )


def test_faixa_invertida_e_recusada_dizendo_qual_campo() -> None:
    """Antes, soc_min > soc_max só aparecia como a mensagem dos três campos juntos."""
    with pytest.raises(ValidationError, match="soc_min <= soc_max"):
        ConfigBateria(
            subestacao="ACU III",
            potencia_mw=100.0,
            capacidade_mwh=400.0,
            soc_min=0.8,
            soc_max=0.3,
        )
