"""Use cases for exam duties (docs/prd.md FR-9, contracts/openapi.yaml): listExamDuties, assignExamDuty, cancelExamDuty and
listMyDuties. They share the conventions of application/service.py, whose helpers they call (one transaction wrapper, one
audit writer, one clock): domain rules first, an audit entry per change, the contract's event published in the same
transaction, one commit, everything rolled back on any failure.

Events: examinations.duty.assigned and examinations.duty.cancelled only.

Decisions of the duties slice (docs/reviewer-decisions.md section 12):
- Invigilation needs a session; evaluation and moderation need a paper, exactly one target (the domain's `Duty`).
- Assigning needs a cycle that is draft, scheduled, in progress or in evaluation (409 once results are published or the
  cycle is closed), and a session that is `scheduled` (a cancelled or completed session is refused). Evaluation and
  moderation do not look at the paper's pipeline status. Over-assigning invigilators is allowed.
- A duplicate (same staff member, type and target, still assigned or completed) is a 409, backed by the partial unique
  indexes of ex_0003; a cancelled duty frees the target. Overlapping invigilation is a 409, back-to-back is fine, and a
  cancelled session never counts.
- Cancelling a session does not cancel its duties. Cancelling a duty needs a reason and works in any cycle status.
- `staff_id` is stored as given, with no identity lookup: nothing here checks that the user exists or belongs to the
  organisation (PRD Q11; the identity SDK does not exist). Assigning a made-up or foreign uuid succeeds.
- Reads: `duty:read-all` sees the organisation's duties; `duty:read-department` alone sees none, because the caller's
  department is unknown (Q13), and is not refused for it. `duty:read-own` serves GET /me/duties.
- Session fields (`starts_at`, `ends_at`, `venue_label`) are the session's, for invigilation, and null otherwise.
  `course_code` is read from the offering read model for evaluation and moderation, and is null while it has no row."""

from __future__ import annotations

from eos_core.db import new_id
from sqlalchemy.orm import Session

from ..domain import cycles as cy
from ..domain import sessions as ses
from ..domain.values import require_choice, require_id
from ..infrastructure import repository as repo
from ..infrastructure.models import ExamDutyRow, ExamPaperRow, ExamSessionRow, OfferingRef, as_utc, iso
from . import schedule as sch
from . import service as base
from .access import DUTY_READ_ALL, Actor
from .errors import ExaminationsError, invalid, not_found

ASSIGN_FIELDS = ("staff_id", "duty_type", "exam_session_id", "exam_paper_id")
# The cycle statuses in which duties can be assigned: results are not published and the cycle is not closed.
ASSIGNABLE_CYCLE_STATUSES = (cy.DRAFT, cy.SCHEDULED, cy.IN_PROGRESS, cy.EVALUATION)
_PLACEHOLDER = "00000000-0000-0000-0000-000000000000"  # stands in for the cycle while the request is checked


# ---------------------------------------------------------------- bodies


def _duty_bodies(db: Session, rows: list[ExamDutyRow]) -> list[dict]:
    """components.schemas.ExamDuty. Nothing is invented: a field the read model does not give is null."""
    if not rows:
        return []
    session_ids = {r.exam_session_id for r in rows if r.exam_session_id}
    paper_ids = {r.exam_paper_id for r in rows if r.exam_paper_id}
    sessions = (
        {s.id: s for s in db.scalars(repo.q(db, ExamSessionRow).where(ExamSessionRow.id.in_(session_ids)))}
        if session_ids
        else {}
    )
    papers = (
        {p.id: p for p in db.scalars(repo.q(db, ExamPaperRow).where(ExamPaperRow.id.in_(paper_ids)))}
        if paper_ids
        else {}
    )
    offerings = {o.course_offering_id for o in papers.values()}
    course_codes = (
        {
            o.course_offering_id: o.course_code
            for o in db.scalars(repo.q(db, OfferingRef).where(OfferingRef.course_offering_id.in_(offerings)))
        }
        if offerings
        else {}
    )
    out = []
    for r in rows:
        session = sessions.get(r.exam_session_id) if r.exam_session_id else None
        paper = papers.get(r.exam_paper_id) if r.exam_paper_id else None
        out.append(
            {
                "id": r.id,
                "organisation_id": r.organisation_id,
                "exam_cycle_id": r.exam_cycle_id,
                "staff_id": r.staff_id,
                "duty_type": r.duty_type,
                "exam_session_id": r.exam_session_id,
                "exam_paper_id": r.exam_paper_id,
                "status": r.status,
                "cancel_reason": r.cancel_reason,
                "starts_at": iso(session.starts_at) if session else None,
                "ends_at": iso(session.ends_at) if session else None,
                "venue_label": session.venue_label if session else None,
                "course_code": course_codes.get(paper.course_offering_id) if paper else None,
            }
        )
    return out


