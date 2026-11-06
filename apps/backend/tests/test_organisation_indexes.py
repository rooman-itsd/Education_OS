"""Every table that holds organisation_id has an index that starts with it (#96; Postgres only, as CI's Postgres step).

Row-level security adds `organisation_id = current_setting('app.organisation_id')` to every query of a module table, and
nearly every query also filters by organisation. Without an index whose first column is organisation_id, each of those
reads the whole table, every tenant's rows, and gets slower as the platform grows: a cost the empty test databases
never show. The index usually comes from eos_core.db.TenantMixin (index=True); a table created another way needs one
in its migration.

KNOWN_UNINDEXED lists the tables that lacked one when this check was added. It may only shrink: a module's owner adds
the index in a migration of that module, then removes the table here. A table missing from the list fails the test.
"""

import pytest
from eos_core.db import engine
from eos_core.settings import settings
from sqlalchemy import text

pytestmark = pytest.mark.skipif(not settings.is_postgres, reason="the catalogue query is Postgres's")

# Table -> the module that owns it. Each line is a migration for that module's owner to write.
KNOWN_UNINDEXED: dict[str, str] = {}

UNINDEXED = text(
    """
    SELECT c.table_name
      FROM information_schema.columns c
      JOIN information_schema.tables t
        ON t.table_schema = c.table_schema AND t.table_name = c.table_name AND t.table_type = 'BASE TABLE'
     WHERE c.table_schema = 'public' AND c.column_name = 'organisation_id'
       AND NOT EXISTS (
             SELECT 1
               FROM pg_index i
               JOIN pg_class tc ON tc.oid = i.indrelid
               JOIN pg_namespace n ON n.oid = tc.relnamespace AND n.nspname = 'public'
               JOIN pg_attribute a ON a.attrelid = tc.oid AND a.attnum = i.indkey[0]
              WHERE tc.relname = c.table_name AND a.attname = 'organisation_id')
     ORDER BY 1
    """
)


def _unindexed() -> set[str]:
    with engine.connect() as conn:
        return {row[0] for row in conn.execute(UNINDEXED)}


def test_every_organisation_table_has_an_index_starting_with_organisation_id(client):
    new = sorted(_unindexed() - set(KNOWN_UNINDEXED))
    assert not new, (
        "these tables have organisation_id but no index that starts with it, so every row-level-security query reads "
        f"the whole table: {new}. Add one in the table's migration (op.create_index(..., ['organisation_id']))."
    )


def test_the_known_gaps_list_only_shrinks(client):
    fixed = sorted(set(KNOWN_UNINDEXED) - _unindexed())
    assert not fixed, f"these tables have their index now (or are gone): remove them from KNOWN_UNINDEXED: {fixed}"
