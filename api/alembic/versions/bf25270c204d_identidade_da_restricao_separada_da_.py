"""identidade da restricao separada da medicao

Revisão: bf25270c204d
Anterior: 7668b3a82f9e
Data: 2026-09-21

Recria `restricao` em vez de transformar, e cria `restricao_snapshot`. Ver a [ADR 0009].

Transformar no lugar não cabe: `snapshot_id` é parte da chave primária atual, e com mais de um
snapshot carregado o `id` se repete — a chave nova, só por `id`, não passaria. E não há o que
preservar: as duas tabelas são recomputáveis com `preparar` mais `carregar`, e o banco é
descartável por decisão da [ADR 0005]. Nenhuma FK aponta para `restricao`, então recriar não
arrasta ninguém: vínculo, aviso, obra e simulação apontam por valor.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bf25270c204d"
down_revision: str | None = "7668b3a82f9e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("restricao")
    op.create_table(
        "restricao",
        sa.Column("id", sa.String(length=12), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("origem", sa.String(length=3), nullable=False),
        sa.Column("razao", sa.String(length=3), nullable=False),
        sa.Column("vista_primeiro_em", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "restricao_snapshot",
        sa.Column("restricao_id", sa.String(length=12), nullable=False),
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("energia_mwh", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["restricao_id"], ["restricao.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["snapshot.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("restricao_id", "snapshot_id"),
    )


def downgrade() -> None:
    op.drop_table("restricao_snapshot")
    op.drop_table("restricao")
    op.create_table(
        "restricao",
        sa.Column("id", sa.String(length=12), nullable=False),
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("origem", sa.String(length=3), nullable=False),
        sa.Column("razao", sa.String(length=3), nullable=False),
        sa.Column("energia_mwh", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["snapshot.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", "snapshot_id"),
    )
