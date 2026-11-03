"""Audit records: append-only for the application role, at the database.

Before, eos_app held UPDATE, DELETE and TRUNCATE on audit_record (infra/docker/db-roles.py grants them on every
table), so only the trigger stood in the way, and the trigger let any session that set `audit.pruning` delete a
single chosen record, and let a "redaction" write arbitrary before/after values (#317 audit, A3).

Now:
- eos_app loses UPDATE, DELETE and TRUNCATE on audit_record: it can only INSERT and SELECT. db-roles.py re-applies
  this after its grants on every deploy (its APPEND_ONLY list); this migration covers the first one.
- Retention runs through audit_prune(cutoff), SECURITY DEFINER (owned by the migrating owner, search_path pinned).
  It refuses a cutoff younger than the retention floor (2555 days), so it can never remove a record the law says
  to keep. eos_app may EXECUTE it; nothing else is granted.
- Redaction runs through audit_redact(record_id), SECURITY DEFINER, executable by the owner only (maintenance):
  it writes the tombstone (before and after NULL, redacted true) and nothing else.
- A purged organisation's trail is kept with its payloads redacted (DPDP erasure; the decision on #317):
  audit_redact_organisation(org), SECURITY DEFINER, executable by eos_app, tombstones the organisation's records
  and the platform-level copies about it. It refuses while the organisation still exists (tenancy_organisation),
  so it cannot be used to blank a live tenant's trail. audit calls it on tenancy.organisation.purged.
- The trigger allows a DELETE or a tombstone only when the session runs as the table's owner, which is the case
  inside those two functions; the `audit.pruning` flag alone no longer opens anything.

Revision ID: audit_0002
Revises: audit_0001
Create Date: 2026-11-02
"""

from __future__ import annotations

from alembic import op

revision = "audit_0002"
down_revision = "audit_0001"
branch_labels = None
depends_on = None

# The SQL below spells out eos_app (infra/docker/db-roles.py's ROLE) and the 2555-day retention floor
# (eos_audit.infrastructure.config.RETENTION_FLOOR_DAYS; the check allows one day of clock skew, 2554).

OWNER_ONLY_TRIGGER = """
CREATE OR REPLACE FUNCTION audit_record_immutable() RETURNS trigger AS $$
DECLARE
  table_owner name;
BEGIN
  SELECT tableowner INTO table_owner FROM pg_tables WHERE schemaname = TG_TABLE_SCHEMA AND tablename = TG_TABLE_NAME;
  IF TG_OP = 'DELETE' THEN
    IF current_setting('audit.pruning', true) = 'on' AND current_user = table_owner THEN
      RETURN OLD;
    END IF;
    RAISE EXCEPTION 'audit records cannot be deleted' USING ERRCODE = 'insufficient_privilege';
  END IF;
  -- UPDATE: only the redaction tombstone, only as the owner (audit_redact). json has no equality operator, so
  -- context is compared as text.
  IF current_user = table_owner
     AND OLD.redacted = false AND NEW.redacted = true
     AND NEW.before IS NULL AND NEW.after IS NULL
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
"""

FUNCTIONS = """
CREATE OR REPLACE FUNCTION audit_prune(cutoff timestamptz) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
  removed integer;
BEGIN
  IF cutoff IS NULL OR cutoff > now() - interval '2554 days' THEN
    RAISE EXCEPTION 'audit retention floor: records younger than 2555 days are kept'
      USING ERRCODE = 'insufficient_privilege';
  END IF;
  PERFORM set_config('audit.pruning', 'on', true);
  DELETE FROM public.audit_record WHERE occurred_at < cutoff;
  GET DIAGNOSTICS removed = ROW_COUNT;
  PERFORM set_config('audit.pruning', 'off', true);
  RETURN removed;
END
$$;

CREATE OR REPLACE FUNCTION audit_redact(record_id varchar) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
  UPDATE public.audit_record SET before = NULL, after = NULL, redacted = true
   WHERE id = record_id AND redacted = false;
  RETURN FOUND;
END
$$;

CREATE OR REPLACE FUNCTION audit_redact_organisation(org varchar) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
  still_there boolean := false;
  redacted_count integer;
BEGIN
  IF to_regclass('public.tenancy_organisation') IS NOT NULL THEN
    EXECUTE 'SELECT EXISTS (SELECT 1 FROM public.tenancy_organisation WHERE id = $1)' INTO still_there USING org;
  END IF;
  IF org IS NULL OR still_there THEN
    RAISE EXCEPTION 'organisation % still exists: its audit trail is redacted only after it is purged', org
      USING ERRCODE = 'insufficient_privilege';
  END IF;
  UPDATE public.audit_record SET before = NULL, after = NULL, redacted = true
   WHERE redacted = false
     AND (organisation_id = org
          OR (organisation_id IS NULL AND context::jsonb ->> 'organisation_id' = org));
  GET DIAGNOSTICS redacted_count = ROW_COUNT;
  RETURN redacted_count;
END
$$;

REVOKE ALL ON FUNCTION audit_prune(timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION audit_redact(varchar) FROM PUBLIC;
REVOKE ALL ON FUNCTION audit_redact_organisation(varchar) FROM PUBLIC;
"""

APP_GRANTS = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eos_app') THEN
    REVOKE UPDATE, DELETE, TRUNCATE ON audit_record FROM eos_app;
    GRANT EXECUTE ON FUNCTION audit_prune(timestamptz) TO eos_app;
    GRANT EXECUTE ON FUNCTION audit_redact_organisation(varchar) TO eos_app;
  END IF;
END
$$;
"""

ORIGINAL_TRIGGER = """
CREATE OR REPLACE FUNCTION audit_record_immutable() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF current_setting('audit.pruning', true) = 'on' THEN
      RETURN OLD;
    END IF;
    RAISE EXCEPTION 'audit records cannot be deleted' USING ERRCODE = 'insufficient_privilege';
  END IF;
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
"""


def _postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _postgres():
        return  # SQLite has no roles, functions or triggers here; the application path is the same
    op.execute(OWNER_ONLY_TRIGGER)
    op.execute(FUNCTIONS)
    op.execute(APP_GRANTS)


def downgrade() -> None:
    if not _postgres():
        return
    op.execute("DROP FUNCTION IF EXISTS audit_prune(timestamptz)")
    op.execute("DROP FUNCTION IF EXISTS audit_redact(varchar)")
    op.execute("DROP FUNCTION IF EXISTS audit_redact_organisation(varchar)")
    op.execute(ORIGINAL_TRIGGER)
    # db-roles.py restores the application role's table grants on the next deploy
