"""procedencia e nota na revisao

Revisão: 442a683c843d
Anterior: a3c5e7f91b2d
Data: 2026-09-23 18:00:00

Feature 17, marco 1, ADR 0011. Duas colunas, aditivas: a revisão que já existe sai `por_pessoa`,
sem nota. `revisao_anterior_id` não muda de coluna, muda de sentido (ADR 0014): passa a ser a
revisão de onde esta nasceu.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "442a683c843d"
down_revision: str | None = "a3c5e7f91b2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "simulacao_revisao",
        sa.Column("procedencia", sa.String(length=12), server_default="por_pessoa", nullable=False),
    )
    op.add_column("simulacao_revisao", sa.Column("nota", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("simulacao_revisao", "nota")
    op.drop_column("simulacao_revisao", "procedencia")
