"""Coursework activity per course space (FR-18), computed from this module's data only.

lms:report:read-all covers the organisation, optionally one department. lms:report:read-department means the caller's
own department, which lms cannot know yet (docs/prd.md LQ13): such a caller gets an empty report for "their"
department, and naming a department they cannot be shown to belong to is refused."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..infrastructure import repository as repo
from ..infrastructure.models import as_utc, iso
from . import access as k
from . import scoring
from .access import Actor
from .content import course_title
from .errors import forbidden

WORK = ("published", "closed")


def coursework_activity(db: Session, a: Actor, department_id: str | None, academic_period_id: str | None) -> dict:
    if not a.can(k.REPORT_READ_ALL):
        if department_id is not None:
            raise forbidden(
                "lms cannot confirm your department yet (docs/prd.md LQ13); lms:report:read-all reads any department",
                "department_unverified",
            )
        return {"department_id": None, "items": []}
    spaces = list(db.scalars(repo.spaces_query(db, {"department_id": department_id})))
    offerings = repo.offerings(db, {s.course_offering_id for s in spaces})
    if academic_period_id is not None:
        spaces = [
            s
            for s in spaces
            if offerings.get(s.course_offering_id) is not None
            and offerings[s.course_offering_id].academic_period_id == academic_period_id
        ]
    ids = [s.id for s in spaces]
    materials = repo.materials(db, ids)
    assignments = repo.assignments(db, ids)
    quizzes = repo.quizzes(db, ids)
    scoring.settle_quizzes(db, [x.id for x in quizzes])
    submissions = repo.submissions(db, [x.id for x in assignments])
    attempts = [t for t in repo.attempts(db, [x.id for x in quizzes]) if t.submitted_at is not None]
    threads = repo.all_threads(db, ids)
    posts = repo.all_posts(db, [t.id for t in threads])
    thread_space = {t.id: t.course_space_id for t in threads}

    def per_space(rows, key) -> dict[str, list]:
        out: dict[str, list] = {}
        for r in rows:
            out.setdefault(key(r), []).append(r)
        return out

    by_material = per_space([m for m in materials if m.status == "published"], lambda m: m.course_space_id)
    by_assignment = per_space([x for x in assignments if x.status in WORK], lambda x: x.course_space_id)
    by_quiz = per_space([x for x in quizzes if x.status in WORK], lambda x: x.course_space_id)
    by_submission = per_space(submissions, lambda s: s.course_space_id)
    by_attempt = per_space(attempts, lambda t: t.course_space_id)
    by_thread = per_space(threads, lambda t: t.course_space_id)
    by_post = per_space(posts, lambda p: thread_space[p.thread_id])

    items = []
    for s in spaces:
        waiting = [x.submitted_at for x in by_submission.get(s.id, []) if x.status == "submitted"]
        waiting += [t.submitted_at for t in by_attempt.get(s.id, []) if t.manual_grading_state == "pending"]
        activity = [m.published_at for m in by_material.get(s.id, []) if m.published_at is not None]
        activity += [x.submitted_at for x in by_submission.get(s.id, [])]
        activity += [t.submitted_at for t in by_attempt.get(s.id, [])]
        activity += [t.created_at for t in by_thread.get(s.id, [])]
        activity += [p.created_at for p in by_post.get(s.id, [])]
        waiting, activity = [as_utc(w) for w in waiting], [as_utc(w) for w in activity]
        items.append(
            {
                "course_space_id": s.id,
                "course_offering_id": s.course_offering_id,
                "course_title": course_title(s, offerings.get(s.course_offering_id)),
                "materials_published": len(by_material.get(s.id, [])),
                "assignments_published": len(by_assignment.get(s.id, [])),
                "quizzes_published": len(by_quiz.get(s.id, [])),
                "submissions_received": len(by_submission.get(s.id, [])),
                "ungraded": len(waiting),
                "oldest_ungraded_since": iso(min(waiting)) if waiting else None,
                "last_activity_at": iso(max(activity)) if activity else None,
            }
        )
    return {"department_id": department_id, "items": items}
