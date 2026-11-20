"""What integration-hub consumes (event-bus entry point `eos.event_consumers`): scheduler.job.due for its own jobs.
Each job reports its outcome with integration-hub.job.finished, which closes the scheduler's run.

The event relay delivers events one after another, so a handler that called providers inline (a sweep of slow
adapters, each allowed minutes) would hold up mail and every other module's events. The handler therefore only hands
the job to a small worker pool of the hub's and returns; the job runs there, outside the relay's session and platform
scope, plans its work in platform scope and does each organisation's part as that organisation (application/common.py,
`as_organisation`), then publishes job.finished in a session of its own. Every job is idempotent and claims its rows,
so a run lost with the process is simply done by the next one; one job never runs twice at once in a process."""

from __future__ import annotations

import contextvars
import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor

from eos_core import events
from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from sqlalchemy.orm import Session

from . import authorisation, deliveries, health
from .jobs import HEALTH, PURGE, REFRESH, SWEEP

log = logging.getLogger("eos.integration_hub")

RUNS = {
    SWEEP: (deliveries.process_due, "{} delivery attempt(s)"),
    HEALTH: (health.check_due, "{} connection(s) checked"),
    REFRESH: (authorisation.refresh_due, "{} token(s) refreshed"),
    PURGE: (deliveries.purge, "{} row(s) purged"),
}

_POOL = ThreadPoolExecutor(max_workers=len(RUNS), thread_name_prefix="integration-hub-job")
_running: set[str] = set()
_lock = threading.Lock()


def _finished(run_id, outcome: str, detail: str) -> None:
    with platform_scope(), SessionLocal() as db:
        events.publish(
            db, "integration-hub.job.finished", None, {"run_id": run_id, "outcome": outcome, "detail": detail}
        )
        db.commit()


def run_job(job: str, run_id) -> None:
    """One run of a job, in the worker: the work, then its outcome for the scheduler. Never raises."""
    run, summary = RUNS[job]
    try:
        count = run()
    except Exception as e:  # noqa: BLE001 - the scheduler hears of the failure; the next run retries
        log.warning("job %s failed: %s", job, type(e).__name__)
        outcome, detail = "failed", f"{job} failed: {type(e).__name__}"
    else:
        outcome, detail = "succeeded", summary.format(count)
    finally:
        with _lock:
            _running.discard(job)
    try:
        _finished(run_id, outcome, detail)
    except Exception as e:  # noqa: BLE001 - the scheduler times the run out instead
        log.warning("job %s finished but could not be reported: %s", job, type(e).__name__)


def on_job_due(db: Session, event) -> Future | None:
    """Hand the job to the worker pool and return at once; the relay's session and scope are not used for it.
    Returns the future (tests wait on it), or None for another module's job or one this process is still running."""
    payload = event.payload or {}
    job = payload.get("job")
    if job not in RUNS:
        return None  # another module's job
    with _lock:
        if job in _running:
            busy = True
        else:
            busy = False
            _running.add(job)
    if busy:
        events.publish(
            db,
            "integration-hub.job.finished",
            event.organisation_id,
            {
                "run_id": payload.get("run_id"),
                "outcome": "succeeded",
                "detail": "skipped: the previous run is still going",
            },
        )
        return None
    # A fresh context: nothing of the relay's (its platform scope among it) reaches the job.
    return _POOL.submit(contextvars.Context().run, run_job, job, payload.get("run_id"))


CONSUMERS = {"scheduler.job.due": on_job_due}
