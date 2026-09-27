"""O ícone do ARCO no cliente MCP: a logo do painel (`web/public/favicon.svg`).

Vai em `serverInfo.icons`, que o cliente recebe ao conectar. Sem ele, o cliente procura um ícone
pelo endereço do MCP e, sem achar, cai no do domínio de cima, que pode ser de outro serviço. O
PNG vem primeiro, porque é o formato que todo cliente que desenha ícone tem de aceitar; o SVG vai
junto, para quem aceita. Os dois vão embutidos (`data:`), sem depender de outro endereço no ar.
"""

from __future__ import annotations

import base64
from pathlib import Path

from mcp.types import Icon

PASTA = Path(__file__).parent


def _embutido(arquivo: str, tipo: str) -> str:
    return f"data:{tipo};base64," + base64.b64encode((PASTA / arquivo).read_bytes()).decode()


ICONES = [
    Icon(src=_embutido("icone.png", "image/png"), mime_type="image/png", sizes=["256x256"]),
    Icon(src=_embutido("icone.svg", "image/svg+xml"), mime_type="image/svg+xml", sizes=["any"]),
]
"""`icone.png` é o `icone.svg` desenhado em 256 px, com fundo transparente."""
