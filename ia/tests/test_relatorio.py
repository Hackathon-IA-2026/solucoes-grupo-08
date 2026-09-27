"""Analista e verificador do relatório (feature 17, task 17.3), com o SDK substituído.

O verificador é o que importa aqui: é ele, e não o modelo, que decide se o relatório vai a
`pronto` ou a `barrado` (ADR 0012).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from arco_ia import config
from arco_ia.relatorio import (
    INSTRUCAO,
    Prosa,
    escrever_prosa,
    frases,
    numeros,
    verificar,
)

PARTE: dict[str, Any] = {
    "cabecalho": {
        "restricao_id": "R-ACU",
        "texto": "CONTROLE DE CARREGAMENTO DA LT 230 KV AÇU III / MOSSORÓ II – C1(Z7)",
        "energia_cortada_mwh": 12_345.6,
        "periodo_inicio": "2025-09-01T00:00:00",
    },
    "por_revisao": [
        {
            "posicao": 1,
            "alavanca": "50 MW · 200 MWh · AÇU III",
            "vpl_reais": -20_000_000.0,
            "fracao_recuperada": 0.1,
            "payback_simples_anos": 18.0,
            "tir_aa": 0.05,
            "custo_por_mwh_reais": 300.0,
        },
        {
            "posicao": 2,
            "alavanca": "100 MW · 200 MWh · AÇU III",
            "vpl_reais": 10_400_000.0,
            "fracao_recuperada": 0.2,
            "payback_simples_anos": 12.0,
            "tir_aa": 0.1,
            "custo_por_mwh_reais": 250.0,
        },
    ],
    "derivados": {
        "diferencas": [{"delta_vpl_vs_base_reais": 30_400_000.0, "delta_fracao_vs_base": 0.1}],
        "sensibilidades": [
            {"delta_vpl_por_unidade_reais": 608_000.0, "delta_energia_por_unidade_mwh": 20.0}
        ],
        "variou": [{"campo": "bateria.potencia_mw", "valores": ["50 MW", "100 MW"]}],
        "ficou_parado": [{"campo": "financeira.taxa_desconto_aa", "valor": "0,08 ao ano"}],
    },
}


def _prosa(**muda: Any) -> Prosa:
    base: dict[str, Any] = {
        "leitura_geral": (
            "A simulação cobre 2 revisões de bateria em AÇU III. O VPL foi de R$ 20 milhões "
            "negativos na rev 1 a R$ 10,4 milhões na rev 2. A fração recuperada ficou entre 10% "
            "e 20%."
        ),
        "o_que_variou": [
            "A potência passou de 50 MW para 100 MW, e o VPL subiu R$ 30 milhões contra a base."
        ],
        "sensibilidade": (
            "Entre as rev 1 e 2, cada MW de potência somou R$ 608 mil de VPL e 20 MWh de "
            "energia recuperada."
        ),
        "fora_do_metodo": (
            "O resultado é contrafactual. Associação entre texto e equipamento não é causalidade."
        ),
        "perguntas_que_ficaram": ["Como o VPL responde a uma taxa de desconto diferente de 8%?"],
    }
    return Prosa(**(base | muda))


# Extração de números -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "valor", "unidade"),
    [
        ("R$ 10,4 milhões", 10_400_000.0, "R$"),
        ("R$ 608 mil", 608_000.0, "R$"),
        ("12.345,6 MWh", 12_345.6, "MWh"),
        ("100 MW", 100.0, "MW"),
        ("12%", 0.12, "fracao"),
        ("10 pontos percentuais", 0.1, "fracao"),
        ("18 anos", 18.0, "anos"),
        ("rev 3", 3.0, None),
        ("0,85", 0.85, None),
        ("0,08 ao ano", 0.08, "fracao"),
    ],
)
def test_numero_no_formato_brasileiro_com_unidade(
    texto: str, valor: float, unidade: str | None
) -> None:
    (n,) = numeros(texto)
    assert n.valor == pytest.approx(valor)
    assert n.unidade == unidade


def test_decimal_com_ponto_e_lido_pelo_valor() -> None:
    """Fora do formato pedido, mas conferido: "1.5 MW" não pode virar um 1 que casa com a rev 1."""
    (n,) = numeros("bateria de 1.5 MW")
    assert (n.valor, n.unidade, n.algarismos) == (1.5, "MW", 2)
    assert numeros("12.34%")[0].valor == pytest.approx(0.1234)
    assert numeros("foram 1.500 MWh.")[0].valor == 1500


def test_sinal_escrito_fica_marcado() -> None:
    assert [n.negativo for n in numeros("de −20 milhões para R$ -3 mil e 5 MW")] == [
        True,
        True,
        False,
    ]
    assert numeros("rev 1-3")[1].negativo is False


def test_digito_colado_em_letra_e_codigo_nao_numero() -> None:
    assert numeros("C1(Z7) e V7") == []


def test_frases_nao_cortam_no_milhar_nem_na_abreviacao() -> None:
    assert frases("Foram 1.000 MWh, +5 p.p. no total. Depois, 2.000 MWh.") == [
        "Foram 1.000 MWh, +5 p.p. no total.",
        "Depois, 2.000 MWh.",
    ]


# Verificador -------------------------------------------------------------------------------


def test_prosa_com_todos_os_numeros_na_parte_calculada_passa() -> None:
    v = verificar(_prosa(), PARTE)
    assert v.falhas == []
    assert v.resultado == "passou"
    assert v.numeros_na_prosa == v.encontrados > 0
    assert v.tolerancia.endswith("no mínimo 2 algarismos significativos")


def test_numero_sem_origem_barra_com_a_secao_e_o_trecho() -> None:
    v = verificar(
        _prosa(sensibilidade="Cada MW somou R$ 750 mil de VPL entre as rev 1 e 2."), PARTE
    )
    assert v.resultado == "falhou"
    (falha,) = v.falhas
    assert (falha.secao, falha.motivo, falha.numero) == (
        "sensibilidade",
        "sem_origem",
        "R$ 750 mil",
    )
    assert falha.trecho == "Cada MW somou R$ 750 mil de VPL entre as rev 1 e 2."
    assert v.encontrados == v.numeros_na_prosa - 1


def test_numero_certo_com_unidade_errada_nao_passa() -> None:
    """20 existe, mas como MWh por MW; "20 anos" não está em lugar nenhum."""
    v = verificar(_prosa(sensibilidade="O payback chegaria a 20 anos."), PARTE)
    assert [(f.motivo, f.numero) for f in v.falhas] == [("sem_origem", "20 anos")]


def test_arredondamento_a_dois_significativos_passa() -> None:
    """R$ 10,4 milhões escrito como R$ 10 milhões: 1,0 × 10⁷ dos dois lados."""
    v = verificar(_prosa(leitura_geral="O VPL da rev 2 foi de R$ 10 milhões."), PARTE)
    assert v.resultado == "passou"


def test_digito_escrito_alem_dos_dois_significativos_tem_de_estar_certo() -> None:
    """10,4 milhões existe. "10,6 milhões" arredonda para os mesmos 11 milhões a dois
    significativos, mas o modelo escreveu três, e o terceiro está errado."""
    certo = verificar(_prosa(leitura_geral="O VPL da rev 2 foi de R$ 10,4 milhões."), PARTE)
    assert certo.falhas == []
    errado = verificar(_prosa(leitura_geral="O VPL da rev 2 foi de R$ 10,6 milhões."), PARTE)
    assert [f.numero for f in errado.falhas] == ["R$ 10,6 milhões"]
    copia = verificar(_prosa(leitura_geral="A energia cortada foi de 12.346,6 MWh."), PARTE)
    assert [f.numero for f in copia.falhas] == ["12.346,6 MWh"]


def test_sinal_escrito_tem_de_bater_e_sem_sinal_vale_a_grandeza() -> None:
    """VPL da rev 1 é −20 milhões. "−R$ 20 milhões" e "R$ 20 milhões negativos" passam; "−R$ 10,4
    milhões" não, porque 10,4 milhões só existe positivo."""
    ok = verificar(_prosa(leitura_geral="O VPL da rev 1 foi de −R$ 20 milhões."), PARTE)
    assert ok.falhas == []
    errado = verificar(_prosa(leitura_geral="O VPL da rev 2 foi de −R$ 10,4 milhões."), PARTE)
    assert [f.numero for f in errado.falhas] == ["−R$ 10,4 milhões"]


