"""The daily auto-close job (PRD main flow 7): close tickets resolved more than HELPDESK_AUTO_CLOSE_DAYS ago that the
requester has not confirmed. It runs across organisations in platform scope; each event still carries its own
organisation_id, with closed_by null. Idempotent: a closed ticket is never closed again, as the scheduler contract
requires of every job handler. Until platform/scheduler exists, a host app calls run_auto_close() on a timer."""

from __future__ import annotations

from datetime import datetime

from eos_core.tenant import platform_scope
from sqlalchemy.orm import Session

from ..domain.windows import due_for_auto_close
from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from . import service


def run_auto_close(db: Session, now: datetime | None = None) -> int:
    """Close every ticket that is due. Returns how many were closed."""
    now = now or service.clock()
    days = load_settings().auto_close_days
    count = 0
    with platform_scope():
        for ticket in repo.resolved_tickets(db):
            if due_for_auto_close(ticket.status, service.as_utc(ticket.resolved_at), now, days):
                service._close(db, None, ticket, None, now)
                count += 1
        db.commit()
    return count
