"""Drives (stories O2, O3, S2): a dated campus event of one company. draft -> scheduled (students see it) ->
completed, or cancelled while no opening of it has applications. Rescheduling a scheduled drive publishes
placement-career.drive.rescheduled; cancelling one cancels its draft and open openings with it."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from ..domain import rules
from ..infrastructure.models import Application, Company, Drive, Opening
from . import common as c
from .access import Actor
from .errors import conflict, invalid


def opening_summary(o: Opening) -> dict:
    return {
        "id": o.id,
        "title": o.title,
        "status": o.status,
        "ctc_per_annum": rules.money_text(o.ctc_per_annum),
        "applications_close_on": c.iso(o.applications_close_on),
    }


def drive_dict(d: Drive, company: Company, openings_count: int, openings: list[Opening] | None = None) -> dict:
    out = {
        "id": d.id,
        "organisation_id": d.organisation_id,
        "company_id": d.company_id,
        "title": d.title,
        "description": d.description,
        "scheduled_on": c.iso(d.scheduled_on),
        "ends_on": c.iso(d.ends_on),
        "venue": d.venue,
        "registration_closes_on": c.iso(d.registration_closes_on),
        "rounds": list(d.rounds or []),
        "eligibility": c.eligibility(d.eligibility),
        "status": d.status,
        "company": c.company_summary(company),
        "openings_count": openings_count,
        "cancel_reason": d.cancel_reason,
        "created_by": d.created_by,
        "created_at": c.iso(d.created_at),
    }
    if openings is not None:
        out["openings"] = [opening_summary(o) for o in openings]
    return out


def _openings_count(db: Session, actor: Actor, drive_ids: list[str]) -> dict[str, int]:
    """Openings of each drive that the caller may see."""
    if not drive_ids:
        return {}
    rows = db.execute(
        c.count(db, Opening)
        .add_columns(Opening.drive_id)
        .where(Opening.drive_id.in_(drive_ids), Opening.status.in_(c.opening_statuses(actor)))
        .group_by(Opening.drive_id)
    ).all()
    return {drive_id: n for n, drive_id in rows}


def _render(db: Session, actor: Actor, d: Drive, *, with_openings: bool = False) -> dict:
    company = c.get(db, Company, d.company_id, "company")
    if not with_openings:
        return drive_dict(d, company, _openings_count(db, actor, [d.id]).get(d.id, 0))
    openings = list(
        db.scalars(
            c.q(db, Opening)
            .where(Opening.drive_id == d.id, Opening.status.in_(c.opening_statuses(actor)))
            .order_by(Opening.applications_close_on, Opening.created_at, Opening.id)
        )
    )
    return drive_dict(d, company, len(openings), openings)


def list_drives(
    db: Session,
    actor: Actor,
    status: str | None,
    company_id: str | None,
    day_from: date | None,
    day_to: date | None,
    cursor,
    limit: int,
) -> dict:
    """Soonest first. A caller without drive:manage sees scheduled and completed drives only, whatever the filter."""
    query = c.q(db, Drive).where(Drive.status.in_(c.drive_statuses(actor)))
    if status:
        query = query.where(Drive.status == status)
    if company_id:
        query = query.where(Drive.company_id == company_id)
    if day_from:
        query = query.where(Drive.scheduled_on >= day_from)
    if day_to:
        query = query.where(Drive.scheduled_on <= day_to)
    result = c.page(db, query.order_by(Drive.scheduled_on, Drive.created_at, Drive.id), cursor, limit, lambda d: d)
    rows = result["items"]
    companies = c.companies_by_id(db, [d.company_id for d in rows])
    counts = _openings_count(db, actor, [d.id for d in rows])
    result["items"] = [drive_dict(d, companies[d.company_id], counts.get(d.id, 0)) for d in rows]
    return result


def get_drive(db: Session, actor: Actor, drive_id: str) -> dict:
    return _render(db, actor, c.visible_drive(db, actor, drive_id), with_openings=True)


def _rounds(raw: list[str] | None) -> list[str]:
    return [r for r in (rules.clean(x) for x in raw or []) if r]


def _fields(body: dict) -> dict:
    """The request's values, checked: title, criteria, and the dates against each other (not against today)."""
    values = {
        "title": c.rule(rules.title, body.get("title")),
        "description": rules.clean(body.get("description")),
        "scheduled_on": body["scheduled_on"],
        "ends_on": body.get("ends_on"),
        "venue": rules.clean(body.get("venue")),
        "registration_closes_on": body.get("registration_closes_on"),
        "rounds": _rounds(body.get("rounds")),
        "eligibility": c.rule(rules.eligibility, body.get("eligibility")),
    }
    c.rule(rules.drive_dates, values["scheduled_on"], values["ends_on"], values["registration_closes_on"])
    return values


