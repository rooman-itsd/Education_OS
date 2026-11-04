"""Initial library schema: titles, copies, loan policies, members, loans, reservations, fines, digital resources,
audit entries. Every table carries organisation_id; on Postgres each gets the tenant_isolation row-level-security
policy. Money columns are Numeric(12, 2).

Revision ID: library_0001
Revises:
Create Date: 2026-10-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "library_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "library_title",
    "library_copy",
    "library_loan_policy",
    "library_member",
    "library_loan",
    "library_reservation",
    "library_fine",
    "library_digital_resource",
    "library_audit_entry",
]


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _money(name: str) -> sa.Column:
    return sa.Column(name, sa.Numeric(12, 2), nullable=False)


def _enable_rls(table: str) -> None:
    """Row-level security on app.organisation_id (eos_core.rls.POLICY). Postgres only; SQLite has none."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "library_title",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("isbn", sa.String(20), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("authors", sa.JSON, nullable=False),
        sa.Column("publisher", sa.String(200), nullable=True),
        sa.Column("year", sa.Integer, nullable=True),
        sa.Column("subjects", sa.JSON, nullable=False),
        sa.Column("kind", sa.String(60), nullable=False),
        _ts("updated_at"),
    )
    op.create_table(
        "library_copy",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("title_id", sa.String(36), sa.ForeignKey("library_title.id"), nullable=False),
        sa.Column("accession_no", sa.String(60), nullable=False),
        sa.Column("barcode", sa.String(60), nullable=False),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("withdraw_reason", sa.Text, nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "accession_no", name="uq_library_copy_accession"),
        sa.UniqueConstraint("organisation_id", "barcode", name="uq_library_copy_barcode"),
    )
    op.create_table(
        "library_loan_policy",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("member_category", sa.String(60), nullable=False),
        sa.Column("max_loans", sa.Integer, nullable=False),
        sa.Column("loan_days", sa.Integer, nullable=False),
        sa.Column("max_renewals", sa.Integer, nullable=False),
        _money("fine_per_day"),
        _money("max_unpaid_fines"),
        sa.Column("hold_days", sa.Integer, nullable=False),
        sa.UniqueConstraint("organisation_id", "member_category", name="uq_library_policy_category"),
    )
    op.create_table(
        "library_member",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("person_name", sa.String(200), nullable=True),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("blocked", sa.Boolean, nullable=False),
        sa.Column("block_reason", sa.Text, nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "person_id", name="uq_library_member_person"),
    )
    op.create_table(
        "library_loan",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("copy_id", sa.String(36), sa.ForeignKey("library_copy.id"), nullable=False),
        sa.Column("title_id", sa.String(36), sa.ForeignKey("library_title.id"), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        _ts("issued_at"),
        sa.Column("issued_by", sa.String(36), nullable=False),
        sa.Column("due_on", sa.Date, nullable=False),
        _ts("returned_at", nullable=True),
        sa.Column("renewals", sa.Integer, nullable=False),
        sa.Column("fine_per_day", sa.Numeric(12, 2), nullable=False),
        sa.Column("max_renewals", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("damage_note", sa.Text, nullable=True),
        _ts("overdue_flagged_at", nullable=True),
    )
    op.create_table(
        "library_reservation",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("title_id", sa.String(36), sa.ForeignKey("library_title.id"), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("held_copy_id", sa.String(36), sa.ForeignKey("library_copy.id"), nullable=True),
        sa.Column("hold_expires_on", sa.Date, nullable=True),
        _ts("placed_at"),
        _ts("resolved_at", nullable=True),
    )
    op.create_table(
        "library_fine",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("loan_id", sa.String(36), sa.ForeignKey("library_loan.id"), nullable=True),
        sa.Column("reason", sa.String(20), nullable=False),
        _money("amount"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("receipt_ref", sa.String(120), nullable=True),
        sa.Column("waive_reason", sa.Text, nullable=True),
        sa.Column("waived_by", sa.String(36), nullable=True),
        _ts("raised_at"),
        _ts("settled_at", nullable=True),
    )
    op.create_table(
        "library_digital_resource",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("provider", sa.String(200), nullable=True),
        sa.Column("kind", sa.String(60), nullable=True),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("access", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        _ts("updated_at"),
    )
    op.create_table(
        "library_audit_entry",
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
    op.create_index("ix_library_title_isbn", "library_title", ["organisation_id", "isbn"])
    op.create_index("ix_library_copy_title_id", "library_copy", ["title_id"])
    op.create_index("ix_library_copy_status", "library_copy", ["status"])
    op.create_index("ix_library_loan_status", "library_loan", ["status"])
    op.create_index("ix_library_loan_person", "library_loan", ["organisation_id", "person_id"])
    op.create_index("ix_library_loan_copy_status", "library_loan", ["organisation_id", "copy_id", "status"])
    op.create_index("ix_library_reservation_person_id", "library_reservation", ["person_id"])
    op.create_index(
        "ix_library_reservation_title_status", "library_reservation", ["organisation_id", "title_id", "status"]
    )
    op.create_index(
        "uq_library_reservation_active",
        "library_reservation",
        ["organisation_id", "person_id", "title_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('waiting', 'ready')"),
        sqlite_where=sa.text("status IN ('waiting', 'ready')"),
    )
    op.create_index("ix_library_fine_person_status", "library_fine", ["organisation_id", "person_id", "status"])
    op.create_index("ix_library_audit_entity", "library_audit_entry", ["organisation_id", "entity", "entity_id"])

    _enable_rls("library_title")
    _enable_rls("library_copy")
    _enable_rls("library_loan_policy")
    _enable_rls("library_member")
    _enable_rls("library_loan")
    _enable_rls("library_reservation")
    _enable_rls("library_fine")
    _enable_rls("library_digital_resource")
    _enable_rls("library_audit_entry")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
