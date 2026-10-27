"""Initial student-information schema: person master records, immutable status history,
attached document references, and issued identity cards.
Every table carries organisation_id; on Postgres each gets the tenant_isolation row-level-security policy.

Revision ID: student_information_0001
Revises:
Create Date: 2026-10-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "student_information_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "student_information_person",
    "student_information_status_history",
    "student_information_document",
    "student_information_id_card",
]

IDENTITY_NOT_NULL = sa.text("identity_number IS NOT NULL")
ACTIVE_CARD = sa.text("status = 'issued'")


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
        "student_information_person",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        _created(),
        sa.Column("first_name", sa.String(120), nullable=False),
        sa.Column("last_name", sa.String(120), nullable=False),
        sa.Column("preferred_name", sa.String(120), nullable=True),
        sa.Column("date_of_birth", sa.Date, nullable=True),
        sa.Column("gender", sa.String(60), nullable=True),
        sa.Column("identity_number", sa.String(100), nullable=True),
        sa.Column("contact", sa.JSON, nullable=True),
        sa.Column("guardians", sa.JSON, nullable=True),
        sa.Column("identity_user_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("status_effective_date", sa.Date, nullable=False),
        sa.Column("source", sa.JSON, nullable=True),
        _ts("updated_at"),
    )

    op.create_table(
        "student_information_status_history",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column(
            "person_id",
            sa.String(36),
            sa.ForeignKey("student_information_person.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("previous_status", sa.String(20), nullable=True),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("changed_by", sa.String(36), nullable=False),
        _ts("changed_at"),
    )

    op.create_table(
        "student_information_document",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column(
            "person_id",
            sa.String(36),
            sa.ForeignKey("student_information_person.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column("uploaded_by", sa.String(36), nullable=False),
        _ts("uploaded_at"),
    )

    op.create_table(
        "student_information_id_card",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column(
            "person_id",
            sa.String(36),
            sa.ForeignKey("student_information_person.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("card_number", sa.String(60), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.Date, nullable=True),
        sa.Column("document_id", sa.String(36), nullable=True),
        sa.Column("issued_by", sa.String(36), nullable=False),
        _ts("issued_at"),
        sa.Column("revoked_by", sa.String(36), nullable=True),
        _ts("revoked_at", nullable=True),
        sa.Column("revoked_reason", sa.Text, nullable=True),
    )

    # Standard organisation_id and foreign key indexes
    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index(
        "ix_student_information_status_history_person_id",
        "student_information_status_history",
        ["person_id"],
    )
    op.create_index(
        "ix_student_information_document_person_id",
        "student_information_document",
        ["person_id"],
    )
    op.create_index(
        "ix_student_information_id_card_person_id",
        "student_information_id_card",
        ["person_id"],
    )

    # Concurrency-safe partial unique indexes
    op.create_index(
        "uq_student_info_person_identity",
        "student_information_person",
        ["organisation_id", "identity_number"],
        unique=True,
        sqlite_where=IDENTITY_NOT_NULL,
        postgresql_where=IDENTITY_NOT_NULL,
    )
    op.create_index(
        "uq_student_info_active_card",
        "student_information_id_card",
        ["organisation_id", "person_id"],
        unique=True,
        sqlite_where=ACTIVE_CARD,
        postgresql_where=ACTIVE_CARD,
    )

    # Postgres RLS policies
    _enable_rls("student_information_person")
    _enable_rls("student_information_status_history")
    _enable_rls("student_information_document")
    _enable_rls("student_information_id_card")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
