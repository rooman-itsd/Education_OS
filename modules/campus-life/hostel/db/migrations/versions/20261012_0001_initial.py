"""Initial hostel schema: hostels, rooms, allocations, mess menu, leave, visits, incidents, notices, audit entries.
Every table carries organisation_id; on Postgres each gets the tenant_isolation row-level-security policy.

Revision ID: hostel_0001
Revises:
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "hostel_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "hostel_hostel",
    "hostel_room",
    "hostel_allocation",
    "hostel_mess_menu",
    "hostel_leave_request",
    "hostel_visit",
    "hostel_incident",
    "hostel_notice",
    "hostel_audit_entry",
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
        "hostel_hostel",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("occupancy_type", sa.String(60), nullable=False),
        sa.Column("warden_ids", sa.JSON, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        _ts("updated_at"),
    )
    op.create_table(
        "hostel_room",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("hostel_id", sa.String(36), sa.ForeignKey("hostel_hostel.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("floor", sa.String(40), nullable=True),
        sa.Column("room_type", sa.String(60), nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("close_reason", sa.Text, nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "hostel_id", "number", name="uq_hostel_room_number"),
    )
    op.create_table(
        "hostel_allocation",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("person_name", sa.String(200), nullable=True),
        sa.Column("academic_year", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("preferred_hostel_id", sa.String(36), nullable=True),
        sa.Column("preferred_room_type", sa.String(60), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("hostel_id", sa.String(36), sa.ForeignKey("hostel_hostel.id"), nullable=True),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("hostel_room.id"), nullable=True),
        sa.Column("bed", sa.String(20), nullable=True),
        sa.Column("from_date", sa.Date, nullable=True),
        sa.Column("to_date", sa.Date, nullable=True),
        _ts("checked_in_at", nullable=True),
        _ts("checked_out_at", nullable=True),
        sa.Column("condition_notes", sa.Text, nullable=True),
        sa.Column("cancel_reason", sa.Text, nullable=True),
        _ts("updated_at"),
    )
    op.create_table(
        "hostel_mess_menu",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("hostel_id", sa.String(36), sa.ForeignKey("hostel_hostel.id"), nullable=False),
        sa.Column("menu_date", sa.Date, nullable=False),
        sa.Column("meal", sa.String(60), nullable=False),
        sa.Column("items", sa.JSON, nullable=False),
        sa.Column("updated_by", sa.String(36), nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "hostel_id", "menu_date", "meal", name="uq_hostel_mess_menu_meal"),
    )
    op.create_table(
        "hostel_leave_request",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("person_name", sa.String(200), nullable=True),
        sa.Column("hostel_id", sa.String(36), sa.ForeignKey("hostel_hostel.id"), nullable=False),
        _ts("from_at"),
        _ts("to_at"),
        sa.Column("destination", sa.String(300), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("contact_phone", sa.String(40), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("decided_by", sa.String(36), nullable=True),
        _ts("decided_at", nullable=True),
        sa.Column("decision_reason", sa.Text, nullable=True),
        _ts("departed_at", nullable=True),
        sa.Column("departure_recorded_by", sa.String(36), nullable=True),
        _ts("returned_at", nullable=True),
        sa.Column("return_recorded_by", sa.String(36), nullable=True),
        _ts("overdue_flagged_at", nullable=True),
        _ts("updated_at"),
    )
    op.create_table(
        "hostel_visit",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("hostel_id", sa.String(36), sa.ForeignKey("hostel_hostel.id"), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("visitor_name", sa.String(200), nullable=False),
        sa.Column("relation", sa.String(100), nullable=True),
        sa.Column("id_document_note", sa.String(100), nullable=True),
        _ts("in_at"),
        _ts("out_at", nullable=True),
        sa.Column("recorded_by", sa.String(36), nullable=False),
    )
    op.create_table(
        "hostel_incident",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("hostel_id", sa.String(36), sa.ForeignKey("hostel_hostel.id"), nullable=False),
        _ts("occurred_at"),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("action_taken", sa.Text, nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("recorded_by", sa.String(36), nullable=False),
        _ts("closed_at", nullable=True),
        _ts("updated_at"),
    )
    op.create_table(
        "hostel_notice",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("hostel_id", sa.String(36), sa.ForeignKey("hostel_hostel.id"), nullable=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        _ts("published_at"),
        sa.Column("published_by", sa.String(36), nullable=False),
        _ts("expires_at", nullable=True),
        _ts("withdrawn_at", nullable=True),
        sa.Column("withdrawn_by", sa.String(36), nullable=True),
    )
    op.create_table(
        "hostel_audit_entry",
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
    op.create_index("ix_hostel_room_hostel_id", "hostel_room", ["hostel_id"])
    op.create_index("ix_hostel_allocation_status", "hostel_allocation", ["status"])
    op.create_index(
        "ix_hostel_allocation_person_year", "hostel_allocation", ["organisation_id", "person_id", "academic_year"]
    )
    op.create_index("ix_hostel_allocation_room_status", "hostel_allocation", ["organisation_id", "room_id", "status"])
    op.create_index("ix_hostel_mess_menu_hostel_id", "hostel_mess_menu", ["hostel_id"])
    op.create_index("ix_hostel_leave_request_hostel_id", "hostel_leave_request", ["hostel_id"])
    op.create_index("ix_hostel_leave_request_status", "hostel_leave_request", ["status"])
    op.create_index("ix_hostel_leave_person", "hostel_leave_request", ["organisation_id", "person_id"])
    op.create_index("ix_hostel_visit_hostel_id", "hostel_visit", ["hostel_id"])
    op.create_index("ix_hostel_visit_person", "hostel_visit", ["organisation_id", "person_id"])
    op.create_index("ix_hostel_incident_hostel_id", "hostel_incident", ["hostel_id"])
    op.create_index("ix_hostel_incident_person", "hostel_incident", ["organisation_id", "person_id"])
    op.create_index("ix_hostel_notice_published_at", "hostel_notice", ["published_at"])
    op.create_index("ix_hostel_audit_entity", "hostel_audit_entry", ["organisation_id", "entity", "entity_id"])

    _enable_rls("hostel_hostel")
    _enable_rls("hostel_room")
    _enable_rls("hostel_allocation")
    _enable_rls("hostel_mess_menu")
    _enable_rls("hostel_leave_request")
    _enable_rls("hostel_visit")
    _enable_rls("hostel_incident")
    _enable_rls("hostel_notice")
    _enable_rls("hostel_audit_entry")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
