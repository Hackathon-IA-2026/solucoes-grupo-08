"""Parte calculada do relatório (feature 17, task 17.2).

Os casos de ouro montam o `Resultado` à mão em vez de rodar o motor: o que se confere aqui é a
derivação entre revisões, e cada número esperado sai de uma conta que cabe no docstring.

Exploração de ouro, três revisões de bateria em SE TESTE, taxa 8% a.a., horizonte 15 anos,
investimento de R$ 100 milhões nas três:

| rev | id  | pot.   | cenário    | VPL (R$) | fração | MWh   | pb s. | pb d. | R$/MWh | TIR |
|-----|-----|--------|------------|----------|--------|-------|-------|-------|--------|-----|
| 1   | 11  | 50 MW  | referência | −20 mi   | 0,10   | 1.000 | 18    | —     | 300    | 5%  |
| 2   | 12  | 100 MW | referência | +10 mi   | 0,20   | 2.000 | 12    | 14    | 250    | 10% |
| 3   | 13  | 100 MW | otimista   | +10 mi   | 0,20   | 2.000 | 10    | 12    | 250    | 12% |

MWh é a energia recuperada; pb s. e pb d., os paybacks simples e descontado, em anos.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from arco_motor.montar import LinhaDoCadastro
from arco_motor.premissas import PREMISSAS_PADRAO, Premissa, StatusPremissa
from arco_motor.relatorio import (
    RevisaoCoberta,
    alavanca,
    derivar,
    escrever,
    folhas,
    numero_br,
)
from arco_motor.simular import _premissas_usadas
from arco_motor.tipos import (
    Cenario,
    Configuracao,
    Resultado,
    ResultadoFinanceiro,
    ResultadoTecnico,
)
from arco_motor.variacao import AlavancaFisica, Variacao, faixa_permitida, montar_variacao
from sinteticos import config_bateria, config_combinada, config_equipamento, configs_combinadas

CRIADA = datetime(2026, 9, 22, 10, 0)


def _resultado(
    *,
    vpl: float,
    fracao: float,
    energia: float,
    payback: float | None,
    descontado: float | None,
    custo: float | None,
    tir: float | None,
    snapshot_id: str = "2026-09-21",
    premissas: dict[str, Premissa] | None = None,
) -> Resultado:
    return Resultado(
        metodo_versao="0.7.0",
        snapshot_id=snapshot_id,
        restricao_id="R1",
        tecnico=ResultadoTecnico(
            cortado_mw=[],
            evitado_equipamento_mw=[],
            absorvido_bateria_mw=[],
            devolvido_bateria_mw=[],
            residual_mw=[],
            soc_mwh=[],
            energia_cortada_mwh=10_000.0,
            energia_evitada_equipamento_mwh=0.0,
            energia_absorvida_bateria_mwh=energia,
            energia_devolvida_bateria_mwh=energia,
            energia_recuperada_mwh=energia,
            fracao_recuperada=fracao,
        ),
        financeiro=ResultadoFinanceiro(
            vpl_reais=vpl,
            tir_aa=tir,
            payback_simples_anos=payback,
            payback_descontado_anos=descontado,
            custo_por_mwh_reais=custo,
            beneficio_bruto_reais=0.0,
            beneficio_liquido_reais=0.0,
            fluxos=[],
        ),
        # Vazio aqui; `_rev` carimba o que `simular` carimbaria para a configuração.
        premissas_usadas=premissas or {},
    )


def _bateria(potencia_mw: float, cenario: Cenario = Cenario.REFERENCIA) -> Configuracao:
    config = config_bateria(potencia_mw=potencia_mw, capacidade_mwh=200.0)
    config.financeira.capex_reais = 100_000_000.0
    config.financeira.cenario = cenario
    config.financeira.preco_energia_reais_mwh = None  # usa a premissa preco_energia
    return config


def _rev(id: int, posicao: int, config: Configuracao, resultado: Resultado) -> RevisaoCoberta:
    if not resultado.premissas_usadas:
        resultado = resultado.model_copy(
            update={"premissas_usadas": _premissas_usadas(config, PREMISSAS_PADRAO)}
        )
    return RevisaoCoberta(
        revisao_id=id,
        posicao=posicao,
        criada_em=CRIADA + timedelta(minutes=posicao),
        configuracao=config,
        resultado=resultado,
        o_que_mudou=f"mudança da rev {posicao}",
    )


R1 = _rev(
    11,
    1,
    _bateria(50.0),
    _resultado(
        vpl=-20e6, fracao=0.10, energia=1000, payback=18, descontado=None, custo=300, tir=0.05
    ),
)
R2 = _rev(
    12,
    2,
    _bateria(100.0),
    _resultado(vpl=10e6, fracao=0.20, energia=2000, payback=12, descontado=14, custo=250, tir=0.10),
)
R3 = _rev(
    13,
    3,
    _bateria(100.0, Cenario.OTIMISTA),
    _resultado(vpl=10e6, fracao=0.20, energia=2000, payback=10, descontado=12, custo=250, tir=0.12),
)
ROTULOS = {"bateria.potencia_mw": "Potência da bateria", "financeira.cenario": "Cenário"}


@pytest.fixture
def ouro():
    # A ordem de entrada não importa: a base é a de menor posição.
    return derivar([R3, R1, R2], ROTULOS)


def test_ordenacao_por_vpl_com_empate_divide_o_lugar(ouro) -> None:
    """R2 e R3 têm VPL de 10 mi: dividem o 1º lugar, e R1 fica em 3º, não em 2º."""
    vpl = ouro.ordenacoes["vpl"]
    assert [(p.posicao, p.revisao_id) for p in vpl] == [(1, 12), (1, 13), (3, 11)]
    assert vpl[0].empate_com == [13]
    assert vpl[1].empate_com == [12]
    assert vpl[2].empate_com == []


def test_payback_descontado_ordena_so_onde_ocorre(ouro) -> None:
    """R1 não paga o investimento descontado no horizonte: não entra. R3 (12) antes de R2 (14)."""
    assert [p.revisao_id for p in ouro.ordenacoes["payback_descontado"]] == [13, 12]


def test_custo_por_mwh_crescente_com_empate(ouro) -> None:
    custo = ouro.ordenacoes["custo_por_mwh"]
    assert [(p.posicao, p.revisao_id, p.valor) for p in custo] == [
        (1, 12, 250),
        (1, 13, 250),
        (3, 11, 300),
    ]


def test_base_e_a_primeira_coberta(ouro) -> None:
    assert (ouro.base.revisao_id, ouro.base.posicao) == (11, 1)


def test_diferencas_contra_a_base_e_a_anterior(ouro) -> None:
    """R2: +30 mi contra R1 nas duas. R3: +30 mi contra a base, 0 contra R2.
    Energia: +1.000 MWh contra a base nas duas; R3 contra R2, 0. Payback: 12 − 18 = −6 e
    10 − 18 = −8."""
    d2, d3 = ouro.diferencas
    assert d2.revisao_id == 12
    assert d2.o_que_mudou == "mudança da rev 2"
    assert (d2.delta_vpl_vs_base_reais, d2.delta_vpl_vs_anterior_reais) == (30e6, 30e6)
    assert (d2.delta_energia_vs_base_mwh, d2.delta_energia_vs_anterior_mwh) == (1000, 1000)
    assert d2.delta_fracao_vs_base == pytest.approx(0.10)
    assert d2.delta_payback_simples_vs_base_anos == -6
    assert d3.revisao_id == 13
    assert (d3.delta_vpl_vs_base_reais, d3.delta_vpl_vs_anterior_reais) == (30e6, 0)
    assert (d3.delta_energia_vs_base_mwh, d3.delta_energia_vs_anterior_mwh) == (1000, 0)
    assert d3.delta_payback_simples_vs_base_anos == -8


def test_sensibilidade_numerica_da_o_valor_por_unidade(ouro) -> None:
    """R1 → R2 muda só a potência, de 50 para 100 MW: 30 mi / 50 MW = R$ 600 mil por MW, e
    1.000 MWh / 50 MW = 20 MWh por MW."""
    s = ouro.sensibilidades[0]
    assert (s.de_revisao_id, s.para_revisao_id, s.tipo) == (11, 12, "numerica")
    assert (s.campo, s.rotulo, s.de, s.para) == (
        "bateria.potencia_mw",
        "Potência da bateria",
        "50 MW",
        "100 MW",
    )
    assert s.delta_vpl_por_unidade_reais == pytest.approx(600_000)
    assert s.delta_energia_por_unidade_mwh == pytest.approx(20)
    assert s.delta_vpl_reais == pytest.approx(30e6)
    assert "Capacidade da bateria" not in s.condicao  # sem rótulo, sai pelo caminho
    assert "bateria.capacidade_mwh: 200 MWh" in s.condicao
    assert "Cenário: referencia" in s.condicao


def test_sensibilidade_categorica_so_tem_o_delta(ouro) -> None:
    s = ouro.sensibilidades[1]
    assert (s.tipo, s.campo, s.de, s.para) == (
        "categorica",
        "financeira.cenario",
        "referencia",
        "otimista",
    )
    assert s.delta_vpl_reais == 0
    assert s.delta_vpl_por_unidade_reais is None
    assert s.delta_energia_por_unidade_mwh is None


def test_dois_campos_mudando_nao_tem_par() -> None:
    config = _bateria(80.0, Cenario.OTIMISTA)
    r = _rev(
        14,
        4,
        config,
        _resultado(vpl=0, fracao=0.1, energia=1, payback=None, descontado=None, custo=None, tir=0),
    )
    (s,) = derivar([R2, r]).sensibilidades
    assert s.tipo == "sem_par"
    assert s.campo is None and s.delta_vpl_reais is None
    assert s.campos_que_mudaram == ["bateria.potencia_mw", "financeira.cenario"]


def test_custo_que_acompanha_o_tamanho_nao_tira_o_par() -> None:
    """Potência de 100 para 150 MW com o investimento de 100 para 160 mi: o efeito é da potência
    com o custo dela. VPL de 10 para 4 mi: −6 mi / 50 MW = −R$ 120 mil por MW."""
    config = _bateria(150.0)
    config.financeira.capex_reais = 160_000_000.0
    config.financeira.opex_fixo_reais_ano = 1_000.0
    r = _rev(
        14,
        4,
        config,
        _resultado(
            vpl=4e6, fracao=0.3, energia=2500, payback=14, descontado=None, custo=240, tir=0.09
        ),
    )
    (s,) = derivar([R2, r], ROTULOS).sensibilidades
    assert (s.tipo, s.campo) == ("numerica", "bateria.potencia_mw")
    assert s.delta_vpl_por_unidade_reais == pytest.approx(-120_000)
    assert s.delta_energia_por_unidade_mwh == pytest.approx(10)
    assert s.campos_que_mudaram == [
        "bateria.potencia_mw",
        "financeira.capex_reais",
        "financeira.opex_fixo_reais_ano",
    ]
    assert s.condicao.startswith(
        "o custo acompanhou a alavanca (financeira.capex_reais: R$ 100.000.000 → R$ 160.000.000;"
    )


def test_potencia_na_mesma_duracao_e_a_alavanca_potencia() -> None:
    """100 MW e 200 MWh para 150 MW e 300 MWh: 2 h nas duas. É a alavanca "potência" do
    explorador, e a capacidade acompanha como o custo (17.11). VPL de 10 para 4 mi: −6 mi / 50
    MW = −R$ 120 mil por MW."""
    config = _bateria(150.0)
    assert config.bateria is not None
    config.bateria.capacidade_mwh = 300.0
    config.financeira.capex_reais = 160_000_000.0
    r = _rev(
        14,
        4,
        config,
        _resultado(
            vpl=4e6, fracao=0.3, energia=2500, payback=14, descontado=None, custo=240, tir=0.09
        ),
    )
    (s,) = derivar([R2, r], ROTULOS).sensibilidades
    assert (s.tipo, s.campo) == ("numerica", "bateria.potencia_mw")
    assert s.delta_vpl_por_unidade_reais == pytest.approx(-120_000)
    assert s.campos_que_mudaram == [
        "bateria.potencia_mw",
        "bateria.capacidade_mwh",
        "financeira.capex_reais",
    ]
    assert s.condicao.startswith("a capacidade acompanhou a potência na mesma duração, 2 h")
    assert (
        "fixos: " in s.condicao
        and "Capacidade da bateria: 200" not in s.condicao.split("fixos: ")[1]
    ), "a capacidade mudou: não é fixa"


def test_potencia_e_duracao_mudando_juntas_nao_tem_par() -> None:
    """100 MW e 200 MWh (2 h) para 150 MW e 250 MWh (1,67 h): duas alavancas."""
    config = _bateria(150.0)
    assert config.bateria is not None
    config.bateria.capacidade_mwh = 250.0
    config.financeira.capex_reais = 160_000_000.0
    r = _rev(
        14,
        4,
        config,
        _resultado(vpl=0, fracao=0.1, energia=1, payback=None, descontado=None, custo=None, tir=0),
    )
    (s,) = derivar([R2, r]).sensibilidades
    assert s.tipo == "sem_par"
    assert s.campos_que_mudaram == [
        "bateria.potencia_mw",
        "bateria.capacidade_mwh",
        "financeira.capex_reais",
    ]


def test_premissa_ou_snapshot_diferente_tira_o_par() -> None:
    """Mesma configuração com outro snapshot, mais a potência: o efeito não é só da potência."""
    outro = R2.resultado.model_copy(update={"snapshot_id": "2026-10-01"})
    r = _rev(14, 4, _bateria(120.0), outro)
    (s,) = derivar([R2, r]).sensibilidades
    assert s.tipo == "sem_par"
    assert s.campos_que_mudaram == ["bateria.potencia_mw", "snapshot_id"]

    premissas = dict(PREMISSAS_PADRAO.itens)
    premissas["fonte_geracao"] = premissas["fonte_geracao"].model_copy(update={"valor": "solar"})
    r = _rev(
        15, 5, _bateria(100.0), R2.resultado.model_copy(update={"premissas_usadas": premissas})
    )
    (s,) = derivar([R2, r]).sensibilidades
    assert s.tipo == "sem_par"
    assert s.campos_que_mudaram == ["premissa.fonte_geracao"]
    assert "não é campo da configuração" in s.condicao


def test_versao_que_muda_resultado_tira_o_par() -> None:
    """De 0.3.0 para 0.7.0 passa a 0.4.0, que mudou a anualização: o efeito não é só da
    potência."""
    antiga = R2.resultado.model_copy(update={"metodo_versao": "0.3.0"})
    r = _rev(14, 4, _bateria(120.0), R2.resultado)
    (s,) = derivar([R2.model_copy(update={"resultado": antiga}), r]).sensibilidades
    assert s.tipo == "sem_par"
    assert s.campos_que_mudaram == ["bateria.potencia_mw", "metodo_versao"]


def test_versao_que_nao_muda_resultado_mantem_o_par() -> None:
    """A 0.7.0 só acrescentou cálculo: uma revisão da 0.6.0 continua comparável."""
    antiga = R2.resultado.model_copy(update={"metodo_versao": "0.6.0"})
    r = _rev(14, 4, _bateria(120.0), R2.resultado)
    (s,) = derivar([R2.model_copy(update={"resultado": antiga}), r]).sensibilidades
    assert (s.tipo, s.campo) == ("numerica", "bateria.potencia_mw")


def test_versoes_que_mudam_resultado_estao_no_historico() -> None:
    from arco_motor import versao

    for v in versao.MUDAM_RESULTADO:
        assert f"- {v} (" in (versao.__doc__ or ""), v


def test_menor_alavanca_e_o_tamanho_nao_a_posicao() -> None:
    """Mesmo investimento, as duas no horizonte: a de 50 MW é a menor alavanca, mesmo vindo
    depois da de 200 MW."""
    boa = _resultado(vpl=1, fracao=0.1, energia=1, payback=5, descontado=6, custo=1, tir=0.2)
    grande = _rev(21, 1, _bateria(200.0), boa)
    pequena = _rev(22, 2, _bateria(50.0), boa)
    f = derivar([grande, pequena]).fronteiras
    assert f.menor_alavanca_com_payback_no_horizonte is not None
    assert f.menor_alavanca_com_payback_no_horizonte.revisao_id == 22
    assert f.tir_passa_taxa is not None
    assert f.tir_passa_taxa.revisao_id == 22


def test_entre_modalidades_a_menor_alavanca_e_o_menor_investimento() -> None:
    boa = _resultado(vpl=1, fracao=0.1, energia=1, payback=5, descontado=6, custo=1, tir=0.2)
    bateria = _rev(21, 1, _bateria(10.0), boa)
    circuito = config_equipamento(300.0)
    circuito.financeira.capex_reais = 1_000.0
    equipamento = _rev(22, 2, circuito, boa)
    f = derivar([bateria, equipamento]).fronteiras
    assert f.menor_alavanca_com_payback_no_horizonte is not None
    assert f.menor_alavanca_com_payback_no_horizonte.revisao_id == 22


def test_fronteiras_entre_as_cobertas(ouro) -> None:
    """Payback simples ≤ 15 anos: R2 (12) e R3 (10), mesmo investimento; fica a de menor
    posição, R2. TIR acima de 8%: R2 e R3, fica R2. Maior fração: 0,20 empatada, fica R2."""
    f = ouro.fronteiras
    assert f.menor_alavanca_com_payback_no_horizonte is not None
    assert f.menor_alavanca_com_payback_no_horizonte.revisao_id == 12
    assert f.menor_alavanca_com_payback_no_horizonte.payback_anos == 12
    assert f.menor_alavanca_com_payback_no_horizonte.horizonte_anos == 15
    assert f.menor_alavanca_com_payback_no_horizonte.alavanca == "100 MW · 200 MWh · SE TESTE"
    assert f.tir_passa_taxa is not None
    assert (f.tir_passa_taxa.revisao_id, f.tir_passa_taxa.tir_aa) == (12, 0.10)
    assert f.tir_passa_taxa.taxa_desconto_aa == 0.08
    assert f.maior_fracao_recuperada is not None
    assert (f.maior_fracao_recuperada.revisao_id, f.maior_fracao_recuperada.fracao) == (12, 0.20)
    assert f.maior_fracao_recuperada.custo_por_mwh_reais == 250


def test_fronteira_nula_quando_nenhuma_revisao_atinge_o_horizonte() -> None:
    f = derivar([R1]).fronteiras
    assert f.menor_alavanca_com_payback_no_horizonte is None
    assert f.tir_passa_taxa is None
    assert f.maior_fracao_recuperada is not None


def test_o_que_variou_e_o_que_ficou_parado(ouro) -> None:
    variou = {c.campo: c.valores for c in ouro.variou}
    assert variou == {
        "bateria.potencia_mw": ["50 MW", "100 MW"],
        "financeira.cenario": ["referencia", "otimista"],
    }
    assert ouro.variou[0].rotulo == "Potência da bateria"
    parado = {c.campo: c.valor for c in ouro.ficou_parado}
    assert parado["modalidade"] == "bateria"
    assert parado["financeira.capex_reais"] == "R$ 100.000.000"
    assert parado["bateria.soc_inicial"] == "vazio"
    assert "equipamento.ganho_limite_mw" not in parado


def test_premissas_expostas_sao_as_nao_validadas_que_o_resultado_tocou(ouro) -> None:
    """Exploração só de bateria: a sensibilidade do equipamento é carimbada para auditoria, mas
    não tocou o resultado, e não é exposta."""
    ids = {p.id for p in ouro.premissas_expostas}
    assert ids == set(_premissas_usadas(R1.configuracao, PREMISSAS_PADRAO)) - {
        "sensibilidade_equipamento"
    }
    preco = next(p for p in ouro.premissas_expostas if p.id == "preco_energia")
    assert (preco.valor, preco.unidade, preco.status, preco.de_metodo) == (
        "216",
        "R$/MWh",
        "proposta",
        False,
    )
    anualizacao = next(p for p in ouro.premissas_expostas if p.id == "anualizacao")
    assert (anualizacao.status, anualizacao.de_metodo) == ("nao_verificada", True)


def test_sensibilidade_do_equipamento_e_exposta_quando_ha_equipamento() -> None:
    r = _rev(
        14,
        4,
        config_equipamento(300.0),
        _resultado(vpl=0, fracao=0.1, energia=1, payback=None, descontado=None, custo=None, tir=0),
    )
    exposta = next(
        p for p in derivar([r]).premissas_expostas if p.id == "sensibilidade_equipamento"
    )
    assert (exposta.status, exposta.de_metodo) == ("nao_verificada", True)


def test_preco_padrao_nao_e_exposto_quando_a_configuracao_o_sobrescreve() -> None:
    """Os sintéticos digitam 150 R$/MWh: o 216 da premissa não entrou em conta nenhuma."""
    config = config_bateria(50.0, 100.0)
    r = _rev(
        14,
        1,
        config,
        _resultado(vpl=0, fracao=0.1, energia=1, payback=None, descontado=None, custo=None, tir=0),
    )
    assert "preco_energia" not in {p.id for p in derivar([r]).premissas_expostas}


def test_status_diferente_entre_revisoes_expoe_o_menos_validado() -> None:
    usadas = _premissas_usadas(R2.configuracao, PREMISSAS_PADRAO)
    editada = dict(usadas)
    editada["anualizacao"] = usadas["anualizacao"].model_copy(
        update={"valor": "outra", "status": StatusPremissa.PROPOSTA}
    )
    r1 = R1.model_copy(
        update={"resultado": R1.resultado.model_copy(update={"premissas_usadas": editada})}
    )
    exposta = next(p for p in derivar([r1, R2]).premissas_expostas if p.id == "anualizacao")
    assert (exposta.valor, exposta.status) == ("outra; proporcional", "nao_verificada")


def test_premissa_validada_nao_e_exposta() -> None:
    validada = PREMISSAS_PADRAO.obter("preco_energia").model_copy(
        update={
            "status": StatusPremissa.VALIDADA,
            "validado_por": "engenheiro",
            "validado_em": CRIADA.date(),
        }
    )
    resultado = R1.resultado.model_copy(update={"premissas_usadas": {"preco_energia": validada}})
    r = R1.model_copy(update={"resultado": resultado})
    assert derivar([r]).premissas_expostas == []


def test_premissa_com_valores_diferentes_entre_revisoes_mostra_os_dois() -> None:
    premissas = dict(PREMISSAS_PADRAO.itens)
    premissas["preco_energia"] = premissas["preco_energia"].model_copy(update={"valor": 250.5})
    r = _rev(
        14, 4, _bateria(100.0), R2.resultado.model_copy(update={"premissas_usadas": premissas})
    )
    preco = next(p for p in derivar([R2, r]).premissas_expostas if p.id == "preco_energia")
    assert preco.valor == "216; 250,5"


def test_uma_revisao_so_produz_derivados_com_listas_vazias() -> None:
    d = derivar([R1])
    assert all(lista == [] for lista in d.ordenacoes.values())
    assert set(d.ordenacoes) == {"vpl", "fracao_recuperada", "payback_descontado", "custo_por_mwh"}
    assert d.diferencas == []
    assert d.sensibilidades == []
    assert d.variou == []
    assert d.ficou_parado
    assert (d.base.revisao_id, d.base.posicao) == (11, 1)


def test_sem_revisao_e_erro() -> None:
    with pytest.raises(ValueError, match="sem revisão"):
        derivar([])


def test_modalidades_diferentes_fazem_o_bloco_ausente_variar() -> None:
    equipamento = _rev(
        14,
        4,
        config_equipamento(300.0),
        _resultado(vpl=0, fracao=0.1, energia=1, payback=None, descontado=None, custo=None, tir=0),
    )
    d = derivar([R2, equipamento])
    variou = {c.campo: c.valores for c in d.variou}
    assert variou["modalidade"] == ["bateria", "equipamento"]
    assert variou["bateria.potencia_mw"] == ["100 MW", "vazio"]
    assert variou["equipamento.ganho_limite_mw"] == ["vazio", "300 MW"]


def test_alavanca_por_modalidade() -> None:
    assert alavanca(config_bateria(50.0, 100.0)) == "50 MW · 100 MWh · SE TESTE"
    assert alavanca(config_equipamento(300.0)) == "LT-TESTE-1 · ganho 300 MW"
    assert (
        alavanca(config_combinada(300.0, 50.5, 100.0))
        == "LT-TESTE-1 · ganho 300 MW + 50,5 MW · 100 MWh · SE TESTE"
    )


@pytest.mark.parametrize(
    ("valor", "campo", "texto"),
    [
        (0.85, "bateria.eficiencia_ida_volta", "0,85"),
        (250_000_000.0, "financeira.capex_reais", "R$ 250.000.000"),
        (216.0, "financeira.preco_energia_reais_mwh", "R$ 216 por MWh"),
        (0.08, "financeira.taxa_desconto_aa", "0,08 ao ano"),
        (5e6, "financeira.opex_fixo_reais_ano", "R$ 5.000.000 por ano"),
        (15, "financeira.horizonte_anos", "15 anos"),
        (None, "bateria.soc_inicial", "vazio"),
        (True, "", "sim"),
        ([], "financeira.reposicoes", "nenhuma"),
        (
            [{"ano": 10, "valor_reais": 5e6}],
            "financeira.reposicoes",
            "ano 10, valor_reais R$ 5.000.000",
        ),
    ],
)
def test_escrever_no_formato_brasileiro(valor: object, campo: str, texto: str) -> None:
    assert escrever(valor, campo) == texto


def test_numero_br_negativo_e_decimal() -> None:
    assert numero_br(-1234567.5) == "-1.234.567,5"
    assert numero_br(0.0) == "0"


@given(
    st.lists(
        configs_combinadas() | st.builds(lambda: config_bateria(10.0, 20.0)), min_size=1, max_size=5
    )
)
def test_variou_e_ficou_parado_particionam_os_campos(configs: list[Configuracao]) -> None:
    resultado = R1.resultado
    revisoes = [_rev(100 + i, i + 1, c, resultado) for i, c in enumerate(configs)]
    d = derivar(revisoes)
    campos = {c for config in configs for c in folhas(config)}
    variou = {c.campo for c in d.variou}
    parado = {c.campo for c in d.ficou_parado}
    assert variou | parado == campos
    assert not variou & parado


def _com_origem(revisao: RevisaoCoberta, origem: RevisaoCoberta | None) -> RevisaoCoberta:
    return revisao.model_copy(update={"revisao_anterior_id": origem.revisao_id if origem else None})


def test_irmas_comparam_com_a_origem_e_nao_uma_com_a_outra() -> None:
    """Ramo (ADR 0014): da R2 (100 MW, 200 MWh, VPL 10 mi) nascem duas variações. A de 150 MW
    em 2 h (300 MWh), VPL 4 mi, e a de 400 MWh em 100 MW, VPL 16 mi. Pela ordem de gravação, a
    segunda seria comparada com a primeira — potência e capacidade mudando juntas em duração
    diferente, `sem_par`. Pela origem, cada uma é numérica contra a R2:
    potência (4 − 10) / 50 = −120 mil por MW; capacidade (16 − 10) / 200 = +30 mil por MWh."""
    potencia = _bateria(150.0)
    assert potencia.bateria is not None
    potencia.bateria.capacidade_mwh = 300.0
    capacidade = _bateria(100.0)
    assert capacidade.bateria is not None
    capacidade.bateria.capacidade_mwh = 400.0
    raiz = _com_origem(R2.model_copy(update={"posicao": 1}), None)
    irma_a = _com_origem(
        _rev(21, 2, potencia, _resultado(vpl=4e6, fracao=0.3, energia=2500, payback=14,
                                         descontado=None, custo=240, tir=0.09)),
        raiz,
    )  # fmt: skip
    irma_b = _com_origem(
        _rev(22, 3, capacidade, _resultado(vpl=16e6, fracao=0.35, energia=3000, payback=11,
                                           descontado=13, custo=230, tir=0.11)),
        raiz,
    )  # fmt: skip

    derivados = derivar([raiz, irma_a, irma_b], ROTULOS)

    por_revisao = {s.para_revisao_id: s for s in derivados.sensibilidades}
    assert {s.de_revisao_id for s in derivados.sensibilidades} == {raiz.revisao_id}
    assert (por_revisao[21].tipo, por_revisao[21].campo) == ("numerica", "bateria.potencia_mw")
    assert por_revisao[21].delta_vpl_por_unidade_reais == pytest.approx(-120_000)
    assert (por_revisao[22].tipo, por_revisao[22].campo) == ("numerica", "bateria.capacidade_mwh")
    assert por_revisao[22].delta_vpl_por_unidade_reais == pytest.approx(30_000)
    diferenca_b = next(d for d in derivados.diferencas if d.revisao_id == 22)
    assert diferenca_b.anterior_revisao_id == raiz.revisao_id
    assert diferenca_b.delta_vpl_vs_anterior_reais == pytest.approx(6e6), "contra a R2, não a A"


def test_cadeia_linear_da_o_mesmo_que_antes_da_origem() -> None:
    """Sem ramos, a origem de cada revisão é a vizinha: gravar `revisao_anterior_id` não muda
    nada do relatório do marco 0."""
    sem = derivar([R1, R2, R3], ROTULOS)
    com = derivar([_com_origem(R1, None), _com_origem(R2, R1), _com_origem(R3, R2)], ROTULOS)

    assert com.sensibilidades == sem.sensibilidades
    assert [d.model_dump(exclude={"anterior_revisao_id"}) for d in com.diferencas] == [
        d.model_dump(exclude={"anterior_revisao_id"}) for d in sem.diferencas
    ]


def test_variacao_de_potencia_do_explorador_tem_sensibilidade() -> None:
    """Da variação montada pelo motor ao relatório: 50 para 100 MW em 4 h muda potência,
    capacidade e custo, e o relatório atribui o efeito à potência."""
    partida = config_bateria(potencia_mw=50.0, capacidade_mwh=200.0)
    partida.financeira.capex_reais = 275_000_000.0
    cadastro = [LinhaDoCadastro(cod_equipamento="LT", papel="monitorado", subestacao_de="SE TESTE")]
    faixa = faixa_permitida(partida, cadastro, PREMISSAS_PADRAO)
    variada = montar_variacao(
        partida,
        Variacao(alavanca=AlavancaFisica.POTENCIA, valor=100.0),
        PREMISSAS_PADRAO,
        faixa,
    ).configuracao
    origem = _com_origem(
        _rev(31, 1, partida, _resultado(vpl=1e6, fracao=0.1, energia=1000, payback=None,
                                        descontado=None, custo=None, tir=None)),
        None,
    )  # fmt: skip
    filha = _com_origem(
        _rev(32, 2, variada, _resultado(vpl=3e6, fracao=0.2, energia=2000, payback=None,
                                        descontado=None, custo=None, tir=None)),
        origem,
    )  # fmt: skip

    (s,) = derivar([origem, filha]).sensibilidades

    assert (s.tipo, s.campo) == ("numerica", "bateria.potencia_mw")
