"""Use cases for exam papers and exam sessions (docs/prd.md FR-4 to FR-6, contracts/openapi.yaml): listExamPapers,
createExamPapers, getExamPaper, updateExamPaper, listExamSessions, scheduleExamSession, getExamSession,
rescheduleExamSession and cancelExamSession. They share the conventions of application/service.py (whose helpers they
call, so one transaction wrapper, one audit writer and one clock serve the module): domain rules first, an audit entry
per change, the contract's event published in the same transaction, one commit, everything rolled back on any failure.

Events: examinations.exam-session.scheduled, .rescheduled and .cancelled only. Papers publish nothing (the contract
names no event for them). A reschedule publishes only when the time or venue changed, as the event is defined.

Known gaps, not worked around here (docs/reviewer-decisions.md section 11):
- A session is not checked against the cycle's dates (FR-5): there is no source for the organisation's time zone, the
  domain's `ensure_within_cycle` needs one, and no decision exists. Guessing UTC would refuse valid local times.
- A candidate clash (FR-5) needs candidates, which wait on the `student_id` mapping. `candidate_count` is 0.
- `course_code`, `course_title` and `department_id` of a paper come from the offering read model, which is not filled,
  so they are not served.
- A cancelled session keeps no paper links (a paper is in at most one session, enforced by a unique index), so it is
  served with no papers; the cancelled papers are in the audit entry and the event."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta

from eos_core.db import new_id
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain import assessment as asm
from ..domain import papers as pap
from ..domain import sessions as ses
from ..domain.values import optional_text, require_id, require_instant, require_integer, require_text
from ..infrastructure import repository as repo
from ..infrastructure.models import (
    AssessmentComponentRow,
    ExamDutyRow,
    ExamPaperRow,
    ExamSessionPaperRow,
    ExamSessionRow,
    OfferingRef,
    as_utc,
    iso,
)
from . import service as base
from .access import Actor
from .errors import ExaminationsError, invalid, not_found

# ---------------------------------------------------------------- parsing


def _instant(value: object, field: str) -> datetime:
    """A contract `format: date-time` with a zone, in UTC."""
    if not isinstance(value, str):
        raise invalid("invalid_datetime", f"{field} must be a date and time with a zone", field)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise invalid("invalid_datetime", f"{field} must be a date and time with a zone", field) from None
    return base._domain(require_instant, parsed, field)


def _require_fields(data: dict, names: Iterable[str]) -> None:
    missing = [n for n in names if n not in data]
    if missing:
        raise invalid("missing_field", f"{', '.join(missing)} is required", missing[0])


def _id_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list):
        raise invalid("invalid_body", f"{field} must be a list", field)
    return [base._domain(require_id, v, f"{field}[{i}]") for i, v in enumerate(value)]


# ---------------------------------------------------------------- papers

CREATE_PAPERS_FIELDS = ("exam_cycle_id", "course_offering_id", "component_codes", "duration_minutes")
UPDATE_PAPER_FIELDS = ("title", "duration_minutes")
TITLE_MAX = 200  # the column


def _paper_bodies(db: Session, rows: list[ExamPaperRow]) -> list[dict]:
    """components.schemas.ExamPaper for each row. `candidate_count`, `course_code`, `course_title` and
    `department_id` are not served (see the module docstring)."""
    if not rows:
        return []
    ids = [r.id for r in rows]
    components = {
        c.id: c
        for c in db.scalars(
            repo.q(db, AssessmentComponentRow).where(
                AssessmentComponentRow.id.in_({r.assessment_component_id for r in rows})
            )
        )
    }
    links = {
        link.exam_paper_id: link.exam_session_id
        for link in db.scalars(repo.q(db, ExamSessionPaperRow).where(ExamSessionPaperRow.exam_paper_id.in_(ids)))
    }
    return [
        {
            "id": r.id,
            "organisation_id": r.organisation_id,
            "exam_cycle_id": r.exam_cycle_id,
            "course_offering_id": r.course_offering_id,
            "assessment_component_id": r.assessment_component_id,
            "component_code": components[r.assessment_component_id].code,
            "max_marks": base._num(r.max_marks),
            "duration_minutes": r.duration_minutes,
            "exam_session_id": links.get(r.id),
            "status": r.status,
            # the contract types `title` as a string (not nullable), so an untitled paper omits it
            **({"title": r.title} if r.title is not None else {}),
        }
        for r in rows
    ]


def _paper_or_404(db: Session, exam_paper_id: str) -> ExamPaperRow:
    row = repo.get(db, ExamPaperRow, exam_paper_id)
    if row is None:
        raise not_found("exam_paper_not_found", "exam paper not found")
    return row


def _paper_domain(row: ExamPaperRow) -> pap.Paper:
    return pap.Paper(
        id=row.id,
        exam_cycle_id=row.exam_cycle_id,
        course_offering_id=row.course_offering_id,
        assessment_component_id=row.assessment_component_id,
        max_marks=row.max_marks,
        duration_minutes=row.duration_minutes,
        status=row.status,
    )


def list_exam_papers(
    db: Session,
    exam_cycle_id: str | None,
    course_offering_id: str | None,
    department_id: str | None,
    status: str | None,
    limit: int,
    offset: int,
) -> dict:
    query = repo.q(db, ExamPaperRow)
    if (cycle := base._optional_id(exam_cycle_id, "exam_cycle_id")) is not None:
        query = query.where(ExamPaperRow.exam_cycle_id == cycle)
    if (offering := base._optional_id(course_offering_id, "course_offering_id")) is not None:
        query = query.where(ExamPaperRow.course_offering_id == offering)
    if (department := base._optional_id(department_id, "department_id")) is not None:
        # The department comes from the offering read model, filled by the offering consumers: an offering whose
        # `offering.created` has not been delivered has no department and is not matched.
        offerings = repo.q(db, OfferingRef).where(OfferingRef.department_id == department)
        query = query.where(
            ExamPaperRow.course_offering_id.in_(offerings.with_only_columns(OfferingRef.course_offering_id))
        )
    if (state := base._optional_choice(status, "status", pap.PAPER_STATUSES)) is not None:
        query = query.where(ExamPaperRow.status == state)
    rows, total = repo.page(db, query, [ExamPaperRow.course_offering_id, ExamPaperRow.id], limit, offset)
    return {"items": _paper_bodies(db, rows), "total": total}


def get_exam_paper(db: Session, exam_paper_id: str) -> dict:
    return _paper_bodies(db, [_paper_or_404(db, exam_paper_id)])[0]


@base.transactional
def create_exam_papers(db: Session, actor: Actor, body: object) -> dict:
    """FR-4: one paper per listed component of the offering's active assessment scheme, in a cycle that can still be
    configured. A cycle or an offering with no active scheme is a 422 (the contract's create declares no 404). The
    offering is not looked up in the read model: it is not filled, and the active scheme is the evidence the offering
    is examined here."""
    data = base._object(body, "body", CREATE_PAPERS_FIELDS)
    _require_fields(data, ("exam_cycle_id", "course_offering_id", "component_codes"))
    cycle_id = base._domain(require_id, data["exam_cycle_id"], "exam_cycle_id")
    offering_id = base._domain(require_id, data["course_offering_id"], "course_offering_id")
    codes = data["component_codes"]
    if not isinstance(codes, list):
        raise invalid("invalid_body", "component_codes must be a list", "component_codes")
    duration = data.get("duration_minutes")
    if "duration_minutes" in data:
        base._domain(require_integer, duration, "duration_minutes", minimum=1)
    cycle_row = repo.cycle(db, cycle_id)
    if cycle_row is None:
        raise ExaminationsError(422, "unknown_exam_cycle", "exam_cycle_id names no exam cycle", field="exam_cycle_id")
    active = next((r for r in repo.schemes_of_offering(db, offering_id) if r.status == asm.ACTIVE), None)
    if active is None:
        raise ExaminationsError(
            422,
            "scheme_not_active",
            "the course offering has no active assessment scheme",
            field="course_offering_id",
        )
    scheme = base._assessment_domain(db, active)
    component_ids = {c.code: c.id for c in repo.components_of(db, active.id)}
    existing = {p.assessment_component_id for p in repo.papers_of_cycle(db, cycle_id)}
    planned = base._domain(
        pap.plan_papers,
        base._cycle_domain(cycle_row),
        scheme,
        component_ids,
        [{"component_code": code, "duration_minutes": duration} for code in codes],
        paper_id=new_id,
        existing_component_ids=existing,
    )
    rows = [
        ExamPaperRow(
            id=p.id,
            organisation_id=actor.organisation_id,
            exam_cycle_id=p.exam_cycle_id,
            course_offering_id=p.course_offering_id,
            assessment_component_id=p.assessment_component_id,
            max_marks=p.max_marks,
            duration_minutes=p.duration_minutes,
            status=pap.DRAFT,
        )
        for p in planned
    ]
    db.add_all(rows)
    for row in rows:
        base._audit(
            db,
            actor,
            "exam_paper.created",
            "exam_paper",
            row,
            after={
                "exam_cycle_id": row.exam_cycle_id,
                "course_offering_id": row.course_offering_id,
                "assessment_component_id": row.assessment_component_id,
                "max_marks": row.max_marks,
                "duration_minutes": row.duration_minutes,
            },
        )
    db.commit()
    return {"items": _paper_bodies(db, rows)}


@base.transactional
def update_exam_paper(db: Session, actor: Actor, exam_paper_id: str, body: object) -> dict:
    """Edits a draft paper's title and duration, while its cycle can be configured. The contract types `title` as a
    string, so it can be replaced but not cleared. A request that changes nothing writes nothing."""
    row = _paper_or_404(db, exam_paper_id)
    data = base._object(body, "body", UPDATE_PAPER_FIELDS)
    cycle_row = repo.cycle(db, row.exam_cycle_id)
    base._domain(base.cy.ensure_configurable, base._cycle_domain(cycle_row))
    if row.status != pap.DRAFT:
        raise ExaminationsError(
            409,
            "paper_not_draft",
            f"only a draft paper can be edited, this one is {row.status}",
            status=row.status,
        )
    changes: dict = {}
    if "title" in data:
        changes["title"] = base._domain(require_text, data["title"], "title", max_length=TITLE_MAX)
    if "duration_minutes" in data:
        changes["duration_minutes"] = base._domain(
            require_integer, data["duration_minutes"], "duration_minutes", minimum=1
        )
    before = {f: getattr(row, f) for f, v in changes.items() if getattr(row, f) != v}
    after = {f: v for f, v in changes.items() if f in before}
    if after:
        for field, value in after.items():
            setattr(row, field, value)
        base._audit(db, actor, "exam_paper.updated", "exam_paper", row, before=before, after=after)
        db.commit()
    return _paper_bodies(db, [row])[0]


# ---------------------------------------------------------------- sessions

SCHEDULE_FIELDS = ("exam_cycle_id", "starts_at", "ends_at", "exam_paper_ids", "invigilators_required", "venue_label")
RESCHEDULE_FIELDS = ("starts_at", "ends_at", "invigilators_required", "venue_label", "reason")
DEFAULT_INVIGILATORS = 1  # contract CreateExamSessionRequest.invigilators_required default
REASON_MAX = 500


def _session_papers(db: Session, session_id: str) -> list[ExamPaperRow]:
    links = db.scalars(repo.q(db, ExamSessionPaperRow).where(ExamSessionPaperRow.exam_session_id == session_id))
    ids = [link.exam_paper_id for link in links]
    if not ids:
        return []
    rows = db.scalars(repo.q(db, ExamPaperRow).where(ExamPaperRow.id.in_(ids)))
    return sorted(rows, key=lambda r: (r.course_offering_id, r.id))


def _session_bodies(db: Session, rows: list[ExamSessionRow]) -> list[dict]:
    """components.schemas.ExamSession. `candidate_count` is 0 until candidates exist; `invigilators_assigned` counts the
    session's assigned invigilation duties."""
    out = []
    for r in rows:
        papers = _session_papers(db, r.id)
        codes = {
            c.id: c.code
            for c in db.scalars(
                repo.q(db, AssessmentComponentRow).where(
                    AssessmentComponentRow.id.in_({p.assessment_component_id for p in papers})
                )
            )
        }
        assigned = db.scalars(
            repo.q(db, ExamDutyRow).where(
                ExamDutyRow.exam_session_id == r.id,
                ExamDutyRow.duty_type == ses.INVIGILATION,
                ExamDutyRow.status == ses.ASSIGNED,
            )
        )
        out.append(
            {
                "id": r.id,
                "organisation_id": r.organisation_id,
                "exam_cycle_id": r.exam_cycle_id,
                "starts_at": iso(r.starts_at),
                "ends_at": iso(r.ends_at),
                "venue_label": r.venue_label,
                "status": r.status,
                "cancel_reason": r.cancel_reason,
                "invigilators_required": r.invigilators_required,
                "invigilators_assigned": len(list(assigned)),
                "candidate_count": 0,
                "papers": [
                    {
                        "exam_paper_id": p.id,
                        "course_offering_id": p.course_offering_id,
                        "component_code": codes[p.assessment_component_id],
                    }
                    for p in papers
                ],
            }
        )
    return out


def _session_or_404(db: Session, exam_session_id: str) -> ExamSessionRow:
    row = repo.get(db, ExamSessionRow, exam_session_id)
    if row is None:
        raise not_found("exam_session_not_found", "exam session not found")
    return row


def _session_domain(row: ExamSessionRow) -> ses.Session:
    return ses.Session(
        id=row.id,
        exam_cycle_id=row.exam_cycle_id,
        starts_at=as_utc(row.starts_at),
        ends_at=as_utc(row.ends_at),
        invigilators_required=row.invigilators_required,
        venue_label=row.venue_label,
        status=row.status,
        cancel_reason=row.cancel_reason,
    )


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def list_exam_sessions(
    db: Session,
    exam_cycle_id: str | None,
    date_from: str | None,
    date_to: str | None,
    course_offering_id: str | None,
    status: str | None,
    limit: int,
    offset: int,
) -> dict:
    """Ordered by start time. `date_from` and `date_to` are days read in UTC (no organisation time zone exists yet): a
    session is listed when it ends on or after `date_from` and starts on or before `date_to`."""
    query = repo.q(db, ExamSessionRow)
    if (cycle := base._optional_id(exam_cycle_id, "exam_cycle_id")) is not None:
        query = query.where(ExamSessionRow.exam_cycle_id == cycle)
    if date_from is not None:
        query = query.where(ExamSessionRow.ends_at >= _day_start(base._parse_date(date_from, "date_from")))
    if date_to is not None:
        query = query.where(
            ExamSessionRow.starts_at < _day_start(base._parse_date(date_to, "date_to")) + timedelta(days=1)
        )
    if (offering := base._optional_id(course_offering_id, "course_offering_id")) is not None:
        in_offering = (
            select(ExamSessionPaperRow.exam_session_id)
            .join(ExamPaperRow, ExamPaperRow.id == ExamSessionPaperRow.exam_paper_id)
            .where(ExamPaperRow.course_offering_id == offering)
        )
        query = query.where(ExamSessionRow.id.in_(repo.scoped(db, in_offering, ExamSessionPaperRow)))
    if (state := base._optional_choice(status, "status", ses.SESSION_STATUSES)) is not None:
        query = query.where(ExamSessionRow.status == state)
    rows, total = repo.page(db, query, [ExamSessionRow.starts_at, ExamSessionRow.id], limit, offset)
    return {"items": _session_bodies(db, rows), "total": total}


def get_exam_session(db: Session, exam_session_id: str) -> dict:
    return _session_bodies(db, [_session_or_404(db, exam_session_id)])[0]


def _paper_rows(db: Session, ids: list[str]) -> list[ExamPaperRow]:
    found = {r.id: r for r in db.scalars(repo.q(db, ExamPaperRow).where(ExamPaperRow.id.in_(ids)))}
    for index, paper_id in enumerate(ids):
        if paper_id not in found:
            raise ExaminationsError(
                422, "unknown_paper", f"paper {paper_id} does not exist", field=f"exam_paper_ids[{index}]"
            )
    return [found[i] for i in ids]


@base.transactional
def schedule_exam_session(db: Session, actor: Actor, body: object) -> dict:
    """FR-5: papers of the session's cycle, still draft and in no other session, with a start and an end. The cycle
    must be draft or scheduled. The papers become `scheduled`. Publishes examinations.exam-session.scheduled."""
    data = base._object(body, "body", SCHEDULE_FIELDS)
    _require_fields(data, ("exam_cycle_id", "starts_at", "ends_at", "exam_paper_ids"))
    cycle_id = base._domain(require_id, data["exam_cycle_id"], "exam_cycle_id")
    starts, ends = _instant(data["starts_at"], "starts_at"), _instant(data["ends_at"], "ends_at")
    paper_ids = _id_list(data["exam_paper_ids"], "exam_paper_ids")
    session = base._domain(
        ses.new_session,
        new_id(),
        cycle_id,
        starts,
        ends,
        invigilators_required=data.get("invigilators_required", DEFAULT_INVIGILATORS),
        venue_label=data.get("venue_label"),
    )
    cycle_row = repo.cycle(db, cycle_id)
    if cycle_row is None:
        raise ExaminationsError(422, "unknown_exam_cycle", "exam_cycle_id names no exam cycle", field="exam_cycle_id")
    base._domain(base.cy.ensure_configurable, base._cycle_domain(cycle_row))
    papers = _paper_rows(db, paper_ids) if paper_ids else []
    base._domain(
        ses.ensure_papers_schedulable,
        [_paper_domain(p) for p in papers],
        cycle_id,
        papers_in_sessions=repo.paper_ids_in_sessions(db, paper_ids),
    )
    row = ExamSessionRow(
        id=session.id,
        organisation_id=actor.organisation_id,
        exam_cycle_id=cycle_id,
        starts_at=session.starts_at,
        ends_at=session.ends_at,
        venue_label=session.venue_label,
        invigilators_required=session.invigilators_required,
        status=ses.SCHEDULED,
    )
    db.add(row)
    db.flush()
    db.add_all(
        ExamSessionPaperRow(organisation_id=actor.organisation_id, exam_session_id=row.id, exam_paper_id=p.id)
        for p in papers
    )
    for paper in papers:
        paper.status = pap.SCHEDULED
        base._audit(
            db,
            actor,
            "exam_paper.scheduled",
            "exam_paper",
            paper,
            before={"status": pap.DRAFT},
            after={"status": pap.SCHEDULED, "exam_session_id": row.id},
        )
    base._audit(
        db,
        actor,
        "exam_session.scheduled",
        "exam_session",
        row,
        after={
            "exam_cycle_id": cycle_id,
            "starts_at": row.starts_at,
            "ends_at": row.ends_at,
            "venue_label": row.venue_label,
            "invigilators_required": row.invigilators_required,
            "exam_paper_ids": paper_ids,
        },
    )
    base._publish(
        db,
        actor,
        "exam-session.scheduled",
        {
            "exam_session_id": row.id,
            "exam_cycle_id": cycle_id,
            "starts_at": iso(row.starts_at),
            "ends_at": iso(row.ends_at),
            "venue_label": row.venue_label,
            "papers": [{"exam_paper_id": p.id, "course_offering_id": p.course_offering_id} for p in papers],
        },
    )
    db.commit()
    return _session_bodies(db, [row])[0]


@base.transactional
def reschedule_exam_session(db: Session, actor: Actor, exam_session_id: str, body: object) -> dict:
    """FR-6: only while scheduled, and while the cycle can be configured. A new time or venue publishes
    examinations.exam-session.rescheduled; a change of `invigilators_required` alone is audited and publishes nothing
    (the event is about time and venue). A request that changes nothing writes nothing."""
    row = _session_or_404(db, exam_session_id)
    data = base._object(body, "body", RESCHEDULE_FIELDS)
    current = _session_domain(row)
    base._domain(ses.ensure_open, current)
    base._domain(base.cy.ensure_configurable, base._cycle_domain(repo.cycle(db, row.exam_cycle_id)))
    reason = None
    if "reason" in data:
        reason = base._domain(optional_text, data["reason"], "reason", max_length=REASON_MAX)
    moved, changed = base._domain(
        ses.plan_reschedule,
        current,
        starts_at=_instant(data["starts_at"], "starts_at") if "starts_at" in data else None,
        ends_at=_instant(data["ends_at"], "ends_at") if "ends_at" in data else None,
        venue_label=data["venue_label"] if "venue_label" in data else ...,
    )
    if "invigilators_required" in data:
        required = base._domain(require_integer, data["invigilators_required"], "invigilators_required", minimum=0)
        if required != moved.invigilators_required:
            moved, changed = replace(moved, invigilators_required=required), [*changed, "invigilators_required"]
    if not changed:
        return _session_bodies(db, [row])[0]
    before = {f: getattr(row, f) for f in changed}
    after = {f: getattr(moved, f) for f in changed}
    for field, value in after.items():
        setattr(row, field, value)
    base._audit(db, actor, "exam_session.rescheduled", "exam_session", row, before=before, after=after, reason=reason)
    if set(changed) & {"starts_at", "ends_at", "venue_label"}:
        base._publish(
            db,
            actor,
            "exam-session.rescheduled",
            {
                "exam_session_id": row.id,
                "exam_cycle_id": row.exam_cycle_id,
                "previous_starts_at": iso(current.starts_at),
                "previous_ends_at": iso(current.ends_at),
                "starts_at": iso(row.starts_at),
                "ends_at": iso(row.ends_at),
                "venue_label": row.venue_label,
                "reason": reason,
            },
        )
    db.commit()
    return _session_bodies(db, [row])[0]


CANCELLABLE_CYCLE_STATUSES = (base.cy.DRAFT, base.cy.SCHEDULED, base.cy.IN_PROGRESS)


def _ensure_cancellable(cycle_row) -> None:
    """A session can be cancelled while its cycle is draft, scheduled or in progress (an examination that is under way
    can lose a sitting). Once the cycle is in evaluation or later, the sittings are over."""
    if cycle_row.status not in CANCELLABLE_CYCLE_STATUSES:
        raise ExaminationsError(
            409,
            "cycle_not_cancellable",
            f"a session can be cancelled while its cycle is draft, scheduled or in progress, this one is {cycle_row.status}",
            status=cycle_row.status,
        )


@base.transactional
def cancel_exam_session(db: Session, actor: Actor, exam_session_id: str, body: object) -> dict:
    """FR-6: a scheduled session is cancelled with a reason, while its cycle is draft, scheduled or in progress; its
    papers return to draft and leave the session, so they can be scheduled again. Publishes
    examinations.exam-session.cancelled."""
    row = _session_or_404(db, exam_session_id)
    data = base._object(body, "body", ("reason",))
    _require_fields(data, ("reason",))
    base._domain(ses.ensure_open, _session_domain(row))
    _ensure_cancellable(repo.cycle(db, row.exam_cycle_id))
    cancelled = base._domain(ses.plan_cancel, _session_domain(row), data["reason"])
    papers = _session_papers(db, row.id)
    for paper in papers:
        base._domain(pap.return_to_draft, _paper_domain(paper))
    links = list(db.scalars(repo.q(db, ExamSessionPaperRow).where(ExamSessionPaperRow.exam_session_id == row.id)))
    for link in links:
        db.delete(link)
    db.flush()
    for paper in papers:
        paper.status = pap.DRAFT
        base._audit(
            db,
            actor,
            "exam_paper.returned_to_draft",
            "exam_paper",
            paper,
            before={"status": pap.SCHEDULED, "exam_session_id": row.id},
            after={"status": pap.DRAFT},
            reason=cancelled.cancel_reason,
        )
    row.status, row.cancel_reason = cancelled.status, cancelled.cancel_reason
    base._audit(
        db,
        actor,
        "exam_session.cancelled",
        "exam_session",
        row,
        before={"status": ses.SCHEDULED},
        after={"status": ses.CANCELLED, "exam_paper_ids": [p.id for p in papers]},
        reason=cancelled.cancel_reason,
    )
    base._publish(
        db,
        actor,
        "exam-session.cancelled",
        {
            "exam_session_id": row.id,
            "exam_cycle_id": row.exam_cycle_id,
            "exam_paper_ids": [p.id for p in papers],
            "reason": cancelled.cancel_reason,
            "cancelled_at": iso(base.clock()),
        },
    )
    db.commit()
    return _session_bodies(db, [row])[0]