def _active_company(db: Session, company_id: str) -> Company:
    company = c.get(db, Company, company_id, "company")
    if not company.active:
        raise conflict("company_inactive", "the company is inactive: it gets no new drives or openings")
    return company


def create_drive(db: Session, actor: Actor, body: dict) -> dict:
    values = _fields(body)
    c.rule(rules.not_before, values["scheduled_on"], c.business_today(), "scheduled_on")
    company = _active_company(db, body["company_id"])
    d = Drive(
        organisation_id=actor.organisation_id,
        company_id=company.id,
        status="draft",
        created_by=actor.user_id,
        created_at=c.clock(),
        **values,
    )
    db.add(d)
    c.audit(db, actor.user_id, "drive.created", "drive", d)
    db.commit()
    return _render(db, actor, d)


def _non_cancelled_openings(db: Session, d: Drive) -> list[Opening]:
    """Locked after the drive, the order of cancel_drive and update_opening (which locks the drive before editing an
    opening's last day or moving it in), so the dates read here cannot change before the commit."""
    query = (
        c.q(db, Opening)
        .where(Opening.drive_id == d.id, Opening.status != "cancelled")
        .order_by(Opening.created_at, Opening.id)
        .with_for_update()
    )
    return list(db.scalars(query.execution_options(populate_existing=True)))


def update_drive(db: Session, actor: Actor, drive_id: str, body: dict) -> dict:
    """A draft or scheduled drive. scheduled_on is checked against today only when it changes; the company changes
    only while the drive has no openings; its openings' last days to apply stay on or before the drive date."""
    d = c.visible_drive(db, actor, drive_id, lock=True)
    if d.status not in ("draft", "scheduled"):
        raise conflict("not_editable", f"a {d.status} drive cannot be edited")
    values = _fields(body)
    if values["scheduled_on"] != d.scheduled_on:
        c.rule(rules.not_before, values["scheduled_on"], c.business_today(), "scheduled_on")
    if body["company_id"] != d.company_id:
        company = _active_company(db, body["company_id"])
        has_openings = db.scalar(c.count(db, Opening).where(Opening.drive_id == d.id))
        if has_openings:
            raise invalid("company_mismatch", "the company of a drive with openings does not change", "company_id")
        d.company_id = company.id
    latest = max((o.applications_close_on for o in _non_cancelled_openings(db, d)), default=None)
    if latest is not None and values["scheduled_on"] < latest:
        raise invalid(
            "close_date_after_drive",
            "an opening of the drive takes applications after this date",
            "scheduled_on",
        )
    moved = values["scheduled_on"] != d.scheduled_on or values["ends_on"] != d.ends_on
    for key, value in values.items():
        setattr(d, key, value)
    c.audit(db, actor.user_id, "drive.updated", "drive", d)
    if d.status == "scheduled" and moved:
        c.audit(db, actor.user_id, "drive.rescheduled", "drive", d)
        c.publish(
            db,
            "drive.rescheduled",
            d.organisation_id,
            {"drive_id": d.id, "scheduled_on": c.iso(d.scheduled_on), "ends_on": c.iso(d.ends_on)},
            actor=actor.user_id,
        )
    db.commit()
    return _render(db, actor, d)


