"""Background sweeps for the scheduler platform service (PRD rules 6 and 8). They run across organisations in
platform scope; each event still carries its own organisation_id. Until platform/scheduler exists, a host
app calls run_sweeps() on a timer."""

from __future__ import annotations

from datetime import datetime

from eos_core.tenant import platform_scope
from sqlalchemy.orm import Session

from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from ..infrastructure.models import as_utc, iso
from . import service


def run_sweeps(db: Session, now: datetime | None = None) -> dict:
    """Mark overdue loans and cancel approved loans nobody picked up. Returns how many of each changed."""
    settings = load_settings()
    now = now or service.clock()
    cutoff = service.expiry_cutoff(settings, now)
    counts = {"overdue": 0, "pickup_expired": 0}
    with platform_scope():
        for loan in repo.all_loans_unscoped(db, ("on_loan", "partially_returned")):
            if now > as_utc(loan.due_at):
                loan.status = "overdue"
                outstanding = [x.id for x in repo.lines_of(db, loan.id) if x.status == "out"]
                service._publish(
                    db,
                    None,
                    "loan.overdue",
                    loan.organisation_id,
                    {
                        "loan_id": loan.id,
                        "borrower_id": loan.borrower_id,
                        "due_at": iso(loan.due_at),
                        "outstanding_line_ids": outstanding,
                    },
                )
                counts["overdue"] += 1
        for loan in repo.all_loans_unscoped(db, ("approved",)):
            approved_at = as_utc(loan.approved_at or loan.created_at)
            if approved_at < cutoff:
                service._cancel(db, None, loan, "scheduler", "not picked up in time")
                counts["pickup_expired"] += 1
        db.commit()
    return counts
