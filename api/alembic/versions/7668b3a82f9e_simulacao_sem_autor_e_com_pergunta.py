"""simulacao sem autor e com pergunta

Revisão: 7668b3a82f9e
Anterior: c68ccd6c85e4
Data: 2026-09-18 18:31:21.572921
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7668b3a82f9e"
down_revision: str | None = "c68ccd6c85e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Remoção de coluna, registrada na ADR 0006: o produto é de uso local, sem autenticação.
    op.add_column("simulacao", sa.Column("pergunta", sa.Text(), nullable=True))
    op.drop_column("simulacao", "autor")


def downgrade() -> None:
    # O autor apagado não volta: a coluna renasce vazia, para a volta não falhar com linhas.
    op.add_column(
        "simulacao",
        sa.Column("autor", sa.String(length=120), server_default="", nullable=False),
    )
    op.drop_column("simulacao", "pergunta")
