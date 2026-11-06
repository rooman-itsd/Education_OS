"""Coursework grades, feedback and release (FR-11, FR-12), the gradebook (FR-13), the caller's own grades, and the
Faculty widget's grading queue (FR-16). Coursework grades only: these are never examination results (docs/prd.md
section 2)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..domain import rules
from ..infrastructure import repository as repo
from ..infrastructure.models import Assignment, CourseSpace, Grade, Quiz, Submission, as_utc, iso
from . import access as k
from . import common as c
from . import scoring
from .access import Actor
from .content import course_title
from .errors import invalid, unprocessable

VISIBLE_WORK = ("published", "closed")


def grade_dict(g: Grade) -> dict:
    return {
        "id": g.id,
        "organisation_id": g.organisation_id,
        "course_space_id": g.course_space_id,
        "item_type": g.item_type,
        "item_id": g.item_id,
        "student_id": g.student_id,
        "points": g.points,
        "max_points": g.max_points,
        "feedback": g.feedback,
        "status": g.status,
        "version": g.version,
        "released_at": iso(g.released_at),
        "change_reason": g.change_reason,
    }


def _item(db: Session, item_type: str, item_id: str, *, for_update: bool = False) -> tuple[object, CourseSpace, float]:
    """The assignment or quiz, its course space and its maximum points; 404 when it does not exist."""
    if item_type == "assignment":
        item = c.get(db, Assignment, item_id, "assignment", for_update=for_update)
        max_points = item.max_points
    else:
        item = c.get(db, Quiz, item_id, "quiz", for_update=for_update)
        max_points = scoring.quiz_max_points(db, item.id)
    return item, c.space_of(db, item.course_space_id), max_points


def _students_with_work(db: Session, item_type: str, item_id: str) -> set[str]:
    if item_type == "assignment":
        return {s.student_id for s in repo.submissions(db, [item_id], include_superseded=True)}
    return {t.student_id for t in repo.attempts(db, [item_id])}


# ---------------------------------------------------------------- entering and releasing


def enter_grades(db: Session, a: Actor, body: dict) -> dict:
    item_type = body["item_type"]
    item, space, max_points = _item(db, item_type, body["item_id"], for_update=True)
    c.require_scope(db, a, space, k.GRADE_MANAGE_ASSIGNED)
    c.require_writable(space)
    if item.status not in VISIBLE_WORK:
        raise unprocessable("item_not_published", f"the {item_type} is not published")
    entries = body["entries"]
    if len({e["student_id"] for e in entries}) != len(entries):
        raise invalid("invalid_request", "a student appears twice in entries")
    allowed = {m.student_id for m in repo.members(db, space.course_offering_id)} | _students_with_work(
        db, item_type, item.id
    )
    out = []
    for e in entries:
        student, reason = e["student_id"], (e.get("reason") or "").strip() or None
        if student not in allowed:
            raise unprocessable("unknown_student", "the student is not registered in this course offering")
        c.check(rules.check_points, e["points"], max_points)
        if item_type == "quiz" and reason is None:
            raise unprocessable("reason_required", "overriding a quiz score needs a reason")
        g = repo.grade_for(db, item_type, item.id, student)
        if g is None:
            g = Grade(
                organisation_id=a.organisation_id,
                item_type=item_type,
                item_id=item.id,
                course_space_id=space.id,
                student_id=student,
                points=e["points"],
                max_points=max_points,
                feedback=e.get("feedback"),
                status="draft",
                version=1,
                change_reason=reason,
                source="manual",
                graded_by=a.user_id,
                created_at=c.clock(),
            )
            db.add(g)
            db.flush()
            c.audit(db, a, "grade.created", "grade", g.id, a.organisation_id)
        elif g.status == "released":
            if reason is None:
                raise unprocessable("reason_required", "changing a released grade needs a reason")
            g.points, g.max_points, g.version, g.change_reason = e["points"], max_points, g.version + 1, reason
            if "feedback" in e:
                g.feedback = e["feedback"]
            g.source, g.graded_by = "manual", a.user_id
            c.audit(db, a, "grade.changed", "grade", g.id, a.organisation_id)
            scoring.release(db, a, g, space)
        else:
            g.points, g.max_points, g.source, g.graded_by = e["points"], max_points, "manual", a.user_id
            if "feedback" in e:
                g.feedback = e["feedback"]
            if reason is not None:
                g.change_reason = reason
            c.audit(db, a, "grade.updated", "grade", g.id, a.organisation_id)
        if item_type == "assignment":
            for s in repo.submissions(db, [item.id], student_id=student, status="submitted"):
                s.status = "graded"
                c.audit(db, a, "submission.graded", "submission", s.id, a.organisation_id)
        out.append(g)
    db.commit()
    return {"items": [grade_dict(g) for g in out]}


def release_grades(db: Session, a: Actor, body: dict) -> dict:
    item, space, _ = _item(db, body["item_type"], body["item_id"], for_update=True)
    c.require_scope(db, a, space, k.GRADE_MANAGE_ASSIGNED)
    c.require_writable(space)
    wanted = set(body["student_ids"]) if body.get("student_ids") is not None else None
    drafts = [
        g
        for g in repo.grades(db, item_type=body["item_type"], item_id=item.id, status="draft")
        if wanted is None or g.student_id in wanted
    ]
    for g in drafts:
        scoring.release(db, a, g, space)
    db.commit()
    return {"released": len(drafts), "skipped": len(wanted) - len(drafts) if wanted is not None else 0}


# ---------------------------------------------------------------- gradebook


def gradebook(db: Session, a: Actor, space_id: str) -> dict:
    space = c.space_of(db, space_id)
    c.require_scope(db, a, space, k.GRADE_READ_ASSIGNED)
    assignments = [x for x in repo.assignments(db, [space.id]) if x.status in VISIBLE_WORK]
    quizzes = [x for x in repo.quizzes(db, [space.id]) if x.status in VISIBLE_WORK]
    scoring.settle_quizzes(db, [x.id for x in quizzes])
    stats = repo.question_stats(db, [x.id for x in quizzes])
    columns = [("assignment", x.id, x.title, iso(x.due_at), x.max_points) for x in assignments] + [
        ("quiz", x.id, x.title, iso(x.closes_at), stats.get(x.id, (0, 0.0))[1]) for x in quizzes
    ]
    grades = {(g.item_type, g.item_id, g.student_id): g for g in repo.grades(db, course_space_id=space.id)}
    submitted: dict[tuple[str, str], Submission] = {
        (s.assignment_id, s.student_id): s for s in repo.submissions(db, [x.id for x in assignments])
    }
    attempted = {
        (t.quiz_id, t.student_id) for t in repo.attempts(db, [x.id for x in quizzes]) if t.status != "in_progress"
    }
    names = repo.member_names(db, space.course_offering_id)
    students = [m.student_id for m in repo.members(db, space.course_offering_id)]
    students += sorted({sid for _, _, sid in grades} | {sid for _, sid in submitted} | {sid for _, sid in attempted})
    rows = []
    for student in dict.fromkeys(students):
        cells, points, max_points = [], 0.0, 0.0
        for item_type, item_id, *_ in columns:
            g = grades.get((item_type, item_id, student))
            sub = submitted.get((item_id, student)) if item_type == "assignment" else None
            if g is not None:
                status = "released" if g.status == "released" else "graded"
                if g.status == "released":
                    points, max_points = points + g.points, max_points + g.max_points
            elif sub is not None or (item_id, student) in attempted:
                status = "submitted"
            else:
                status = "missing"
            cells.append(
                {
                    "item_type": item_type,
                    "item_id": item_id,
                    "status": status,
                    "points": g.points if g is not None else None,
                    "late": bool(sub.late) if sub is not None else False,
                }
            )
        row = {
            "student_id": student,
            "cells": cells,
            "released_points": round(points, 4),
            "released_max_points": round(max_points, 4),
            "released_percent": rules.percent(points, max_points),
        }
        if names.get(student):
            row["student_name"] = names[student]
        rows.append(row)
    return {
        "course_space_id": space.id,
        "items": [
            {"item_type": t, "item_id": i, "title": title, "due_at": due, "max_points": mx}
            for t, i, title, due, mx in columns
        ],
        "students": rows,
    }


def my_grades(db: Session, a: Actor, space_id: str | None) -> dict:
    released = repo.grades(db, student_id=c.learner_ids(db, a), status="released", course_space_id=space_id)
    by_space: dict[str, list[Grade]] = {}
    for g in released:
        by_space.setdefault(g.course_space_id, []).append(g)
    spaces = {s: repo.get(db, CourseSpace, s) for s in by_space}
    offerings = repo.offerings(db, {s.course_offering_id for s in spaces.values() if s is not None})
    items = []
    for space_key, grades in by_space.items():
        space = spaces[space_key]
        item = {
            "course_space_id": space_key,
            "grades": [grade_dict(g) for g in grades],
            "released_points": round(sum(g.points for g in grades), 4),
            "released_max_points": round(sum(g.max_points for g in grades), 4),
        }
        if space is not None:
            item["course_title"] = course_title(space, offerings.get(space.course_offering_id))
        items.append(item)
    return {"items": items}


# ---------------------------------------------------------------- the Faculty widget (FR-16)


def grading_queue(db: Session, a: Actor) -> dict:
    """Published or closed assignments and quizzes in the non-archived spaces the caller teaches with work waiting for
    a grade: current submissions not yet graded, or quiz attempts waiting for essay scores. Oldest waiting first."""
    taught = repo.taught_offerings(db, a.user_id)
    spaces = {s.id: s for s in repo.spaces_for_offerings(db, taught) if s.status != "archived"}
    offerings = repo.offerings(db, {s.course_offering_id for s in spaces.values()})
    assignments = [x for x in repo.assignments(db, list(spaces)) if x.status in VISIBLE_WORK]
    quizzes = [x for x in repo.quizzes(db, list(spaces)) if x.status in VISIBLE_WORK]
    scoring.settle_quizzes(db, [x.id for x in quizzes])
    waiting: dict[str, list] = {}
    for s in repo.submissions(db, [x.id for x in assignments], status="submitted"):
        waiting.setdefault(s.assignment_id, []).append(s.submitted_at)
    for t in repo.attempts(db, [x.id for x in quizzes], manual_grading_state="pending"):
        waiting.setdefault(t.quiz_id, []).append(t.submitted_at)
    items = []
    for item_type, rows in (("assignment", assignments), ("quiz", quizzes)):
        for x in rows:
            times = [as_utc(w) for w in waiting.get(x.id, []) if w is not None]
            if not times:
                continue
            space = spaces[x.course_space_id]
            items.append(
                {
                    "course_space_id": space.id,
                    "course_title": course_title(space, offerings.get(space.course_offering_id)),
                    "item_type": item_type,
                    "item_id": x.id,
                    "title": x.title,
                    "due_at": iso(x.due_at if item_type == "assignment" else x.closes_at),
                    "waiting_count": len(times),
                    "oldest_waiting_since": iso(min(times)),
                }
            )
    items.sort(key=lambda i: (i["oldest_waiting_since"], i["item_id"]))
    return {"items": items, "total": len(items)}
