"""Record a guardian's consent for a minor (DPDP gap D7): the institution obtains it offline, the platform records it.

Four nullable columns on `student_information_person` (no backfill: no consent was recorded before; nullable and
without a default, so the upgrade is metadata-only on Postgres and no row is rewritten; the person table's existing
row-level-security policy covers them), and the append-only `student_information_guardian_consent_history`, which
carries `organisation_id` and its own tenant_isolation policy. Batch mode makes the same revision work on SQLite, which
the module's tests use.

Revision ID: student_information_0002
Revises: student_information_0001
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "student_information_0002"
down_revision = "student_information_0001"
branch_labels = None
depends_on = None

PERSON = "student_information_person"
HISTORY = "student_information_guardian_consent_history"


def _enable_rls(table: str) -> None:
    """Row-level security on app.organisation_id (eos_core.rls.POLICY). Postgres only; SQLite has none."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    with op.batch_alter_table(PERSON) as batch:
        batch.add_column(sa.Column("guardian_consent_obtained", sa.Boolean, nullable=True))
        batch.add_column(sa.Column("guardian_consent_obtained_on", sa.Date, nullable=True))
        batch.add_column(sa.Column("guardian_consent_recorded_by", sa.String(36), nullable=True))
        batch.add_column(sa.Column("guardian_consent_note", sa.Text, nullable=True))

    op.create_table(
        HISTORY,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("person_id", sa.String(36), sa.ForeignKey(f"{PERSON}.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("obtained_on", sa.Date, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("changed_by", sa.String(36), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(f"ix_{HISTORY}_organisation_id", HISTORY, ["organisation_id"])
    op.create_index(f"ix_{HISTORY}_person_id", HISTORY, ["person_id"])
    _enable_rls(HISTORY)


def downgrade() -> None:
    op.drop_table(HISTORY)
    with op.batch_alter_table(PERSON) as batch:
        batch.drop_column("guardian_consent_note")
        batch.drop_column("guardian_consent_recorded_by")
        batch.drop_column("guardian_consent_obtained_on")
        batch.drop_column("guardian_consent_obtained")
