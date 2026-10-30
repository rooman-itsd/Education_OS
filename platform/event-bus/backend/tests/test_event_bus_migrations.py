"""The chain owns outbox_event: a new database gets it from 0001, a database the API already started on keeps its
table (0001 is recorded, not run), and both end at a head that matches eos_core's model column for column."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from eos_core.events import OutboxEvent
from sqlalchemy import JSON, Boolean, Column, DateTime, MetaData, String, Table, create_engine, inspect, text

CHAIN = Path(__file__).resolve().parents[2] / "db"


def _config(url: str) -> Config:
    cfg = Config(str(CHAIN / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url}"]})()
    return cfg


def _url() -> str:
    return f"sqlite:///{tempfile.mkdtemp()}/chain.db"


def _shape(url: str) -> tuple[dict, set]:
    table = inspect(create_engine(url))
    columns = {c["name"]: (type(c["type"]).__name__.upper(), c["nullable"]) for c in table.get_columns("outbox_event")}
    indexes = {(i["name"], tuple(i["column_names"])) for i in table.get_indexes("outbox_event")}
    return columns, indexes


def _model_shape() -> tuple[dict, set]:
    url = _url()
    engine = create_engine(url)
    OutboxEvent.__table__.create(engine)
    return _shape(url)


def test_a_new_database_reaches_a_head_that_matches_the_model():
    url = _url()
    command.upgrade(_config(url), "head")
    assert _shape(url) == _model_shape()
    assert "event_bus_alembic_version" in inspect(create_engine(url)).get_table_names()


def test_a_database_the_api_created_keeps_its_rows_which_are_not_redelivered():
    """Rows written before any relay existed are marked published, so starting the relay does not mail history."""
    url = _url()
    engine = create_engine(url)
    old = Table(
        "outbox_event",
        MetaData(),
        Column("id", String(36), primary_key=True),
        Column("organisation_id", String(36), index=True, nullable=True),
        Column("name", String(120), index=True, nullable=False),
        Column("actor", String(36), nullable=True),
        Column("payload", JSON, nullable=False),
        Column("occurred_at", DateTime(timezone=True), nullable=False),
        Column("published", Boolean, nullable=False),
    )
    old.create(engine)
    with engine.begin() as c:
        c.execute(
            old.insert().values(
                id="e1",
                name="tenancy.organisation.registered",
                payload={},
                occurred_at=datetime(2026, 10, 1, tzinfo=UTC),
                published=False,
            )
        )
    command.upgrade(_config(url), "head")
    assert _shape(url) == _model_shape()
    with engine.connect() as c:
        published, attempts, version = c.execute(text("SELECT published, attempts, version FROM outbox_event")).one()
    assert published and attempts == 0 and version == 1


def test_the_chain_downgrades_to_nothing():
    url = _url()
    command.upgrade(_config(url), "head")
    command.downgrade(_config(url), "base")
    assert "outbox_event" not in inspect(create_engine(url)).get_table_names()
