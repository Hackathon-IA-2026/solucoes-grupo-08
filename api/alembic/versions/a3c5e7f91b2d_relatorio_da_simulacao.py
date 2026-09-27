"""relatorio da simulacao

Revisão: a3c5e7f91b2d
Anterior: e109bbd4e32e
Data: 2026-09-22 20:00:00

Feature 17, marco 0. Tabela nova, aditiva: nada existente muda.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3c5e7f91b2d"
down_revision: str | None = "e109bbd4e32e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

Json = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "relatorio",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("simulacao_id", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=10), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("gerado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("metodo_versao", sa.String(length=20), nullable=False),
        sa.Column("modelo", sa.String(length=60), nullable=True),
        sa.Column("versao_prompt", sa.String(length=20), nullable=True),
        sa.Column("revisoes_cobertas", Json, nullable=False),
        sa.Column("parte_calculada", Json, nullable=True),
        sa.Column("prosa", Json, nullable=True),
        sa.Column("verificacao", Json, nullable=True),
        sa.Column("prosa_barrada", Json, nullable=True),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["simulacao_id"], ["simulacao.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_relatorio_simulacao_id", "relatorio", ["simulacao_id"])
    op.create_index(
        "uq_relatorio_gerando",
        "relatorio",
        ["simulacao_id"],
        unique=True,
        postgresql_where=sa.text("estado = 'gerando'"),
        sqlite_where=sa.text("estado = 'gerando'"),
    )


def downgrade() -> None:
    op.drop_index("uq_relatorio_gerando", table_name="relatorio")
    op.drop_index("ix_relatorio_simulacao_id", table_name="relatorio")
    op.drop_table("relatorio")
