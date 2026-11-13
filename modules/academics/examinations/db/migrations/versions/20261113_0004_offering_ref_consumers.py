"""Read-model support for the academic-management offering consumers: `processed_event` (envelope ids already applied)
and the changes `offering_ref` needs because events arrive unordered: its creation-event columns become nullable (a
status change can arrive before the creation), and `status` and `status_as_of` (the envelope time of the event that set
the status) are added. `processed_event` carries organisation_id and gets the tenant_isolation row-level-security policy
on Postgres (eos_core.rls.POLICY). No row is changed.

Revision ID: ex_0004
Revises: ex_0003
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "ex_0004"
down_revision = "ex_0003"
branch_labels = None
depends_on = None

P = "examinations_"
CREDITS = sa.Numeric(6, 2, asdecimal=True)
NEW_TABLES = [f"{P}processed_event"]


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per request (eos_core.rls.POLICY)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        f"{P}processed_event",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.UniqueConstraint("organisation_id", "event_id", name="uq_examinations_processed_event"),
    )
    for table in NEW_TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
        enable_rls(table)

    with op.batch_alter_table(f"{P}offering_ref") as batch:
        batch.alter_column("course_id", existing_type=sa.String(36), nullable=True)
        batch.alter_column("academic_period_id", existing_type=sa.String(36), nullable=True)
        batch.alter_column("course_code", existing_type=sa.String(40), nullable=True)
        batch.alter_column("course_title", existing_type=sa.String(200), nullable=True)
        batch.alter_column("credits", existing_type=CREDITS, nullable=True)
        batch.alter_column("department_id", existing_type=sa.String(36), nullable=True)
        batch.add_column(sa.Column("status", sa.String(20), nullable=True))
        batch.add_column(sa.Column("status_as_of", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Rows an event created only in part (no creation event yet, or a creation that carried no department) cannot
    # satisfy the NOT NULL columns again. A row with no creation event holds nothing the old schema could keep, so it is
    # removed; a known row whose department was NULL gets the empty string, the old schema's "not known".
    offering = sa.table(f"{P}offering_ref", sa.column("academic_period_id"), sa.column("department_id"))
    op.execute(sa.delete(offering).where(offering.c.academic_period_id.is_(None)))
    op.execute(sa.update(offering).where(offering.c.department_id.is_(None)).values(department_id=""))
    with op.batch_alter_table(f"{P}offering_ref") as batch:
        batch.drop_column("status_as_of")
        batch.drop_column("status")
        batch.alter_column("department_id", existing_type=sa.String(36), nullable=False)
        batch.alter_column("credits", existing_type=CREDITS, nullable=False)
        batch.alter_column("course_title", existing_type=sa.String(200), nullable=False)
        batch.alter_column("course_code", existing_type=sa.String(40), nullable=False)
        batch.alter_column("academic_period_id", existing_type=sa.String(36), nullable=False)
        batch.alter_column("course_id", existing_type=sa.String(36), nullable=False)
    for table in reversed(NEW_TABLES):
        op.drop_table(table)
