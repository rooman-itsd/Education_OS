"""Use cases for marks (docs/prd.md FR-10 to FR-12, contracts/openapi.yaml): listMarks, enterMarks, submitMarks,
moderateMarks and lockMarks. They share the conventions of application/service.py (one transaction wrapper, one audit
writer, one clock): domain rules first, an audit entry per state change, one commit, everything rolled back on any
failure. The contract declares no marks event, so none is published.

Decisions of the marks slice (docs/reviewer-decisions.md section 15):
- The candidates of a paper are the rows of `examinations_candidate` with `eligibility_status = 'eligible'`. Nothing
  creates candidates yet (registration and eligibility are a later slice), so until then a paper has none: listMarks
  answers an empty list and submitting or locking an empty paper is allowed (every eligible candidate has marks: none).
- Scope. `marks:*-all` keys act on any paper of the organisation. `marks:read-assigned` reads, and
  `marks:enter-assigned` enters and submits, papers the caller holds a live (assigned or completed) duty for: evaluation
  for entering and submitting, evaluation or moderation for reading. `marks:moderate-assigned` moderates papers with a
  live moderation duty. The `*-department` keys grant nothing alone, because the caller's department is unknown (Q13);
  a caller without a scope is refused (403), not shown an empty list.
- Pipeline. enterMarks needs the paper in `marks_entry`, submitMarks moves it to `moderation` and needs every eligible
  candidate to have marks or be absent, moderateMarks needs `moderation` and lockMarks needs `moderation` and
  complete marks; each wrong status is a 409. A paper reaches `marks_entry` through nothing in this module yet: the PRD's
  rule that a finished session moves its papers there is not built, and no operation of the contract does it.
- Moderation delta replaces any earlier one; locking sets every entry of the paper to `locked`."""

from __future__ import annotations

from decimal import Decimal

from eos_core.db import new_id
from sqlalchemy.orm import Session

from ..domain import marks as mk
from ..domain import papers as pap
from ..infrastructure import repository as repo
from ..infrastructure.models import CandidateRow, ExamDutyRow, ExamPaperRow, MarkEntryRow, iso
from . import schedule as sch
from . import service as base
from .access import (
    MARKS_ENTER_ALL,
    MARKS_ENTER_ASSIGNED,
    MARKS_LOCK,
    MARKS_MODERATE_ASSIGNED,
    MARKS_READ_ALL,
    MARKS_READ_ASSIGNED,
    Actor,
    require,
)
from .errors import ExaminationsError, forbidden

ELIGIBLE = "eligible"  # contract EligibilityStatus
EVALUATION, MODERATION_DUTY = "evaluation", "moderation"  # contract DutyType


# ---------------------------------------------------------------- scope and lookups


def _holds_duty(db: Session, actor: Actor, exam_paper_id: str, duty_types: tuple[str, ...]) -> bool:
    query = repo.q(db, ExamDutyRow).where(
        ExamDutyRow.exam_paper_id == exam_paper_id,
        ExamDutyRow.staff_id == actor.user_id,
        ExamDutyRow.duty_type.in_(duty_types),
        ExamDutyRow.status.in_(repo.LIVE_DUTY_STATUSES),
    )
    return db.scalars(query).first() is not None


def _authorise(
    db: Session, actor: Actor, exam_paper_id: str, *, wide: str | None, narrow: str, duty_types: tuple[str, ...]
) -> None:
    """403 unless the caller holds the organisation-wide key, or the narrow key and a live duty of one of `duty_types`
    on this paper. A department key alone is no grant (the caller's department is unknown, Q13)."""
    require(actor, narrow)
    if wide is not None and actor.can(wide):
        return
    if not _holds_duty(db, actor, exam_paper_id, duty_types):
        raise forbidden(f"{narrow} covers only the papers you hold a {' or '.join(duty_types)} duty for")


def _eligible(db: Session, exam_paper_id: str) -> list[CandidateRow]:
    rows = db.scalars(
        repo.q(db, CandidateRow).where(
            CandidateRow.exam_paper_id == exam_paper_id, CandidateRow.eligibility_status == ELIGIBLE
        )
    )
    return sorted(rows, key=lambda r: (r.student_id, r.id))


def _candidates_by_id(db: Session, exam_paper_id: str) -> dict[str, CandidateRow]:
    return {c.id: c for c in db.scalars(repo.q(db, CandidateRow).where(CandidateRow.exam_paper_id == exam_paper_id))}


def _entries_of(db: Session, candidate_ids: list[str]) -> dict[str, MarkEntryRow]:
    if not candidate_ids:
        return {}
    rows = db.scalars(repo.q(db, MarkEntryRow).where(MarkEntryRow.candidate_id.in_(candidate_ids)))
    return {e.candidate_id: e for e in rows}


