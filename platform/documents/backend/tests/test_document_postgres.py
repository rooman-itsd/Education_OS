"""PostgreSQL row-level security tests for documents: proves tenant isolation as non-superuser eos_app."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

ADMIN_URL = os.environ.get("EOS_PG_ADMIN_URL")
pytestmark = pytest.mark.skipif(not ADMIN_URL, reason="set EOS_PG_ADMIN_URL to run the PostgreSQL checks")

DB_DIR = Path(__file__).resolve().parents[2] / "db"
DATABASE = "eos_documents_pg"
APP_ROLE = "eos_app"
APP_PASSWORD = "eos_app_test"
ORG_A = str(uuid.uuid4())
ORG_B = str(uuid.uuid4())


def _admin(database: str | None = None):
    url = ADMIN_URL if database is None else ADMIN_URL.rsplit("/", 1)[0] + "/" + database
    return create_engine(url, isolation_level="AUTOCOMMIT", future=True)


def _app_url() -> str:
    base = ADMIN_URL.rsplit("/", 1)[0]
    scheme, _, rest = base.partition("://")
    return f"{scheme}://{APP_ROLE}:{APP_PASSWORD}@{rest.rsplit('@', 1)[-1]}/{DATABASE}"


@pytest.fixture(scope="module")
def app_engine():
    with _admin().begin() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {DATABASE}"))
        if not conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": APP_ROLE}).scalar():
            conn.execute(text(f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{APP_PASSWORD}'"))
        conn.execute(text(f"ALTER ROLE {APP_ROLE} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"))
        conn.execute(text(f"CREATE DATABASE {DATABASE}"))

    cfg = Config(str(DB_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={ADMIN_URL.rsplit('/', 1)[0]}/{DATABASE}"]})()
    command.upgrade(cfg, "head")

    with _admin(DATABASE).begin() as conn:
        conn.execute(text(f"GRANT ALL ON ALL TABLES IN SCHEMA public TO {APP_ROLE}"))
        conn.execute(text(f"GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}"))

    engine = create_engine(_app_url(), future=True)
    yield engine
    engine.dispose()


def _as(conn, org: str | None, *, bypass: bool = False):
    conn.execute(text("SELECT set_config('app.organisation_id', :o, true)"), {"o": org or ""})
    conn.execute(text("SELECT set_config('app.bypass_rls', :b, true)"), {"b": "on" if bypass else "off"})


def _insert_doc(conn, org: str) -> str:
    doc_id = str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO documents_document (id, organisation_id, title, filename, mime_type, size_bytes, storage_path, bucket, status, uploaded_by, tags, created_at, updated_at) "
            "VALUES (:id, :org, 'Doc Title', 'doc.pdf', 'application/pdf', 1024, 'path/to/doc', 'bucket', 'available', 'user-1', '[]', now(), now())"
        ),
        {"id": doc_id, "org": org},
    )
    return doc_id


def test_the_app_role_is_not_superuser_or_bypass(app_engine):
    with app_engine.connect() as conn:
        sup, bypass = conn.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
    assert not sup and not bypass


def test_organisation_isolation_on_documents(app_engine):
    with app_engine.begin() as conn:
        _as(conn, ORG_A)
        doc_a = _insert_doc(conn, ORG_A)

    with app_engine.begin() as conn:
        _as(conn, ORG_B)
        doc_b = _insert_doc(conn, ORG_B)

    # When connected as ORG_A, cannot see ORG_B
    with app_engine.begin() as conn:
        _as(conn, ORG_A)
        visible = set(conn.execute(text("SELECT id FROM documents_document")).scalars())
        assert doc_a in visible
        assert doc_b not in visible


def test_organisation_cannot_write_into_another(app_engine):
    with pytest.raises(DBAPIError), app_engine.begin() as conn:
        _as(conn, ORG_A)
        # Attempting to insert a row for ORG_B while authenticated as ORG_A
        _insert_doc(conn, ORG_B)
