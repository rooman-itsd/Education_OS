"""Use cases for candidates (docs/prd.md FR-7, contracts/openapi.yaml): determineEligibility, listCandidates and
overrideCandidateEligibility. They share the conventions of application/service.py (one transaction wrapper, one audit
writer, one clock): domain rules first, an audit entry per change, the contract's event, one commit.

Decisions (issue #325):
- D2, registration types: candidates are made from the `registration_ref` read model, which the registration consumers keep
  from enrolment-registration's events. `regular`, `supplementary` and `backlog` registrations make candidates in the
  cycles the rule in domain/eligibility.py names. A withdrawn registration makes no candidate and turns an existing one
  ineligible (`not_registered`); a confirmed one is a registration that counts (not an eligibility: the other inputs decide).
- D7, the minimum attendance is the exam cycle's `min_attendance_percent`.
- Inputs without a source stay unavailable and leave the candidate `pending`: student status has no source (Q2 is open
  with Praveen), attendance has none wired (timetable-attendance's `POST /reports/attendance-eligibility` is not called from
  here yet) and dues have none (fees-accounts' response shape is not confirmed by examinations). So a run leaves candidates
  pending, with `pending_inputs` saying which inputs are missing, until the sources are connected or a controller overrides.
- A manual override is kept by later runs. A candidate that has marks is not changed by a run, and cannot be made
  ineligible by an override, so marks never belong to someone who may not sit the paper.
- One `candidate.eligibility-determined` event per student whose candidacy a run created or changed, naming the papers that
  changed (an unchanged run publishes nothing); an override publishes one for its student."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from ..domain import eligibility as el
from ..domain.values import require_choice, require_id, require_text
from ..infrastructure import repository as repo
from ..infrastructure.models import (
    CandidateRow,
    ExamCycleRow,
    ExamPaperRow,
    MarkEntryRow,
    RegistrationRef,
    iso,
)
from . import schedule as sch
from . import service as base
from .access import CANDIDATE_READ_ALL, Actor
from .errors import ExaminationsError, forbidden, invalid, not_found

CONFIRMED = "confirmed"
REASON_MAX = 500
REASON_CODES = (*el.REASON_CODE.values(), "exam_rule", "manual_override")  # contract EligibilityReasonCode


def _cycle_or_404(db: Session, exam_cycle_id: str, *, lock: bool = False) -> ExamCycleRow:
    row = (repo.get_locked if lock else repo.get)(db, ExamCycleRow, exam_cycle_id)
    if row is None:
        raise not_found("exam_cycle_not_found", "exam cycle not found")
    return row


def _require_open(cycle: ExamCycleRow) -> None:
    if cycle.status in repo.PUBLISHED_CYCLE_STATUSES:
        raise ExaminationsError(
            409,
            "cycle_results_published",
            f"the cycle is {cycle.status}, so candidates no longer change",
            status=cycle.status,
        )


def _outcomes(cycle: ExamCycleRow, *, registered: bool) -> dict[str, str]:
    """The result of each eligibility input for a candidate of this cycle: registration from the read model, the rest from
    what has a source (none yet, see the module docstring)."""
    return {
        el.REGISTRATION: el.PASSED if registered else el.FAILED,
        el.STUDENT_STATUS: el.UNAVAILABLE,
        el.ATTENDANCE: el.attendance_input(None, cycle.min_attendance_percent),
        el.DUES: el.UNAVAILABLE if cycle.check_dues else el.NOT_REQUIRED,
    }


def candidate_body(row: CandidateRow, cycle: ExamCycleRow | None) -> dict:
    """components.schemas.Candidate. `pending_inputs` is worked out from the cycle: what no source answers yet."""
    overridden = row.overridden_by is not None
    pending = [] if overridden or cycle is None else list(el.decide(_outcomes(cycle, registered=True)).pending_inputs)
    return {
        "id": row.id,
        "organisation_id": row.organisation_id,
        "exam_cycle_id": row.exam_cycle_id,
        "exam_paper_id": row.exam_paper_id,
        "course_offering_id": row.course_offering_id,
        "student_id": row.student_id,
        "eligibility_status": row.eligibility_status,
        "eligibility_reasons": list(row.eligibility_reasons),
        "pending_inputs": pending,
        "overridden_by": row.overridden_by,
        "determined_at": iso(row.determined_at),
    }


def _with_marks(db: Session, candidate_ids: list[str]) -> set[str]:
    if not candidate_ids:
        return set()
    return set(
        db.scalars(
            repo.q(db, MarkEntryRow)
            .with_only_columns(MarkEntryRow.candidate_id)
            .where(MarkEntryRow.candidate_id.in_(candidate_ids))
        )
    )


def _publish_determined(db: Session, actor: Actor, cycle_id: str, by_student: dict[str, list[dict]]) -> None:
    now = iso(base.clock())
    for student_id in sorted(by_student):
        base._publish(
            db,
            actor,
            "candidate.eligibility-determined",
            {
                "exam_cycle_id": cycle_id,
                "student_id": student_id,
                "papers": by_student[student_id],
                "determined_at": now,
            },
        )


def _paper_entry(row: CandidateRow) -> dict:
    return {
        "exam_paper_id": row.exam_paper_id,
        "course_offering_id": row.course_offering_id,
        "eligibility_status": row.eligibility_status,
        "reasons": [r["code"] for r in row.eligibility_reasons],
    }


@base.transactional
def determine_eligibility(db: Session, actor: Actor, exam_cycle_id: str, body: object) -> dict:
    """FR-7: creates or refreshes the candidates of the cycle's papers (or of the listed papers) from the registrations, and
    applies the eligibility inputs. Overridden candidates and candidates with marks are kept as they are."""
    data = base._object({} if body is None else body, "body", ("exam_paper_ids",))
    cycle = _cycle_or_404(db, exam_cycle_id, lock=True)  # one run at a time per cycle
    _require_open(cycle)
    papers = list(db.scalars(repo.q(db, ExamPaperRow).where(ExamPaperRow.exam_cycle_id == cycle.id)))
    if data.get("exam_paper_ids") is not None:
        wanted = data["exam_paper_ids"]
        if not isinstance(wanted, list):
            raise invalid("invalid_body", "exam_paper_ids must be a list", "exam_paper_ids")
        ids = [base._domain(require_id, w, "exam_paper_ids") for w in wanted]
        known = {p.id: p for p in papers}
        missing = [i for i in ids if i not in known]
        if missing:
            raise not_found("exam_paper_not_found", "a listed paper is not a paper of this cycle")
        papers = [known[i] for i in dict.fromkeys(ids)]
    offerings = {p.course_offering_id for p in papers}
    registrations: dict[str, dict[str, list[RegistrationRef]]] = defaultdict(lambda: defaultdict(list))
    if offerings:
        for r in db.scalars(
            repo.q(db, RegistrationRef).where(
                RegistrationRef.course_offering_id.in_(offerings),
                RegistrationRef.academic_period_id == cycle.academic_period_id,
                RegistrationRef.registration_type.is_not(None),
            )
        ):
            if el.registration_makes_candidate(cycle.cycle_type, r.registration_type):
                registrations[r.course_offering_id][r.person_id].append(r)
    existing = {
        (c.exam_paper_id, c.student_id): c
        for c in db.scalars(
            repo.q(db, CandidateRow).where(CandidateRow.exam_paper_id.in_([p.id for p in papers] or [""]))
        )
    }
    marked = _with_marks(db, [c.id for c in existing.values()])
    now = base.clock()
    changed: dict[str, list[dict]] = defaultdict(list)
    for paper in sorted(papers, key=lambda p: p.id):
        for person, regs in sorted(registrations.get(paper.course_offering_id, {}).items()):
            active = any(r.status == CONFIRMED for r in regs)
            row = existing.get((paper.id, person))
            if row is None and not active:
                continue  # withdrawn before ever being a candidate
            if row is not None and (row.overridden_by is not None or row.id in marked):
                continue  # an override stands; marks are never taken from or given to someone by a run
            decision = el.decide(_outcomes(cycle, registered=active))
            reasons = list(decision.reasons)
            if row is None:
                row = CandidateRow(
                    organisation_id=actor.organisation_id,
                    exam_cycle_id=cycle.id,
                    exam_paper_id=paper.id,
                    course_offering_id=paper.course_offering_id,
                    student_id=person,
                    eligibility_status=decision.status,
                    eligibility_reasons=reasons,
                    determined_at=now,
                )
                db.add(row)
                existing[(paper.id, person)] = row
                base._audit(
                    db, actor, "candidate.determined", "candidate", row, after={"eligibility_status": decision.status}
                )
            elif (row.eligibility_status, list(row.eligibility_reasons)) != (decision.status, reasons):
                before = {"eligibility_status": row.eligibility_status}
                row.eligibility_status, row.eligibility_reasons, row.determined_at = decision.status, reasons, now
                base._audit(
                    db,
                    actor,
                    "candidate.determined",
                    "candidate",
                    row,
                    before=before,
                    after={"eligibility_status": decision.status},
                )
            else:
                continue
            changed[person].append(_paper_entry(row))
    _publish_determined(db, actor, cycle.id, changed)
    db.commit()
    scoped = [c for (paper_id, _), c in existing.items() if paper_id in {p.id for p in papers}]
    counts = {s: sum(1 for c in scoped if c.eligibility_status == s) for s in el.ELIGIBILITY_STATUSES}
    return {
        "exam_cycle_id": cycle.id,
        "candidates": len(scoped),
        "eligible": counts[el.ELIGIBLE],
        "ineligible": counts[el.INELIGIBLE],
        "pending": counts[el.PENDING],
    }


def list_candidates(
    db: Session,
    actor: Actor,
    exam_cycle_id: str | None,
    exam_paper_id: str | None,
    course_offering_id: str | None,
    student_id: str | None,
    eligibility_status: str | None,
    reason_code: str | None,
    limit: int,
    offset: int,
) -> dict:
    """The candidates, for a caller with the organisation-wide key. `candidate:read-department` alone grants nothing: the
    caller's department is unknown (Q13), so it is refused (403) rather than shown an empty list."""
    if not actor.can(CANDIDATE_READ_ALL):
        raise forbidden(
            "examinations:candidate:read-department needs the caller's department, which is not known yet (Q13)"
        )
    query = repo.q(db, CandidateRow)
    for column, value, field in (
        (CandidateRow.exam_cycle_id, exam_cycle_id, "exam_cycle_id"),
        (CandidateRow.exam_paper_id, exam_paper_id, "exam_paper_id"),
        (CandidateRow.course_offering_id, course_offering_id, "course_offering_id"),
        (CandidateRow.student_id, student_id, "student_id"),
    ):
        if (checked := base._optional_id(value, field)) is not None:
            query = query.where(column == checked)
    if (state := base._optional_choice(eligibility_status, "eligibility_status", el.ELIGIBILITY_STATUSES)) is not None:
        query = query.where(CandidateRow.eligibility_status == state)
    code = base._optional_choice(reason_code, "reason_code", REASON_CODES)
    order = [CandidateRow.exam_paper_id, CandidateRow.student_id, CandidateRow.id]
    cycles: dict[str, ExamCycleRow | None] = {}

    def body(row: CandidateRow) -> dict:
        if row.exam_cycle_id not in cycles:
            cycles[row.exam_cycle_id] = repo.get(db, ExamCycleRow, row.exam_cycle_id)
        return candidate_body(row, cycles[row.exam_cycle_id])

    if code is None:
        rows, total = repo.page(db, query, order, limit, offset)
        return {"items": [body(r) for r in rows], "total": total}
    # The reasons are a JSON list, so a reason filter is applied to the rows the other filters leave, then paged.
    matching = [r for r in db.scalars(query.order_by(*order)) if any(x["code"] == code for x in r.eligibility_reasons)]
    return {"items": [body(r) for r in matching[offset : offset + limit]], "total": len(matching)}


