"""Initial tournament-events schema: tournaments, entries, fixtures, officials, results, logistics, the athlete links
learnt from athlete-performance's events and the interim audit entries. Every table carries organisation_id; on
Postgres each gets the tenant_isolation row-level-security policy (eos_core.rls.POLICY) through enable_rls().

Revision ID: te_0001
Revises:
Create Date: 2026-10-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "te_0001"
down_revision = None
branch_labels = None
depends_on = None

P = "tournament_events_"
TABLES = (
    f"{P}tournament",
    f"{P}entry",
    f"{P}fixture",
    f"{P}official",
    f"{P}result",
    f"{P}logistics",
    f"{P}athlete_link",
    f"{P}audit_entry",
)


def enable_rls(table: str) -> None:
    """tenant_isolation policy on app.organisation_id (Postgres only; SQLite scoping is in the repositories)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def _base(created: bool = True) -> list[sa.Column]:
    cols = [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
    ]
    if created:
        cols.append(sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    cols.append(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    return cols


def _ref(name: str, table: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.String(36), sa.ForeignKey(f"{P}{table}.id"), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        f"{P}tournament",
        *_base(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("discipline", sa.String(120), nullable=False),
        sa.Column("discipline_id", sa.String(36), nullable=True),
        sa.Column("level", sa.String(30), nullable=False),
        sa.Column("format", sa.String(30), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("venue", sa.String(300), nullable=True),
        sa.Column("hosting", sa.String(10), nullable=True),
        sa.Column("registration_closes_on", sa.Date, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text, nullable=True),
    )
    op.create_table(
        f"{P}entry",
        *_base(),
        _ref("tournament_id", "tournament"),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("team_name", sa.String(200), nullable=True),
        sa.Column("athlete_ids", sa.JSON, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
    )
    op.create_table(
        f"{P}fixture",
        *_base(),
        _ref("tournament_id", "tournament"),
        sa.Column("round", sa.String(120), nullable=False),
        sa.Column("category", sa.String(120), nullable=True),
        sa.Column("entry_ids", sa.JSON, nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("venue", sa.String(300), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
    )
    op.create_table(
        f"{P}official",
        *_base(),
        _ref("tournament_id", "tournament"),
        _ref("fixture_id", "fixture", nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("official_role", sa.String(30), nullable=False),
        sa.Column("confirmed", sa.Boolean, nullable=False),
    )
    op.create_table(
        f"{P}result",
        *_base(),
        _ref("tournament_id", "tournament"),
        _ref("fixture_id", "fixture"),
        sa.Column("placings", sa.JSON, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", sa.String(36), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organisation_id", "fixture_id", name="uq_tournament_events_result_fixture"),
    )
    op.create_table(
        f"{P}logistics",
        *_base(created=False),
        _ref("tournament_id", "tournament"),
        sa.Column("travel_mode", sa.String(10), nullable=True),
        sa.Column("departure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("return_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accommodation", sa.Text, nullable=True),
        sa.Column("travelling_count", sa.Integer, nullable=True),
        sa.Column("contact_person_id", sa.String(36), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.UniqueConstraint("organisation_id", "tournament_id", name="uq_tournament_events_logistics_tournament"),
    )
    op.create_table(
        f"{P}athlete_link",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("athlete_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organisation_id", "athlete_id", name="uq_tournament_events_link_athlete"),
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
        sa.UniqueConstraint("organisation_id", "client_token", name="uq_tournament_events_audit_client_token"),
    )

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    for table, column in (
        (f"{P}tournament", "status"),
        (f"{P}fixture", "scheduled_at"),
        (f"{P}official", "tournament_id"),
        (f"{P}result", "tournament_id"),
        (f"{P}athlete_link", "user_id"),
    ):
        op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_index(
        "ix_tournament_events_tournament_dates", f"{P}tournament", ["organisation_id", "start_date", "end_date"]
    )
    op.create_index("ix_tournament_events_entry_tournament", f"{P}entry", ["tournament_id", "category"])
    op.create_index("ix_tournament_events_fixture_tournament", f"{P}fixture", ["tournament_id", "scheduled_at"])
    op.create_index(
        "ix_tournament_events_audit_entity", f"{P}audit_entry", ["organisation_id", "entity_type", "entity_id"]
    )

    for table in TABLES:
        enable_rls(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
