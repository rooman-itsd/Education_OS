"""The daily jobs for the scheduler platform service (docs/prd.md flows 6 and 7): flag overdue loans once, and expire
holds that were not collected, passing the copy to the next member waiting. They run across organisations in
platform scope; each event still carries its own organisation_id. Until platform/scheduler calls them, a host app
calls run_daily() on a timer."""

from __future__ import annotations

from eos_core.tenant import platform_scope
from sqlalchemy.orm import Session

from ..infrastructure import repository as repo
from ..infrastructure.models import Copy, iso
from . import service


def flag_overdue_loans(db: Session) -> int:
    """Publish library.loan.overdue once for every active loan past its due date. Returns how many."""
    now = service.clock()
    count = 0
    with platform_scope():
        for loan in repo.unflagged_overdue_loans(db, now.date()):
            loan.overdue_flagged_at = now
            service._publish(
                db,
                None,
                "loan.overdue",
                loan.organisation_id,
                {
                    "loan_id": loan.id,
                    "person_id": loan.person_id,
                    "title_id": loan.title_id,
                    "due_on": iso(loan.due_on),
                },
            )
            service._audit(db, None, "loan.overdue", "loan", loan.id, loan.organisation_id)
            count += 1
        db.commit()
    return count


def expire_holds(db: Session) -> int:
    """Expire ready reservations whose hold ran out; the copy is held for the next member or becomes available."""
    now = service.clock()
    count = 0
    with platform_scope():
        for r in repo.expired_holds(db, now.date()):
            copy_id = r.held_copy_id
            r.status, r.resolved_at = "expired", now
            service._publish(
                db,
                None,
                "reservation.expired",
                r.organisation_id,
                {"reservation_id": r.id, "person_id": r.person_id, "title_id": r.title_id},
            )
            service._audit(db, None, "reservation.expired", "reservation", r.id, r.organisation_id)
            db.flush()
            # Title and copy ids are unique, so the queue below belongs to this reservation's organisation.
            c = db.get(Copy, copy_id) if copy_id else None
            if c is not None and c.status == "on-hold":
                service._hold_or_release(db, None, c)
            count += 1
        db.commit()
    return count


def run_daily(db: Session) -> dict:
    """Both daily jobs, on the module's clock (service.clock), so holds and due dates use the same "today"."""
    return {"overdue": flag_overdue_loans(db), "expired_holds": expire_holds(db)}