@base.transactional
def override_candidate_eligibility(db: Session, actor: Actor, candidate_id: str, body: object) -> dict:
    """FR-7: the controller sets a candidate `eligible` or `ineligible` with a mandatory reason, recorded as a
    `manual_override` reason. Later runs keep it. A candidate who has marks cannot be made ineligible."""
    data = base._object(body, "body", ("eligibility_status", "reason"))
    sch._require_fields(data, ("eligibility_status", "reason"))
    status = base._domain(
        require_choice, data["eligibility_status"], "eligibility_status", (el.ELIGIBLE, el.INELIGIBLE)
    )
    reason = base._domain(require_text, data["reason"], "reason", max_length=REASON_MAX)
    row = repo.get_locked(db, CandidateRow, candidate_id)
    if row is None:
        raise not_found("candidate_not_found", "candidate not found")
    cycle = _cycle_or_404(db, row.exam_cycle_id)
    _require_open(cycle)
    if status != el.ELIGIBLE and row.id in _with_marks(db, [row.id]):
        raise ExaminationsError(
            409, "candidate_has_marks", "a candidate who has marks cannot be made ineligible", candidate_id=row.id
        )
    before = {"eligibility_status": row.eligibility_status, "overridden_by": row.overridden_by}
    row.eligibility_status = status
    row.eligibility_reasons = [{"code": "manual_override", "detail": reason}]
    row.overridden_by, row.override_reason, row.determined_at = actor.user_id, reason, base.clock()
    base._audit(
        db,
        actor,
        "candidate.overridden",
        "candidate",
        row,
        before=before,
        after={"eligibility_status": status, "overridden_by": actor.user_id},
        reason=reason,
    )
    _publish_determined(db, actor, row.exam_cycle_id, {row.student_id: [_paper_entry(row)]})
    db.commit()
    return candidate_body(row, cycle)
