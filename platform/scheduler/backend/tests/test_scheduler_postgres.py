"""PostgreSQL: two schedulers starting together seed a platform default once (#316 audit, F5).

Before scheduler_0002, seed_platform_defaults() checked "no schedule yet" and inserted with no lock or key; the
audit reproduced a duplicate billing.expire-trials schedule in 20 out of 20 simultaneous start-ups, after which the
job ran twice per window. Runs only with EOS_PG_ADMIN_URL (a throwaway database is created), as the non-superuser
eos_app, with row-level security on."""

from __future__ import annotations

import os
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

ADMIN_URL = os.environ.get("EOS_PG_ADMIN_URL")
pytestmark = pytest.mark.skipif(not ADMIN_URL, reason="set EOS_PG_ADMIN_URL to run the PostgreSQL checks")

DB_DIR = Path(__file__).resolve().parents[2] / "db"
DATABASE = "eos_scheduler_pg"
APP_ROLE = "eos_app"
APP_PASSWORD = "eos_app_test"
ROUNDS = 20


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
    engine = create_engine(_app_url(), future=True)
    yield engine
    engine.dispose()


def test_the_app_role_cannot_bypass_row_level_security(app_engine):
    with app_engine.connect() as conn:
        assert conn.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")).one() == (
            False,
            False,
        )
        forced = conn.execute(
            text("SELECT relforcerowsecurity FROM pg_class WHERE relname = 'scheduler_seeded_default'")
        ).scalar()
    assert forced is True


def test_simultaneous_start_ups_seed_one_platform_schedule(app_engine):
    from eos_scheduler.application.jobs import Job
    from eos_scheduler.application.ticker import Ticker
    from eos_scheduler.infrastructure.config import SchedulerConfig

    job = "billing.expire-trials"
    jobs = {job: Job.declare("billing", job, {"scope": "platform", "default_cron": "15 0 * * *", "idempotent": True})}
    factory = sessionmaker(bind=app_engine, expire_on_commit=False)
    now = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)

    for _ in range(ROUNDS):
        with _admin(DATABASE).begin() as conn:
            conn.execute(text("DELETE FROM scheduler_schedule; DELETE FROM scheduler_seeded_default"))
        start = threading.Barrier(2)
        created: list[int] = []

        def start_up(start=start, created=created):
            ticker = Ticker(jobs, SchedulerConfig(), session_factory=factory, clock=lambda: now)
            start.wait()
            created.append(ticker.seed_platform_defaults())

        threads = [threading.Thread(target=start_up) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(15)
        with _admin(DATABASE).connect() as conn:
            schedules = conn.execute(
                text("SELECT count(*) FROM scheduler_schedule WHERE job = :j"), {"j": job}
            ).scalar()
        assert sorted(created) == [0, 1] and schedules == 1
