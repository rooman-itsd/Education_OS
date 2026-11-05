"""Row-level security on a real PostgreSQL server. SQLite has no policies, so the rest of this module's tests
prove only that the repositories scope their queries; this one proves the database refuses the rest. The
fixture creates a throwaway database and an unprivileged probe role (no superuser, no BYPASSRLS, not the table
owner), runs the migration, and drops both afterwards. Needs PRODUCTIONS_TEST_POSTGRES_URL or
EOS_TEST_POSTGRES_URL for a user with CREATEDB and CREATEROLE; skipped otherwise."""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

SERVER_URL = os.environ.get("PRODUCTIONS_TEST_POSTGRES_URL") or os.environ.get("EOS_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not SERVER_URL, reason="PRODUCTIONS_TEST_POSTGRES_URL or EOS_TEST_POSTGRES_URL is not set"
)

DB_DIR = Path(__file__).resolve().parents[2] / "db"
ORG_A = "00000000-0000-4000-8000-00000000000a"
ORG_B = "00000000-0000-4000-8000-00000000000b"

INSERT_PRODUCTION = (
    "INSERT INTO productions_production "
    "(id, organisation_id, title, kind, status, lead_user_id, created_by, created_at, updated_at) "
    "VALUES (:id, :org, :title, 'performance', 'planned', 'u-1', 'u-1', now(), now())"
)


def _server_url():
    from sqlalchemy.engine import make_url

    url = make_url(SERVER_URL)
    if url.get_backend_name() != "postgresql":
        pytest.fail("the PostgreSQL test URL must be a postgresql:// URL")
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url


def _alembic(url, revision: str, upgrade: bool) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(DB_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url.render_as_string(hide_password=False)}"]})()
    (command.upgrade if upgrade else command.downgrade)(cfg, revision)


@pytest.fixture(scope="module")
def pg():
    pytest.importorskip("psycopg")
    from eos_productions.infrastructure.models import TABLES
    from sqlalchemy import create_engine, text

    server = _server_url()
    suffix = uuid.uuid4().hex[:12]
    db_name, role = f"productions_rls_{suffix}", f"productions_probe_{suffix}"
    admin = create_engine(server, isolation_level="AUTOCOMMIT")
    engine = None
    try:
        with admin.connect() as c:
            c.execute(text(f'CREATE DATABASE "{db_name}"'))
            c.execute(text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT'))
            c.execute(text(f'GRANT "{role}" TO CURRENT_USER'))

        db_url = server.set(database=db_name)
        _alembic(db_url, "head", upgrade=True)
        engine = create_engine(db_url)
        with engine.begin() as c:
            c.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
            for table in TABLES:
                c.execute(text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON "{table.name}" TO "{role}"'))
        try:
            yield engine, role
        finally:
            engine.dispose()
            _alembic(db_url, "base", upgrade=False)
    finally:
        if engine is not None:
            engine.dispose()
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
            c.execute(text(f'DROP ROLE IF EXISTS "{role}"'))
        admin.dispose()


@contextmanager
def as_role(engine, role: str, organisation_id: str):
    from sqlalchemy import text

    with engine.begin() as c:
        c.execute(text(f'SET LOCAL ROLE "{role}"'))
        c.execute(text("SELECT set_config('app.organisation_id', :org, true)"), {"org": organisation_id})
        yield c


def test_every_table_has_a_forced_tenant_isolation_policy(pg):
    from eos_productions.infrastructure.models import TABLES
    from sqlalchemy import text

    engine, _ = pg
    with engine.connect() as c:
        policies = {
            r[0] for r in c.execute(text("SELECT tablename FROM pg_policies WHERE policyname = 'tenant_isolation'"))
        }
        forced = {
            r[0] for r in c.execute(text("SELECT relname FROM pg_class WHERE relrowsecurity AND relforcerowsecurity"))
        }
    names = {t.name for t in TABLES}
    assert names <= policies, f"no tenant_isolation policy on {names - policies}"
    assert names <= forced, f"row security not forced on {names - forced}"


def test_the_probe_role_sees_and_writes_only_its_own_organisation(pg):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    engine, role = pg
    with engine.connect() as c:
        superuser, bypass = c.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :r"), {"r": role}
        ).one()
    assert (superuser, bypass) == (False, False)

    a_id, b_id = str(uuid.uuid4()), str(uuid.uuid4())
    for org, production_id, title in ((ORG_A, a_id, "A's show"), (ORG_B, b_id, "B's show")):
        with as_role(engine, role, org) as c:
            c.execute(text(INSERT_PRODUCTION), {"id": production_id, "org": org, "title": title})

    with as_role(engine, role, ORG_A) as c:
        seen = {r[0] for r in c.execute(text("SELECT id FROM productions_production"))}
    assert a_id in seen and b_id not in seen

    with as_role(engine, role, ORG_B) as c:
        seen = {r[0] for r in c.execute(text("SELECT id FROM productions_production"))}
    assert b_id in seen and a_id not in seen

    with pytest.raises(DBAPIError), as_role(engine, role, ORG_A) as c:
        c.execute(text(INSERT_PRODUCTION), {"id": str(uuid.uuid4()), "org": ORG_B, "title": "Planted in B"})


def test_a_part_and_a_task_cannot_be_read_or_written_across_organisations(pg):
    """The child tables carry their own organisation_id, so a row of A's production written under B's
    scope is refused, and B never sees A's cast list."""
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    engine, role = pg
    production_id = str(uuid.uuid4())
    with as_role(engine, role, ORG_A) as c:
        c.execute(text(INSERT_PRODUCTION), {"id": production_id, "org": ORG_A, "title": "Cast list"})
        c.execute(
            text(
                "INSERT INTO productions_role "
                "(id, organisation_id, production_id, user_id, role_name, kind, status, assigned_by, created_at) "
                "VALUES (:id, :org, :p, 'u-2', 'Viola', 'cast', 'invited', 'u-1', now())"
            ),
            {"id": str(uuid.uuid4()), "org": ORG_A, "p": production_id},
        )
        c.execute(
            text(
                "INSERT INTO productions_task "
                "(id, organisation_id, production_id, title, status, position, added_by, created_at) "
                "VALUES (:id, :org, :p, 'Hire lights', 'open', 1, 'u-1', now())"
            ),
            {"id": str(uuid.uuid4()), "org": ORG_A, "p": production_id},
        )

    with as_role(engine, role, ORG_B) as c:
        assert c.execute(text("SELECT count(*) FROM productions_role")).scalar() == 0
        assert c.execute(text("SELECT count(*) FROM productions_task")).scalar() == 0
        # Even the id is useless: the update matches no visible row.
        assert c.execute(text("UPDATE productions_role SET status = 'confirmed'")).rowcount == 0

    with pytest.raises(DBAPIError), as_role(engine, role, ORG_B) as c:
        c.execute(
            text(
                "INSERT INTO productions_task "
                "(id, organisation_id, production_id, title, status, position, added_by, created_at) "
                "VALUES (:id, :org, :p, 'Planted', 'open', 2, 'u-9', now())"
            ),
            {"id": str(uuid.uuid4()), "org": ORG_A, "p": production_id},
        )
