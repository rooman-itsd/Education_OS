"""The scheduler on arq, the approved job runner: `arq eos_scheduler.worker.WorkerSettings`, with Redis at
SCHEDULER_REDIS_URL. arq only provides the clock and a single owner per Redis (its cron job is unique across
workers); the work is the same `tick` the plain loop runs, so the two behave identically."""

from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings

from .__main__ import build_ticker
from .infrastructure.config import SchedulerConfig


async def startup(ctx: dict) -> None:
    ctx["ticker"] = build_ticker()


async def tick(ctx: dict) -> None:
    ctx["ticker"].tick()


async def prune(ctx: dict) -> None:
    ctx["ticker"].prune()


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(SchedulerConfig.from_env().redis_url)
    on_startup = startup
    functions: list = []
    cron_jobs = [
        cron(tick, second={0, 30}, unique=True, run_at_startup=True),
        cron(prune, hour={3}, minute={0}, unique=True),
    ]
