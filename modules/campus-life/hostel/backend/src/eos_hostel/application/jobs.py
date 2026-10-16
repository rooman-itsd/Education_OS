"""The daily job for the scheduler platform service (docs/prd.md flow 6): flag residents not back from leave.
It runs across organisations in platform scope; each event still carries its own organisation_id.
Until platform/scheduler exists, a host app calls flag_overdue_leave() on a timer."""

from __future__ import annotations

from datetime import datetime

from eos_core.tenant import platform_scope
from sqlalchemy.orm import Session

from ..infrastructure import repository as repo
from ..infrastructure.models import iso
from . import service


def flag_overdue_leave(db: Session, now: datetime | None = None) -> int:
    """Publish hostel.leave.overdue once for every approved leave past its end without a return. Returns how many."""
    now = now or service.clock()
    count = 0
    with platform_scope():
        for lv in repo.unflagged_overdue_leave(db, now):
            lv.overdue_flagged_at = now
            service._publish(
                db,
                None,
                "leave.overdue",
                lv.organisation_id,
                {"leave_id": lv.id, "person_id": lv.person_id, "hostel_id": lv.hostel_id, "due_at": iso(lv.to_at)},
            )
            service._audit(db, None, "leave.overdue", "leave", lv.id, lv.organisation_id)
            count += 1
        db.commit()
    return count