def test_data_id_e_url_nao_viram_origem_de_numero() -> None:
    """A revisão criada em 2026-09-22T14:35 com id 57 não autoriza "35 meses" nem "57"."""
    parte = PARTE | {
        "trilha": [{"revisao_id": 57, "criada_em": "2026-09-22T14:35:12", "url": "/simulacoes/57"}]
    }
    falhas = verificar(_prosa(leitura_geral="O payback seria de 35 meses, ou 57 dias."), parte)
    assert [f.numero for f in falhas.falhas] == ["35", "57"]


def test_nada_variou_nao_aceita_item_em_o_que_variou() -> None:
    parte = PARTE | {"derivados": PARTE["derivados"] | {"variou": []}}
    v = verificar(_prosa(o_que_variou=["A potência variou pouco."]), parte)
    assert v.contagens["o_que_variou"] == (1, 0)
    assert [f.motivo for f in v.falhas] == ["tamanho"]


def test_porcentagem_que_o_modelo_calculou_nao_passa() -> None:
    """A fração dobrou de 10% para 20%: "100% a mais" é razão que a parte calculada não tem."""
    v = verificar(
        _prosa(leitura_geral="A fração recuperada cresceu 100% entre a rev 1 e a rev 2."), PARTE
    )
    assert [(f.motivo, f.numero) for f in v.falhas] == [("sem_origem", "100%")]


