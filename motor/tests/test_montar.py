"""`montar_configuracao`: a configuração inteira a partir da alavanca, cada valor com fonte.

Os custos unitários de referência, de `docs/premissas.md`: bateria 1.375 R$/kWh; linha de
500 kV em circuito simples, coluna de leilão, 2.471.843 R$/km.
"""

from __future__ import annotations

import pytest
from test_spec_tela_criar_simulacao import campos

from arco_motor.montar import (
    Alavanca,
    EscolhaDaBateria,
    EscolhaDoCircuito,
    LinhaDoCadastro,
    OrigemDoCampo,
    montar_configuracao,
)
from arco_motor.premissas import PREMISSAS_PADRAO, StatusPremissa
from arco_motor.tipos import Cenario, Modalidade

LINHA = LinhaDoCadastro(
    cod_equipamento="LT-500-1",
    papel="monitorado",
    tensao_kv=500,
    comprimento_km=210.0,
    capacidade_longa_mva=3005.0,
    subestacao_de="JAGUARUANA II",
    subestacao_para="ACU III",
)
BATERIA_50_MW_4_H = EscolhaDaBateria(potencia_mw=50, capacidade_mwh=200, subestacao="ACU III")
CIRCUITO_40_MW = EscolhaDoCircuito(cod_equipamento="LT-500-1", ganho_limite_mw=40)


def _codigos(montada) -> list[str]:  # type: ignore[no-untyped-def]
    return [aviso.codigo for aviso in montada.avisos]


def _aviso(montada, codigo: str):  # type: ignore[no-untyped-def]
    (aviso,) = [a for a in montada.avisos if a.codigo == codigo]
    return aviso


def _montar(modalidade: Modalidade, alavanca: Alavanca, linha: LinhaDoCadastro = LINHA):
    return montar_configuracao(modalidade, Cenario.REFERENCIA, alavanca, PREMISSAS_PADRAO, [linha])


def test_bateria_de_50_mw_e_200_mwh_no_cenario_de_referencia() -> None:
    """Capex = 200 MWh x 1.000 kWh/MWh x 1.375 R$/kWh = 275.000.000 R$.

    Faixa: 200.000 kWh x 1.250 = 250.000.000 a 200.000 x 2.250 = 450.000.000 R$, os cenários
    otimista e conservador do mesmo custo unitário."""
    montada = _montar(Modalidade.BATERIA, Alavanca(bateria=BATERIA_50_MW_4_H))

    assert montada.configuracao.financeira.capex_reais == pytest.approx(275_000_000)
    (parcela,) = montada.investimento
    assert parcela.custo_unitario is not None
    assert parcela.custo_unitario.id == "bateria_capex_kwh"
    assert (parcela.quantidade, parcela.unidade_da_quantidade) == (200_000, "kWh")
    assert parcela.faixa_reais == pytest.approx((250_000_000, 450_000_000))
    assert _codigos(montada) == ["custos_de_operacao_zerados"], "4 horas está dentro da faixa"


@pytest.mark.parametrize("modalidade", list(Modalidade))
def test_todo_campo_sai_com_premissa_fonte_e_status(modalidade: Modalidade) -> None:
    """Toda folha da configuração aparece em `campos`, e só a escolha de quem monta fica sem
    fonte e sem status: ela não é premissa."""
    alavanca = Alavanca(
        bateria=BATERIA_50_MW_4_H if modalidade is not Modalidade.EQUIPAMENTO else None,
        circuito=CIRCUITO_40_MW if modalidade is not Modalidade.BATERIA else None,
    )
    montada = _montar(modalidade, alavanca)

    nomes = [c.campo for c in montada.campos]
    assert len(nomes) == len(set(nomes)), "campo repetido"
    esperados = {
        c.replace("[].ano", "").replace("[].valor_reais", "")
        for c in campos()
        if not (c.startswith("bateria.") and montada.configuracao.bateria is None)
        and not (c.startswith("equipamento.") and montada.configuracao.equipamento is None)
    }
    assert set(nomes) == esperados
    for campo in montada.campos:
        if campo.origem is OrigemDoCampo.ESCOLHA:
            assert (campo.fonte, campo.status) == (None, None), campo.campo
        else:
            assert campo.fonte and campo.status is not None, campo.campo
    por_campo = {c.campo: c for c in montada.campos}
    assert por_campo["financeira.taxa_desconto_aa"].premissa_id == "taxa_desconto"
    assert por_campo["financeira.taxa_desconto_aa"].origem is OrigemDoCampo.CENARIO
    assert por_campo["financeira.preco_energia_reais_mwh"].premissa_id == "preco_energia"
    assert montada.configuracao.financeira.preco_energia_reais_mwh is None


def test_circuito_novo_em_linha_de_500_kv() -> None:
    """Capex = 210 km x 2.471.843 R$/km = 519.087.030 R$. A linha não tem faixa: as colunas do
    BPR são obras diferentes, não incerteza, e a de leilão vale nos três cenários."""
    montada = _montar(Modalidade.EQUIPAMENTO, Alavanca(circuito=CIRCUITO_40_MW))

    assert montada.configuracao.financeira.capex_reais == pytest.approx(519_087_030)
    (parcela,) = montada.investimento
    assert parcela.custo_unitario is not None
    assert parcela.custo_unitario.id == "linha_500kv_simples_km"
    assert parcela.faixa_reais is None
    assert montada.configuracao.equipamento is not None
    assert montada.configuracao.equipamento.ganho_limite_mw == 40
    parcial = _aviso(montada, "investimento_do_circuito_parcial")
    assert "PIS/COFINS" in parcial.mensagem
    assert "210 km" in parcial.mensagem, "o comprimento suposto fica dito"


