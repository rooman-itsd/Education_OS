"""Daily jobs for the scheduler platform service (docs/prd.md flows 4, 5 and 7): expire passes, flag expiring
vehicle and driver documents, purge old positions. They run across organisations in platform scope; each event
still carries its own organisation_id. Until platform/scheduler exists, a host app calls run_daily() on a timer."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta

from eos_core.tenant import platform_scope
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain import rules
from ..infrastructure import repository as repo
from ..infrastructure.models import DocumentFlag, iso
from . import service

# config/env.example documents both keys.
DEFAULT_EXPIRY_NOTICE_DAYS = 30
DEFAULT_POSITION_RETENTION_DAYS = 30


def _days(key: str, default: int) -> int:
    try:
        return max(int(os.environ.get(key, default)), 0)
    except ValueError:
        return default


def expire_passes(db: Session, on: date | None = None) -> int:
    """Expire every issued pass whose end date has passed; publish transport.pass.expired once each. Returns how many."""
    on = on or service.today()
    count = 0
    with platform_scope():
        for p in repo.issued_past_end(db, on):
            p.status = rules.transition(rules.PASS_TRANSITIONS, "expire", p.status)
            service._publish(
                db,
                None,
                "pass.expired",
                p.organisation_id,
                {"pass_id": p.id, "person_id": p.person_id, "route_id": p.route_id},
            )
            service._audit(db, None, "pass.expired", "pass", p.id, p.organisation_id)
            count += 1
        db.commit()
    return count


def flag_expiring_documents(db: Session, on: date | None = None, days: int | None = None) -> int:
    """Publish transport.document.expiry-flagged once per document `days` (default 30) before it expires. A document
    already inside the window when it is recorded is flagged on the next run. Returns how many were flagged."""
    on = on or service.today()
    days = _days("TRANSPORT_DOCUMENT_EXPIRY_NOTICE_DAYS", DEFAULT_EXPIRY_NOTICE_DAYS) if days is None else days
    count = 0
    with platform_scope():
        subjects = [("vehicle", v, service._vehicle_documents(v)) for v in repo.all_vehicles(db)]
        subjects += [("driver", d, {"licence": d.licence_expires_on}) for d in repo.all_drivers(db)]
        for subject, row, documents in subjects:
            for document, expires_on in documents.items():
                if not rules.expires_within(expires_on, on, days):
                    continue
                flagged = db.scalars(
                    select(DocumentFlag).where(
                        DocumentFlag.organisation_id == row.organisation_id,
                        DocumentFlag.subject_id == row.id,
                        DocumentFlag.document == document,
                        DocumentFlag.expires_on == expires_on,
                    )
                ).first()
                if flagged is not None:
                    continue
                db.add(
                    DocumentFlag(
                        organisation_id=row.organisation_id,
                        subject=subject,
                        subject_id=row.id,
                        document=document,
                        expires_on=expires_on,
                        flagged_at=service.clock(),
                    )
                )
                service._publish(
                    db,
                    None,
                    "document.expiry-flagged",
                    row.organisation_id,
                    {"subject": subject, "subject_id": row.id, "document": document, "expires_on": iso(expires_on)},
                )
                count += 1
        db.commit()
    return count


def purge_positions(db: Session, now: datetime | None = None, retention_days: int | None = None) -> int:
    """Delete positions older than the retention period (default 30 days, PRD open question 2). Returns how many."""
    now = now or service.clock()
    if retention_days is None:
        retention_days = _days("TRANSPORT_POSITION_RETENTION_DAYS", DEFAULT_POSITION_RETENTION_DAYS)
    with platform_scope():
        count = repo.purge_positions(db, now - timedelta(days=retention_days))
        db.commit()
    return count


def run_daily(db: Session) -> dict[str, int]:
    return {
        "passes_expired": expire_passes(db),
        "documents_flagged": flag_expiring_documents(db),
        "positions_purged": purge_positions(db),
    }
