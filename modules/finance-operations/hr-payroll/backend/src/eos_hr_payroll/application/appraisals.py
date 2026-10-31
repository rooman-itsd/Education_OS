"""Appraisals: HR opens a cycle for a list of employees; each writes a self review and submits it; a reviewer (not
the employee) rates it and completes it. A completed appraisal does not change."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..infrastructure.models import Appraisal, Employee
from . import common, employees
from .access import APPRAISAL_REVIEW, Actor
from .common import audit, get, iso, publish, q, text
from .errors import conflict, forbidden, invalid


def appraisal_dict(a: Appraisal, names: dict[str, str]) -> dict:
    return {
        "id": a.id,
        "organisation_id": a.organisation_id,
        "cycle": a.cycle,
        "employee_id": a.employee_id,
        "employee_name": names.get(a.employee_id, ""),
        "status": a.status,
        "self_review": a.self_review,
        "reviewer_id": a.reviewer_id,
        "reviewer_comments": a.reviewer_comments,
        "rating": a.rating,
        "completed_at": iso(a.completed_at),
        "created_at": iso(a.created_at),
    }


def _render(db: Session, rows: list[Appraisal]) -> list[dict]:
    names = employees.names(db, {a.employee_id for a in rows})
    return [appraisal_dict(a, names) for a in rows]


def list_appraisals(db: Session, cycle: str | None, status: str | None) -> list[dict]:
    query = q(db, Appraisal)
    if cycle:
        query = query.where(Appraisal.cycle == cycle)
    if status:
        query = query.where(Appraisal.status == status)
    return _render(db, list(db.scalars(query.order_by(Appraisal.cycle.desc(), Appraisal.created_at, Appraisal.id))))


def my_appraisals(db: Session, actor: Actor) -> list[dict]:
    e = common.require_own_employee(db, actor)
    rows = q(db, Appraisal).where(Appraisal.employee_id == e.id).order_by(Appraisal.cycle.desc())
    return _render(db, list(db.scalars(rows)))


@common.duplicate_is_409("appraisal_exists", "an employee already has an appraisal in this cycle")
def open_cycle(db: Session, actor: Actor, cycle: str, employee_ids: list[str]) -> list[dict]:
    cycle = text(cycle)
    if not cycle or len(cycle) > 20:
        raise invalid("invalid_cycle", "cycle must be 1 to 20 characters, e.g. 2026-27", "cycle")
    rows = []
    for employee_id in sorted(set(employee_ids)):
        e = get(db, Employee, employee_id, "employee")
        if e.status == "exited":
            raise invalid("employee_exited", "an employee in the list has exited", "employee_ids")
        if db.scalar(q(db, Appraisal).where(Appraisal.employee_id == e.id, Appraisal.cycle == cycle)) is not None:
            raise conflict("appraisal_exists", "an employee already has an appraisal in this cycle")
        a = Appraisal(
            organisation_id=e.organisation_id,
            cycle=cycle,
            employee_id=e.id,
            status="self_review",
            self_review="",
            reviewer_comments="",
            opened_by=actor.user_id,
        )
        db.add(a)
        audit(db, actor.user_id, "appraisal.opened", "appraisal", a)
        rows.append(a)
    db.commit()
    return _render(db, rows)


def _readable(db: Session, actor: Actor, appraisal_id: str) -> tuple[Appraisal, Employee]:
    a = get(db, Appraisal, appraisal_id, "appraisal")
    e = get(db, Employee, a.employee_id, "employee")
    if not common.is_self(actor, e) and not actor.can(APPRAISAL_REVIEW):
        raise forbidden("you can see only your own appraisal")
    return a, e


def get_appraisal(db: Session, actor: Actor, appraisal_id: str) -> dict:
    a, e = _readable(db, actor, appraisal_id)
    return appraisal_dict(a, {e.id: e.name})


def save(db: Session, actor: Actor, appraisal_id: str, body: dict) -> dict:
    """The employee saves their self review while it is theirs to write; a reviewer saves comments and the rating
    while it is in review. submit=true moves it on: to the reviewer, or completed (a rating is needed)."""
    a = get(db, Appraisal, appraisal_id, "appraisal", lock=True)
    a, e = _readable(db, actor, a.id)
    reviewer_fields = body.get("reviewer_comments") is not None or body.get("rating") is not None
    if a.status == "completed":
        raise conflict("appraisal_completed", "the appraisal is completed")
    if common.is_self(actor, e):
        if reviewer_fields:
            raise forbidden("you cannot review or rate your own appraisal")
        if a.status != "self_review":
            raise conflict("not_in_self_review", "the self review has been submitted")
        if body.get("self_review") is not None:
            a.self_review = text(body["self_review"])
        if body.get("submit"):
            if not a.self_review:
                raise invalid("self_review_required", "write the self review before submitting it", "self_review")
            a.status = "manager_review"
        audit(
            db,
            actor.user_id,
            "appraisal.self_review_submitted" if body.get("submit") else "appraisal.self_review_saved",
            "appraisal",
            a,
        )
        db.commit()
        return appraisal_dict(a, {e.id: e.name})
    if body.get("self_review") is not None:
        raise forbidden("only the employee writes the self review")
    if a.status != "manager_review":
        raise conflict("not_in_manager_review", "the employee has not submitted the self review yet")
    if body.get("reviewer_comments") is not None:
        a.reviewer_comments = text(body["reviewer_comments"])
    if body.get("rating") is not None:
        a.rating = body["rating"]
    a.reviewer_id = actor.user_id
    if body.get("submit"):
        if a.rating is None:
            raise invalid("rating_required", "rate the appraisal before completing it", "rating")
        a.status, a.completed_at = "completed", common.clock()
        publish(
            db,
            "appraisal.completed",
            a.organisation_id,
            {"appraisal_id": a.id, "employee_id": e.id, "cycle": a.cycle},
            actor.user_id,
        )
    audit(db, actor.user_id, "appraisal.completed" if body.get("submit") else "appraisal.reviewed", "appraisal", a)
    db.commit()
    return appraisal_dict(a, {e.id: e.name})