def _body(candidate: CandidateRow, entry: MarkEntryRow | None) -> dict:
    """components.schemas.MarkEntry: a candidate not yet marked has no id, marks or status."""
    if entry is None:
        return {
            "id": None,
            "candidate_id": candidate.id,
            "student_id": candidate.student_id,
            "marks_obtained": None,
            "absent": False,
            "moderation_delta": None,
            "moderation_reason": None,
            "final_marks": None,
            "entered_by": None,
            "entered_at": None,
            "moderated_by": None,
            "status": None,
        }
    return {
        "id": entry.id,
        "candidate_id": candidate.id,
        "student_id": candidate.student_id,
        "marks_obtained": base._num(entry.marks_obtained),
        "absent": entry.absent,
        "moderation_delta": base._num(entry.moderation_delta),
        "moderation_reason": entry.moderation_reason,
        "final_marks": base._num(mk.final_marks(entry.marks_obtained, entry.moderation_delta)),
        "entered_by": entry.entered_by,
        "entered_at": iso(entry.entered_at),
        "moderated_by": entry.moderated_by,
        "status": entry.status,
    }


def _bodies(db: Session, candidates: list[CandidateRow]) -> list[dict]:
    entries = _entries_of(db, [c.id for c in candidates])
    return [_body(c, entries.get(c.id)) for c in candidates]


def _require_status(row: ExamPaperRow, wanted: str) -> None:
    if row.status != wanted:
        raise ExaminationsError(
            409, f"paper_not_in_{wanted}", f"the paper is {row.status}, this needs {wanted}", status=row.status
        )


def _require_complete(candidates: list[CandidateRow], entries: dict[str, MarkEntryRow]) -> None:
    """FR-11 and FR-12: every eligible candidate has marks or is absent."""
    unmarked = [c.id for c in candidates if c.id not in entries]
    if unmarked:
        raise ExaminationsError(
            409,
            "marks_incomplete",
            f"{len(unmarked)} eligible candidate(s) have neither marks nor an absence",
            unmarked=len(unmarked),
        )


# ---------------------------------------------------------------- reads


def list_marks(db: Session, actor: Actor, exam_paper_id: str) -> dict:
    """One row per eligible candidate; an unmarked one has no marks yet. 404 for an unknown paper, 403 without scope."""
    row = sch._paper_or_404(db, exam_paper_id)
    _authorise(
        db,
        actor,
        exam_paper_id,
        wide=MARKS_READ_ALL,
        narrow=MARKS_READ_ASSIGNED,
        duty_types=(EVALUATION, MODERATION_DUTY),
    )
    items = _bodies(db, _eligible(db, exam_paper_id))
    return {
        "exam_paper_id": row.id,
        "max_marks": base._num(row.max_marks),
        "paper_status": row.status,
        "items": items,
        "total": len(items),
    }


# ---------------------------------------------------------------- state changes


@base.transactional
def enter_marks(db: Session, actor: Actor, exam_paper_id: str, body: object) -> dict:
    """FR-10: creates or overwrites marks of eligible candidates of a paper in `marks_entry`, all or none. Candidates of
    another paper or not eligible are refused (422), as are marks out of range (422)."""
    row = sch._paper_or_404(db, exam_paper_id)
    _authorise(db, actor, exam_paper_id, wide=MARKS_ENTER_ALL, narrow=MARKS_ENTER_ASSIGNED, duty_types=(EVALUATION,))
    data = base._object(body, "body", ("entries",))
    sch._require_fields(data, ("entries",))
    entries = base._domain(mk.parse_entries, data["entries"], row.max_marks)
    _require_status(row, pap.MARKS_ENTRY)
    candidates = _candidates_by_id(db, exam_paper_id)
    for entry in entries:
        candidate = candidates.get(entry.candidate_id)
        if candidate is None:
            raise ExaminationsError(
                422,
                "candidate_not_on_paper",
                "the candidate is not a candidate of this paper",
                candidate_id=entry.candidate_id,
            )
        if candidate.eligibility_status != ELIGIBLE:
            raise ExaminationsError(
                422,
                "candidate_not_eligible",
                "only eligible candidates can have marks",
                candidate_id=entry.candidate_id,
            )
    existing = _entries_of(db, [e.candidate_id for e in entries])
    now = base.clock()
    for entry in entries:
        current = existing.get(entry.candidate_id)
        after = {"marks_obtained": entry.marks_obtained, "absent": entry.absent}
        if current is None:
            current = MarkEntryRow(
                id=new_id(),
                organisation_id=actor.organisation_id,
                candidate_id=entry.candidate_id,
                marks_obtained=entry.marks_obtained,
                absent=entry.absent,
                entered_by=actor.user_id,
                entered_at=now,
                status=mk.ENTERED,
            )
            db.add(current)
            base._audit(db, actor, "mark_entry.entered", "mark_entry", current, after=after)
            continue
        before = {"marks_obtained": current.marks_obtained, "absent": current.absent}
        if before == after:
            continue  # nothing changes, nothing is written
        current.marks_obtained, current.absent = entry.marks_obtained, entry.absent
        current.entered_by, current.entered_at = actor.user_id, now
        base._audit(db, actor, "mark_entry.entered", "mark_entry", current, before=before, after=after)
    db.commit()
    return {"exam_paper_id": row.id, "items": _bodies(db, _eligible(db, exam_paper_id))}


