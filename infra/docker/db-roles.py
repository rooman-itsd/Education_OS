"""Run inside the API image as the database owner (EOS_DATABASE_URL), first in the migrate step: create or
update the role the API connects as, `eos_app`, and give it row access only.

  eos_app   LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE, password from EOS_APP_DB_PASSWORD
  tables    SELECT, INSERT, UPDATE, DELETE        sequences   USAGE, SELECT
  later     ALTER DEFAULT PRIVILEGES FOR ROLE <owner>, so tables the migration chains create next get the same

No DDL: tables stay owned by the owner, and the tenant_isolation policy (FORCE ROW LEVEL SECURITY) applies to
eos_app because it is neither a superuser nor the owner. Safe to run on every deploy."""

import os
import sys

from sqlalchemy import create_engine, text

ROLE = "eos_app"
ATTRIBUTES = "LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"
TABLES = "SELECT, INSERT, UPDATE, DELETE"
SEQUENCES = "USAGE, SELECT"


def say(message: str) -> None:
    # stdout, not logging, like stamp-chains.py
    sys.stdout.write(f"db-roles: {message}\n")
    sys.stdout.flush()


password = os.environ.get("EOS_APP_DB_PASSWORD", "")
if not password:
    raise SystemExit("db-roles: set EOS_APP_DB_PASSWORD (infra/docker/.env.api) for the eos_app role")

with create_engine(os.environ["EOS_DATABASE_URL"]).begin() as conn:
    owner, database = conn.execute(text("SELECT quote_ident(current_user), quote_ident(current_database())")).one()
    exists = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": ROLE}).scalar() is not None
    if not exists:
        conn.execute(text(f"CREATE ROLE {ROLE} {ATTRIBUTES}"))
    # A password cannot be a bind parameter in DDL, so Postgres quotes it as a literal (%L).
    alter = conn.execute(
        text(f"SELECT format('ALTER ROLE {ROLE} WITH {ATTRIBUTES} PASSWORD %L', CAST(:pw AS text))"), {"pw": password}
    ).scalar()
    conn.exec_driver_sql(alter)  # as is: text() would read a ":" inside the password as a parameter
    for statement in (
        f"GRANT CONNECT ON DATABASE {database} TO {ROLE}",
        f"GRANT USAGE ON SCHEMA public TO {ROLE}",
        f"GRANT {TABLES} ON ALL TABLES IN SCHEMA public TO {ROLE}",
        f"GRANT {SEQUENCES} ON ALL SEQUENCES IN SCHEMA public TO {ROLE}",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA public GRANT {TABLES} ON TABLES TO {ROLE}",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA public GRANT {SEQUENCES} ON SEQUENCES TO {ROLE}",
    ):
        conn.execute(text(statement))
say(f"{'updated' if exists else 'created'} {ROLE}: row access on every table, and on tables {owner} creates later")
