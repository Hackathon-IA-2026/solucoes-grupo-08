"""O processo de `make agentes`: os dois perfis por HTTP (streamable HTTP), num servidor real.

Sobe o mesmo app que `arco-agentes servir` sobe, com a API falsa, numa porta livre, e fala com
ele como o cliente externo e o explorador falam: pela rede, em `/mcp` e `/explorador/mcp`. E
como a API fala ao criar uma exploração, em `/exploracoes/{tarefa_id}` (task 17.19).
"""

from __future__ import annotations

import asyncio
import socket
import threading
import time
from collections.abc import Coroutine, Iterator
from typing import Any

import httpx
import pytest
import uvicorn
from fastmcp import Client

from arco_agentes.servidor import Contexto, criar_app


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def no_ar(contexto: Contexto) -> Iterator[str]:
    porta = _porta_livre()
    servidor = uvicorn.Server(
        uvicorn.Config(criar_app(contexto), host="127.0.0.1", port=porta, log_level="warning")
    )
    linha = threading.Thread(target=servidor.run, daemon=True)
    linha.start()
    base = f"http://127.0.0.1:{porta}"
    for _ in range(100):
        try:
            if httpx.get(f"{base}/saude").status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.05)
    yield base
    servidor.should_exit = True
    linha.join(timeout=10)


def test_os_dois_perfis_respondem_pela_rede(no_ar: str) -> None:
    async def ferramentas(url: str) -> set[str]:
        async with Client(url) as cliente:
            return {t.name for t in await cliente.list_tools()}

    chat = asyncio.run(ferramentas(f"{no_ar}/mcp"))
    explorador = asyncio.run(ferramentas(f"{no_ar}/explorador/mcp"))

    assert "explorar_variacoes" in chat
    assert "disparar_lote" not in chat
    assert "disparar_lote" in explorador
    assert "explorar_variacoes" not in explorador
    assert httpx.get(f"{no_ar}/saude").json()["explorador"] == "/explorador/mcp"


def test_chamada_pela_rede_chega_a_api(no_ar: str, api_falsa) -> None:  # type: ignore[no-untyped-def]
    async def chamar() -> str:
        async with Client(f"{no_ar}/mcp") as cliente:
            resultado = await cliente.call_tool("ver_revisao", {"revisao_id": 1})
            return getattr(resultado.content[0], "text", "")

    assert "Revisão 1" in asyncio.run(chamar())
    assert api_falsa.pedidos("GET", "/simulacoes/1")


def _com_tarefa(contexto: Contexto) -> None:
    asyncio.run(contexto.api.criar_tarefa(1, {"pedido": "x", "teto": 30}))


def _recebe(recebidas: list[int]):  # type: ignore[no-untyped-def]
    """Um explorador que anota a tarefa na hora de ser solto e fica rodando até o servidor
    descer, para o segundo disparo achá-lo em curso."""

    def iniciar(tarefa: dict[str, Any]) -> Coroutine[Any, Any, None]:
        recebidas.append(tarefa["id"])
        return asyncio.sleep(3600)

    return iniciar


def test_a_api_dispara_a_exploracao_pela_rede(no_ar: str, contexto: Contexto) -> None:
    recebidas: list[int] = []
    contexto.iniciar_exploracao = _recebe(recebidas)
    _com_tarefa(contexto)

    primeira = httpx.post(f"{no_ar}/exploracoes/7")
    segunda = httpx.post(f"{no_ar}/exploracoes/7")

    assert (primeira.status_code, primeira.json()) == (202, {"tarefa_id": 7})
    assert recebidas == [7]
    assert segunda.status_code == 409
    assert "já roda neste processo" in segunda.json()["detail"]
    assert recebidas == [7], "o mesmo disparo não solta o explorador duas vezes"


def test_disparo_recusado_diz_por_que(no_ar: str, contexto: Contexto, api_falsa) -> None:  # type: ignore[no-untyped-def]
    recebidas: list[int] = []
    contexto.iniciar_exploracao = _recebe(recebidas)

    _com_tarefa(contexto)
    desconhecida = httpx.post(f"{no_ar}/exploracoes/8")
    assert desconhecida.status_code == 404

    api_falsa.tarefa["estado"] = "concluida"
    terminada = httpx.post(f"{no_ar}/exploracoes/7")
    assert terminada.status_code == 409
    assert terminada.json()["detail"] == "a exploração 7 já terminou: concluida"

    contexto.iniciar_exploracao = None
    contexto.explorador_indisponivel = "sem GEMINI_API_KEY, o explorador não roda neste servidor"
    sem_explorador = httpx.post(f"{no_ar}/exploracoes/7")
    assert sem_explorador.status_code == 503
    assert sem_explorador.json()["detail"].startswith("sem GEMINI_API_KEY")
    assert recebidas == []
