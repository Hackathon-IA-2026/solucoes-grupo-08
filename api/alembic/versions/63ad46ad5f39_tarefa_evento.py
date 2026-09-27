"""tarefa e evento

Revisão: 63ad46ad5f39
Anterior: 442a683c843d
Data: 2026-09-23 20:00:00

Feature 17, marco 1, task 17.12. Duas tabelas novas, aditivas: nada existente muda.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "63ad46ad5f39"
down_revision: str | None = "442a683c843d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

Json = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "tarefa",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("simulacao_id", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=12), nullable=False),
        sa.Column("teto", sa.Integer(), nullable=False),
        sa.Column("pedido", sa.Text(), nullable=False),
        sa.Column("revisao_partida_id", sa.Integer(), nullable=False),
        sa.Column("faixa", Json, nullable=False),
        sa.Column(
            "criada_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("terminada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column("relatorio_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["simulacao_id"], ["simulacao.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["revisao_partida_id"], ["simulacao_revisao.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["relatorio_id"], ["relatorio.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tarefa_simulacao_id", "tarefa", ["simulacao_id"])
    op.create_index(
        "uq_tarefa_em_andamento",
        "tarefa",
        ["simulacao_id"],
        unique=True,
        postgresql_where=sa.text("estado = 'em_andamento'"),
        sqlite_where=sa.text("estado = 'em_andamento'"),
    )
    op.create_table(
        "evento",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tarefa_id", sa.Integer(), nullable=False),
        sa.Column("instante", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("dados", Json, nullable=False),
        sa.ForeignKeyConstraint(["tarefa_id"], ["tarefa.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evento_tarefa_id", "evento", ["tarefa_id"])


def downgrade() -> None:
    op.drop_index("ix_evento_tarefa_id", table_name="evento")
    op.drop_table("evento")
    op.drop_index("uq_tarefa_em_andamento", table_name="tarefa")
    op.drop_index("ix_tarefa_simulacao_id", table_name="tarefa")
    op.drop_table("tarefa")
