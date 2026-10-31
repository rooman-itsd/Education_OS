"""What e-office consumes (event-bus entry point `eos.event_consumers`): scheduler.job.due for its own job. The run's
outcome is reported with e-office.job.finished, which closes the scheduler's run. The relay runs the handler in the
event's scope (platform scope for the platform job) and commits after it, as for billing."""

from __future__ import annotations

from eos_core import events
from sqlalchemy.orm import Session

from . import service

JOB = "e-office.flag-overdue"


def on_job_due(db: Session, event) -> None:
    payload = event.payload or {}
    if payload.get("job") != JOB:
        return  # another module's job
    flagged = service.flag_overdue(db)
    events.publish(
        db,
        "e-office.job.finished",
        event.organisation_id,
        {"run_id": payload.get("run_id"), "outcome": "succeeded", "detail": f"{flagged} file(s) flagged overdue"},
    )


CONSUMERS = {"scheduler.job.due": on_job_due}
