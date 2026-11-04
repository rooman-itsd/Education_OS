"""Read-model support for the academic-management event consumers: `term_ref` (a term's dates) and
`processed_event` (envelope ids already applied), and the changes the offering and section read models need because
events arrive unordered: their creation-event columns and `status` become nullable (a status change can arrive before
the creation), and `status_as_of` records the envelope time of the event that set `status`. Both new tables carry
organisation_id and get the tenant_isolation row-level-security policy on Postgres (eos_core.rls.POLICY).

Revision ID: tt_0002
Revises: tt_0001
Create Date: 2026-11-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "tt_0002"
down_revision = "tt_0001"
branch_labels = None
depends_on = None

P = "timetable_attendance_"
NEW_TABLES = [f"{P}term_ref", f"{P}processed_event"]


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per request (eos_core.rls.POLICY)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        f"{P}term_ref",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("academic_period_id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("starts_on", sa.Date, nullable=False),
        sa.Column("ends_on", sa.Date, nullable=False),
        sa.UniqueConstraint("organisation_id", "academic_period_id", name="uq_timetable_attendance_term_ref"),
    )
    op.create_table(
        f"{P}processed_event",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.UniqueConstraint("organisation_id", "event_id", name="uq_timetable_attendance_processed_event"),
    )
    for table in NEW_TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
        enable_rls(table)

    with op.batch_alter_table(f"{P}offering_ref") as batch:
        batch.alter_column("academic_period_id", existing_type=sa.String(36), nullable=True)
        batch.alter_column("course_code", existing_type=sa.String(40), nullable=True)
        batch.alter_column("course_title", existing_type=sa.String(200), nullable=True)
        batch.alter_column("status", existing_type=sa.String(20), nullable=True)
        batch.add_column(sa.Column("status_as_of", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table(f"{P}section_ref") as batch:
        batch.alter_column("code", existing_type=sa.String(40), nullable=True)
        batch.alter_column("status", existing_type=sa.String(20), nullable=True)
        batch.add_column(sa.Column("status_as_of", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Rows an event created only in part (no creation event yet) cannot satisfy the NOT NULL columns again; they carry
    # nothing the old schema could hold, so they are removed, and the rest keep their values (status NULL becomes
    # an empty string, the old schema's "not known").
    offering = sa.table(f"{P}offering_ref", sa.column("academic_period_id"), sa.column("status"))
    section = sa.table(f"{P}section_ref", sa.column("code"), sa.column("status"))
    op.execute(sa.delete(offering).where(offering.c.academic_period_id.is_(None)))
    op.execute(sa.delete(section).where(section.c.code.is_(None)))
    op.execute(sa.update(offering).where(offering.c.status.is_(None)).values(status=""))
    op.execute(sa.update(section).where(section.c.status.is_(None)).values(status=""))
    with op.batch_alter_table(f"{P}section_ref") as batch:
        batch.drop_column("status_as_of")
        batch.alter_column("status", existing_type=sa.String(20), nullable=False)
        batch.alter_column("code", existing_type=sa.String(40), nullable=False)
    with op.batch_alter_table(f"{P}offering_ref") as batch:
        batch.drop_column("status_as_of")
        batch.alter_column("status", existing_type=sa.String(20), nullable=False)
        batch.alter_column("course_title", existing_type=sa.String(200), nullable=False)
        batch.alter_column("course_code", existing_type=sa.String(40), nullable=False)
        batch.alter_column("academic_period_id", existing_type=sa.String(36), nullable=False)
    for table in reversed(NEW_TABLES):
        op.drop_table(table)