def test_porcentagem_que_esta_na_parte_calculada_passa() -> None:
    v = verificar(_prosa(leitura_geral="A TIR da rev 2 foi de 10% ao ano, contra 8%."), PARTE)
    assert v.resultado == "passou"


@pytest.mark.parametrize(
    "frase",
    [
        "Recomenda-se a rev 2.",
        "A rev 2 é a melhor opção.",
        "Deve-se instalar a bateria da rev 2.",
        "Instale 100 MW.",
        "A rev 2 é a vencedora.",
        "Vale a pena a rev 2.",
        "O relatório escolhe a rev 2.",
        "O relatório não faz escolha entre elas.",
    ],
)
def test_forma_de_recomendacao_barra(frase: str) -> None:
    v = verificar(_prosa(leitura_geral=frase), PARTE)
    assert v.resultado == "falhou"
    assert "forma_proibida" in {f.motivo for f in v.falhas}
    assert all(f.secao == "leitura_geral" for f in v.falhas if f.motivo == "forma_proibida")


def test_melhora_e_ordenacao_nao_sao_recomendacao() -> None:
    v = verificar(
        _prosa(leitura_geral="A rev 2 tem o maior VPL entre as cobertas, e a fração melhora."),
        PARTE,
    )
    assert v.resultado == "passou"


def test_secao_com_sete_frases_falha_por_tamanho() -> None:
    sete = " ".join(["Uma frase curta."] * 7)
    v = verificar(_prosa(leitura_geral=sete), PARTE)
    assert v.contagens["leitura_geral"] == (7, 6)
    tamanho = [f for f in v.falhas if f.motivo == "tamanho"]
    assert [(f.secao, f.numero) for f in tamanho] == [("leitura_geral", None)]


def test_um_item_por_campo_que_variou() -> None:
    dois = ["A potência variou de 50 MW para 100 MW.", "A rev 2 teve outro resultado."]
    v = verificar(_prosa(o_que_variou=dois), PARTE)
    assert v.contagens["o_que_variou"] == (2, 1)
    assert [f.motivo for f in v.falhas] == ["tamanho"]


def test_pergunta_que_e_instrucao_barra() -> None:
    v = verificar(_prosa(perguntas_que_ficaram=["Teste uma taxa de desconto diferente."]), PARTE)
    assert [(f.secao, f.motivo) for f in v.falhas] == [("perguntas_que_ficaram", "forma_proibida")]


def test_quatro_perguntas_passam_do_limite() -> None:
    quatro = [f"E a pergunta {n}?" for n in ("um", "dois", "três", "quatro")]
    v = verificar(_prosa(perguntas_que_ficaram=quatro), PARTE)
    assert v.contagens["perguntas_que_ficaram"] == (4, 3)
    assert [f.motivo for f in v.falhas] == ["tamanho"]


def test_contagens_cobrem_as_cinco_secoes() -> None:
    v = verificar(_prosa(), PARTE)
    assert v.contagens == {
        "leitura_geral": (3, 6),
        "o_que_variou": (1, 1),
        "sensibilidade": (1, 4),
        "fora_do_metodo": (2, 4),
        "perguntas_que_ficaram": (1, 3),
    }


# Analista ----------------------------------------------------------------------------------


class _Resposta:
    def __init__(self, texto: str) -> None:
        self.output_text = texto
        self.usage = None


class _Interactions:
    def __init__(self, texto: str) -> None:
        self._texto = texto
        self.chamadas: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _Resposta:
        self.chamadas.append(kwargs)
        return _Resposta(self._texto)


class _Cliente:
    def __init__(self, texto: str) -> None:
        self.interactions = _Interactions(texto)


