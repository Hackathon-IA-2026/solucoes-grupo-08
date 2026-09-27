"""Conjunto de avaliação do explorador: roda só quando pedido, e imprime a comparação.

`uv run pytest -m lento agentes/tests/avaliacao`, com `GEMINI_API_KEY` e `ARCO_TEST_DATABASE_URL`
apontando para um Postgres **descartável**, que a avaliação zera. Sem `-m lento`, os casos saem
pulados, mesmo com a chave: `make test` não chama o modelo. Sem a chave ou sem o banco,
pulados também, e nunca como falha.
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
    terminalreporter.section("avaliação do explorador")
    cabecalho = (
        f"{'caso':<12}{'decisor':<12}{'achou':>6}{'intervalo':>14}{'largura':>9}"
        f"{'revisões':>10}{'recusas':>9}{'rodadas':>9}{'tokens':>9}{'s':>7}"
    )
    terminalreporter.write_line(cabecalho)
    for linha in LINHAS:
        intervalo = (
            f"{linha['antes']:g} a {linha['depois']:g}" if linha["antes"] is not None else "-"
        )
        terminalreporter.write_line(
            f"{linha['caso']:<12}{linha['decisor']:<12}{'sim' if linha['achou'] else 'não':>6}"
            f"{intervalo:>14}{linha['largura'] if linha['largura'] is not None else '-':>9}"
            f"{linha['revisoes']:>10}{linha['recusas']:>9}{linha['rodadas']:>9}"
            f"{linha['tokens']:>9}{linha['tempo_s']:>7.0f}"
        )
    EXECUCOES.mkdir(exist_ok=True)
    destino = EXECUCOES / f"{datetime.now():%Y-%m-%d_%H%M%S}.json"
    destino.write_text(json.dumps(LINHAS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    terminalreporter.write_line(f"gravado em {destino}")
