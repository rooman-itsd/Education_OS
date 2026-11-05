"""Assignments and submissions (FR-6, FR-7). Each change checks the domain rules, writes an audit entry and publishes
its event to the outbox in the same transaction."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..domain import rules
from ..infrastructure import repository as repo
from ..infrastructure.models import Assignment, ContentUnit, CourseSpace, Submission, as_utc, iso
from . import access as k
from . import common as c
from .access import Actor
from .errors import conflict, forbidden, not_found, unprocessable

VISIBLE_WORK = ("published", "closed")


# ---------------------------------------------------------------- serialisation


def assignment_dict(x: Assignment) -> dict:
    out = {
        "id": x.id,
        "organisation_id": x.organisation_id,
        "course_space_id": x.course_space_id,
        "title": x.title,
        "due_at": iso(x.due_at),
        "max_points": x.max_points,
        "submission_type": x.submission_type,
        "max_attempts": x.max_attempts,
        "late_policy": {"accept_late": x.accept_late, "late_cutoff_at": iso(x.late_cutoff_at)},
        "target_section_ids": list(x.target_section_ids or []),
        "status": x.status,
        "published_at": iso(x.published_at),
    }
    if x.instructions is not None:
        out["instructions"] = x.instructions
    if x.unit_id is not None:
        out["unit_id"] = x.unit_id
    return out


def submission_dict(s: Submission) -> dict:
    return {
        "id": s.id,
        "organisation_id": s.organisation_id,
        "assignment_id": s.assignment_id,
        "student_id": s.student_id,
        "attempt": s.attempt,
        "document_ids": list(s.document_ids or []),
        "text": s.text,
        "submitted_at": iso(s.submitted_at),
        "late": s.late,
        "status": s.status,
    }


def visible_to(view: c.Viewer, item, published_units: set[str], sections: list[str] | None = None) -> bool:
    """A published or closed assignment or quiz, outside unpublished units, for the viewer's section."""
    if view.staff:
        return True
    if item.status not in VISIBLE_WORK:
        return False
    if item.unit_id is not None and item.unit_id not in published_units:
        return False
    return view.sees(sections or [])


def published_units(db: Session, space_id: str) -> set[str]:
    return {u.id for u in repo.units(db, space_id) if u.published}


def unit_in(db: Session, space: CourseSpace, unit_id: str | None) -> None:
    if unit_id is None:
        return
    unit = repo.get(db, ContentUnit, unit_id)
    if unit is None or unit.course_space_id != space.id:
        raise unprocessable("unknown_unit", "the content unit is not in this course space")


# ---------------------------------------------------------------- assignments


def list_assignments(db: Session, a: Actor, space_id: str, status: str | None, unit_id: str | None) -> dict:
    space = c.space_of(db, space_id)
    view = c.viewer(db, a, space)
    units = published_units(db, space.id)
    rows = [
        x
        for x in repo.assignments(db, [space.id])
        if visible_to(view, x, units, x.target_section_ids)
        and (status is None or x.status == status)
        and (unit_id is None or x.unit_id == unit_id)
    ]
    return {"items": [assignment_dict(x) for x in rows]}


def create_assignment(db: Session, a: Actor, space_id: str, body: dict) -> dict:
    space = c.get(db, CourseSpace, space_id, "course space", for_update=True)
    c.require_scope(db, a, space, k.ASSIGNMENT_MANAGE_ASSIGNED)
    c.require_writable(space)
    policy = body.get("late_policy") or {"accept_late": False, "late_cutoff_at": None}
    c.check(rules.check_late_policy, body["due_at"], policy["accept_late"], policy.get("late_cutoff_at"))
    unit_in(db, space, body.get("unit_id"))
    x = Assignment(
        organisation_id=a.organisation_id,
        course_space_id=space.id,
        unit_id=body.get("unit_id"),
        title=body["title"],
        instructions=body.get("instructions"),
        due_at=body["due_at"],
        max_points=body["max_points"],
        submission_type=body["submission_type"],
        max_attempts=body.get("max_attempts", 1),
        accept_late=policy["accept_late"],
        late_cutoff_at=policy.get("late_cutoff_at"),
        target_section_ids=body.get("target_section_ids") or [],
        status="draft",
        created_by=a.user_id,
        created_at=c.clock(),
    )
    db.add(x)
    db.flush()
    c.audit(db, a, "assignment.created", "assignment", x.id, a.organisation_id)
    db.commit()
    return assignment_dict(x)


