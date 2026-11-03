"""Job openings (stories O4, O5, S1, S2): jobs only, never internships (P1). In a drive of the same company or on
their own (P3). draft -> open -> closed, or cancelled while there are no applications. An opening in a drive is
published once the drive is scheduled and stops taking applications on or before the drive date. Every reader sees the
CTC (P6); applications_count only with placement-career:application:read."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..domain import rules
from ..infrastructure.models import Application, Company, Drive, Opening
from . import common as c
from .access import APPLICATION_READ, Actor
from .drives import required_reason
from .errors import conflict, invalid


def opening_dict(o: Opening, company: Company, drive: Drive | None, applications_count: int | None) -> dict:
    return {
        "id": o.id,
        "organisation_id": o.organisation_id,
        "company_id": o.company_id,
        "drive_id": o.drive_id,
        "title": o.title,
        "description": o.description,
        "location": o.location,
        "ctc_per_annum": rules.money_text(o.ctc_per_annum),
        "positions": o.positions,
        "applications_close_on": c.iso(o.applications_close_on),
        "eligibility": c.eligibility(o.eligibility),
        "status": o.status,
        "company": c.company_summary(company),
        "drive": c.drive_brief(drive),
        "applications_count": applications_count,
        "cancel_reason": o.cancel_reason,
        "published_at": c.iso(o.published_at),
        "created_by": o.created_by,
        "created_at": c.iso(o.created_at),
    }


def application_counts(db: Session, opening_ids: list[str]) -> dict[str, int]:
    """Every application of each opening, a withdrawn one included."""
    if not opening_ids:
        return {}
    rows = db.execute(
        c.count(db, Application)
        .add_columns(Application.opening_id)
        .where(Application.opening_id.in_(opening_ids))
        .group_by(Application.opening_id)
    ).all()
    return {opening_id: n for n, opening_id in rows}


def _render_many(db: Session, actor: Actor, rows: list[Opening]) -> list[dict]:
    companies = c.companies_by_id(db, [o.company_id for o in rows])
    drives = c.drives_by_id(db, [o.drive_id for o in rows])
    visible = c.drive_statuses(actor)
    counts = application_counts(db, [o.id for o in rows]) if actor.can(APPLICATION_READ) else None
    out = []
    for o in rows:
        drive = drives.get(o.drive_id)
        out.append(
            opening_dict(
                o,
                companies[o.company_id],
                drive if drive is not None and drive.status in visible else None,
                None if counts is None else counts.get(o.id, 0),
            )
        )
    return out


def _render(db: Session, actor: Actor, o: Opening) -> dict:
    return _render_many(db, actor, [o])[0]


def list_openings(db: Session, actor: Actor, filters: dict, cursor, limit: int) -> dict:
    """Newest first. A caller without opening:manage sees open and closed openings only, whatever the filter."""
    query = c.q(db, Opening).where(Opening.status.in_(c.opening_statuses(actor)))
    if filters.get("status"):
        query = query.where(Opening.status == filters["status"])
    if filters.get("drive_id"):
        query = query.where(Opening.drive_id == filters["drive_id"])
    if filters.get("company_id"):
        query = query.where(Opening.company_id == filters["company_id"])
    if filters.get("without_drive") is True:
        query = query.where(Opening.drive_id.is_(None))
    elif filters.get("without_drive") is False:
        query = query.where(Opening.drive_id.is_not(None))
    query = query.order_by(Opening.created_at.desc(), Opening.id.desc())
    result = c.page(db, query, cursor, limit, lambda o: o)
    result["items"] = _render_many(db, actor, result["items"])
    return result


def get_opening(db: Session, actor: Actor, opening_id: str) -> dict:
    return _render(db, actor, c.visible_opening(db, actor, opening_id))


def _fields(body: dict) -> dict:
    return {
        "title": c.rule(rules.title, body.get("title")),
        "description": rules.clean(body.get("description")),
        "location": rules.clean(body.get("location")),
        "ctc_per_annum": c.rule(rules.money, body.get("ctc_per_annum")),
        "positions": c.rule(rules.positions, body.get("positions")),
        "applications_close_on": body["applications_close_on"],
        "eligibility": c.rule(rules.eligibility, body.get("eligibility")),
    }


def _company(db: Session, company_id: str) -> Company:
    company = c.get(db, Company, company_id, "company")
    if not company.active:
        raise conflict("company_inactive", "the company is inactive: it gets no new drives or openings")
    return company


def _drive(db: Session, drive_id: str, *, lock: bool = False) -> Drive:
    drive = c.get(db, Drive, drive_id, "drive", lock=lock)
    if drive.status not in ("draft", "scheduled"):
        raise conflict("drive_not_open_for_openings", f"a {drive.status} drive takes no openings")
    return drive


def _in_drive(company_id: str, close_on, drive: Drive | None) -> None:
    """An opening in a drive belongs to the drive's company and closes on or before the drive date."""
    if drive is None:
        return
    if drive.company_id != company_id:
        raise invalid("company_mismatch", "an opening in a drive belongs to the drive's company", "company_id")
    c.rule(rules.within_drive, close_on, drive.scheduled_on)


