"""What billing consumes (event-bus entry point `eos.event_consumers`): scheduler.job.due for its own jobs. Each
job reports its outcome with billing.job.finished, which closes the scheduler's run."""

from __future__ import annotations

from eos_core import events
from sqlalchemy.orm import Session

from . import service

RUNS = {
    "billing.expire-trials": (service.expire_trials, "{} trial(s) expired"),
    "billing.trial-reminders": (service.remind_trials, "{} trial reminder(s) raised"),
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
        "billing.job.finished",
        event.organisation_id,
        {"run_id": payload.get("run_id"), "outcome": "succeeded", "detail": summary.format(count)},
    )


CONSUMERS = {"scheduler.job.due": on_job_due}
