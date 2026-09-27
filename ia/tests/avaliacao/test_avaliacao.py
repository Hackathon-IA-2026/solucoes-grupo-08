"""Casos de ouro que o modelo de verdade tem de passar (feature 17, task 17.5).

Vigia o analista e compara modelos: a prosa de cada caso passa no verificador, respeita os
limites e não contém forma proibida — e o verificador é o mesmo que decide `pronto` ou
`barrado` na API. Os casos estão em `casos/`, gerados por `gerar_casos.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arco_ia import config
from arco_ia.relatorio import escrever_prosa, verificar

CASOS = sorted(Path(__file__).with_name("casos").glob("*.json"))


@pytest.mark.lento
@pytest.mark.parametrize("caso", CASOS, ids=[c.stem for c in CASOS])
def test_prosa_do_modelo_passa_no_verificador(caso: Path, registrar: Any) -> None:
    if not config.chave():
        pytest.skip(f"sem {config.VARIAVEL_DA_CHAVE}")
    parte = json.loads(caso.read_text(encoding="utf-8"))
    resposta = escrever_prosa(parte)
    verificacao = verificar(resposta.saida, parte)
    registro = resposta.registro
    registrar(
        {
            "caso": caso.stem,
            "modelo": registro.modelo,
            "versao_prompt": registro.versao_prompt,
            "resultado": verificacao.resultado,
            "numeros_na_prosa": verificacao.numeros_na_prosa,
            "encontrados": verificacao.encontrados,
            "tokens_entrada": registro.tokens_entrada,
            "tokens_saida": registro.tokens_saida,
            "latencia_s": registro.latencia_s,
            "tentativas": registro.tentativas,
            "falhas": [f.model_dump() for f in verificacao.falhas],
            "contagens": verificacao.contagens,
            "prosa": resposta.saida.model_dump(),
        }
    )
    assert verificacao.falhas == [], json.dumps(
        [f.model_dump() for f in verificacao.falhas], ensure_ascii=False, indent=2
    )


def test_os_quatro_casos_existem() -> None:
    assert [c.stem for c in CASOS] == [
        "bateria_sete_revisoes",
        "combinada",
        "exploracao_com_ramos",
        "uma_revisao",
    ]


def test_casos_estao_em_dia_com_o_gerador() -> None:
    """Mudou o motor ou o formato: rode `gerar_casos.py` e confira o diff antes de gravar."""
    import importlib.util

    espec = importlib.util.spec_from_file_location(
        "gerar_casos", Path(__file__).with_name("gerar_casos.py")
    )
    assert espec is not None and espec.loader is not None
    gerador = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(gerador)
    for nome, caso in gerador.casos().items():
        gravado = json.loads((Path(__file__).with_name("casos") / f"{nome}.json").read_text())
        assert gravado == json.loads(json.dumps(caso, ensure_ascii=False)), nome