def get_assignment(db: Session, a: Actor, assignment_id: str) -> dict:
    x = c.get(db, Assignment, assignment_id, "assignment")
    space = c.space_of(db, x.course_space_id)
    view = c.viewer(db, a, space)
    if not visible_to(view, x, published_units(db, space.id), x.target_section_ids):
        raise not_found("assignment")
    return assignment_dict(x)


def _updated_payload(space: CourseSpace, x: Assignment, changed: list[str]) -> dict:
    return {
        "assignment_id": x.id,
        "course_space_id": space.id,
        "course_offering_id": space.course_offering_id,
        "changed_fields": changed,
        "due_at": iso(x.due_at),
        "max_points": x.max_points,
        "target_section_ids": list(x.target_section_ids or []),
        "status": x.status,
    }


def update_assignment(db: Session, a: Actor, assignment_id: str, body: dict) -> dict:
    x = c.get(db, Assignment, assignment_id, "assignment", for_update=True)
    space = c.space_of(db, x.course_space_id)
    c.require_scope(db, a, space, k.ASSIGNMENT_MANAGE_ASSIGNED)
    c.require_writable(space)
    if x.status == "closed":
        raise conflict("invalid_status", "a closed assignment cannot be edited")
    before = {
        "due_at": as_utc(x.due_at),
        "max_points": x.max_points,
        "target_section_ids": list(x.target_section_ids or []),
        "late_policy": (x.accept_late, as_utc(x.late_cutoff_at)),
    }
    if "unit_id" in body:
        unit_in(db, space, body["unit_id"])
    for name in ("title", "instructions", "unit_id", "due_at", "max_points", "submission_type", "max_attempts"):
        if name in body and (body[name] is not None or name in ("instructions", "unit_id")):
            setattr(x, name, body[name])
    if "target_section_ids" in body:
        x.target_section_ids = list(body["target_section_ids"] or [])
    if body.get("late_policy") is not None:
        x.accept_late = body["late_policy"]["accept_late"]
        x.late_cutoff_at = body["late_policy"].get("late_cutoff_at")
    c.check(rules.check_late_policy, as_utc(x.due_at), x.accept_late, as_utc(x.late_cutoff_at))
    after = {
        "due_at": as_utc(x.due_at),
        "max_points": x.max_points,
        "target_section_ids": list(x.target_section_ids or []),
        "late_policy": (x.accept_late, as_utc(x.late_cutoff_at)),
    }
    if after["max_points"] != before["max_points"]:
        graded = repo.grades(db, item_type="assignment", item_id=x.id)
        if any(g.points > x.max_points for g in graded):
            raise conflict("points_above_max", "a grade already has more points than the new max_points")
        for g in graded:
            g.max_points = x.max_points
    c.audit(db, a, "assignment.updated", "assignment", x.id, a.organisation_id)
    changed = [f for f in rules.ASSIGNMENT_NOTIFIED_FIELDS if after[f] != before[f]]
    if x.status == "published" and changed:
        c.publish(db, a, "assignment.updated", a.organisation_id, _updated_payload(space, x, changed))
    db.commit()
    return assignment_dict(x)


