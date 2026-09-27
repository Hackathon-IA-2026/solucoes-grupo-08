"""Configuração da API, lida do ambiente e do .env da raiz."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# O .env da raiz, por caminho absoluto: `make migrar` roda o Alembic de dentro de `api/`, e um
# caminho relativo faria a migration ignorar o .env e cair na porta padrão.
ENV = Path(__file__).resolve().parents[3] / ".env"


class Configuracao(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV, env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://arco:arco@localhost:5432/arco"
    snapshot_repo: str = "Hackathon-IA-2026/solucoes-grupo-08"
    # Origens de navegador que podem chamar a API, separadas por vírgula. `*` libera todas.
    cors_origens: str = "http://localhost:5173,http://127.0.0.1:5173"
    # O processo de `agentes`, que roda o explorador: a API o chama ao criar a exploração.
    arco_agentes_url: str = "http://localhost:8100"

    def origens(self) -> list[str]:
        return [origem.strip() for origem in self.cors_origens.split(",") if origem.strip()]


def configuracao() -> Configuracao:
    return Configuracao()
