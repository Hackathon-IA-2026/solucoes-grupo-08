"""Gera contratos/openapi.json a partir da aplicação. `python -m arco_api.contrato`."""

from __future__ import annotations

import json
from pathlib import Path

from arco_api.main import app

RAIZ = Path(__file__).resolve().parents[3]
DESTINO = RAIZ / "contratos" / "openapi.json"


def gerar(destino: Path = DESTINO) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    conteudo = json.dumps(app.openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    destino.write_text(conteudo, encoding="utf-8")
    return destino


if __name__ == "__main__":
    print(gerar())
