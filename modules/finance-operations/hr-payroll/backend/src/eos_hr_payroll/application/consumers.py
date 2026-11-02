"""What hr-payroll consumes (event-bus entry point `eos.event_consumers`, module.yaml consumes_events):
scheduler.job.due for its own job. The bus runs a platform job's event in platform scope, in its own transaction, and
commits it; the job reports its outcome with hr-payroll.job.finished, which closes the scheduler's run.

The event is read by attribute (organisation_id, payload), so this module does not import the event bus."""

from __future__ import annotations

from eos_core import events
from sqlalchemy.orm import Session

from . import employees

JOB = "hr-payroll.publish-due-exits"


def on_job_due(db: Session, event) -> None:
    payload = event.payload or {}
    if payload.get("job") != JOB:
        return  # another module's job
    count = employees.publish_due_exits(db)
    events.publish(
        db,
        "hr-payroll.job.finished",
        event.organisation_id,
        {"run_id": payload.get("run_id"), "outcome": "succeeded", "detail": f"{count} exit(s) published"},
    )


CONSUMERS = {"scheduler.job.due": on_job_due}
