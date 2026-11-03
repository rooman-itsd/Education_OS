"""What workflow consumes (event-bus entry point `eos.event_consumers`): scheduler.job.due for its own job. The
outcome is reported with workflow.job.finished, which closes the scheduler's run."""

from __future__ import annotations

import logging

from eos_core import events
from sqlalchemy.orm import Session

from . import service
from .jobs import SLA_CHECK

log = logging.getLogger("eos.workflow")


def on_job_due(db: Session, event) -> None:
    """A failed check is reported, not raised: the next run (15 minutes later) checks again, and every step it
    missed is still overdue then."""
    payload = event.payload or {}
    if payload.get("job") != SLA_CHECK:
        return  # another module's job
    try:
        count = service.escalate_overdue(db)
        outcome, detail = "succeeded", f"{count} overdue step(s) escalated"
    except Exception as e:  # noqa: BLE001  reported to the run; never the message, which can carry data
        db.rollback()
        log.exception("workflow.sla-check failed")
        outcome, detail = "failed", type(e).__name__
    events.publish(
        db,
        "workflow.job.finished",
        event.organisation_id,
        {"run_id": payload.get("run_id"), "outcome": outcome, "detail": detail},
    )


CONSUMERS = {"scheduler.job.due": on_job_due}