@base.transactional
def submit_marks(db: Session, actor: Actor, exam_paper_id: str) -> dict:
    """FR-11: moves a paper in `marks_entry` to `moderation` once every eligible candidate has marks or is absent."""
    row = sch._paper_or_404(db, exam_paper_id)
    _authorise(db, actor, exam_paper_id, wide=MARKS_ENTER_ALL, narrow=MARKS_ENTER_ASSIGNED, duty_types=(EVALUATION,))
    _require_status(row, pap.MARKS_ENTRY)
    candidates = _eligible(db, exam_paper_id)
    _require_complete(candidates, _entries_of(db, [c.id for c in candidates]))
    moved = base._domain(pap.plan_status_change, sch._paper_domain(row), pap.MODERATION)
    row.status = moved.status
    base._audit(
        db,
        actor,
        "exam_paper.marks_submitted",
        "exam_paper",
        row,
        before={"status": pap.MARKS_ENTRY},
        after={"status": pap.MODERATION},
    )
    db.commit()
    return sch._paper_bodies(db, [row])[0]


@base.transactional
def moderate_marks(db: Session, actor: Actor, exam_paper_id: str, body: object) -> dict:
    """FR-11: adjusts the marks of a paper in `moderation`, uniformly or per candidate, with a reason. The original marks
    are kept, the moderated ones stay within 0 and `max_marks` (422), and all of it is applied or none."""
    row = sch._paper_or_404(db, exam_paper_id)
    _authorise(db, actor, exam_paper_id, wide=None, narrow=MARKS_MODERATE_ASSIGNED, duty_types=(MODERATION_DUTY,))
    data = base._object(body, "body", ("reason", "uniform_delta", "adjustments"))
    sch._require_fields(data, ("reason",))
    moderation = base._domain(mk.parse_moderation, data)
    _require_status(row, pap.MODERATION)
    candidates = _candidates_by_id(db, exam_paper_id)
    eligible = {c.id for c in _eligible(db, exam_paper_id)}
    entries = _entries_of(db, list(eligible))
    deltas: dict[str, Decimal] = {}
    if moderation.uniform_delta is not None:
        for candidate_id in eligible:
            entry = entries.get(candidate_id)
            if entry is not None and not entry.absent:
                deltas[candidate_id] = moderation.uniform_delta
    else:
        for candidate_id, delta in moderation.adjustments.items():
            if candidate_id not in candidates or candidate_id not in eligible:
                raise ExaminationsError(
                    422,
                    "candidate_not_eligible",
                    "only eligible candidates of this paper can be moderated",
                    candidate_id=candidate_id,
                )
            entry = entries.get(candidate_id)
            if entry is None or entry.absent:
                raise ExaminationsError(
                    422, "no_marks_to_moderate", "the candidate has no marks to adjust", candidate_id=candidate_id
                )
            deltas[candidate_id] = delta
    for candidate_id, delta in deltas.items():
        base._domain(mk.moderated, entries[candidate_id].marks_obtained, delta, row.max_marks, candidate_id)
    for candidate_id, delta in deltas.items():
        entry = entries[candidate_id]
        before = {
            "moderation_delta": entry.moderation_delta,
            "moderation_reason": entry.moderation_reason,
            "status": entry.status,
        }
        entry.moderation_delta, entry.moderation_reason = delta, moderation.reason
        entry.moderated_by, entry.status = actor.user_id, mk.MODERATED
        base._audit(
            db,
            actor,
            "mark_entry.moderated",
            "mark_entry",
            entry,
            before=before,
            after={"moderation_delta": delta, "status": mk.MODERATED},
            reason=moderation.reason,
        )
    db.commit()
    return {"exam_paper_id": row.id, "items": _bodies(db, _eligible(db, exam_paper_id))}


@base.transactional
def lock_marks(db: Session, actor: Actor, exam_paper_id: str) -> dict:
    """FR-12: locks the marks of a paper in `moderation`, once every eligible candidate has marks or is absent. Locked
    marks change only through result revision."""
    row = sch._paper_or_404(db, exam_paper_id)
    require(actor, MARKS_LOCK)
    _require_status(row, pap.MODERATION)
    candidates = _eligible(db, exam_paper_id)
    entries = _entries_of(db, [c.id for c in candidates])
    _require_complete(candidates, entries)
    moved = base._domain(pap.plan_status_change, sch._paper_domain(row), pap.LOCKED)
    row.status = moved.status
    for entry in entries.values():
        entry.status = mk.LOCKED
    base._audit(
        db,
        actor,
        "exam_paper.marks_locked",
        "exam_paper",
        row,
        before={"status": pap.MODERATION},
        after={"status": pap.LOCKED, "entries_locked": len(entries)},
    )
    db.commit()
    return sch._paper_bodies(db, [row])[0]


__all__ = ["enter_marks", "list_marks", "lock_marks", "moderate_marks", "submit_marks"]
