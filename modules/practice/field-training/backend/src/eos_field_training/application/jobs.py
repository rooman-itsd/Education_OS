"""Daily job for the scheduler platform service (docs/prd.md flow 4): assigned placements become active on their
start date. It runs across organisations in platform scope; each event still carries its own organisation_id.
Until platform/scheduler exists, a host app calls run_daily() on a timer, once a day after midnight Asia/Kolkata."""

from __future__ import annotations

from datetime import date

from eos_core.tenant import platform_scope
from sqlalchemy.orm import Session

from ..infrastructure import repository as repo
from . import service


def start_due_placements(db: Session, on: date | None = None) -> int:
    """Start every assigned placement whose start date has come; publish field-training.placement.started once each.
    A placement the job missed (the scheduler was down) starts on the next run, dated that day. Returns how many."""
    on = on or service.today()
    count = 0
    with platform_scope():
        for p in repo.assigned_from(db, on):
            service._started(db, None, p, on)
            count += 1
        db.commit()
    return count


def run_daily(db: Session) -> dict[str, int]:
    return {"placements_started": start_due_placements(db)}
