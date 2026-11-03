"""The reports behind the staff widgets: upcoming drives (placement-career.drives, story O8) and the openings summary
(placement-career.openings-summary, stories O9 and V1). Counts only: no student, declaration or offer appears here, so
the viewer (report:read without application:read) sees no individual application."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from ..domain import rules
from ..infrastructure.models import Application, Drive, Opening
from . import common as c
from .drives import drive_application_counts
from .openings import application_counts

UPCOMING_DAYS = 30


def drives_upcoming(db: Session, limit: int) -> dict:
    """Scheduled drives dated today (IST) or later, soonest first. openings_count counts the drive's published
    openings (open or closed), the ones students see."""
    today = c.business_today()
    upcoming = c.q(db, Drive).where(Drive.status == "scheduled", Drive.scheduled_on >= today)
    drives = list(db.scalars(upcoming.order_by(Drive.scheduled_on, Drive.created_at, Drive.id).limit(limit)))
    next_30 = db.scalar(
        c.count(db, Drive).where(
            Drive.status == "scheduled",
            Drive.scheduled_on >= today,
            Drive.scheduled_on <= today + timedelta(days=UPCOMING_DAYS),
        )
    )
    ids = [d.id for d in drives]
    companies = c.companies_by_id(db, [d.company_id for d in drives])
    openings = {}
    if ids:
        openings = dict(
            (drive_id, n)
            for n, drive_id in db.execute(
                c.count(db, Opening)
                .add_columns(Opening.drive_id)
                .where(Opening.drive_id.in_(ids), Opening.status.in_(rules.PUBLIC_OPENING_STATUSES))
                .group_by(Opening.drive_id)
            ).all()
        )
    applications = drive_application_counts(db, ids)
    return {
        "next_30_days": next_30 or 0,
        "drives": [
            {
                "id": d.id,
                "title": d.title,
                "company": c.company_summary(companies[d.company_id]),
                "scheduled_on": c.iso(d.scheduled_on),
                "venue": d.venue,
                "registration_closes_on": c.iso(d.registration_closes_on),
                "openings_count": openings.get(d.id, 0),
                "applications": applications[d.id],
            }
            for d in drives
        ],
    }


def openings_summary(db: Session, limit: int) -> dict:
    """Openings by status (draft, open, closed), applications by status, distinct students with an accepted offer, and
    the open openings with the soonest last day to apply."""
    openings = {"draft": 0, "open": 0, "closed": 0}
    for n, status in db.execute(c.count(db, Opening).add_columns(Opening.status).group_by(Opening.status)).all():
        if status in openings:
            openings[status] = n
    applications = dict.fromkeys(rules.APPLICATION_STATUSES, 0)
    for n, status in db.execute(
        c.count(db, Application).add_columns(Application.status).group_by(Application.status)
    ).all():
        applications[status] = n
    placed = db.scalar(
        c.scoped(db, select(func.count(distinct(Application.student_id))), Application).where(
            Application.status == "accepted"
        )
    )
    soonest = list(
        db.scalars(
            c.q(db, Opening)
            .where(Opening.status == "open")
            .order_by(Opening.applications_close_on, Opening.created_at, Opening.id)
            .limit(limit)
        )
    )
    companies = c.companies_by_id(db, [o.company_id for o in soonest])
    counts = application_counts(db, [o.id for o in soonest])
    return {
        "openings": openings,
        "applications": applications,
        "students_placed": placed or 0,
        "closing_soon": [
            {
                "id": o.id,
                "title": o.title,
                "company_name": companies[o.company_id].name,
                "applications_close_on": c.iso(o.applications_close_on),
                "applications_count": counts.get(o.id, 0),
            }
            for o in soonest
        ],
    }
