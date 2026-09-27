"""O que mudou de uma revisão para a anterior, e o rótulo que a tela usa para dizer isso."""

from __future__ import annotations

from arco_api.mudancas import ROTULOS_PREMISSA, descrever, resumir
from arco_motor.premissas import PREMISSAS_PADRAO

CONFIG = {
    "modalidade": "equipamento",
    "equipamento": {
        "tipo": "adicao_circuito",
        "cod_equipamento": "LT-1",
        "ganho_limite_mw": 40.0,
    },
    "financeira": {"cenario": "referencia", "taxa_desconto_aa": 0.08, "capex_reais": 1000.0},
}


def test_sem_anterior_e_a_original() -> None:
    assert descrever(CONFIG, None, "2026-09-15", None, None).startswith("Original")


def test_campo_alterado_sai_com_rotulo_e_os_dois_valores() -> None:
    depois = {
        **CONFIG,
        "equipamento": {**CONFIG["equipamento"], "ganho_limite_mw": 25.0},  # type: ignore[dict-item]
    }
    frase = descrever(depois, CONFIG, "2026-09-15", "2026-09-15", 1)
    assert frase == "Ganho de limite: 40 → 25."


def test_snapshot_diferente_com_parametros_iguais() -> None:
    frase = descrever(CONFIG, CONFIG, "2026-10-01", "2026-09-15", 2)
    assert frase == "Snapshot do ONS diferente; parâmetros iguais à rev 2."


def test_muita_mudanca_vira_contagem() -> None:
    """A coluna é uma linha de tabela, não um parágrafo."""
    depois = {
        "modalidade": "combinada",
        "equipamento": {
            "tipo": "adicao_circuito",
            "cod_equipamento": "LT-2",
            "ganho_limite_mw": 25.0,
        },
        "financeira": {"cenario": "otimista", "taxa_desconto_aa": 0.12, "capex_reais": 2000.0},
    }
    frase = descrever(depois, CONFIG, "2026-09-15", "2026-09-15", 1)
    assert frase.endswith("e mais 2.")
    assert frase.count(";") == 4


def test_bloco_que_nasce_ou_some_aparece() -> None:
    """Trocar de modalidade acrescenta ou tira um bloco inteiro, e isso é mudança."""
    com_bateria = {
        **CONFIG,
        "modalidade": "combinada",
        "bateria": {"potencia_mw": 50.0, "capacidade_mwh": 200.0, "subestacao": "ACU III"},
    }
    frase = descrever(com_bateria, CONFIG, "2026-09-15", "2026-09-15", 1)
    assert "Potência da bateria: vazio → 50" in frase


def _premissa(id: str, valor: object) -> dict[str, object]:
    """Uma premissa como ela fica salva na revisão: só `valor` importa para a comparação."""
    return {"id": id, "descricao": id, "valor": valor, "fonte": "teste", "status": "proposta"}


def test_toda_premissa_do_motor_tem_rotulo() -> None:
    """Premissa sem rótulo sairia na tela pelo id cru, como `bateria_carrega_so_do_corte`."""
    assert set(ROTULOS_PREMISSA) == set(PREMISSAS_PADRAO.itens)


def test_so_a_fonte_muda_e_a_coluna_diz_qual() -> None:
    """Era o caso que saía como "mesmos parâmetros" com o número diferente ao lado."""
    antes = {"fonte_geracao": _premissa("fonte_geracao", "eolica")}
    depois = {"fonte_geracao": _premissa("fonte_geracao", "ambas")}
    frase = descrever(CONFIG, CONFIG, "2026-09-15", "2026-09-15", 1, depois, antes)
    assert frase == "Fonte de geração: eolica → ambas."


def test_booleano_de_premissa_sai_em_portugues() -> None:
    antes = {"correcao_minutos": _premissa("correcao_minutos", True)}
    depois = {"correcao_minutos": _premissa("correcao_minutos", False)}
    frase = descrever(CONFIG, CONFIG, "2026-09-15", "2026-09-15", 1, depois, antes)
    assert frase == "Correção pelos minutos: sim → não."


def test_premissa_que_nasce_com_a_modalidade_nao_vira_mudanca() -> None:
    """`premissas_usadas` carimba premissa conforme a modalidade, então trocar bateria por
    combinada faz nascer `ordem_combinada`. Reportá-la seria chamar de mudança própria o que é
    consequência da modalidade, que a linha da modalidade já diz."""
    antes = {"fonte_geracao": _premissa("fonte_geracao", "eolica")}
    depois = {
        "fonte_geracao": _premissa("fonte_geracao", "eolica"),
        "ordem_combinada": _premissa("ordem_combinada", "equipamento_depois_bateria"),
    }
    frase = descrever(CONFIG, CONFIG, "2026-09-15", "2026-09-15", 1, depois, antes)
    assert "Ordem" not in frase
    assert frase.startswith("Recalculada com os mesmos parâmetros")


def test_premissa_igual_nos_dois_lados_nao_vira_mudanca() -> None:
    iguais = {"fonte_geracao": _premissa("fonte_geracao", "eolica")}
    frase = descrever(CONFIG, CONFIG, "2026-09-15", "2026-09-15", 1, iguais, dict(iguais))
    assert frase.startswith("Recalculada com os mesmos parâmetros")


def test_resumir_bateria_com_cenario() -> None:
    config = {
        "modalidade": "bateria",
        "bateria": {"potencia_mw": 50.0, "capacidade_mwh": 200.0, "subestacao": "Açu III"},
        "financeira": {"cenario": "referencia"},
    }
    assert resumir(config) == "Bateria de 50 MW e 200 MWh em Açu III, cenário de referência"


def test_resumir_equipamento_e_combinada() -> None:
    assert resumir(CONFIG) == "Circuito novo em LT-1 com ganho de 40 MW, cenário de referência"
    combinada = CONFIG | {
        "modalidade": "combinada",
        "bateria": {"potencia_mw": 12.5, "capacidade_mwh": 50.0, "subestacao": "SE X"},
        "financeira": {"cenario": "otimista"},
    }
    assert resumir(combinada) == (
        "Circuito novo em LT-1 com ganho de 40 MW e bateria de 12,5 MW e 50 MWh em SE X, "
        "cenário otimista"
    )
