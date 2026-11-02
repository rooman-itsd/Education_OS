"""Initial audit schema: audit_record, tenant-scoped with the tenant_isolation policy, and immutable.

On PostgreSQL a trigger refuses every UPDATE and DELETE, except the two docs/prd.md allows: a redaction
tombstone (only before/after/redacted change, and redacted only goes false -> true), and a retention prune
(a DELETE inside a transaction that set app-local `audit.pruning` to 'on'). TRUNCATE is refused outright,
because row triggers do not fire for it. The database role is shared by every module, so per-table grants
cannot express "insert and select only"; the trigger guards against application-level mutations.

Revision ID: audit_0001
Revises:
Create Date: 2026-10-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "audit_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLE = "audit_record"

IMMUTABLE = """
CREATE OR REPLACE FUNCTION audit_record_immutable() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF current_setting('audit.pruning', true) = 'on' THEN
      RETURN OLD;
    END IF;
    RAISE EXCEPTION 'audit records cannot be deleted' USING ERRCODE = 'insufficient_privilege';
  END IF;
  -- UPDATE: only the redaction tombstone. json has no equality operator, so context is compared as text.
  IF OLD.redacted = false AND NEW.redacted = true
     AND NEW.id = OLD.id
     AND NEW.organisation_id IS NOT DISTINCT FROM OLD.organisation_id
     AND NEW.actor IS NOT DISTINCT FROM OLD.actor
     AND NEW.module = OLD.module
     AND NEW.action = OLD.action
     AND NEW.entity_type = OLD.entity_type
     AND NEW.entity_id = OLD.entity_id
     AND NEW.summary IS NOT DISTINCT FROM OLD.summary
     AND NEW.context::text IS NOT DISTINCT FROM OLD.context::text
     AND NEW.client_token IS NOT DISTINCT FROM OLD.client_token
     AND NEW.occurred_at = OLD.occurred_at THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'audit records cannot be altered' USING ERRCODE = 'insufficient_privilege';
END
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION audit_record_no_truncate() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit records cannot be truncated' USING ERRCODE = 'insufficient_privilege';
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_record_immutable BEFORE UPDATE OR DELETE ON audit_record
  FOR EACH ROW EXECUTE FUNCTION audit_record_immutable();
CREATE TRIGGER audit_record_no_truncate BEFORE TRUNCATE ON audit_record
  FOR EACH STATEMENT EXECUTE FUNCTION audit_record_no_truncate();
"""


def _postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per request (eos_core.rls.POLICY)."""
    if _postgres():
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),  # null: a platform-level action
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("module", sa.String(60), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("entity_type", sa.String(60), nullable=False),
        sa.Column("entity_id", sa.String(120), nullable=False),
        sa.Column("summary", sa.String(300), nullable=True),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("client_token", sa.String(120), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redacted", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_audit_record_organisation_id", TABLE, ["organisation_id"])
    op.create_index("ix_audit_record_org_occurred", TABLE, ["organisation_id", "occurred_at"])
    op.create_index("ix_audit_record_org_entity", TABLE, ["organisation_id", "entity_type", "entity_id", "occurred_at"])
    op.create_index("ix_audit_record_org_module", TABLE, ["organisation_id", "module"])
    op.create_index(
        "uq_audit_record_org_token", TABLE, [sa.text("coalesce(organisation_id, '')"), "client_token"], unique=True
    )
    enable_rls(TABLE)
    if _postgres():
        op.execute(IMMUTABLE)


def downgrade() -> None:
    if _postgres():
        op.execute(f"DROP TRIGGER IF EXISTS audit_record_no_truncate ON {TABLE}")
        op.execute(f"DROP TRIGGER IF EXISTS audit_record_immutable ON {TABLE}")
        op.execute("DROP FUNCTION IF EXISTS audit_record_no_truncate()")
        op.execute("DROP FUNCTION IF EXISTS audit_record_immutable()")
    op.drop_table(TABLE)
