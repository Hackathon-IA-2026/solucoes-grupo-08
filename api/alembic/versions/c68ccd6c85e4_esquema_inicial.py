"""esquema inicial

Revisão: c68ccd6c85e4
Anterior:
Data: 2026-09-18 00:08:38.831710
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c68ccd6c85e4"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    op.create_table(
        "aviso_restricao",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("restricao_id", sa.String(length=12), nullable=False),
        sa.Column("codigo", sa.String(length=60), nullable=False),
        sa.Column("mensagem", sa.Text(), nullable=False),
        sa.Column("fonte", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_aviso_restricao_restricao_id"), "aviso_restricao", ["restricao_id"], unique=False
    )
    op.create_table(
        "obra_prevista",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("restricao_id", sa.String(length=12), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("situacao", sa.String(length=60), nullable=True),
        sa.Column("previsao", sa.String(length=60), nullable=True),
        sa.Column("fonte", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_obra_prevista_restricao_id"), "obra_prevista", ["restricao_id"], unique=False
    )
    op.create_table(
        "simulacao",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("autor", sa.String(length=120), nullable=False),
        sa.Column("restricao_id", sa.String(length=12), nullable=False),
        sa.Column(
            "criada_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_simulacao_restricao_id"), "simulacao", ["restricao_id"], unique=False)
    op.create_table(
        "snapshot",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column(
            "carregado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("periodo_inicio", sa.DateTime(), nullable=True),
        sa.Column("periodo_fim", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "vinculo_restricao_equipamento",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("restricao_id", sa.String(length=12), nullable=False),
        sa.Column("cod_equipamento", sa.String(length=40), nullable=True),
        sa.Column("papel", sa.String(length=20), nullable=False),
        sa.Column("alternativo", sa.Boolean(), nullable=False),
        sa.Column("situacao", sa.String(length=20), nullable=False),
        sa.Column("citacao", sa.Text(), nullable=True),
        sa.Column("candidatos", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("origem", sa.String(length=12), nullable=False),
        sa.Column("validado_por", sa.String(length=120), nullable=True),
        sa.Column("validado_em", sa.Date(), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("restricao_id", "cod_equipamento", "papel", name="uq_vinculo"),
    )
    op.create_index(
        op.f("ix_vinculo_restricao_equipamento_cod_equipamento"),
        "vinculo_restricao_equipamento",
        ["cod_equipamento"],
        unique=False,
    )
    op.create_index(
        op.f("ix_vinculo_restricao_equipamento_restricao_id"),
        "vinculo_restricao_equipamento",
        ["restricao_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_vinculo_restricao_equipamento_status"),
        "vinculo_restricao_equipamento",
        ["status"],
        unique=False,
    )
    op.create_table(
        "equipamento",
        sa.Column("cod_equipamento", sa.String(length=40), nullable=False),
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("tensao_kv", sa.Integer(), nullable=True),
        sa.Column("subestacao_de", sa.String(length=120), nullable=True),
        sa.Column("subestacao_para", sa.String(length=120), nullable=True),
        sa.Column("num_barra_de", sa.Integer(), nullable=True),
        sa.Column("num_barra_para", sa.Integer(), nullable=True),
        sa.Column("nome", sa.Text(), nullable=True),
        sa.Column("proprietario", sa.Text(), nullable=True),
        sa.Column("comprimento_km", sa.Float(), nullable=True),
        sa.Column(
            "capacidades",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["snapshot_id"], ["snapshot.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("cod_equipamento", "snapshot_id"),
    )
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
    op.create_table(
        "serie_restricao",
        sa.Column("restricao_id", sa.String(length=12), nullable=False),
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("fonte", sa.String(length=10), nullable=False),
        sa.Column("instante", sa.DateTime(), nullable=False),
        sa.Column("corte_mw", sa.Float(), nullable=False),
        sa.Column("minutos_cnf", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["snapshot_id"], ["snapshot.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("restricao_id", "snapshot_id", "fonte", "instante"),
    )
    op.create_table(
        "simulacao_revisao",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("simulacao_id", sa.Integer(), nullable=False),
        sa.Column("revisao_anterior_id", sa.Integer(), nullable=True),
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("metodo_versao", sa.String(length=20), nullable=False),
        sa.Column(
            "configuracao",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "premissas_usadas",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "resultado",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "avisos",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "criada_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["revisao_anterior_id"], ["simulacao_revisao.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["simulacao_id"], ["simulacao.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["snapshot.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_simulacao_revisao_simulacao_id"),
        "simulacao_revisao",
        ["simulacao_id"],
        unique=False,
    )
    op.create_table(
        "subestacao",
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["snapshot_id"], ["snapshot.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("nome", "snapshot_id"),
    )


def downgrade() -> None:

    op.drop_table("subestacao")
    op.drop_index(op.f("ix_simulacao_revisao_simulacao_id"), table_name="simulacao_revisao")
    op.drop_table("simulacao_revisao")
    op.drop_table("serie_restricao")
    op.drop_table("restricao")
    op.drop_table("equipamento")
    op.drop_index(
        op.f("ix_vinculo_restricao_equipamento_status"), table_name="vinculo_restricao_equipamento"
    )
    op.drop_index(
        op.f("ix_vinculo_restricao_equipamento_restricao_id"),
        table_name="vinculo_restricao_equipamento",
    )
    op.drop_index(
        op.f("ix_vinculo_restricao_equipamento_cod_equipamento"),
        table_name="vinculo_restricao_equipamento",
    )
    op.drop_table("vinculo_restricao_equipamento")
    op.drop_table("snapshot")
    op.drop_index(op.f("ix_simulacao_restricao_id"), table_name="simulacao")
    op.drop_table("simulacao")
    op.drop_index(op.f("ix_obra_prevista_restricao_id"), table_name="obra_prevista")
    op.drop_table("obra_prevista")
    op.drop_index(op.f("ix_aviso_restricao_restricao_id"), table_name="aviso_restricao")
    op.drop_table("aviso_restricao")
