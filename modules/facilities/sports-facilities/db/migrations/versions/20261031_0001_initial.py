"""Initial sports-facilities schema: facilities, spaces, weekly operating hours, usage records and the interim audit
entries. Every table carries organisation_id; on Postgres each gets the tenant_isolation row-level-security policy
(eos_core.rls.POLICY) through enable_rls().

Revision ID: sf_0001
Revises:
Create Date: 2026-10-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "sf_0001"
down_revision = None
branch_labels = None
depends_on = None

P = "sports_facilities_"
TABLES = (
    f"{P}facility",
    f"{P}space",
    f"{P}operating_hours",
    f"{P}usage",
    f"{P}audit_entry",
)


def enable_rls(table: str) -> None:
    """tenant_isolation policy on app.organisation_id (Postgres only; SQLite scoping is in the repositories)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def _base(timestamps: bool = True) -> list[sa.Column]:
    cols = [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
    ]
    if timestamps:
        cols.append(sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
        cols.append(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    return cols


def _ref(name: str, table: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.String(36), sa.ForeignKey(f"{P}{table}.id"), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        f"{P}facility",
        *_base(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("facility_type", sa.String(20), nullable=False),
        sa.Column("sports", sa.JSON, nullable=False),
        sa.Column("surface", sa.String(120), nullable=True),
        sa.Column("indoor", sa.Boolean, nullable=False),
        sa.Column("capacity", sa.Integer, nullable=True),
        sa.Column("location", sa.String(300), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("status_reason", sa.String(500), nullable=True),
        sa.Column("status_until", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organisation_id", "name", name="uq_sports_facilities_facility_name"),
    )
    op.create_table(
        f"{P}space",
        *_base(),
        _ref("facility_id", "facility"),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("capacity", sa.Integer, nullable=True),
        sa.Column("sports", sa.JSON, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.UniqueConstraint("organisation_id", "facility_id", "name", name="uq_sports_facilities_space_name"),
    )
    op.create_table(
        f"{P}operating_hours",
        *_base(timestamps=False),
        _ref("facility_id", "facility"),
        sa.Column("day_of_week", sa.Integer, nullable=False),
        sa.Column("opens_at", sa.String(5), nullable=False),
        sa.Column("closes_at", sa.String(5), nullable=False),
    )
    op.create_table(
        f"{P}usage",
        *_base(),
        _ref("facility_id", "facility"),
        _ref("space_id", "space", nullable=True),
        sa.Column("used_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("group_name", sa.String(200), nullable=True),
        sa.Column("headcount", sa.Integer, nullable=True),
        sa.Column("booking_reference", sa.String(100), nullable=True),
        sa.Column("recorded_by", sa.String(36), nullable=False),
    )
    op.create_table(
        f"{P}audit_entry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("client_token", sa.String(120), nullable=False),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("summary", sa.String(300), nullable=False),
        sa.Column("before", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("after", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organisation_id", "client_token", name="uq_sports_facilities_audit_client_token"),
    )

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    for table, column in (
        (f"{P}facility", "facility_type"),
        (f"{P}facility", "status"),
        (f"{P}space", "facility_id"),
        (f"{P}operating_hours", "facility_id"),
        (f"{P}usage", "purpose"),
    ):
        op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_index(
        "ix_sports_facilities_usage_facility_from", f"{P}usage", ["organisation_id", "facility_id", "used_from"]
    )
    op.create_index(
        "ix_sports_facilities_audit_entity", f"{P}audit_entry", ["organisation_id", "entity_type", "entity_id"]
    )

    for table in TABLES:
        enable_rls(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
