"""Background sweeps for the scheduler platform service (PRD rules 2, 5 and 7). They run across organisations in
platform scope; each event still carries its own organisation_id. Until platform/scheduler exists, a host
app calls run_sweeps() on a timer."""

from __future__ import annotations

from datetime import datetime

from eos_core.tenant import platform_scope
from sqlalchemy.orm import Session

from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from . import service


def run_sweeps(db: Session, now: datetime | None = None) -> dict:
    """Raise due preventive tickets, flag SLA breaches and auto-close resolved tickets nobody confirmed.
    Returns how many of each happened."""
    settings = load_settings()
    now = now or service.clock()
    counts = {"preventive_raised": 0, "sla_breached": 0, "auto_closed": 0}
    with platform_scope():
        for s in repo.active_schedules_unscoped(db):
            if service.schedule_due(db, s, now.date()):
                service.raise_from_schedule(db, None, s, settings)
                counts["preventive_raised"] += 1
        for t in repo.tickets_unscoped(db, ("open", "assigned", "in_progress")):
            counts["sla_breached"] += service.flag_breaches(db, t, now)
        for t in repo.tickets_unscoped(db, ("resolved",)):
            if service.auto_close(db, t, now, settings):
                counts["auto_closed"] += 1
        db.commit()
    return counts
