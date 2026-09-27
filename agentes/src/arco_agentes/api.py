"""Cliente HTTP da API do ARCO. É o único caminho de `agentes` para o dado: nada aqui importa
`arco_api`, e só a API toca o banco ([ADR 0013](../../../docs/adr/0013-pilha-dos-agentes.md)).

Cada método é uma rota, com o JSON da API de volta como veio. Resumir para o modelo é de
`resumos.py`; conferir regra de negócio é da API, que devolve 422 e 409 com o motivo em
`detail`, e esse motivo chega a quem chamou em `ErroDaApi`.
"""

from __future__ import annotations

from typing import Any

import httpx

TEMPO_LIMITE_S = 120.0
"""Uma variação calcula um ano de série: segundos, não minutos. O limite só impede que uma API
travada segure a ferramenta para sempre."""


class ErroDaApi(Exception):
    """A API recusou ou falhou. `detalhe` é o `detail` dela, que já diz o porquê."""

    def __init__(self, status: int, detalhe: Any) -> None:
        self.status = status
        self.detalhe = detalhe
        super().__init__(f"{status}: {self.mensagem}")

    @property
    def mensagem(self) -> str:
        if isinstance(self.detalhe, dict):
            return str(self.detalhe.get("mensagem") or self.detalhe)
        if isinstance(self.detalhe, list):
            # Erro de validação do FastAPI: uma entrada por campo.
            return "; ".join(
                f"{'.'.join(str(p) for p in e.get('loc', [])[1:])}: {e.get('msg')}"
                for e in self.detalhe
                if isinstance(e, dict)
            )
        return str(self.detalhe)


class ClienteDaApi:
    """As rotas que o MCP usa. `transporte` existe para o teste pôr uma API falsa no lugar."""

    def __init__(self, base_url: str, transporte: httpx.AsyncBaseTransport | None = None) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url, timeout=TEMPO_LIMITE_S, transport=transporte
        )

    async def fechar(self) -> None:
        await self._http.aclose()

    async def _pedir(self, metodo: str, caminho: str, **kwargs: Any) -> Any:
        try:
            resposta = await self._http.request(metodo, caminho, **kwargs)
        except httpx.HTTPError as erro:
            raise ErroDaApi(503, f"a API não respondeu em {self._http.base_url}: {erro}") from erro
        if resposta.status_code >= 400:
            try:
                detalhe = resposta.json().get("detail", resposta.text)
            except ValueError:
                detalhe = resposta.text
            raise ErroDaApi(resposta.status_code, detalhe)
        return resposta.json()

    # Consultas -----------------------------------------------------------------------------

    async def listar_restricoes(self, fonte: str, limite: int) -> dict[str, Any]:
        return await self._pedir("GET", "/restricoes", params={"fonte": fonte, "limite": limite})

    async def ver_restricao(self, restricao_id: str, fonte: str) -> dict[str, Any]:
        return await self._pedir("GET", f"/restricoes/{restricao_id}", params={"fonte": fonte})

    async def listar_simulacoes(self, restricao_id: str | None) -> list[dict[str, Any]]:
        params = {"restricao_id": restricao_id} if restricao_id else {}
        return await self._pedir("GET", "/simulacoes", params=params)

    async def ver_revisao(self, revisao_id: int) -> dict[str, Any]:
        return await self._pedir("GET", f"/simulacoes/{revisao_id}")

    async def listar_relatorios(self, simulacao_id: int) -> list[dict[str, Any]]:
        return await self._pedir("GET", f"/simulacoes/{simulacao_id}/relatorios")

    async def ver_relatorio(self, simulacao_id: int, relatorio_id: int) -> dict[str, Any]:
        return await self._pedir("GET", f"/simulacoes/{simulacao_id}/relatorios/{relatorio_id}")

    # Ações ---------------------------------------------------------------------------------

    async def montar(self, restricao_id: str, parametros: dict[str, Any]) -> dict[str, Any]:
        params = {k: v for k, v in parametros.items() if v is not None}
        return await self._pedir("GET", f"/restricoes/{restricao_id}/montar", params=params)

    async def salvar(self, pedido: dict[str, Any]) -> dict[str, Any]:
        return await self._pedir("POST", "/simulacoes", json=pedido)

    async def salvar_variacao(self, simulacao_id: int, pedido: dict[str, Any]) -> dict[str, Any]:
        return await self._pedir("POST", f"/simulacoes/{simulacao_id}/variacoes", json=pedido)

    async def pedir_relatorio(self, simulacao_id: int) -> dict[str, Any]:
        return await self._pedir("POST", f"/simulacoes/{simulacao_id}/relatorios")

    # Exploração ----------------------------------------------------------------------------

    async def resumo_da_exploracao(
        self, simulacao_id: int, revisao_partida_id: int | None, alavancas: list[str] | None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if revisao_partida_id is not None:
            params["revisao_partida_id"] = revisao_partida_id
        if alavancas:
            params["alavancas"] = alavancas
        return await self._pedir("GET", f"/simulacoes/{simulacao_id}/exploracao", params=params)

    async def criar_tarefa(self, simulacao_id: int, pedido: dict[str, Any]) -> dict[str, Any]:
        return await self._pedir("POST", f"/simulacoes/{simulacao_id}/tarefas", json=pedido)

    async def ver_tarefa(self, tarefa_id: int) -> dict[str, Any]:
        return await self._pedir("GET", f"/tarefas/{tarefa_id}")

    async def registrar_evento(self, tarefa_id: int, evento: dict[str, Any]) -> dict[str, Any]:
        return await self._pedir("POST", f"/tarefas/{tarefa_id}/eventos", json=evento)
