"""The reindex worker on arq, the approved job runner: `arq eos_search.worker.WorkerSettings`, with Redis at
SEARCH_REDIS_URL and SEARCH_JOB_RUNNER=arq on the API. With the default `inline` runner the API process runs the job
itself after answering, which is what dev and CI use."""

from __future__ import annotations

import asyncio

from arq.connections import RedisSettings

from .application.reindex import run_reindex_job
from .infrastructure.config import SearchConfig


async def run_reindex(ctx, job_id: str) -> None:
    await asyncio.to_thread(run_reindex_job, job_id)


class WorkerSettings:
    functions = [run_reindex]
    redis_settings = RedisSettings.from_dsn(SearchConfig.from_env().redis_url)
    max_jobs = 2
    job_timeout = 3600
