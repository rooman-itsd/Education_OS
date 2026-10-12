"""Initial facility-booking schema: resource types, resources, opening hours, closures, series, bookings.
Every table carries organisation_id; on Postgres each gets the tenant_isolation row-level-security policy.

Revision ID: fb_0001
Revises:
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "fb_0001"
down_revision = None
branch_labels = None
depends_on = None

P = "facility_booking_"
TABLES = ["resource_type", "resource", "opening_hours", "blackout", "series", "booking"]


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _org() -> sa.Column:
    return sa.Column("organisation_id", sa.String(36), nullable=True)


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        f"{P}resource_type",
        _id(),
        _org(),
        _created(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("colour", sa.String(7), nullable=True),
        sa.Column("default_rules", sa.JSON, nullable=False),
        sa.UniqueConstraint("organisation_id", "name", name="uq_facility_booking_resource_type_name"),
    )
    op.create_table(
        f"{P}resource",
        _id(),
        _org(),
        _created(),
        sa.Column("type_id", sa.String(36), sa.ForeignKey(f"{P}resource_type.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("code", sa.String(40), nullable=True),
        sa.Column("location", sa.String(300), nullable=True),
        sa.Column("capacity", sa.Integer, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("attributes", sa.JSON, nullable=False),
        sa.Column("image_document_id", sa.String(100), nullable=True),
        sa.Column("approver_user_ids", sa.JSON, nullable=False),
        sa.Column("rules", sa.JSON, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "code", name="uq_facility_booking_resource_code"),
    )
    op.create_table(
        f"{P}opening_hours",
        _id(),
        _org(),
        sa.Column("resource_id", sa.String(36), sa.ForeignKey(f"{P}resource.id"), nullable=False),
        sa.Column("weekday", sa.Integer, nullable=False),
        sa.Column("opens", sa.String(5), nullable=False),
        sa.Column("closes", sa.String(5), nullable=False),
    )
    op.create_table(
        f"{P}blackout",
        _id(),
        _org(),
        _created(),
        sa.Column("resource_id", sa.String(36), sa.ForeignKey(f"{P}resource.id"), nullable=False),
        _ts("start_at"),
        _ts("end_at"),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
    )
    op.create_table(
        f"{P}series",
        _id(),
        _org(),
        _created(),
        sa.Column("resource_id", sa.String(36), sa.ForeignKey(f"{P}resource.id"), nullable=False),
        sa.Column("recurrence", sa.JSON, nullable=False),
        sa.Column("booked_by", sa.String(36), nullable=False),
        sa.Column("booked_for", sa.String(36), nullable=False),
    )
    op.create_table(
        f"{P}booking",
        _id(),
        _org(),
        _created(),
        sa.Column("resource_id", sa.String(36), sa.ForeignKey(f"{P}resource.id"), nullable=False),
        sa.Column("series_id", sa.String(36), sa.ForeignKey(f"{P}series.id"), nullable=True),
        _ts("start_at"),
        _ts("end_at"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("party_size", sa.Integer, nullable=False),
        sa.Column("booked_by", sa.String(36), nullable=False),
        sa.Column("booked_for", sa.String(36), nullable=False),
        sa.Column("source", sa.JSON, nullable=True),
        sa.Column("decided_by", sa.String(36), nullable=True),
        _ts("decided_at", nullable=True),
        sa.Column("decision_note", sa.Text, nullable=True),
        sa.Column("cancelled_by", sa.String(36), nullable=True),
        sa.Column("cancel_reason", sa.Text, nullable=True),
        _ts("checked_in_at", nullable=True),
        _ts("updated_at"),
    )
    for table in TABLES:
        op.create_index(f"ix_{P}{table}_organisation_id", f"{P}{table}", ["organisation_id"])
    op.create_index("ix_facility_booking_resource_type_id", f"{P}resource", ["type_id"])
    op.create_index("ix_facility_booking_opening_hours_resource_id", f"{P}opening_hours", ["resource_id"])
    op.create_index("ix_facility_booking_blackout_resource_id", f"{P}blackout", ["resource_id"])
    op.create_index("ix_facility_booking_series_resource_id", f"{P}series", ["resource_id"])
    op.create_index(
        "ix_facility_booking_booking_resource_start", f"{P}booking", ["organisation_id", "resource_id", "start_at"]
    )
    op.create_index("ix_facility_booking_booking_status", f"{P}booking", ["status"])
    op.create_index("ix_facility_booking_booking_booked_by", f"{P}booking", ["booked_by"])
    op.create_index("ix_facility_booking_booking_booked_for", f"{P}booking", ["booked_for"])
    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(POLICY.format(table=f"{P}{table}"))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(f"{P}{table}")