def test_combinada_soma_as_duas_parcelas() -> None:
    montada = _montar(
        Modalidade.COMBINADA, Alavanca(bateria=BATERIA_50_MW_4_H, circuito=CIRCUITO_40_MW)
    )

    assert montada.configuracao.financeira.capex_reais == pytest.approx(275_000_000 + 519_087_030)
    assert [p.intervencao for p in montada.investimento] == ["bateria", "circuito"]


def test_bateria_so_de_bateria_usa_a_vida_util_como_horizonte() -> None:
    """O horizonte vem de `valores_iniciais`, que na bateria é a vida útil dela (20 anos)."""
    montada = _montar(Modalidade.BATERIA, Alavanca(bateria=BATERIA_50_MW_4_H))
    assert montada.configuracao.financeira.horizonte_anos == 20


@pytest.mark.parametrize(
    ("capacidade_mwh", "horas"),
    [
        (50.0, "1 h, abaixo de 2 h"),
        (98.0, "1,96 h, abaixo de 2 h"),
        (302.0, "6,04 h, acima de 6 h"),
    ],
)
def test_duracao_fora_de_2_a_6_horas_avisa(capacidade_mwh: float, horas: str) -> None:
    """1,96 h não pode sair como "2 h, fora da faixa de 2 a 6 h": o arredondamento contradiria o
    aviso."""
    bateria = EscolhaDaBateria(potencia_mw=50, capacidade_mwh=capacidade_mwh, subestacao="ACU III")
    montada = _montar(Modalidade.BATERIA, Alavanca(bateria=bateria))

    aviso = _aviso(montada, "duracao_fora_da_calibracao")
    assert horas in aviso.mensagem
    assert aviso.premissa_id == "bateria_duracao_horas"


def test_linha_sem_comprimento_nao_inventa_investimento() -> None:
    sem_comprimento = LINHA.model_copy(update={"comprimento_km": None})
    montada = _montar(Modalidade.EQUIPAMENTO, Alavanca(circuito=CIRCUITO_40_MW), sem_comprimento)

    assert montada.configuracao.financeira.capex_reais == 0
    (parcela,) = montada.investimento
    assert not parcela.estimada
    aviso = _aviso(montada, "investimento_do_circuito_nao_estimado")
    assert "comprimento" in aviso.mensagem
    capex = next(c for c in montada.campos if c.campo == "financeira.capex_reais")
    assert capex.status is StatusPremissa.NAO_VERIFICADA


def test_tensao_sem_custo_unitario_avisa() -> None:
    em_345 = LINHA.model_copy(update={"tensao_kv": 345})
    montada = _montar(Modalidade.EQUIPAMENTO, Alavanca(circuito=CIRCUITO_40_MW), em_345)

    aviso = _aviso(montada, "investimento_do_circuito_nao_estimado")
    assert "linha_345kv_simples_km" in aviso.mensagem
    assert montada.configuracao.financeira.capex_reais == 0


def test_cenario_conservador_muda_o_custo_unitario() -> None:
    """Conservador: 200.000 kWh x 2.250 R$/kWh = 450.000.000 R$."""
    montada = montar_configuracao(
        Modalidade.BATERIA,
        Cenario.CONSERVADOR,
        Alavanca(bateria=BATERIA_50_MW_4_H),
        PREMISSAS_PADRAO,
        [LINHA],
    )
    assert montada.configuracao.financeira.capex_reais == pytest.approx(450_000_000)
    assert montada.configuracao.financeira.taxa_desconto_aa == pytest.approx(0.12)


def test_alavanca_incoerente_com_a_modalidade_recusa() -> None:
    with pytest.raises(ValueError, match="não aceita circuito"):
        _montar(Modalidade.BATERIA, Alavanca(bateria=BATERIA_50_MW_4_H, circuito=CIRCUITO_40_MW))
    with pytest.raises(ValueError, match="exige bateria"):
        _montar(Modalidade.COMBINADA, Alavanca(circuito=CIRCUITO_40_MW))


def test_linha_fora_do_cadastro_recusa() -> None:
    outra = EscolhaDoCircuito(cod_equipamento="LT-OUTRA", ganho_limite_mw=40)
    with pytest.raises(ValueError, match="fora do cadastro"):
        _montar(Modalidade.EQUIPAMENTO, Alavanca(circuito=outra))


def test_custo_de_operacao_zerado_avisa_que_favorece_o_vpl() -> None:
    """Custo fixo, reposição e residual nascem zero, do tipo e sem fonte: não é neutro."""
    montada = _montar(Modalidade.BATERIA, Alavanca(bateria=BATERIA_50_MW_4_H))

    aviso = _aviso(montada, "custos_de_operacao_zerados")
    assert "favorece o VPL" in aviso.mensagem
    custo_fixo = next(c for c in montada.campos if c.campo == "financeira.opex_fixo_reais_ano")
    assert custo_fixo.status is StatusPremissa.NAO_VERIFICADA
    assert custo_fixo.fonte is not None and "favorece o VPL" in custo_fixo.fonte
