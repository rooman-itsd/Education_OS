"""integration-hub on a real PostgreSQL: the guarantees SQLite cannot show (row locks, unique indexes under
concurrency, forced row-level security), for the OAuth state redemption, webhook dedupe, callback resolution and
invoke idempotency.

Skipped unless INTEGRATION_HUB_TEST_POSTGRES_URL points at a PostgreSQL server as a superuser, for example the
postgres:16-alpine service CI runs (.github/workflows/api.yml). Point it at a throwaway server only. The test never
touches existing data: it creates its own database (integration_hub_pg_<random>), runs the hub's Alembic chain into
it, and drops it at the end, also when a check fails."""

import os
import threading
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

SERVER_URL = os.environ.get("INTEGRATION_HUB_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not SERVER_URL, reason="INTEGRATION_HUB_TEST_POSTGRES_URL is not set")

DB_DIR = Path(__file__).resolve().parents[2] / "db"
ADAPTER = "fake-adapter"


def _server_url():
    from sqlalchemy.engine import make_url

    url = make_url(SERVER_URL)
    if url.get_backend_name() != "postgresql":
        pytest.fail("INTEGRATION_HUB_TEST_POSTGRES_URL must be a postgresql:// URL")
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")  # the driver on the approved stack
    return url


def _alembic(url, revision: str, upgrade: bool) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(DB_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(DB_DIR / "migrations"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url.render_as_string(hide_password=False)}"]})()
    (command.upgrade if upgrade else command.downgrade)(cfg, revision)


@pytest.fixture(scope="module")
def pg():
    """A sessionmaker on a throwaway database holding the hub's schema. Dropped afterwards."""
    pytest.importorskip("psycopg")
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    server = _server_url()
    db_name = f"integration_hub_pg_{uuid.uuid4().hex[:12]}"
    admin = create_engine(server, isolation_level="AUTOCOMMIT")
    engine = None
    try:
        with admin.connect() as c:
            c.execute(text(f'CREATE DATABASE "{db_name}"'))
        db_url = server.set(database=db_name)
        _alembic(db_url, "head", upgrade=True)
        engine = create_engine(db_url)
        try:
            yield sessionmaker(bind=engine, expire_on_commit=False)
        finally:
            engine.dispose()
            _alembic(db_url, "base", upgrade=False)  # the chain also downgrades cleanly on Postgres
    finally:
        if engine is not None:
            engine.dispose()
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
        admin.dispose()


def _now():
    from eos_integration_hub.application.common import clock

    return clock()


def _connection(db, org: str, **fields):
    from eos_integration_hub.infrastructure.models import Connection

    c = Connection(
        organisation_id=org,
        adapter=ADAPTER,
        provider=fields.pop("provider", "fakewear"),
        port=fields.pop("port", "wearable-data"),
        mode="sandbox",
        enabled=True,
        settings={},
        connection_key_hash=uuid.uuid4().hex * 2,
        authorised=False,
        health_status="healthy",
        health_window_runs=0,
        **fields,
    )
    db.add(c)
    db.flush()
    return c


def _link(db, c, subject: str, status: str, created_at):
    from eos_integration_hub.infrastructure.models import AccountLink

    link = AccountLink(
        organisation_id=c.organisation_id,
        connection_id=c.id,
        person_id=str(uuid.uuid4()),
        port=c.port,
        provider=c.provider,
        provider_subject=subject,
        status=status,
        granted_scopes=[],
        created_at=created_at,
    )
    db.add(link)
    db.flush()
    return link


def test_every_hub_table_has_the_forced_tenant_isolation_policy(pg):
    from eos_integration_hub.infrastructure.models import TABLES
    from sqlalchemy import text

    with pg() as db:
        policies = {
            r[0] for r in db.execute(text("SELECT tablename FROM pg_policies WHERE policyname = 'tenant_isolation'"))
        }
        forced = {
            r[0] for r in db.execute(text("SELECT relname FROM pg_class WHERE relrowsecurity AND relforcerowsecurity"))
        }
    names = {t.name for t in TABLES}
    assert names <= policies and names <= forced, sorted(names - (policies & forced))


# ------------------------------------------------------------------ finding 2: the state is redeemed once


def test_a_state_is_redeemed_once_while_a_second_redemption_waits_on_the_row_lock(pg):
    from eos_core.tenant import platform_scope
    from eos_integration_hub.application.authorisation import claim_state
    from eos_integration_hub.infrastructure.models import OAuthState

    org, state_hash = str(uuid.uuid4()), uuid.uuid4().hex * 2
    with platform_scope():
        with pg() as db:
            db.add(
                OAuthState(
                    organisation_id=org,
                    state_hash=state_hash,
                    adapter=ADAPTER,
                    connection_id=str(uuid.uuid4()),
                    person_id=str(uuid.uuid4()),
                    browser_binding_hash="0" * 64,
                    code_verifier_encrypted=b"x",
                    return_url="https://app.example.test/",
                    expires_at=_now() + timedelta(minutes=10),
                    created_at=_now(),
                )
            )
            db.commit()
        first, second = pg(), pg()
        try:
            assert claim_state(first, state_hash, ADAPTER, _now()) == 1  # not committed: it holds the row
            got = {}

            def race():
                with platform_scope():
                    got["second"] = claim_state(second, state_hash, ADAPTER, _now())

            t = threading.Thread(target=race)
            t.start()
            t.join(timeout=1)
            assert t.is_alive()  # the second redemption waits for the first's transaction
            first.commit()
            t.join(timeout=10)
            assert got["second"] == 0  # re-checked after the commit: used_at is set, nothing matches
            second.commit()
        finally:
            first.close()
            second.close()


# ------------------------------------------------------------------ finding 3: dedupe per connection


def test_the_same_event_id_is_unique_per_connection_not_per_adapter(pg):
    from eos_core.tenant import platform_scope
    from eos_integration_hub.infrastructure.models import InboundReceipt
    from sqlalchemy.exc import IntegrityError

    def receipt(org, conn):
        return InboundReceipt(
            organisation_id=org,
            adapter=ADAPTER,
            connection_id=conn,
            dedupe_key="evt-1",
            verdict="accepted",
            received_at=_now(),
        )

    a, b = (str(uuid.uuid4()), str(uuid.uuid4())), (str(uuid.uuid4()), str(uuid.uuid4()))
    with platform_scope(), pg() as db:
        db.add_all([receipt(*a), receipt(*b)])  # two organisations' connections, one event id: both kept
        db.commit()
        db.add(receipt(*a))
        with pytest.raises(IntegrityError):
            db.commit()  # the same connection's redelivery is refused by the database itself


# ------------------------------------------------------------------ finding 4: app-level callbacks resolve safely


def test_a_subject_resolves_to_the_one_active_link_never_a_revoked_or_ambiguous_one(pg):
    from eos_core.tenant import platform_scope
    from eos_integration_hub.application.inbound import _resolve

    subject = f"athlete-{uuid.uuid4().hex[:8]}"
    org_a, org_b, org_c = (str(uuid.uuid4()) for _ in range(3))
    with platform_scope(), pg() as db:
        ca, cb, cc = _connection(db, org_a), _connection(db, org_b), _connection(db, org_c)
        active = _link(db, ca, subject, "active", _now() - timedelta(days=2))
        _link(db, cb, subject, "revoked", _now())  # newer, but revoked
        db.commit()
        c, link = _resolve(db, ADAPTER, {"account_link_subject": subject})
        assert (c.id, link.id) == (ca.id, active.id)
        # the same provider account also active in a third organisation: ambiguous, never guessed
        in_c = _link(db, cc, subject, "active", _now())
        db.commit()
        assert _resolve(db, ADAPTER, {"account_link_subject": subject}) == (None, None)
        # unless the callback names the connection: then only that connection's links count
        c, link = _resolve(db, ADAPTER, {"account_link_subject": subject, "connection_id": cc.id})
        assert (c.id, link.id) == (cc.id, in_c.id)
        c, link = _resolve(db, ADAPTER, {"account_link_subject": subject, "connection_id": cb.id})
        assert (c.id, link) == (cb.id, None)


# ------------------------------------------------------------------ finding 6: one delivery per idempotency key


def test_two_invokes_racing_with_one_key_insert_one_delivery_on_postgres(pg, monkeypatch, client):
    from eos_core.tenant import platform_scope
    from eos_integration_hub.application import deliveries
    from eos_integration_hub.application.invoke import invoke
    from eos_integration_hub.infrastructure.models import Delivery
    from sqlalchemy import func, select
    from sqlalchemy.exc import IntegrityError

    org = str(uuid.uuid4())
    with platform_scope(), pg() as db:
        _connection(db, org, provider="fakecert", port="certificate-issuance")
        db.commit()
    monkeypatch.setattr(deliveries, "SessionLocal", pg)
    barrier = threading.Barrier(2)
    real = deliveries.enqueue

    def enqueue_after_both_checked(*a, **kw):
        try:
            barrier.wait(timeout=5)  # both calls found no delivery for the key
        except threading.BrokenBarrierError:
            pass
        return real(*a, **kw)

    monkeypatch.setattr(deliveries, "enqueue", enqueue_after_both_checked)
    results = []

    def call():
        results.append(
            invoke(
                port="certificate-issuance",
                operation="issue",
                input={"issuance_key": "pg-1", "doc_kind": "marksheet", "holder": {"person_id": "p-1"}},
                idempotency_key="exam:pg-1",
                caller_module="examinations",
                organisation_id=org,
            )
        )

    threads = [threading.Thread(target=call) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert len(results) == 2 and len({r["delivery_id"] for r in results}) == 1, results
    assert sorted(r["replayed"] for r in results) == [False, True]
    with platform_scope(), pg() as db:
        n = db.scalar(select(func.count()).select_from(Delivery).where(Delivery.organisation_id == org))
        assert n == 1
        # and the index itself refuses a second row for the key
        db.add(
            Delivery(
                organisation_id=org,
                direction="outbound",
                port="certificate-issuance",
                operation="issue",
                caller_module="examinations",
                idempotency_key="exam:pg-1",
                refs={},
                status="queued",
                attempts=0,
                sync=False,
                created_at=_now(),
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
