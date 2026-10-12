"""Background sweeps for the scheduler platform service (PRD rules 8 and the lifecycle in section 5).
They run across organisations in platform scope; each event still carries its own organisation_id.
Until platform/scheduler exists, a host app calls run_sweeps() on a timer."""

from __future__ import annotations

from datetime import datetime, timedelta

from eos_core.tenant import platform_scope
from sqlalchemy.orm import Session

from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from ..infrastructure.models import Resource, as_utc, iso
from . import service


def run_sweeps(db: Session, now: datetime | None = None) -> dict:
    """Mark no-shows and completed bookings. Returns how many of each changed."""
    settings = load_settings()
    now = now or service.clock()
    grace = timedelta(minutes=settings.no_show_grace_minutes)
    counts = {"no_show": 0, "completed": 0}
    with platform_scope():
        check_in_required: dict[str, bool] = {}
        for b in repo.all_unfinished_bookings(db):
            start, end = as_utc(b.start_at), as_utc(b.end_at)
            if b.resource_id not in check_in_required:
                r = db.get(Resource, b.resource_id)
                check_in_required[b.resource_id] = bool(r) and service._rules_for(db, r, settings).check_in_required
            if b.status == "confirmed" and check_in_required[b.resource_id] and now > start + grace:
                service._mark_no_show(db, None, b, "scheduler")
                counts["no_show"] += 1
            elif end <= now and (b.status == "checked_in" or not check_in_required[b.resource_id]):
                b.status = "completed"
                service._publish(
                    db,
                    None,
                    "booking.completed",
                    b.organisation_id,
                    {
                        "booking_id": b.id,
                        "resource_id": b.resource_id,
                        "booked_for": b.booked_for,
                        "start_at": iso(start),
                        "end_at": iso(end),
                    },
                )
                counts["completed"] += 1
        db.commit()
    return counts
