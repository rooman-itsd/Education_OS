"""GET /me/exam-schedule (docs/prd.md, contracts/openapi.yaml `getMyExamSchedule`): the exam sessions a student sits, for
the widget `examinations.upcoming-assessments`. Exams only (PRD Q6): coursework deadlines are not here.

A student is their candidacies: the rows of `examinations_candidate` whose `student_id` is the caller. `student_id` holds
the canonical `person_id` (decision on #325), and this module has no map from a sign-in account to a person (the
timetable-attendance module reads one from `student-information.person.account-linked`; examinations does not consume
it), so until one exists the caller's user id is taken as their student id, as timetable-attendance does before a link is
known. Nothing creates candidates yet, so every student's schedule is empty until the registration slice lands.

Only scheduled sessions that have not ended are listed, from `date_from` (default today, UTC: the organisation has no
time zone yet), by start time. `hall_ticket_status` is null: hall tickets are not built."""

from __future__ import annotations

from datetime import UTC, datetime, time

from sqlalchemy.orm import Session

from ..domain import sessions as ses
from ..infrastructure import repository as repo
from ..infrastructure.models import (
    AssessmentComponentRow,
    CandidateRow,
    ExamPaperRow,
    ExamSessionPaperRow,
    ExamSessionRow,
    OfferingRef,
    as_utc,
    iso,
)
from . import service as base
from .access import Actor


def my_exam_schedule(db: Session, actor: Actor, date_from: str | None) -> dict:
    start = base._parse_date(date_from, "date_from") if date_from is not None else base.clock().date()
    since = datetime.combine(start, time.min, tzinfo=UTC)
    candidates = list(db.scalars(repo.q(db, CandidateRow).where(CandidateRow.student_id == actor.user_id)))
    if not candidates:
        return {"items": []}
    by_paper = {c.exam_paper_id: c for c in candidates}
    links = list(db.scalars(repo.q(db, ExamSessionPaperRow).where(ExamSessionPaperRow.exam_paper_id.in_(by_paper))))
    sessions = {
        s.id: s
        for s in db.scalars(
            repo.q(db, ExamSessionRow).where(ExamSessionRow.id.in_({link.exam_session_id for link in links}))
        )
    }
    papers = {p.id: p for p in db.scalars(repo.q(db, ExamPaperRow).where(ExamPaperRow.id.in_(by_paper)))}
    components = {
        c.id: c
        for c in db.scalars(
            repo.q(db, AssessmentComponentRow).where(
                AssessmentComponentRow.id.in_({p.assessment_component_id for p in papers.values()})
            )
        )
    }
    offerings = {
        o.course_offering_id: o
        for o in db.scalars(
            repo.q(db, OfferingRef).where(
                OfferingRef.course_offering_id.in_({c.course_offering_id for c in candidates})
            )
        )
    }
    items = []
    for link in links:
        session = sessions.get(link.exam_session_id)
        if session is None or session.status != ses.SCHEDULED or as_utc(session.ends_at) < since:
            continue
        candidate, paper = by_paper[link.exam_paper_id], papers[link.exam_paper_id]
        offering = offerings.get(candidate.course_offering_id)
        item = {
            "exam_session_id": session.id,
            "exam_cycle_id": session.exam_cycle_id,
            "starts_at": iso(session.starts_at),
            "ends_at": iso(session.ends_at),
            "venue_label": session.venue_label,
            "exam_paper_id": paper.id,
            "course_offering_id": candidate.course_offering_id,
            "component_code": components[paper.assessment_component_id].code,
            "eligibility_status": candidate.eligibility_status,
            "hall_ticket_status": None,
        }
        if offering is not None and offering.course_code:
            item["course_code"], item["course_title"] = offering.course_code, offering.course_title
        items.append(item)
    items.sort(key=lambda i: (i["starts_at"], i["exam_paper_id"]))
    return {"items": items}
