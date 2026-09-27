"""Ambiente do Alembic. A URL vem de DATABASE_URL; o alvo é o metadata dos modelos."""

from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool

from arco_api.config import configuracao
from arco_api.modelos import Base

config = context.config
config.set_main_option("sqlalchemy.url", configuracao().database_url)
target_metadata = Base.metadata


def offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def online() -> None:
    conectavel = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with conectavel.connect() as conexao:
        context.configure(connection=conexao, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    offline()
else:
    online()
