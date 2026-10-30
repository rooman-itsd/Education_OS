"""The chain's head matches the models, the settings are bounded, and the arq worker runs the same tick."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from eos_core.db import Base
from eos_scheduler.domain.models import TABLE_NAMES
from eos_scheduler.infrastructure.config import SchedulerConfig
from sqlalchemy import create_engine, inspect

CHAIN = Path(__file__).resolve().parents[2] / "db"


def _shape(url: str) -> dict:
    found = inspect(create_engine(url))
    return {
        t: (
            {c["name"]: (type(c["type"]).__name__.upper(), c["nullable"]) for c in found.get_columns(t)},
            {(i["name"], tuple(i["column_names"])) for i in found.get_indexes(t)},
        )
        for t in TABLE_NAMES
    }


def test_the_chain_head_matches_the_models_and_downgrades_cleanly():
    url = f"sqlite:///{tempfile.mkdtemp()}/chain.db"
    cfg = Config(str(CHAIN / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url}"]})()
    command.upgrade(cfg, "head")
    model_url = f"sqlite:///{tempfile.mkdtemp()}/model.db"
    Base.metadata.create_all(create_engine(model_url), tables=[Base.metadata.tables[t] for t in TABLE_NAMES])
    assert _shape(url) == _shape(model_url)
    command.downgrade(cfg, "base")
    assert not set(TABLE_NAMES) & set(inspect(create_engine(url)).get_table_names())


def test_defaults_match_env_example():
    assert SchedulerConfig.from_env() == SchedulerConfig()


@pytest.mark.parametrize(
    ("key", "value"),
    [("SCHEDULER_TICK_INTERVAL_S", "0"), ("SCHEDULER_DEFAULT_CATCH_UP", "twice"), ("SCHEDULER_ENABLED", "yes")],
)
def test_an_unusable_setting_is_refused(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match=key):
        SchedulerConfig.from_env()


def test_the_arq_worker_ticks_and_prunes_on_its_clock_without_needing_redis_to_import():
    from eos_scheduler import worker

    names = {job.name for job in worker.WorkerSettings.cron_jobs}
    assert names == {"cron:tick", "cron:prune"}
    assert all(job.unique for job in worker.WorkerSettings.cron_jobs)