def _duty_or_404(db: Session, exam_duty_id: str) -> ExamDutyRow:
    row = repo.duty(db, exam_duty_id)
    if row is None:
        raise not_found("exam_duty_not_found", "exam duty not found")
    return row


def _duty_domain(row: ExamDutyRow) -> ses.Duty:
    return ses.Duty(
        id=row.id,
        exam_cycle_id=row.exam_cycle_id,
        staff_id=row.staff_id,
        duty_type=row.duty_type,
        exam_session_id=row.exam_session_id,
        exam_paper_id=row.exam_paper_id,
        status=row.status,
        cancel_reason=row.cancel_reason,
    )


# ---------------------------------------------------------------- reads


def list_exam_duties(
    db: Session,
    actor: Actor,
    exam_cycle_id: str | None,
    staff_id: str | None,
    duty_type: str | None,
    exam_session_id: str | None,
    exam_paper_id: str | None,
    status: str | None,
    limit: int,
    offset: int,
) -> dict:
    """The organisation's duties for a holder of `duty:read-all`; nothing for `duty:read-department` alone (see the
    module docstring). The filters are checked either way, so a bad one is a 400 for every caller."""
    cycle = base._optional_id(exam_cycle_id, "exam_cycle_id")
    staff = base._optional_id(staff_id, "staff_id")
    kind = base._optional_choice(duty_type, "duty_type", ses.DUTY_TYPES)
    session = base._optional_id(exam_session_id, "exam_session_id")
    paper = base._optional_id(exam_paper_id, "exam_paper_id")
    state = base._optional_choice(status, "status", ses.DUTY_STATUSES)
    if not actor.can(DUTY_READ_ALL):
        return {"items": [], "total": 0}
    query = repo.q(db, ExamDutyRow)
    for column, value in (
        (ExamDutyRow.exam_cycle_id, cycle),
        (ExamDutyRow.staff_id, staff),
        (ExamDutyRow.duty_type, kind),
        (ExamDutyRow.exam_session_id, session),
        (ExamDutyRow.exam_paper_id, paper),
        (ExamDutyRow.status, state),
    ):
        if value is not None:
            query = query.where(column == value)
    rows, total = repo.page(db, query, [ExamDutyRow.created_at.desc(), ExamDutyRow.id], limit, offset)
    return {"items": _duty_bodies(db, rows), "total": total}


def _include_past(value: str | None) -> bool:
    if value is None:
        return False
    if value in ("true", "false"):
        return value == "true"
    raise invalid("invalid_boolean", "include_past must be true or false", "include_past")


def list_my_duties(db: Session, actor: Actor, include_past: str | None) -> dict:
    """The caller's `assigned` duties. By default only upcoming ones: an invigilation duty whose session is scheduled and
    has not ended, and every duty tied to a paper (evaluation and moderation have no date). With `include_past=true`
    every assigned duty, including those of past and cancelled sessions. Ordered by session start (then end, then the
    order assigned); the undated ones come after, in the order they were assigned."""
    past = _include_past(include_past)
    rows = repo.duties_of_staff(db, actor.user_id, ses.ASSIGNED)
    session_ids = {r.exam_session_id for r in rows if r.exam_session_id}
    sessions = (
        {s.id: s for s in db.scalars(repo.q(db, ExamSessionRow).where(ExamSessionRow.id.in_(session_ids)))}
        if session_ids
        else {}
    )
    now = base.clock()

    def upcoming(r: ExamDutyRow) -> bool:
        if not r.exam_session_id:
            return True
        s = sessions[r.exam_session_id]
        return s.status == ses.SCHEDULED and as_utc(s.ends_at) >= now

    kept = [r for r in rows if past or upcoming(r)]

    def order(r: ExamDutyRow):
        """A total order, so equal start times never leave the result to chance: dated duties by session start, then
        end, then the order they were assigned, then id; undated duties after them by the order they were assigned,
        then id. (Two of one staff member's duties can share a start only through a cancelled session, in
        `include_past`.)"""
        if r.exam_session_id:
            session = sessions[r.exam_session_id]
            return (0, as_utc(session.starts_at), as_utc(session.ends_at), as_utc(r.created_at), r.id)
        return (1, as_utc(r.created_at), r.id)

    return {"items": _duty_bodies(db, sorted(kept, key=order))}


# ---------------------------------------------------------------- writes


def _target_conflict(db: Session, staff_id: str, duty_type: str, session_id: str | None, paper_id: str | None) -> None:
    existing = repo.live_duplicate_duty(db, staff_id, duty_type, session_id, paper_id)
    if existing is not None:
        raise ExaminationsError(
            409,
            "duty_exists",
            "the staff member already holds this duty",
            exam_duty_id=existing.id,
            status=existing.status,
        )


