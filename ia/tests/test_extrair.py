"""Extração por modelo, com o SDK substituído: a suíte roda sem chave e sem rede.

O que se prova aqui é o contorno — tipagem, recusa de alucinação, rastro do modelo. Se o modelo
acerta o conteúdo é a conferência contra o cadastro que diz, e ela mora em `dados`.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from arco_ia import IndisponivelSemChave, config
from arco_ia.extrair import Extracao, NomeForaDoTexto, extrair

TEXTO = (
    "Controle de inequação: CONTROLE DE CARREGAMENTO DA LT 230 KV AÇU III / MOSSORÓ II – "
    "C1(Z7) PARA CONTINGÊNCIA DA LT 500 KV AÇU III / JAGUARUANA II – C1(V7) - IO-ON.NE.5NE"
)


class _Resposta:
    def __init__(self, texto: str) -> None:
        self.output_text = texto


class _Interactions:
    def __init__(self, devolve: dict[str, Any]) -> None:
        self._devolve = devolve
        self.chamada: dict[str, Any] = {}
        self.vezes = 0

    def create(self, **kwargs: Any) -> _Resposta:
        self.chamada = kwargs
        self.vezes += 1
        return _Resposta(json.dumps(self._devolve))


class _Cliente:
    def __init__(self, devolve: dict[str, Any]) -> None:
        self.interactions = _Interactions(devolve)


DOIS_EQUIPAMENTOS = {
    "equipamentos": [
        {
            "tensao_kv": 230,
            "de": "AÇU III",
            "para": "MOSSORÓ II",
            "ordem_circuito": 1,
            "codigo_circuito": "Z7",
            "papel": "monitorado",
        },
        {
            "tensao_kv": 500,
            "de": "AÇU III",
            "para": "JAGUARUANA II",
            "ordem_circuito": 1,
            "codigo_circuito": "V7",
            "papel": "contingenciado",
        },
    ]
}


def test_saida_vem_tipada_e_com_o_papel_de_cada_equipamento() -> None:
    lido = extrair(TEXTO, cliente=_Cliente(DOIS_EQUIPAMENTOS))
    assert [e.papel for e in lido.equipamentos] == ["monitorado", "contingenciado"]
    assert lido.equipamentos[0].codigo_circuito == "Z7"


def test_extracao_carrega_o_modelo_e_a_versao_do_prompt() -> None:
    """Sem esse rastro não há como saber o que reprocessar quando o modelo ou o prompt mudar."""
    lido = extrair(TEXTO, cliente=_Cliente(DOIS_EQUIPAMENTOS))
    assert (lido.modelo, lido.versao_prompt) == (config.MODELO, config.VERSAO_PROMPT)


def test_nome_que_nao_esta_no_texto_e_erro_e_nao_achado() -> None:
    """Vínculo errado não estoura erro sozinho: vira VPL errado com cara de número bom."""
    inventado = {
        "equipamentos": [
            {
                "tensao_kv": 230,
                "de": "SUBESTAÇÃO QUE NÃO EXISTE",
                "para": "MOSSORÓ II",
                "ordem_circuito": 1,
                "codigo_circuito": "Z7",
                "papel": "monitorado",
            }
        ]
    }
    cliente = _Cliente(inventado)
    with pytest.raises(NomeForaDoTexto, match="não aparece no texto"):
        extrair(TEXTO, cliente=cliente)
    assert cliente.interactions.vezes == 1, "conferência de conteúdo não volta ao modelo"


def test_lista_vazia_e_resposta_valida() -> None:
    """Texto sem linha citada devolve vazio. Não inventar é resposta, não falha."""
    assert extrair(TEXTO, cliente=_Cliente({"equipamentos": []})).equipamentos == []


def test_papel_fora_do_vocabulario_nao_passa() -> None:
    torto = {
        "equipamentos": [
            {
                "tensao_kv": 230,
                "de": "AÇU III",
                "para": "MOSSORÓ II",
                "ordem_circuito": 1,
                "codigo_circuito": "Z7",
                "papel": "inventado",
            }
        ]
    }
    with pytest.raises(ValueError):
        extrair(TEXTO, cliente=_Cliente(torto))


def test_a_chamada_pede_saida_estruturada_e_leva_o_texto() -> None:
    cliente = _Cliente(DOIS_EQUIPAMENTOS)
    extrair(TEXTO, cliente=cliente)
    chamada = cliente.interactions.chamada
    assert chamada["model"] == config.MODELO
    assert TEXTO in chamada["input"]
    assert chamada["response_format"]["schema"] == Extracao.model_json_schema()


def test_sem_chave_falha_alto_dizendo_o_que_faltou(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "chave", lambda: "")
    with pytest.raises(IndisponivelSemChave, match=config.VARIAVEL_DA_CHAVE):
        config.cliente()


def test_chave_do_env_da_raiz_e_enxergada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quem põe a chave no `.env` tem de ver funcionar: só a `api` carregava o arquivo."""
    monkeypatch.setenv(config.VARIAVEL_DA_CHAVE, "chave-de-teste")
    assert config.chave() == "chave-de-teste"
