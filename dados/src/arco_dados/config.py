"""Configuração do pacote: o que vem do ambiente ou do `.env` da raiz.

O mesmo padrão de `api/config.py` e `ia/config.py`. Sem isto, quem põe `GITHUB_TOKEN` no `.env`,
como o `.env.exemplo` manda, vê `make snapshot` falhar sem entender por quê: o comando lia só
`os.environ`, e `make` não exporta o `.env`.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV = Path(__file__).resolve().parents[3] / ".env"
"""O `.env` da raiz, por caminho absoluto."""


class Configuracao(BaseSettings):
    """Ambiente primeiro, `.env` depois, como manda o pydantic."""

    model_config = SettingsConfigDict(env_file=ENV, env_file_encoding="utf-8", extra="ignore")

    github_token: str = ""
    gh_token: str = ""
    snapshot_repo: str = ""


def token_do_github() -> str:
    """O token para baixar release, ou string vazia.

    `GH_TOKEN` é aceito porque é o nome que o `gh` usa, e quem já tem um exportado não deveria
    precisar duplicá-lo com outro nome.
    """
    c = Configuracao()
    return (c.github_token or c.gh_token).strip()


def repositorio_de_snapshots() -> str:
    """`dono/repo` de onde as releases de snapshot são baixadas."""
    return Configuracao().snapshot_repo.strip()
