"""`arco-agentes`: sobe o MCP do ARCO (`servir`) e roda uma exploração sem cliente externo
(`explorar`)."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Annotated, Any

import httpx
import typer

from arco_agentes.api import ClienteDaApi, ErroDaApi
from arco_agentes.config import CAMINHO_DO_CHAT, CAMINHO_DO_EXPLORADOR, Configuracao
from arco_agentes.servidor import Contexto, criar_app, em_segundo_plano

app = typer.Typer(help="MCP do ARCO e o explorador de variações.", no_args_is_help=True)


def _explorar_em_fundo(config: Configuracao, url_do_mcp: str) -> Any:
    """O que `explorar_variacoes` chama com a tarefa criada: a exploração com o modelo, pelo
    MCP deste mesmo processo."""
    from arco_agentes.explorador import explorar_com

    async def iniciar(tarefa: dict[str, Any]) -> None:
        await explorar_com(config.api_url, url_do_mcp, int(tarefa["id"]))

    return iniciar


@app.command()
def servir(
    porta: Annotated[int | None, typer.Option(help="Padrão: ARCO_MCP_PORTA, ou 8100.")] = None,
    host: Annotated[str, typer.Option(help="Só a máquina: o túnel alcança por localhost.")] = (
        "127.0.0.1"
    ),
) -> None:
    """Sobe o MCP: o perfil do chat em /mcp e o do explorador em /explorador/mcp."""
    import uvicorn

    from arco_ia.chamada import configurar_rastro
    from arco_ia.config import VARIAVEL_DA_CHAVE, chave

    # O Strands emite rastro OpenTelemetry pelo provedor global: o mesmo exportador da camada
    # de chamada de `ia`, Langfuse com as chaves e console sem elas (ADR 0013).
    configurar_rastro()
    config = Configuracao()
    porta = porta or config.mcp_porta
    contexto = Contexto(api=ClienteDaApi(config.api_url), config=config)
    if chave():
        contexto.iniciar_exploracao = _explorar_em_fundo(
            config, f"http://127.0.0.1:{porta}{CAMINHO_DO_EXPLORADOR}"
        )
    else:
        contexto.explorador_indisponivel = (
            f"sem {VARIAVEL_DA_CHAVE}, o explorador não roda neste servidor"
        )
    typer.echo(
        f"MCP do ARCO em http://{host}:{porta}{CAMINHO_DO_CHAT} (chat) e "
        f"{CAMINHO_DO_EXPLORADOR} (explorador), falando com a API em {config.api_url}. "
        + ("Explorador pronto." if chave() else f"Explorador desligado: falta {VARIAVEL_DA_CHAVE}.")
    )
    uvicorn.run(criar_app(contexto), host=host, port=porta)


@app.command()
def explorar(
    simulacao_id: int,
    pedido: str,
    teto: Annotated[int, typer.Option(min=1, max=30, help="Revisões que pode salvar.")] = 30,
    referencia: Annotated[
        bool, typer.Option(help="A árvore de referência, sem modelo, no lugar do agente.")
    ] = False,
    revisao_partida: Annotated[
        int | None, typer.Option(help="De onde parte. Padrão: a revisão mais nova.")
    ] = None,
    alavanca: Annotated[
        list[str] | None, typer.Option(help="Só esta alavanca; repita para mais de uma.")
    ] = None,
) -> None:
    """Roda uma exploração até o fim, sem cliente externo: cria a tarefa, decide as rodadas e
    pede o relatório. Usa o MCP em ARCO_MCP_PORTA se estiver no ar; senão sobe um aqui."""
    from arco_ia.chamada import configurar_rastro

    configurar_rastro()
    config = Configuracao()
    with _mcp(config) as url_do_mcp:
        asyncio.run(
            _explorar(
                config,
                url_do_mcp,
                simulacao_id,
                pedido,
                teto,
                referencia,
                revisao_partida,
                alavanca,
            )
        )


@contextlib.contextmanager
def _mcp(config: Configuracao):  # type: ignore[no-untyped-def]
    local = f"http://127.0.0.1:{config.mcp_porta}"
    try:
        no_ar = httpx.get(f"{local}/saude", timeout=2).status_code == 200
    except httpx.HTTPError:
        no_ar = False
    if no_ar:
        yield f"{local}{CAMINHO_DO_EXPLORADOR}"
        return
    contexto = Contexto(api=ClienteDaApi(config.api_url), config=config)
    with em_segundo_plano(contexto) as base:
        yield f"{base}{CAMINHO_DO_EXPLORADOR}"


async def _explorar(
    config: Configuracao,
    url_do_mcp: str,
    simulacao_id: int,
    pedido: str,
    teto: int,
    referencia: bool,
    revisao_partida: int | None,
    alavancas: list[str] | None,
) -> None:
    from arco_agentes import resumos
    from arco_agentes.explorador import explorar_com
    from arco_agentes.referencia import ArvoreDeReferencia

    api = ClienteDaApi(config.api_url)
    try:
        tarefa = await api.criar_tarefa(
            simulacao_id,
            {
                "pedido": pedido,
                "teto": teto,
                "revisao_partida_id": revisao_partida,
                "alavancas": alavancas,
                # A CLI roda o próprio explorador, com o modelo ou a árvore de referência.
                "disparar": False,
            },
        )
    except ErroDaApi as erro:
        await api.fechar()
        raise typer.Exit(_falha(erro)) from erro
    link = config.link_ver_processamento(simulacao_id, tarefa["id"])
    typer.echo(f"Exploração {tarefa['id']} criada. Ver processamento: {link}")
    exploracao = await explorar_com(
        config.api_url,
        url_do_mcp,
        tarefa["id"],
        ArvoreDeReferencia() if referencia else None,
    )
    for rodada, decisao in enumerate(exploracao.decisoes, start=1):
        typer.echo(f"Rodada {rodada}: {decisao['acao']}. {decisao['porque']}")
    texto, _ = resumos.andamento(await api.ver_tarefa(tarefa["id"]), link)
    await api.fechar()
    typer.echo(texto)
    if exploracao.erro:
        raise typer.Exit(_falha(exploracao.erro))


def _falha(erro: object) -> int:
    typer.echo(f"Falhou: {erro}", err=True)
    return 1


@app.callback()
def _principal() -> None:
    """Sem isto o Typer trataria o único comando como o programa inteiro."""


def principal() -> None:
    app()