def create_opening(db: Session, actor: Actor, body: dict) -> dict:
    values = _fields(body)
    c.rule(rules.not_before, values["applications_close_on"], c.business_today(), "applications_close_on")
    company = c.get(db, Company, body["company_id"], "company")
    drive = c.get(db, Drive, body["drive_id"], "drive") if body.get("drive_id") else None
    if not company.active:
        raise conflict("company_inactive", "the company is inactive: it gets no new drives or openings")
    if drive is not None:
        drive = _drive(db, drive.id, lock=True)
    _in_drive(company.id, values["applications_close_on"], drive)
    o = Opening(
        organisation_id=actor.organisation_id,
        company_id=company.id,
        drive_id=drive.id if drive else None,
        status="draft",
        created_by=actor.user_id,
        created_at=c.clock(),
        **values,
    )
    db.add(o)
    c.audit(db, actor.user_id, "opening.created", "opening", o)
    db.commit()
    return _render(db, actor, o)


def _has_applications(db: Session, o: Opening) -> bool:
    return bool(db.scalar(c.count(db, Application).where(Application.opening_id == o.id)))


def update_opening(db: Session, actor: Actor, opening_id: str, body: dict) -> dict:
    """A draft or open opening. applications_close_on is checked against today only when it changes; the company and
    the drive change only while there are no applications. Existing applications are not changed."""
    o = c.visible_opening(db, actor, opening_id, lock=True)
    if o.status not in ("draft", "open"):
        raise conflict("not_editable", f"a {o.status} opening cannot be edited")
    values = _fields(body)
    if values["applications_close_on"] != o.applications_close_on:
        c.rule(rules.not_before, values["applications_close_on"], c.business_today(), "applications_close_on")
    company_id, drive_id = body["company_id"], body.get("drive_id") or None
    company_changes, drive_changes = company_id != o.company_id, drive_id != o.drive_id
    if company_changes:
        c.get(db, Company, company_id, "company")
    if drive_changes and drive_id:
        c.get(db, Drive, drive_id, "drive")
    if (company_changes or drive_changes) and _has_applications(db, o):
        raise conflict("has_applications", "the company and drive of an opening with applications do not change")
    if company_changes:
        _company(db, company_id)
    drive = None
    if drive_id:
        drive = _drive(db, drive_id) if drive_changes else c.get(db, Drive, drive_id, "drive")
        if drive_changes and o.status == "open" and drive.status != "scheduled":
            raise conflict("drive_not_scheduled", "an open opening moves only into a scheduled drive")
    _in_drive(company_id, values["applications_close_on"], drive)
    o.company_id, o.drive_id = company_id, drive_id
    for key, value in values.items():
        setattr(o, key, value)
    c.audit(db, actor.user_id, "opening.updated", "opening", o)
    db.commit()
    return _render(db, actor, o)


def publish_opening(db: Session, actor: Actor, opening_id: str) -> dict:
    o = c.visible_opening(db, actor, opening_id)
    drive = c.get(db, Drive, o.drive_id, "drive", lock=True) if o.drive_id else None  # the drive first, as cancel
    o = c.visible_opening(db, actor, opening_id, lock=True)
    if o.status != "draft":
        raise conflict("not_draft", "only a draft opening is published")
    if drive is not None and drive.status != "scheduled":
        raise conflict("drive_not_scheduled", "an opening in a drive is published once the drive is scheduled")
    company = c.get(db, Company, o.company_id, "company")
    if not company.active:
        raise conflict("company_inactive", "the company is inactive: it gets no new drives or openings")
    c.rule(rules.not_before, o.applications_close_on, c.business_today(), "applications_close_on")
    o.status, o.published_at = "open", c.clock()
    c.audit(db, actor.user_id, "opening.published", "opening", o)
    c.publish(
        db,
        "opening.published",
        o.organisation_id,
        {
            "opening_id": o.id,
            "company_id": o.company_id,
            "drive_id": o.drive_id,
            "applications_close_on": c.iso(o.applications_close_on),
        },
        actor=actor.user_id,
    )
    db.commit()
    return _render(db, actor, o)


def close_opening(db: Session, actor: Actor, opening_id: str) -> dict:
    """Stops new applications; existing ones continue through their sequence."""
    o = c.visible_opening(db, actor, opening_id, lock=True)
    if o.status != "open":
        raise conflict("not_open", "only an open opening is closed")
    o.status = "closed"
    c.audit(db, actor.user_id, "opening.closed", "opening", o)
    c.publish(db, "opening.closed", o.organisation_id, {"opening_id": o.id}, actor=actor.user_id)
    db.commit()
    return _render(db, actor, o)


def cancel_opening(db: Session, actor: Actor, opening_id: str, raw_reason: str | None) -> dict:
    """A draft or open opening with no application, a withdrawn one included. Only an open one publishes."""
    reason = required_reason(raw_reason)
    o = c.visible_opening(db, actor, opening_id, lock=True)
    if o.status not in ("draft", "open"):
        raise conflict("not_cancellable", f"a {o.status} opening cannot be cancelled")
    if _has_applications(db, o):
        raise conflict("has_applications", "the opening has applications: close it instead")
    was_open = o.status == "open"
    o.status, o.cancel_reason = "cancelled", reason
    c.audit(db, actor.user_id, "opening.cancelled", "opening", o)
    if was_open:
        c.publish(
            db, "opening.cancelled", o.organisation_id, {"opening_id": o.id, "reason": reason}, actor=actor.user_id
        )
    db.commit()
    return _render(db, actor, o)
