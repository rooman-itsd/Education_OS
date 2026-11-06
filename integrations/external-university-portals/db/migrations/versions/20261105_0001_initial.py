"""Initial external-university-portals schema: exchanges with partner institutions.
Every table carries organisation_id; on Postgres each gets the forced tenant_isolation row-level-security policy.

Revision ID: eup_0001
Revises:
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "eup_0001"
down_revision = None
branch_labels = None
depends_on = None

P = "external_university_portals_"
TABLES = ["exchange"]


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        f"{P}exchange",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("connection_id", sa.String(36), nullable=True),
        sa.Column("exchange_key", sa.String(100), nullable=False),
        sa.Column("partner_id", sa.String(60), nullable=False),
        sa.Column("partner_name", sa.String(200), nullable=True),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=True),
        sa.Column("format", sa.String(12), nullable=False),
        sa.Column("channel", sa.String(20), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("integrity", sa.String(10), nullable=True),
        sa.Column("unmapped", sa.JSON, nullable=False),
        sa.Column("caller_module", sa.String(60), nullable=True),
        sa.Column("caller_reference", sa.String(100), nullable=True),
        sa.Column("delivered_on", sa.Date, nullable=True),
        sa.Column("delivered_by", sa.String(36), nullable=True),
        sa.Column("partner_reference", sa.String(100), nullable=True),
        _ts("link_expires_at", nullable=True),
        _ts("updated_at"),
    )
    op.create_index(f"ix_{P}exchange_organisation_id", f"{P}exchange", ["organisation_id"])
    op.create_index(f"ix_{P}exchange_partner_id", f"{P}exchange", ["partner_id"])
    op.create_index(f"ix_{P}exchange_direction", f"{P}exchange", ["direction"])
    op.create_index(f"ix_{P}exchange_person_id", f"{P}exchange", ["person_id"])
    op.create_index(f"ix_{P}exchange_status", f"{P}exchange", ["status"])
    op.create_index(
        "uq_external_university_portals_exchange_key",
        f"{P}exchange",
        ["organisation_id", "exchange_key", "direction"],
        unique=True,
    )
    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(POLICY.format(table=f"{P}{table}"))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(f"{P}{table}")
