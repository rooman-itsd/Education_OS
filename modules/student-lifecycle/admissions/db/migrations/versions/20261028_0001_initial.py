"""Initial admissions schema: applications, their documents and offers, merit lists with ranked entries, and the
module's audit trail. Every table carries organisation_id; on Postgres each gets the tenant_isolation
row-level-security policy.

Revision ID: admissions_0001
Revises:
Create Date: 2026-10-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "admissions_0001"
down_revision = None
branch_labels = None
depends_on = None

OPEN_OFFER = sa.text("status = 'open'")


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _fk(name: str, table: str) -> sa.Column:
    return sa.Column(name, sa.String(36), sa.ForeignKey(f"{table}.id", ondelete="CASCADE"), nullable=False)


def _enable_rls(table: str) -> None:
    """Row-level security on app.organisation_id (eos_core.rls.POLICY). Postgres only; SQLite has none."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "admissions_application",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("reference_number", sa.String(32), nullable=False),
        sa.Column("applicant_first_name", sa.String(120), nullable=False),
        sa.Column("applicant_last_name", sa.String(120), nullable=False),
        sa.Column("applicant_email", sa.String(320), nullable=False),
        sa.Column("applicant_phone", sa.String(40), nullable=True),
        sa.Column("applicant_date_of_birth", sa.Date, nullable=True),
        sa.Column("programme_id", sa.String(36), nullable=False),
        sa.Column("academic_year", sa.String(20), nullable=False),
        sa.Column("selection_process_round_id", sa.String(36), nullable=True),
        sa.Column("portfolio_item_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        _ts("submitted_at"),
        _ts("decided_at", nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_admissions_application_organisation_id", "admissions_application", ["organisation_id"])
    op.create_index(
        "uq_admissions_application_reference",
        "admissions_application",
        ["organisation_id", "reference_number"],
        unique=True,
    )
    op.create_index("ix_admissions_application_status", "admissions_application", ["organisation_id", "status"])
    op.create_index(
        "ix_admissions_application_programme",
        "admissions_application",
        ["organisation_id", "programme_id", "academic_year"],
    )

    op.create_table(
        "admissions_application_document",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        _fk("application_id", "admissions_application"),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("document_id", sa.String(64), nullable=False),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column("verification_status", sa.String(20), nullable=False),
        sa.Column("verification_note", sa.Text, nullable=True),
        sa.Column("verified_by", sa.String(36), nullable=True),
        _ts("verified_at", nullable=True),
        _ts("uploaded_at"),
    )
    op.create_index(
        "ix_admissions_application_document_organisation_id", "admissions_application_document", ["organisation_id"]
    )
    op.create_index(
        "ix_admissions_application_document_application_id", "admissions_application_document", ["application_id"]
    )
    op.create_index(
        "ix_admissions_application_document_queue",
        "admissions_application_document",
        ["organisation_id", "verification_status", "uploaded_at"],
    )

    op.create_table(
        "admissions_offer",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        _fk("application_id", "admissions_application"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        _ts("expires_at", nullable=True),
        sa.Column("offered_by", sa.String(36), nullable=False),
        _ts("offered_at"),
        _ts("decided_at", nullable=True),
        sa.Column("decline_reason", sa.Text, nullable=True),
    )
    op.create_index("ix_admissions_offer_organisation_id", "admissions_offer", ["organisation_id"])
    op.create_index("ix_admissions_offer_application_id", "admissions_offer", ["application_id"])
    op.create_index(
        "uq_admissions_offer_open",
        "admissions_offer",
        ["application_id"],
        unique=True,
        sqlite_where=OPEN_OFFER,
        postgresql_where=OPEN_OFFER,
    )

    op.create_table(
        "admissions_merit_list",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("programme_id", sa.String(36), nullable=False),
        sa.Column("academic_year", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        _ts("published_at", nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        _ts("created_at"),
    )
    op.create_index("ix_admissions_merit_list_organisation_id", "admissions_merit_list", ["organisation_id"])
    op.create_index(
        "ix_admissions_merit_list_programme",
        "admissions_merit_list",
        ["organisation_id", "programme_id", "academic_year"],
    )

    op.create_table(
        "admissions_merit_list_entry",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        _fk("merit_list_id", "admissions_merit_list"),
        _fk("application_id", "admissions_application"),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("score", sa.Float, nullable=True),
    )
    op.create_index(
        "ix_admissions_merit_list_entry_organisation_id", "admissions_merit_list_entry", ["organisation_id"]
    )
    op.create_index(
        "uq_admissions_merit_list_entry_application",
        "admissions_merit_list_entry",
        ["merit_list_id", "application_id"],
        unique=True,
    )
    op.create_index(
        "uq_admissions_merit_list_entry_rank", "admissions_merit_list_entry", ["merit_list_id", "rank"], unique=True
    )

    op.create_table(
        "admissions_audit_entry",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("detail", sa.JSON, nullable=True),
        _ts("occurred_at"),
    )
    op.create_index("ix_admissions_audit_entry_organisation_id", "admissions_audit_entry", ["organisation_id"])
    op.create_index("ix_admissions_audit_entry_entity", "admissions_audit_entry", ["entity", "entity_id"])

    # One literal call per table: tools/scripts/check-migrations.py looks for each table name in an rls call.
    _enable_rls("admissions_application")
    _enable_rls("admissions_application_document")
    _enable_rls("admissions_offer")
    _enable_rls("admissions_merit_list")
    _enable_rls("admissions_merit_list_entry")
    _enable_rls("admissions_audit_entry")


def downgrade() -> None:
    op.drop_table("admissions_merit_list_entry")
    op.drop_table("admissions_merit_list")
    op.drop_table("admissions_offer")
    op.drop_table("admissions_application_document")
    op.drop_table("admissions_audit_entry")
    op.drop_table("admissions_application")
