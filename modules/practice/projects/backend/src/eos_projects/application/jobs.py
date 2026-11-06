"""Daily job for the scheduler platform service (docs/prd.md flow 4): publish projects.milestone.overdue once per
milestone the day after its due date when it is still pending or returned. It runs across organisations in platform
scope; each event still carries its own organisation_id. Until platform/scheduler exists, a host app calls
run_daily() on a timer, best just after midnight in Asia/Kolkata, when the business date changes."""

from __future__ import annotations

from datetime import date

from eos_core.tenant import platform_scope
from sqlalchemy.orm import Session

from ..infrastructure import repository as repo
from ..infrastructure.models import iso
from . import service


def flag_overdue_milestones(db: Session, on: date | None = None) -> int:
    """Publish projects.milestone.overdue for every pending or returned milestone of an active project due before
    `on` (default: today in Asia/Kolkata) that has not been flagged yet. Returns how many were flagged."""
    on = on or service.today()
    count = 0
    with platform_scope():
        for m in repo.overdue_candidates(db, on):
            m.overdue_flagged_at = service.clock()
            service._publish(
                db,
                None,
                "milestone.overdue",
                m.organisation_id,
                {"milestone_id": m.id, "project_id": m.project_id, "due_on": iso(m.due_on)},
            )
            service._audit(db, None, "milestone.overdue", "milestone", m.id, m.organisation_id)
            count += 1
        db.commit()
    return count


def run_daily(db: Session) -> dict[str, int]:
    return {"milestones_overdue": flag_overdue_milestones(db)}
