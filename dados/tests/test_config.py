"""A chave do GitHub sai do `.env` da raiz, não só do shell.

Quem põe `GITHUB_TOKEN` no `.env`, como o `.env.exemplo` manda, via `make snapshot` falhar sem
entender por quê: `releases.py` lia só `os.environ`, e o `make` não exporta o `.env`. O mesmo
defeito que `ia/config.py` já tinha consertado para a chave do modelo.
"""

from __future__ import annotations

import pytest

from arco_dados import config


@pytest.fixture(autouse=True)
def sem_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    """O teste não pode depender do que está exportado na máquina de quem roda."""
    for nome in ("GITHUB_TOKEN", "GH_TOKEN", "SNAPSHOT_REPO"):
        monkeypatch.delenv(nome, raising=False)


def _com_env(monkeypatch: pytest.MonkeyPatch, tmp_path, conteudo: str) -> None:  # type: ignore[no-untyped-def]
    env = tmp_path / ".env"
    env.write_text(conteudo, encoding="utf-8")
    monkeypatch.setattr(
        config.Configuracao, "model_config", {**config.Configuracao.model_config, "env_file": env}
    )


def test_le_a_chave_do_env_da_raiz(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    _com_env(monkeypatch, tmp_path, "GITHUB_TOKEN=do-arquivo\n")

    assert config.token_do_github() == "do-arquivo"


def test_o_ambiente_vence_o_arquivo(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Ordem do pydantic, e é a que permite `GITHUB_TOKEN=... make snapshot` sobrepor."""
    _com_env(monkeypatch, tmp_path, "GITHUB_TOKEN=do-arquivo\n")
    monkeypatch.setenv("GITHUB_TOKEN", "do-shell")

    assert config.token_do_github() == "do-shell"


def test_aceita_gh_token(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """É o nome que o `gh` exporta; quem já tem um não deveria duplicá-lo."""
    _com_env(monkeypatch, tmp_path, "GH_TOKEN=do-gh\n")

    assert config.token_do_github() == "do-gh"


def test_sem_chave_e_string_vazia(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Vazio, e não erro: a CLI é que decide avisar, e o preparo roda sem chave nenhuma."""
    _com_env(monkeypatch, tmp_path, "")

    assert config.token_do_github() == ""


def test_repositorio_tambem_sai_do_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    _com_env(monkeypatch, tmp_path, "SNAPSHOT_REPO=dono/repo\n")

    assert config.repositorio_de_snapshots() == "dono/repo"
