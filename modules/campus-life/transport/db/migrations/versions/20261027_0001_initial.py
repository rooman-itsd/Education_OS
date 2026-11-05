"""Initial transport schema: stops, vehicles, drivers, routes and their stops, passes, trips, positions, notices,
document expiry flags, audit entries. Every table carries organisation_id; on Postgres each gets the
tenant_isolation row-level-security policy.

Revision ID: transport_0001
Revises:
Create Date: 2026-10-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "transport_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "transport_stop",
    "transport_vehicle",
    "transport_driver",
    "transport_route",
    "transport_route_stop",
    "transport_pass",
    "transport_trip",
    "transport_position",
    "transport_notice",
    "transport_document_flag",
    "transport_audit_entry",
]


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _enable_rls(table: str) -> None:
    """Row-level security on app.organisation_id (eos_core.rls.POLICY). Postgres only; SQLite has none."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "transport_stop",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        _ts("updated_at"),
    )
    op.create_table(
        "transport_vehicle",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("registration_no", sa.String(40), nullable=False),
        sa.Column("type", sa.String(60), nullable=True),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("insurance_expires_on", sa.Date, nullable=True),
        sa.Column("fitness_expires_on", sa.Date, nullable=True),
        sa.Column("permit_expires_on", sa.Date, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "registration_no", name="uq_transport_vehicle_reg"),
    )
    op.create_table(
        "transport_driver",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("person_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("licence_no", sa.String(60), nullable=False),
        sa.Column("licence_expires_on", sa.Date, nullable=False),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False),
        _ts("updated_at"),
    )
    op.create_table(
        "transport_route",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("direction", sa.String(100), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("vehicle_id", sa.String(36), sa.ForeignKey("transport_vehicle.id"), nullable=True),
        sa.Column("driver_id", sa.String(36), sa.ForeignKey("transport_driver.id"), nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "code", name="uq_transport_route_code"),
    )
    op.create_table(
        "transport_route_stop",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("route_id", sa.String(36), sa.ForeignKey("transport_route.id"), nullable=False),
        sa.Column("stop_id", sa.String(36), sa.ForeignKey("transport_stop.id"), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("scheduled_time", sa.String(5), nullable=True),
        sa.UniqueConstraint("organisation_id", "route_id", "stop_id", name="uq_transport_route_stop"),
    )
    op.create_table(
        "transport_pass",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("person_name", sa.String(200), nullable=True),
        sa.Column("rider_type", sa.String(10), nullable=False),
        sa.Column("route_id", sa.String(36), sa.ForeignKey("transport_route.id"), nullable=False),
        sa.Column("stop_id", sa.String(36), sa.ForeignKey("transport_stop.id"), nullable=False),
        sa.Column("valid_from", sa.Date, nullable=False),
        sa.Column("valid_to", sa.Date, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("decided_by", sa.String(36), nullable=True),
        _ts("decided_at", nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("capacity_override_reason", sa.Text, nullable=True),
        sa.Column("cancelled_on", sa.Date, nullable=True),
        _ts("updated_at"),
    )
    op.create_table(
        "transport_trip",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("route_id", sa.String(36), sa.ForeignKey("transport_route.id"), nullable=False),
        sa.Column("vehicle_id", sa.String(36), sa.ForeignKey("transport_vehicle.id"), nullable=False),
        sa.Column("driver_id", sa.String(36), sa.ForeignKey("transport_driver.id"), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        _ts("started_at"),
        sa.Column("started_by", sa.String(36), nullable=False),
        _ts("ended_at", nullable=True),
        sa.Column("delay_minutes", sa.Integer, nullable=False),
        sa.Column("delay_note", sa.Text, nullable=True),
    )
    op.create_table(
        "transport_position",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("trip_id", sa.String(36), sa.ForeignKey("transport_trip.id"), nullable=False),
        _ts("recorded_at"),
        sa.Column("latitude", sa.Float, nullable=False),
        sa.Column("longitude", sa.Float, nullable=False),
        sa.Column("speed_kmh", sa.Float, nullable=True),
    )
    op.create_table(
        "transport_notice",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("route_id", sa.String(36), sa.ForeignKey("transport_route.id"), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        _ts("published_at"),
        sa.Column("published_by", sa.String(36), nullable=False),
        _ts("expires_at", nullable=True),
        _ts("withdrawn_at", nullable=True),
        sa.Column("withdrawn_by", sa.String(36), nullable=True),
    )
    op.create_table(
        "transport_document_flag",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("subject", sa.String(10), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("document", sa.String(20), nullable=False),
        sa.Column("expires_on", sa.Date, nullable=False),
        _ts("flagged_at"),
        sa.UniqueConstraint(
            "organisation_id", "subject_id", "document", "expires_on", name="uq_transport_document_flag"
        ),
    )
    op.create_table(
        "transport_audit_entry",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        _ts("occurred_at"),
    )

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index("ix_transport_driver_person", "transport_driver", ["organisation_id", "person_id"])
    op.create_index("ix_transport_route_stop_route_id", "transport_route_stop", ["route_id"])
    op.create_index("ix_transport_route_stop_stop_id", "transport_route_stop", ["stop_id"])
    op.create_index("ix_transport_pass_status", "transport_pass", ["status"])
    op.create_index("ix_transport_pass_person", "transport_pass", ["organisation_id", "person_id"])
    op.create_index("ix_transport_pass_route_status", "transport_pass", ["organisation_id", "route_id", "status"])
    op.create_index("ix_transport_trip_route_status", "transport_trip", ["organisation_id", "route_id", "status"])
    op.create_index("ix_transport_position_recorded_at", "transport_position", ["recorded_at"])
    op.create_index(
        "ix_transport_position_trip_time", "transport_position", ["organisation_id", "trip_id", "recorded_at"]
    )
    op.create_index("ix_transport_notice_published_at", "transport_notice", ["published_at"])
    op.create_index("ix_transport_audit_entity", "transport_audit_entry", ["organisation_id", "entity", "entity_id"])

    _enable_rls("transport_stop")
    _enable_rls("transport_vehicle")
    _enable_rls("transport_driver")
    _enable_rls("transport_route")
    _enable_rls("transport_route_stop")
    _enable_rls("transport_pass")
    _enable_rls("transport_trip")
    _enable_rls("transport_position")
    _enable_rls("transport_notice")
    _enable_rls("transport_document_flag")
    _enable_rls("transport_audit_entry")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
