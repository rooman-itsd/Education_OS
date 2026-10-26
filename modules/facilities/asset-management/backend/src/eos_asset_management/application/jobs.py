"""Background sweep for the scheduler platform service (PRD rule 3). It runs across organisations in platform scope;
each event still carries its own organisation_id. Until platform/scheduler exists, a host app calls run_sweeps()
on a timer."""

from __future__ import annotations

from datetime import date

from eos_core.tenant import platform_scope
from sqlalchemy.orm import Session

from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from . import service


def run_sweeps(db: Session, today: date | None = None) -> dict:
    """Publish verification-overdue once per due date for every asset past it. Returns how many were flagged."""
    settings = load_settings()
    today = today or service.today()
    counts = {"verification_overdue": 0}
    with platform_scope():
        for a in repo.assets_unscoped(db):
            if service.flag_overdue(db, a, today, settings):
                counts["verification_overdue"] += 1
        db.commit()
    return counts