def change_assignment_status(db: Session, a: Actor, assignment_id: str, status: str) -> dict:
    x = c.get(db, Assignment, assignment_id, "assignment", for_update=True)
    space = c.space_of(db, x.course_space_id)
    c.require_scope(db, a, space, k.ASSIGNMENT_MANAGE_ASSIGNED)
    c.require_writable(space)
    x.status = c.check(rules.transition, rules.WORK_TRANSITIONS, status, x.status, "assignment")
    c.audit(db, a, f"assignment.{status}", "assignment", x.id, a.organisation_id)
    if status == "published":
        x.published_at = c.clock()
        c.publish(
            db,
            a,
            "assignment.published",
            a.organisation_id,
            {
                "assignment_id": x.id,
                "course_space_id": space.id,
                "course_offering_id": space.course_offering_id,
                "title": x.title,
                "due_at": iso(x.due_at),
                "max_points": x.max_points,
                "target_section_ids": list(x.target_section_ids or []),
                "published_at": iso(x.published_at),
            },
        )
    else:
        c.publish(db, a, "assignment.updated", a.organisation_id, _updated_payload(space, x, ["status"]))
    db.commit()
    return assignment_dict(x)


# ---------------------------------------------------------------- submissions


def submit(db: Session, a: Actor, assignment_id: str, body: dict) -> dict:
    x = c.get(db, Assignment, assignment_id, "assignment", for_update=True)
    space = c.space_of(db, x.course_space_id)
    view = c.viewer(db, a, space)
    if not view.learner:
        raise forbidden("only students of the course space submit", "not_a_student")
    if x.unit_id is not None and x.unit_id not in published_units(db, space.id):
        raise not_found("assignment")
    if x.status != "published":
        raise conflict("assignment_not_published", "the assignment is not open for submissions")
    if not view.sees(x.target_section_ids or []):
        raise forbidden("the assignment is not set for your section", "not_targeted")
    if space.status != "active":
        raise conflict("course_space_not_active", "the course space is not active")
    document_ids, text = body.get("document_ids") or [], body.get("text")
    c.check(rules.check_submission_content, x.submission_type, document_ids, text)
    now = c.clock()
    late = c.check(rules.submission_lateness, now, as_utc(x.due_at), x.accept_late, as_utc(x.late_cutoff_at))
    earlier = repo.submissions(db, [x.id], student_id=a.user_id, include_superseded=True)
    c.check(rules.check_attempts_left, len(earlier), x.max_attempts)
    for s in earlier:
        if s.status != "superseded":
            s.status = "superseded"
            c.audit(db, a, "submission.superseded", "submission", s.id, a.organisation_id)
    s = Submission(
        organisation_id=a.organisation_id,
        assignment_id=x.id,
        course_space_id=space.id,
        student_id=a.user_id,
        attempt=len(earlier) + 1,
        document_ids=document_ids,
        text=text,
        submitted_at=now,
        late=late,
        status="submitted",
    )
    db.add(s)
    c.flush_unique(db, "no_attempts_left", "another submission was recorded at the same moment; try again")
    c.audit(db, a, "submission.submitted", "submission", s.id, a.organisation_id)
    c.publish(
        db,
        a,
        "submission.submitted",
        a.organisation_id,
        {
            "submission_id": s.id,
            "assignment_id": x.id,
            "course_space_id": space.id,
            "student_id": a.user_id,
            "attempt": s.attempt,
            "submitted_at": iso(s.submitted_at),
            "late": s.late,
        },
    )
    db.commit()
    return submission_dict(s)


def list_submissions(db: Session, a: Actor, assignment_id: str, filters: dict, limit: int, offset: int) -> dict:
    x = c.get(db, Assignment, assignment_id, "assignment")
    space = c.space_of(db, x.course_space_id)
    c.require_scope(db, a, space, k.SUBMISSION_READ_ASSIGNED)
    rows = repo.submissions(
        db, [x.id], status=filters.get("status"), include_superseded=bool(filters.get("include_superseded"))
    )
    return {"items": [submission_dict(s) for s in rows[offset : offset + limit]], "total": len(rows)}


def my_submissions(db: Session, a: Actor, assignment_id: str | None, space_id: str | None) -> dict:
    rows = repo.student_submissions(db, a.user_id)
    if assignment_id:
        rows = [s for s in rows if s.assignment_id == assignment_id]
    if space_id:
        rows = [s for s in rows if s.course_space_id == space_id]
    return {"items": [submission_dict(s) for s in rows]}
