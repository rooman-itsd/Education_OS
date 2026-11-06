"""Applications (stories O6, O7, S1, S3, S4, S5). A student applies to an open opening up to and including its last
day (IST), declaring that they meet the criteria; nothing checks the declaration (P4). The officer moves it one step
at a time along the fixed sequence and records the offer and the student's answer (P5). A student with an accepted
offer is flagged `student_placed` to the officer and nothing is blocked: there is no one-offer rule in v1.0.

Students see their own applications only (another student's answers 404), without the placed flag."""

from __future__ import annotations

from decimal import Decimal

from eos_core.db import scoped
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain import rules
from ..infrastructure.models import Application, ApplicationHistory, Opening
from . import common as c
from .access import Actor
from .errors import conflict, invalid, not_found

# Events per officer step; moving to in_process publishes nothing (contract).
STEP_EVENTS = {
    "shortlisted": "application.shortlisted",
    "offered": "application.offered",
    "accepted": "application.accepted",
    "declined": "application.declined",
    "rejected": "application.rejected",
}
WITH_COMPANY = ("offered", "accepted")  # the payloads of events.yaml that carry company_id


def _number(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def declared(a: Application) -> dict:
    return {
        "programme": a.declared_programme,
        "graduating_year": a.declared_graduating_year,
        "cgpa": _number(a.declared_cgpa),
        "active_backlogs": a.declared_active_backlogs,
    }


def offer(a: Application) -> dict | None:
    if a.offered_at is None:
        return None
    return {
        "ctc_per_annum": rules.money_text(a.offer_ctc_per_annum),
        "joining_on": c.iso(a.offer_joining_on),
        "notes": a.offer_notes,
    }


def _placed_students(db: Session):
    """Students with an accepted offer in the caller's organisation, on any opening."""
    return scoped(db, select(Application.student_id), Application).where(Application.status == "accepted")


def _context(db: Session, rows: list[Application]):
    openings = (
        {o.id: o for o in db.scalars(c.q(db, Opening).where(Opening.id.in_({a.opening_id for a in rows})))}
        if rows
        else {}
    )
    companies = c.companies_by_id(db, [o.company_id for o in openings.values()])
    return openings, companies


def _base(a: Application, o: Opening, companies) -> dict:
    return {
        "id": a.id,
        "organisation_id": a.organisation_id,
        "opening_id": a.opening_id,
        "opening_title": o.title,
        "company": c.company_summary(companies[o.company_id]),
        "drive_id": o.drive_id,
        "status": a.status,
        "declared": declared(a),
        "offer": offer(a),
        "reason": a.reason,
        "applied_at": c.iso(a.applied_at),
        "updated_at": c.iso(a.updated_at),
    }


def _staff_many(db: Session, rows: list[Application]) -> list[dict]:
    openings, companies = _context(db, rows)
    students = {a.student_id for a in rows}
    placed = set(db.scalars(_placed_students(db).where(Application.student_id.in_(students)))) if students else set()
    return [
        {
            **_base(a, openings[a.opening_id], companies),
            "student_id": a.student_id,
            "student_name": a.student_name,
            "student_placed": a.student_id in placed,
            "declares_eligible": a.declares_eligible,
        }
        for a in rows
    ]


def _history(db: Session, a: Application) -> list[dict]:
    rows = db.scalars(
        c.q(db, ApplicationHistory)
        .where(ApplicationHistory.application_id == a.id)
        .order_by(ApplicationHistory.sequence)
    )
    return [{"status": h.status, "at": c.iso(h.at), "by": h.actor_id} for h in rows]


def _staff(db: Session, a: Application, *, with_history: bool = False) -> dict:
    out = _staff_many(db, [a])[0]
    if with_history:
        out["history"] = _history(db, a)
    return out


def _mine_many(db: Session, rows: list[Application]) -> list[dict]:
    openings, companies = _context(db, rows)
    return [_base(a, openings[a.opening_id], companies) for a in rows]


# ---------------------------------------------------------------- the officer


def list_applications(db: Session, filters: dict, cursor, limit: int) -> dict:
    query = c.q(db, Application)
    if filters.get("opening_id"):
        query = query.where(Application.opening_id == filters["opening_id"])
    if filters.get("drive_id"):
        in_drive = scoped(db, select(Opening.id), Opening).where(Opening.drive_id == filters["drive_id"])
        query = query.where(Application.opening_id.in_(in_drive))
    if filters.get("status"):
        query = query.where(Application.status == filters["status"])
    if filters.get("student_id"):
        query = query.where(Application.student_id == filters["student_id"])
    if filters.get("student_placed") is True:
        query = query.where(Application.student_id.in_(_placed_students(db)))
    elif filters.get("student_placed") is False:
        query = query.where(Application.student_id.not_in(_placed_students(db)))
    query = query.order_by(Application.applied_at.desc(), Application.id.desc())
    result = c.page(db, query, cursor, limit, lambda a: a)
    result["items"] = _staff_many(db, result["items"])
    return result


def get_application(db: Session, application_id: str) -> dict:
    return _staff(db, c.get(db, Application, application_id, "application"), with_history=True)


def _record(db: Session, actor: Actor, a: Application, status: str) -> None:
    """The new status, its history line and its audit record."""
    now = c.clock()
    last = db.scalar(c.count(db, ApplicationHistory).where(ApplicationHistory.application_id == a.id))
    a.status, a.updated_at = status, now
    db.add(
        ApplicationHistory(
            organisation_id=a.organisation_id,
            application_id=a.id,
            sequence=(last or 0) + 1,
            status=status,
            actor_id=actor.user_id,
            at=now,
        )
    )
    action = "application.submitted" if status == "applied" else f"application.{status}"
    c.audit(db, actor.user_id, action, "application", a)


def _event(db: Session, actor: Actor, a: Application, o: Opening, name: str, *, with_company: bool) -> None:
    payload = {"application_id": a.id, "opening_id": a.opening_id, "student_id": a.student_id}
    if with_company:
        payload["company_id"] = o.company_id
    c.publish(db, name, a.organisation_id, payload, actor=actor.user_id)


def change_status(db: Session, actor: Actor, application_id: str, body: dict) -> dict:
    """One step along the sequence, or a rejection with a reason. The offer is recorded when moving to offered; an
    offer or a reason sent with any other step is not recorded (contract: "Recorded when status is offered")."""
    target = body.get("status")
    if target not in rules.STEPS:
        raise invalid("invalid_status", "status must be one of " + ", ".join(rules.STEPS), "status")
    reason = rules.clean(body.get("reason")) if target == "rejected" else None
    if target == "rejected" and reason is None:
        raise invalid("reason_required", "a rejection needs a reason, which the student sees", "reason")
    offered = None
    if target == "offered":
        raw = body.get("offer") or {}
        offered = {
            "ctc": c.rule(rules.money, raw.get("ctc_per_annum"), "offer.ctc_per_annum"),
            "joining_on": c.rule(rules.not_before, raw.get("joining_on"), c.business_today(), "offer.joining_on"),
            "notes": rules.clean(raw.get("notes")),
        }
    a = c.get(db, Application, application_id, "application", lock=True)
    c.rule(rules.step, a.status, target)
    o = c.get(db, Opening, a.opening_id, "opening")
    if offered is not None:
        a.offered_at = c.clock()
        a.offer_ctc_per_annum, a.offer_joining_on, a.offer_notes = (
            offered["ctc"],
            offered["joining_on"],
            offered["notes"],
        )
    if reason is not None:
        a.reason = reason
    _record(db, actor, a, target)
    if target in STEP_EVENTS:
        _event(db, actor, a, o, STEP_EVENTS[target], with_company=target in WITH_COMPANY)
    db.commit()
    return _staff(db, a, with_history=True)


# ---------------------------------------------------------------- the student


def my_openings(db: Session, actor: Actor, cursor, limit: int) -> dict:
    """Open openings that still take applications (applications_close_on today or later, IST), soonest closing
    first, each with the caller's own application if any."""
    query = (
        c.q(db, Opening)
        .where(Opening.status == "open", Opening.applications_close_on >= c.business_today())
        .order_by(Opening.applications_close_on, Opening.created_at, Opening.id)
    )
    result = c.page(db, query, cursor, limit, lambda o: o)
    rows: list[Opening] = result["items"]
    companies = c.companies_by_id(db, [o.company_id for o in rows])
    drives = c.drives_by_id(db, [o.drive_id for o in rows])
    mine = {}
    if rows:
        mine = {
            a.opening_id: a
            for a in db.scalars(
                c.q(db, Application).where(
                    Application.student_id == actor.user_id, Application.opening_id.in_([o.id for o in rows])
                )
            )
        }
    result["items"] = [
        {
            "id": o.id,
            "title": o.title,
            "company": c.company_summary(companies[o.company_id]),
            "drive": c.drive_brief(drives.get(o.drive_id)),
            "location": o.location,
            "ctc_per_annum": rules.money_text(o.ctc_per_annum),
            "applications_close_on": c.iso(o.applications_close_on),
            "eligibility": c.eligibility(o.eligibility),
            "my_application": ({"id": mine[o.id].id, "status": mine[o.id].status} if o.id in mine else None),
        }
        for o in rows
    ]
    return result


def my_applications(db: Session, actor: Actor, cursor, limit: int) -> dict:
    query = (
        c.q(db, Application)
        .where(Application.student_id == actor.user_id)
        .order_by(Application.applied_at.desc(), Application.id.desc())
    )
    result = c.page(db, query, cursor, limit, lambda a: a)
    result["items"] = _mine_many(db, result["items"])
    return result


@c.duplicate_is_409("already_applied", "you already applied to this opening")
def apply(db: Session, actor: Actor, body: dict) -> dict:
    if body.get("declares_eligible") is not True:
        raise invalid("declaration_required", "declare that you meet the criteria shown", "declares_eligible")
    values = c.rule(rules.declaration, body.get("declared"))
    o = c.visible_opening(db, actor, body["opening_id"], lock=True)  # takes turns with close and cancel
    if o.status != "open":
        raise conflict("opening_not_open", "the opening does not take applications")
    if c.business_today() > o.applications_close_on:
        raise conflict("applications_closed", "the last day to apply has passed")
    taken = c.q(db, Application).where(Application.opening_id == o.id, Application.student_id == actor.user_id)
    if db.scalar(taken) is not None:
        raise conflict("already_applied", "you already applied to this opening")
    now = c.clock()
    a = Application(
        organisation_id=actor.organisation_id,
        opening_id=o.id,
        student_id=actor.user_id,
        student_name=(actor.name or "")[:200],
        status="applied",
        declares_eligible=True,
        declared_programme=values["programme"],
        declared_graduating_year=values["graduating_year"],
        declared_cgpa=None if values["cgpa"] is None else Decimal(str(values["cgpa"])),
        declared_active_backlogs=values["active_backlogs"],
        applied_at=now,
        updated_at=now,
    )
    db.add(a)
    db.flush()
    _record(db, actor, a, "applied")
    _event(db, actor, a, o, "application.submitted", with_company=False)
    db.commit()
    return _mine_many(db, [a])[0]


def withdraw(db: Session, actor: Actor, application_id: str) -> dict:
    a = db.scalar(
        c.q(db, Application)
        .where(Application.id == application_id, Application.student_id == actor.user_id)
        .with_for_update()
    )
    if a is None:
        raise not_found("application")
    if not rules.withdrawable(a.status):
        raise conflict("not_withdrawable", f"an application {a.status} cannot be withdrawn")
    o = c.get(db, Opening, a.opening_id, "opening")
    _record(db, actor, a, "withdrawn")
    _event(db, actor, a, o, "application.withdrawn", with_company=False)
    db.commit()
    return _mine_many(db, [a])[0]