def test_analista_faz_uma_chamada_com_a_parte_calculada_e_o_esquema() -> None:
    cliente = _Cliente(_prosa().model_dump_json())
    resposta = escrever_prosa(PARTE, cliente=cliente)
    assert resposta.saida == _prosa()
    assert resposta.registro.papel == "analista"
    assert resposta.registro.modelo == config.PAPEIS["analista"].modelo
    (chamada,) = cliente.interactions.chamadas
    assert chamada["system_instruction"] == INSTRUCAO
    assert json.dumps(PARTE, ensure_ascii=False) in chamada["input"]
    assert chamada["response_format"]["schema"] == Prosa.model_json_schema()


def test_a_instrucao_proibe_as_formas_da_adr_0012() -> None:
    for forma in ("melhor", "recomenda", "deve", "instale", "escolha"):
        assert f'"{forma}"' in INSTRUCAO


def test_explicar_deixou_de_existir() -> None:
    with pytest.raises(ModuleNotFoundError):
        __import__("arco_ia.explicar")


def test_premissa_exposta_casa_com_a_unidade_declarada_ao_lado() -> None:
    """A premissa traz `valor: "1"` e `unidade: "MW/MW"` em campos separados."""
    expostas = [
        {"id": "sensibilidade_equipamento", "valor": "1", "unidade": "MW/MW"},
        {"id": "preco_energia", "valor": "216", "unidade": "R$/MWh"},
    ]
    parte = PARTE | {"derivados": PARTE["derivados"] | {"premissas_expostas": expostas}}
    texto = "A sensibilidade de 1 MW por MW e o preço de R$ 216 por MWh não foram validados."
    v = verificar(_prosa(sensibilidade=texto), parte)
    assert [f.numero for f in v.falhas] == []


def test_porcentagem_casa_com_fracao_sem_unidade_so_entre_zero_e_um() -> None:
    """A eficiência parada vem como "0,85": "85%" casa. "100%" não casa com a posição 1."""
    parados = [
        *PARTE["derivados"]["ficou_parado"],
        {"campo": "bateria.eficiencia_ida_volta", "valor": "0,85"},
    ]
    parte = PARTE | {"derivados": PARTE["derivados"] | {"ficou_parado": parados}}
    assert verificar(_prosa(leitura_geral="A eficiência ficou em 85%."), parte).falhas == []
    falhas = verificar(_prosa(leitura_geral="A fração subiu 100%."), parte).falhas
    assert [f.numero for f in falhas] == ["100%"]


def test_custo_anual_e_preco_por_mwh_sao_moeda() -> None:
    """`_reais_ano` e `_reais_mwh` são R$: o preço de 216 por MWh não é 216 MWh."""
    parte = {
        "por_revisao": [{"opex_fixo_reais_ano": 5e6, "preco_energia_reais_mwh": 216.0}],
        "derivados": {"ficou_parado": [{"valor": "R$ 5.000.000 por ano"}]},
    }
    ok = verificar(
        _prosa(
            leitura_geral="O custo fixo ficou em R$ 5 milhões ao ano, e o preço em R$ 216 por MWh.",
            o_que_variou=[],
            sensibilidade="Sem par.",
            perguntas_que_ficaram=["E outro custo?"],
        ),
        parte,
    )
    assert ok.falhas == []
    errado = verificar(
        _prosa(
            leitura_geral="Foram 216 MWh.",
            o_que_variou=[],
            sensibilidade="Sem par.",
            perguntas_que_ficaram=["E outro custo?"],
        ),
        parte,
    )
    assert [f.numero for f in errado.falhas] == ["216 MWh"]


def test_numero_da_nota_nao_vira_origem_de_numero() -> None:
    """A nota é de quem salvou — o agente escreveu "espero VPL de 42 milhões". O número não foi
    calculado: a prosa que o repetir não passa. O resumo por template, que sai da configuração,
    continua valendo como origem."""
    parte = PARTE | {
        "trilha": [
            {
                "posicao": 2,
                "procedencia": "por_agente",
                "texto": "Rodada 1: espero VPL de 42 milhões e 77 MW de saturação.",
                "origem_do_texto": "nota_do_agente",
            },
            {
                "posicao": 1,
                "procedencia": "por_pessoa",
                "texto": "Bateria de 61 MW e 244 MWh em Açu III",
                "origem_do_texto": "resumo_da_configuracao",
            },
        ]
    }

    da_nota = verificar(_prosa(leitura_geral="A rev 2 esperava 42 milhões de VPL."), parte)
    do_resumo = verificar(_prosa(leitura_geral="A rev 1 tem bateria de 61 MW."), parte)

    assert [f.numero for f in da_nota.falhas] == ["42 milhões"]
    assert do_resumo.falhas == []
