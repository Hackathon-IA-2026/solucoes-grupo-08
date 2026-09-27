"""Conferência do `make servidor`: cada item diz o que está ok e, quando falta, como resolver."""

from __future__ import annotations

import socket
from collections.abc import Iterable
from pathlib import Path

import pytest
from sqlalchemy import create_engine, insert, text

from arco_api.modelos import Base, Snapshot
from arco_api.verificar import (
    _cabecas,
    _por_que,
    conferir_banco,
    conferir_chave,
    conferir_porta,
    main,
)


def _sqlite(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'arco.db'}"


def _preparar(url: str, versoes: Iterable[str], snapshot_ativo: str | None = None) -> None:
    """Banco com o esquema dos modelos, carimbado nas versões dadas do Alembic."""
    motor = create_engine(url)
    Base.metadata.create_all(motor)
    with motor.begin() as conexao:
        conexao.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        for versao in versoes:
            conexao.execute(text("INSERT INTO alembic_version VALUES (:v)"), {"v": versao})
        if snapshot_ativo:
            conexao.execute(insert(Snapshot).values(id=snapshot_ativo, ativo=True))
    motor.dispose()


def _porta_livre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reserva:
        reserva.bind(("127.0.0.1", 0))
        return reserva.getsockname()[1]


def test_banco_inacessivel_diz_onde_e_como_subir() -> None:
    itens = conferir_banco("postgresql+psycopg://arco:segredo@127.0.0.1:1/arco")
    assert len(itens) == 1
    assert not itens[0].ok
    assert "127.0.0.1:1/arco" in itens[0].texto
    assert "segredo" not in itens[0].texto
    assert "make db" in itens[0].dica


def test_senha_recusada_nao_manda_subir_o_banco() -> None:
    """Outro Postgres na mesma porta responde com senha recusada: subir o do projeto não resolve."""
    motivo, dica = _por_que(
        'connection to server at "127.0.0.1", port 5432 failed: FATAL:  password '
        'authentication failed for user "arco"'
    )
    assert motivo == "usuário ou senha recusados"
    assert "ARCO_PG_PORTA" in dica


def test_banco_sem_esquema_manda_migrar_e_carregar(tmp_path: Path) -> None:
    itens = conferir_banco(_sqlite(tmp_path))
    assert [item.ok for item in itens] == [True, False, False]
    assert "make migrar" in itens[1].dica
    assert "make banco" in itens[2].dica


def test_esquema_desatualizado_manda_migrar(tmp_path: Path) -> None:
    _preparar(_sqlite(tmp_path), ["versao_antiga"])
    itens = conferir_banco(_sqlite(tmp_path))
    assert not itens[1].ok
    assert "desatualizado" in itens[1].texto
    assert itens[1].dica == "make migrar"


def test_esquema_em_dia_sem_snapshot_manda_carregar(tmp_path: Path) -> None:
    _preparar(_sqlite(tmp_path), _cabecas())
    itens = conferir_banco(_sqlite(tmp_path))
    assert [item.ok for item in itens] == [True, True, False]
    assert "make banco" in itens[2].dica


def test_esquema_em_dia_com_snapshot_ativo_passa(tmp_path: Path) -> None:
    _preparar(_sqlite(tmp_path), _cabecas(), snapshot_ativo="2026-09-21")
    itens = conferir_banco(_sqlite(tmp_path))
    assert all(item.ok for item in itens)
    assert "2026-09-21" in itens[-1].texto


def test_chave_ausente_diz_o_que_deixa_de_rodar() -> None:
    item = conferir_chave("")
    assert not item.ok
    assert "GEMINI_API_KEY" in item.texto
    assert ".env" in item.dica
    assert conferir_chave("uma-chave").ok


def test_porta_ocupada_trava_e_livre_passa() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ouvinte:
        ouvinte.bind(("127.0.0.1", 0))
        ouvinte.listen()
        porta = ouvinte.getsockname()[1]
        ocupada = conferir_porta(porta, "a API", "outra porta")
    assert not ocupada.ok
    assert "ocupada" in ocupada.texto
    assert conferir_porta(porta, "a API", "outra porta").ok


def test_sai_1_quando_falta_algo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DATABASE_URL", _sqlite(tmp_path))
    monkeypatch.setenv("GEMINI_API_KEY", "")
    portas = ["--porta-api", str(_porta_livre()), "--porta-mcp", str(_porta_livre())]
    assert main(portas) == 1
    assert "falta" in capsys.readouterr().out


def test_sai_0_quando_tudo_esta_pronto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _preparar(_sqlite(tmp_path), _cabecas(), snapshot_ativo="2026-09-21")
    monkeypatch.setenv("DATABASE_URL", _sqlite(tmp_path))
    monkeypatch.setenv("GEMINI_API_KEY", "uma-chave")
    portas = ["--porta-api", str(_porta_livre()), "--porta-mcp", str(_porta_livre())]
    assert main(portas) == 0
