"""Conjunto de avaliação: roda só quando pedido, e imprime o que cada caso custou.

`uv run pytest -m lento ia/tests/avaliacao`. Sem `-m lento` os casos saem pulados, mesmo com a
chave no `.env`: `make test` não deve chamar o modelo a cada execução. Sem a chave, pulados
também, e nunca como falha.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

EXECUCOES = Path(__file__).with_name("execucoes")
LINHAS: list[dict[str, Any]] = []


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if "lento" in (config.getoption("markexpr") or ""):
        return
    pular = pytest.mark.skip(reason="avaliação com modelo de verdade: rode com -m lento")
    for item in items:
        if "lento" in item.keywords:
            item.add_marker(pular)


@pytest.fixture
def registrar() -> Any:
    return LINHAS.append


def pytest_terminal_summary(terminalreporter: Any) -> None:
    if not LINHAS:
        return
    terminalreporter.section("avaliação do analista")
    cabecalho = f"{'caso':<24}{'resultado':<10}{'números':>8}{'achados':>8}{'tokens':>10}{'s':>7}"
    terminalreporter.write_line(cabecalho)
    for linha in LINHAS:
        terminalreporter.write_line(
            f"{linha['caso']:<24}{linha['resultado']:<10}{linha['numeros_na_prosa']:>8}"
            f"{linha['encontrados']:>8}{linha['tokens_entrada'] + linha['tokens_saida']:>10}"
            f"{linha['latencia_s']:>7.1f}"
        )
    EXECUCOES.mkdir(exist_ok=True)
    destino = EXECUCOES / f"{datetime.now():%Y-%m-%d_%H%M%S}.json"
    destino.write_text(json.dumps(LINHAS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    terminalreporter.write_line(f"gravado em {destino}")
