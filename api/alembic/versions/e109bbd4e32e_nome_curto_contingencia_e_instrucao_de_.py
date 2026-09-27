"""nome curto, contingencia e instrucao de operacao

Revisão: e109bbd4e32e
Anterior: bf25270c204d
Data: 2026-09-21

Três colunas nulas na identidade da restrição, compostas por regra a partir do texto do ONS
(feature 10). Aditiva: nada é renomeado nem removido, e o que a regra não reconhecer fica nulo.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e109bbd4e32e"
down_revision: str | None = "bf25270c204d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("restricao", sa.Column("nome_curto", sa.String(length=200), nullable=True))
    op.add_column("restricao", sa.Column("contingencia", sa.String(length=200), nullable=True))
    op.add_column("restricao", sa.Column("instrucao_operacao", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("restricao", "instrucao_operacao")
    op.drop_column("restricao", "contingencia")
    op.drop_column("restricao", "nome_curto")
