"""What integration-hub consumes (event-bus entry point `eos.event_consumers`): scheduler.job.due for its own jobs.
Each job reports its outcome with integration-hub.job.finished, which closes the scheduler's run."""

from __future__ import annotations

from eos_core import events
from sqlalchemy.orm import Session

from . import authorisation, deliveries, health
from .jobs import HEALTH, PURGE, REFRESH, SWEEP

RUNS = {
    SWEEP: (deliveries.process_due, "{} delivery attempt(s)"),
    HEALTH: (health.check_due, "{} connection(s) checked"),
    REFRESH: (authorisation.refresh_due, "{} token(s) refreshed"),
    PURGE: (deliveries.purge, "{} row(s) purged"),
}


def on_job_due(db: Session, event) -> None:
    payload = event.payload or {}
    job = payload.get("job")
    if job not in RUNS:
        return  # another module's job
    run, summary = RUNS[job]
    count = run(db)
    events.publish(
        db,
        "integration-hub.job.finished",
        event.organisation_id,
        {"run_id": payload.get("run_id"), "outcome": "succeeded", "detail": summary.format(count)},
    )


CONSUMERS = {"scheduler.job.due": on_job_due}
