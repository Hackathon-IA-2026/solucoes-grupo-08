"""Onde a API, o MCP e o painel estão. Lido do ambiente ou do `.env` da raiz."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV = Path(__file__).resolve().parents[3] / ".env"
"""O `.env` da raiz, por caminho absoluto, como em `api` e `ia`."""

CAMINHO_DO_CHAT = "/mcp"
"""Onde o cliente externo (Claude web, ChatGPT web) conecta: o perfil do chat."""

CAMINHO_DO_EXPLORADOR = "/explorador/mcp"
"""Onde o explorador conecta, por `localhost`: o perfil sem as ferramentas de disparo."""

TELA_VER_PROCESSAMENTO = "/simulacoes/{simulacao_id}/exploracoes/{tarefa_id}"
"""A rota da tela Ver processamento no painel, no padrão das rotas de lá
(`/simulacoes/{simulacao_id}/relatorios/{relatorio_id}`). A tela é da task 17.17: se ela ficar
em outro caminho, é aqui que muda."""


class Configuracao(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV, env_file_encoding="utf-8", env_prefix="ARCO_", extra="ignore"
    )

    api_url: str = "http://localhost:8000"
    """`ARCO_API_URL`: a API que o MCP chama. O MCP roda na mesma máquina."""
    mcp_porta: int = 8100
    """`ARCO_MCP_PORTA`: a porta do MCP, que o túnel expõe num segundo hostname."""
    painel_url: str = "http://localhost:5173"
    """`ARCO_PAINEL_URL`: o painel, para o link Ver processamento que o chat mostra."""

    def link_ver_processamento(self, simulacao_id: int, tarefa_id: int) -> str:
        caminho = TELA_VER_PROCESSAMENTO.format(simulacao_id=simulacao_id, tarefa_id=tarefa_id)
        return self.painel_url.rstrip("/") + caminho