@base.transactional
def assign_exam_duty(db: Session, actor: Actor, body: object) -> dict:
    """FR-9. Order of refusals: the request itself (400), a session or paper that does not exist for the caller (422),
    then the cycle (409), the session (409), a duplicate (409) and an overlap (409). Publishes
    examinations.duty.assigned."""
    data = base._object(body, "body", ASSIGN_FIELDS)
    sch._require_fields(data, ("staff_id", "duty_type"))
    staff_id = base._domain(require_id, data["staff_id"], "staff_id")
    duty_type = base._domain(require_choice, data["duty_type"], "duty_type", ses.DUTY_TYPES)
    session_id = (
        base._domain(require_id, data["exam_session_id"], "exam_session_id") if "exam_session_id" in data else None
    )
    paper_id = base._domain(require_id, data["exam_paper_id"], "exam_paper_id") if "exam_paper_id" in data else None
    # exactly one target, of the kind the type needs: the domain's rule, checked before anything is read
    base._domain(
        ses.Duty,
        id=new_id(),
        exam_cycle_id=_PLACEHOLDER,
        staff_id=staff_id,
        duty_type=duty_type,
        exam_session_id=session_id,
        exam_paper_id=paper_id,
    )
    session_row = paper_row = None
    if session_id is not None:
        session_row = repo.get(db, ExamSessionRow, session_id)
        if session_row is None:
            raise ExaminationsError(
                422, "unknown_session", "exam_session_id names no exam session", field="exam_session_id"
            )
        cycle_id = session_row.exam_cycle_id
    else:
        paper_row = repo.get(db, ExamPaperRow, paper_id)
        if paper_row is None:
            raise ExaminationsError(422, "unknown_paper", "exam_paper_id names no exam paper", field="exam_paper_id")
        cycle_id = paper_row.exam_cycle_id
    cycle_row = repo.cycle(db, cycle_id)
    if cycle_row.status not in ASSIGNABLE_CYCLE_STATUSES:
        raise ExaminationsError(
            409,
            "cycle_not_open_for_duties",
            f"duties can be assigned while the cycle is draft, scheduled, in progress or in evaluation, this one is "
            f"{cycle_row.status}",
            status=cycle_row.status,
        )
    session = None
    if session_row is not None:
        session = sch._session_domain(session_row)
        base._domain(ses.ensure_open, session)  # only a scheduled session takes duties
    _target_conflict(db, staff_id, duty_type, session_id, paper_id)
    if session is not None:
        others = [sch._session_domain(s) for s in repo.assigned_invigilation_sessions(db, staff_id)]
        base._domain(ses.ensure_no_invigilation_clash, session, others)
    row = ExamDutyRow(
        id=new_id(),
        organisation_id=actor.organisation_id,
        exam_cycle_id=cycle_id,
        staff_id=staff_id,
        duty_type=duty_type,
        exam_session_id=session_id,
        exam_paper_id=paper_id,
        status=ses.ASSIGNED,
    )
    db.add(row)
    base._audit(
        db,
        actor,
        "exam_duty.assigned",
        "exam_duty",
        row,
        after={
            "exam_cycle_id": cycle_id,
            "staff_id": staff_id,
            "duty_type": duty_type,
            "exam_session_id": session_id,
            "exam_paper_id": paper_id,
        },
    )
    base._publish(
        db,
        actor,
        "duty.assigned",
        {
            "exam_duty_id": row.id,
            "exam_cycle_id": cycle_id,
            "staff_id": staff_id,
            "duty_type": duty_type,
            "exam_session_id": session_id,
            "exam_paper_id": paper_id,
            "starts_at": iso(session_row.starts_at) if session_row is not None else None,
        },
    )
    db.commit()
    return _duty_bodies(db, [row])[0]


@base.transactional
def cancel_exam_duty(db: Session, actor: Actor, exam_duty_id: str, body: object) -> dict:
    """FR-9: cancels an assigned duty, with a reason, in any cycle status. A foreign or unknown id is a 404. Publishes
    examinations.duty.cancelled."""
    row = _duty_or_404(db, exam_duty_id)
    data = base._object(body, "body", ("reason",))
    sch._require_fields(data, ("reason",))
    cancelled = base._domain(ses.plan_duty_cancel, _duty_domain(row), data["reason"])
    row.status, row.cancel_reason = cancelled.status, cancelled.cancel_reason
    base._audit(
        db,
        actor,
        "exam_duty.cancelled",
        "exam_duty",
        row,
        before={"status": ses.ASSIGNED},
        after={"status": ses.DUTY_CANCELLED},
        reason=cancelled.cancel_reason,
    )
    base._publish(
        db,
        actor,
        "duty.cancelled",
        {
            "exam_duty_id": row.id,
            "exam_cycle_id": row.exam_cycle_id,
            "staff_id": row.staff_id,
            "duty_type": row.duty_type,
            "reason": cancelled.cancel_reason,
            "cancelled_at": iso(base.clock()),
        },
    )
    db.commit()
    return _duty_bodies(db, [row])[0]
