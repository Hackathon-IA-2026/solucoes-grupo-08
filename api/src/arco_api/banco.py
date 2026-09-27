"""Conexão e sessão. O banco é destino, nunca fonte: pode ser jogado fora e refeito."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from arco_api.config import configuracao

_motores: dict[str, Engine] = {}


def motor(database_url: str | None = None) -> Engine:
    url = database_url or configuracao().database_url
    if url not in _motores:
        criado = create_engine(url, future=True)
        if criado.dialect.name == "sqlite":
            # SQLite ignora chave estrangeira por padrão, e a suíte precisa vê-las valendo.
            @event.listens_for(criado, "connect")
            def _ligar_fk(conexao, _registro) -> None:  # type: ignore[no-untyped-def]
                conexao.execute("PRAGMA foreign_keys=ON")

        _motores[url] = criado
    return _motores[url]


@contextmanager
def sessao(database_url: str | None = None) -> Iterator[Session]:
    fabrica = sessionmaker(bind=motor(database_url), future=True, expire_on_commit=False)
    with fabrica() as aberta:
        yield aberta