def schedule_drive(db: Session, actor: Actor, drive_id: str) -> dict:
    d = c.visible_drive(db, actor, drive_id, lock=True)
    if d.status != "draft":
        raise conflict("not_draft", "only a draft drive is scheduled")
    _active_company(db, d.company_id)
    c.rule(rules.not_before, d.scheduled_on, c.business_today(), "scheduled_on")
    d.status = "scheduled"
    c.audit(db, actor.user_id, "drive.scheduled", "drive", d)
    c.publish(
        db,
        "drive.scheduled",
        d.organisation_id,
        {
            "drive_id": d.id,
            "company_id": d.company_id,
            "scheduled_on": c.iso(d.scheduled_on),
            "registration_closes_on": c.iso(d.registration_closes_on),
        },
        actor=actor.user_id,
    )
    db.commit()
    return _render(db, actor, d)


def complete_drive(db: Session, actor: Actor, drive_id: str) -> dict:
    """On or after the drive date. Its openings and applications are not changed."""
    d = c.visible_drive(db, actor, drive_id, lock=True)
    if d.status != "scheduled":
        raise conflict("not_scheduled", "only a scheduled drive is completed")
    if c.business_today() < d.scheduled_on:
        raise invalid("invalid_date", "a drive is completed on or after its date", "scheduled_on")
    d.status = "completed"
    c.audit(db, actor.user_id, "drive.completed", "drive", d)
    c.publish(
        db,
        "drive.completed",
        d.organisation_id,
        {"drive_id": d.id, "company_id": d.company_id, "scheduled_on": c.iso(d.scheduled_on)},
        actor=actor.user_id,
    )
    db.commit()
    return _render(db, actor, d)


def required_reason(raw: str | None) -> str:
    reason = rules.clean(raw)
    if reason is None:
        raise invalid("reason_required", "a reason is required", "reason")
    return reason


def cancel_drive(db: Session, actor: Actor, drive_id: str, raw_reason: str | None) -> dict:
    """A draft or scheduled drive whose openings have no application, a withdrawn one included. Its draft and open
    openings are cancelled with it (closed ones stay closed); each open one publishes opening.cancelled."""
    reason = required_reason(raw_reason)
    d = c.visible_drive(db, actor, drive_id, lock=True)
    if d.status not in ("draft", "scheduled"):
        raise conflict("not_cancellable", f"a {d.status} drive cannot be cancelled")
    openings = list(
        db.scalars(
            c.q(db, Opening).where(Opening.drive_id == d.id).order_by(Opening.created_at, Opening.id).with_for_update()
        )
    )
    if openings:
        applied = db.scalar(c.count(db, Application).where(Application.opening_id.in_([o.id for o in openings])))
        if applied:
            raise conflict("has_applications", "an opening of the drive has applications: close it instead")
    d.status, d.cancel_reason = "cancelled", reason
    c.audit(db, actor.user_id, "drive.cancelled", "drive", d)
    for o in openings:
        if o.status not in ("draft", "open"):
            continue
        was_open = o.status == "open"
        o.status, o.cancel_reason = "cancelled", reason
        c.audit(db, actor.user_id, "opening.cancelled", "opening", o)
        if was_open:
            c.publish(
                db,
                "opening.cancelled",
                o.organisation_id,
                {"opening_id": o.id, "reason": reason},
                actor=actor.user_id,
            )
    c.publish(
        db,
        "drive.cancelled",
        d.organisation_id,
        {"drive_id": d.id, "company_id": d.company_id, "reason": reason},
        actor=actor.user_id,
    )
    db.commit()
    return _render(db, actor, d)


def drive_application_counts(db: Session, drive_ids: list[str]) -> dict[str, dict[str, int]]:
    """Applications to the openings of each drive, by status (every status present, zero included)."""
    out = {drive_id: dict.fromkeys(rules.APPLICATION_STATUSES, 0) for drive_id in drive_ids}
    if not drive_ids:
        return out
    rows = db.execute(
        c.count(db, Application)
        .add_columns(Opening.drive_id, Application.status)
        .join(Opening, Opening.id == Application.opening_id)
        .where(Opening.drive_id.in_(drive_ids))
        .group_by(Opening.drive_id, Application.status)
    ).all()
    for n, drive_id, status in rows:
        out[drive_id][status] = n
    return out
