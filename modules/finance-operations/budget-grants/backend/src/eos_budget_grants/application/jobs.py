"""The daily sweep. Until platform/scheduler exists, the host calls `run_daily(db)` once a day."""

from __future__ import annotations

from datetime import date

from eos_core.tenant import organisation_scope, platform_scope
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..infrastructure.config import load_settings
from ..infrastructure.models import Alert, Grant
from . import service


def run_daily(db: Session, day: date | None = None) -> dict:
    """Publish budget-grants.utilisation-certificate.due for every active grant whose next certificate falls due within
    a reminder window (BUDGET_GRANTS_UC_REMINDER_DAYS), once per grant, due date and window."""
    day = day or service.today()
    db.rollback()  # never inherit an open transaction begun in another scope
    windows = sorted(load_settings().uc_reminder_days, reverse=True)
    with platform_scope():
        grants = [(g.id, g.organisation_id) for g in db.scalars(select(Grant).where(Grant.status == "active"))]
        db.commit()
    sent = 0
    for grant_id, org in grants:
        with organisation_scope(org):
            g = db.scalar(service._q(db, Grant).where(Grant.id == grant_id))
            due = service.grant_next_uc_due(db, g) if g else None
            if due is None:
                db.rollback()
                continue
            days_left = (due - day).days
            window = next((w for w in reversed(windows) if days_left <= w), None)  # the tightest window reached
            if window is None:
                db.rollback()
                continue
            key = f"{due.isoformat()}/{window}"
            if db.scalar(
                service._q(db, Alert).where(Alert.kind == "uc_due", Alert.subject_id == g.id, Alert.key == key)
            ):
                db.rollback()
                continue
            db.add(Alert(organisation_id=org, kind="uc_due", subject_id=g.id, key=key, sent_at=service.clock()))
            service._publish(
                db,
                "utilisation-certificate.due",
                org,
                {"grant_id": g.id, "due_on": due.isoformat(), "days_left": days_left},
            )
            try:
                db.commit()
                sent += 1
            except IntegrityError:
                db.rollback()  # another sweep sent it first
    return {"reminders_published": sent}
