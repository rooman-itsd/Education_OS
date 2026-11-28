"""Use cases for results (docs/prd.md FR-13 to FR-17, contracts/openapi.yaml): computeResults, approveResultsDepartment,
approveResults, publishResults, listResults, listMyResults and reviseResult. They share the conventions of
application/service.py (one transaction wrapper, one audit writer, one clock): domain rules first, an audit entry per state
change, the contract's events, one commit, everything rolled back on any failure.

Decisions (issue #325):
- D4, the state machine is owned by this module (Q10: no platform/workflow): `computed`, then department approval
  (`department_approved`, key `result:approve-department`), then organisation approval (`approved`, key
  `result:approve-all`), then publication (`published`, key `result:publish`). A revision makes a new published version.
- The caller's department is unknown (Q13, D14), so `result:approve-department` and `result:read-department` alone grant
  nothing and are refused (403), as for candidates and marks; the organisation-wide keys do the work. The department
  stage is recorded (who, when) all the same, so the second stage is a separate, auditable decision.
- Every state change is guarded by the locked cycle row and the status each result must be in, so a retried request
  repeats nothing: a result already past the stage is reported under `skipped`, never advanced twice and never
  published twice. A result in an earlier stage than the one asked for is a 409 when its offering was named.
- Computation, approval and publication need the cycle in `evaluation`; once its results are published the cycle is
  closed to them (409 `cycle_results_published`), and revision is the only change left (FR-17).
- Publication publishes one `result.published` event per student with the course results published now; when every
  offering of the cycle has its papers locked and its results published, the cycle moves to `results_published`.
- Students read their own results as `GET /me/results`; a student's id is the caller's user id, as for
  `GET /me/exam-schedule` (no account-to-person mapping exists in this module)."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy.orm import Session

from ..domain import marks as mk
from ..domain import papers as pap
from ..domain import results as rs
from ..domain.errors import DomainRuleError
from ..domain.grading import Band
from ..domain.values import require_id, require_text
from ..infrastructure import repository as repo
from ..infrastructure.models import (
    AssessmentComponentRow,
    AssessmentSchemeRow,
    CandidateRow,
    ExamCycleRow,
    ExamPaperRow,
    GradingBandRow,
    MarkEntryRow,
    OfferingRef,
    ResultRow,
    iso,
)
from . import candidates as cnd
from . import service as base
from .access import RESULT_APPROVE_ALL, RESULT_READ_ALL, Actor
from .errors import ExaminationsError, forbidden, not_found

REASON_MAX = 500
ELIGIBLE = "eligible"
EVALUATION = "evaluation"
RESULTS_PUBLISHED = "results_published"


# ---------------------------------------------------------------- lookups


def _cycle(db: Session, exam_cycle_id: str) -> ExamCycleRow:
    """The cycle, locked for the rest of the transaction: computing, approving and publishing read what each result's status
    is and then change it, so two of them must take turns."""
    return cnd._cycle_or_404(db, base._domain(require_id, exam_cycle_id, "exam_cycle_id"), lock=True)


def _require_evaluation(cycle: ExamCycleRow, *, retry_of_publish: bool = False) -> None:
    """409 unless the cycle is in evaluation. A retried publication of a cycle that the first request already moved to
    `results_published` is not a conflict: it finds nothing approved left and says so."""
    if retry_of_publish and cycle.status == RESULTS_PUBLISHED:
        return
    if cycle.status in repo.PUBLISHED_CYCLE_STATUSES:
        raise ExaminationsError(
            409,
            "cycle_results_published",
            f"the cycle is {cycle.status}; only a result revision changes its results now",
            status=cycle.status,
        )
    if cycle.status != EVALUATION:
        raise ExaminationsError(
            409,
            "cycle_not_in_evaluation",
            f"results are computed, approved and published while the cycle is in evaluation, not {cycle.status}",
            status=cycle.status,
        )


def _selection(body: object) -> list[str] | None:
    """CourseOfferingSelection: the offerings named, or None for all of them."""
    data = base._object({} if body is None else body, "body", ("course_offering_ids",))
    if "course_offering_ids" not in data:
        return None
    ids = data["course_offering_ids"]
    if not isinstance(ids, list):
        raise base.invalid("invalid_selection", "course_offering_ids must be a list", "course_offering_ids")
    return sorted({base._domain(require_id, v, "course_offering_ids") for v in ids})


def _papers_by_offering(db: Session, exam_cycle_id: str) -> dict[str, list[ExamPaperRow]]:
    grouped: dict[str, list[ExamPaperRow]] = defaultdict(list)
    for paper in db.scalars(repo.q(db, ExamPaperRow).where(ExamPaperRow.exam_cycle_id == exam_cycle_id)):
        grouped[paper.course_offering_id].append(paper)
    return grouped


def _current(db: Session, exam_cycle_id: str) -> dict[str, list[ResultRow]]:
    """The results that count (not superseded) of the cycle, by offering."""
    grouped: dict[str, list[ResultRow]] = defaultdict(list)
    query = repo.q(db, ResultRow).where(ResultRow.exam_cycle_id == exam_cycle_id, ResultRow.status != rs.SUPERSEDED)
    for row in db.scalars(query.order_by(ResultRow.student_id, ResultRow.id)):
        grouped[row.course_offering_id].append(row)
    return grouped


def _bands(db: Session, cycle: ExamCycleRow) -> list[Band]:
    rows = db.scalars(repo.q(db, GradingBandRow).where(GradingBandRow.grading_scheme_id == cycle.grading_scheme_id))
    return [Band(r.min_percent, r.max_percent, r.grade, r.grade_point, r.is_pass) for r in rows]


def _offering_refs(db: Session, offering_ids: set[str]) -> dict[str, OfferingRef]:
    if not offering_ids:
        return {}
    query = repo.q(db, OfferingRef).where(OfferingRef.course_offering_id.in_(offering_ids))
    return {r.course_offering_id: r for r in db.scalars(query)}


# ---------------------------------------------------------------- bodies


def result_body(row: ResultRow, ref: OfferingRef | None = None) -> dict:
    """components.schemas.Result. The course facts come from the offering read model when it has them."""
    body = {
        "id": row.id,
        "organisation_id": row.organisation_id,
        "exam_cycle_id": row.exam_cycle_id,
        "student_id": row.student_id,
        "course_offering_id": row.course_offering_id,
        "version": row.version,
        "components": row.components,
        "weighted_percent": base._num(row.weighted_percent),
        "grade": row.grade,
        "grade_point": base._num(row.grade_point),
        "passed": row.passed,
        "status": row.status,
        "approved_by": row.approved_by,
        "published_at": iso(row.published_at),
        "revision_reason": row.revision_reason,
    }
    if ref is not None:
        for field, value in (("course_code", ref.course_code), ("course_title", ref.course_title)):
            if value is not None:
                body[field] = value
        body["credits"] = base._num(ref.credits)
    return body


def _snapshot(row: ResultRow) -> dict:
    return {
        "weighted_percent": base._num(row.weighted_percent),
        "grade": row.grade,
        "grade_point": base._num(row.grade_point),
        "passed": row.passed,
    }


def _summary(exam_cycle_id: str, offerings: int, results: int, skipped: list[dict]) -> dict:
    body = {"exam_cycle_id": exam_cycle_id, "course_offerings": offerings, "results": results}
    if skipped:
        body["skipped"] = skipped
    return body


# ---------------------------------------------------------------- compute


def _scheme_components(
    db: Session, papers: list[ExamPaperRow]
) -> tuple[AssessmentSchemeRow, list[AssessmentComponentRow]]:
    components = list(
        db.scalars(
            repo.q(db, AssessmentComponentRow).where(
                AssessmentComponentRow.id.in_([p.assessment_component_id for p in papers])
            )
        )
    )
    scheme = repo.get(db, AssessmentSchemeRow, components[0].assessment_scheme_id)
    every = list(
        db.scalars(repo.q(db, AssessmentComponentRow).where(AssessmentComponentRow.assessment_scheme_id == scheme.id))
    )
    return scheme, every


def _compute_offering(
    db: Session,
    actor: Actor,
    cycle: ExamCycleRow,
    offering_id: str,
    papers: list[ExamPaperRow],
    existing: list[ResultRow],
    bands: list[Band],
) -> tuple[int, str | None]:
    """The results of one offering, or the reason it is skipped. Nothing is written for a skipped offering."""
    if any(p.status != pap.LOCKED for p in papers):
        return 0, "papers_not_locked"
    if any(r.status != rs.COMPUTED for r in existing):
        return 0, "results_already_approved"
    scheme, every = _scheme_components(db, papers)
    paper_of = {p.assessment_component_id: p for p in papers}
    if any(c.id not in paper_of for c in every):
        return 0, "components_without_paper"
    candidates = list(
        db.scalars(
            repo.q(db, CandidateRow).where(
                CandidateRow.exam_cycle_id == cycle.id,
                CandidateRow.course_offering_id == offering_id,
                CandidateRow.eligibility_status == ELIGIBLE,
            )
        )
    )
    by_student: dict[str, dict[str, CandidateRow]] = defaultdict(dict)
    for c in candidates:
        by_student[c.student_id][c.exam_paper_id] = c
    entries = (
        {
            e.candidate_id: e
            for e in db.scalars(
                repo.q(db, MarkEntryRow).where(MarkEntryRow.candidate_id.in_([c.id for c in candidates]))
            )
        }
        if candidates
        else {}
    )
    outcomes: dict[str, rs.Outcome] = {}
    for student_id, held in sorted(by_student.items()):
        if len(held) != len(papers) or any(c.id not in entries for c in held.values()):
            continue  # not a candidate of every paper, or a paper not marked: no result for this student
        parts = []
        for component in sorted(every, key=lambda c: c.code):
            entry = entries[held[paper_of[component.id].id].id]
            parts.append(
                rs.Component(
                    component.code,
                    component.weightage_percent,
                    component.max_marks,
                    component.pass_marks,
                    mk.final_marks(entry.marks_obtained, entry.moderation_delta),
                    entry.absent,
                )
            )
        try:
            outcomes[student_id] = rs.compute(parts, scheme.pass_percent, bands)
        except DomainRuleError as err:
            return 0, err.code
    now = base.clock()
    by_existing = {r.student_id: r for r in existing}
    written = 0
    for student_id, outcome in outcomes.items():
        row = by_existing.get(student_id)
        if row is None:
            row = ResultRow(
                organisation_id=actor.organisation_id,
                exam_cycle_id=cycle.id,
                student_id=student_id,
                course_offering_id=offering_id,
                version=1,
                status=rs.COMPUTED,
            )
            db.add(row)
        row.components = outcome.components
        row.weighted_percent = outcome.weighted_percent
        row.grade, row.grade_point, row.passed = outcome.grade, outcome.grade_point, outcome.passed
        row.computed_by = actor.user_id
        written += 1
    dropped = 0
    for student_id, row in by_existing.items():
        if student_id not in outcomes:
            row.status = rs.SUPERSEDED  # no longer a candidate of every paper; the row is kept
            dropped += 1
    base._audit(
        db,
        actor,
        "exam_result.computed",
        "exam_cycle",
        cycle,
        after={"course_offering_id": offering_id, "results": written, "superseded": dropped, "at": now},
    )
    return written, None


@base.transactional
def compute_results(db: Session, actor: Actor, exam_cycle_id: str, body: object) -> dict:
    """FR-13: results for the offerings whose papers are all locked; recomputing replaces only `computed` results."""
    cycle = _cycle(db, exam_cycle_id)
    selected = _selection(body)
    _require_evaluation(cycle)
    grouped = _papers_by_offering(db, cycle.id)
    existing = _current(db, cycle.id)
    bands = _bands(db, cycle)
    offerings = sorted(selected if selected is not None else grouped)
    done, results, skipped = 0, 0, []
    for offering_id in offerings:
        papers = grouped.get(offering_id)
        if not papers:
            skipped.append({"course_offering_id": offering_id, "reason": "no_papers_in_cycle"})
            continue
        written, reason = _compute_offering(db, actor, cycle, offering_id, papers, existing.get(offering_id, []), bands)
        if reason is not None:
            skipped.append({"course_offering_id": offering_id, "reason": reason})
            continue
        done += 1
        results += written
    db.commit()
    return _summary(cycle.id, done, results, skipped)


# ---------------------------------------------------------------- approval and publication


def _advance(
    db: Session,
    actor: Actor,
    cycle: ExamCycleRow,
    selected: list[str] | None,
    *,
    source: str,
    target: str,
    action: str,
) -> tuple[list[ResultRow], list[dict]]:
    """Moves the results of the selected offerings (all of them when none are named) from `source` to `target`, and
    returns the rows moved with what was skipped. Results already at or past `target` are skipped, which makes a retry safe;
    a named offering whose results have not reached `source` is a 409."""
    order = rs.PIPELINE
    current = _current(db, cycle.id)
    offerings = sorted(selected if selected is not None else current)
    moved: list[ResultRow] = []
    skipped: list[dict] = []
    behind: list[str] = []
    for offering_id in offerings:
        rows = current.get(offering_id, [])
        if not rows:
            if selected is not None:
                skipped.append({"course_offering_id": offering_id, "reason": "no_results"})
            continue
        ready = [r for r in rows if r.status == source]
        if ready:
            moved.extend(ready)
            continue
        if any(order.index(r.status) < order.index(source) for r in rows):
            if selected is not None:
                behind.append(offering_id)
            continue
        if selected is not None:
            skipped.append({"course_offering_id": offering_id, "reason": f"already_{target}"})
    if behind:
        raise ExaminationsError(
            409,
            "invalid_status_transition",
            f"results of these offerings are not {source} yet",
            course_offering_ids=behind,
            required_status=source,
        )
    now = base.clock()
    for row in moved:
        before = row.status
        row.status = target
        if target == rs.DEPARTMENT_APPROVED:
            row.department_approved_by, row.department_approved_at = actor.user_id, now
        elif target == rs.APPROVED:
            row.approved_by, row.approved_at = actor.user_id, now
        elif target == rs.PUBLISHED:
            row.published_by, row.published_at = actor.user_id, now
        base._audit(db, actor, action, "exam_result", row, before={"status": before}, after={"status": target})
    return moved, skipped


def _counts(rows: list[ResultRow]) -> tuple[int, int]:
    return len({r.course_offering_id for r in rows}), len(rows)


@base.transactional
def approve_results_department(db: Session, actor: Actor, exam_cycle_id: str, body: object) -> dict:
    """FR-14, first stage: `computed` results become `department_approved`. The caller's department is unknown (Q13), so
    the stage needs the organisation-wide key; `result:approve-department` alone is refused."""
    if not actor.can(RESULT_APPROVE_ALL):
        raise forbidden(
            "examinations:result:approve-department needs the caller's department, which is not known yet (Q13)"
        )
    cycle = _cycle(db, exam_cycle_id)
    selected = _selection(body)
    _require_evaluation(cycle)
    moved, skipped = _advance(
        db,
        actor,
        cycle,
        selected,
        source=rs.COMPUTED,
        target=rs.DEPARTMENT_APPROVED,
        action="exam_result.department_approved",
    )
    db.commit()
    return _summary(cycle.id, *_counts(moved), skipped)


@base.transactional
def approve_results(db: Session, actor: Actor, exam_cycle_id: str, body: object) -> dict:
    """FR-14, second stage: `department_approved` results become `approved`, with approver and time."""
    cycle = _cycle(db, exam_cycle_id)
    selected = _selection(body)
    _require_evaluation(cycle)
    moved, skipped = _advance(
        db, actor, cycle, selected, source=rs.DEPARTMENT_APPROVED, target=rs.APPROVED, action="exam_result.approved"
    )
    db.commit()
    return _summary(cycle.id, *_counts(moved), skipped)


def _offering_credits(refs: dict[str, OfferingRef], offering_id: str) -> Decimal | None:
    ref = refs.get(offering_id)
    return None if ref is None else ref.credits


def _cycle_complete(db: Session, cycle: ExamCycleRow) -> bool:
    """Every offering with papers in the cycle has them all locked and its results published (an offering with no result
    to publish counts as done)."""
    current = _current(db, cycle.id)
    for offering_id, papers in _papers_by_offering(db, cycle.id).items():
        if any(p.status != pap.LOCKED for p in papers):
            return False
        if any(r.status != rs.PUBLISHED for r in current.get(offering_id, [])):
            return False
    return True


@base.transactional
def publish_results(db: Session, actor: Actor, exam_cycle_id: str, body: object) -> dict:
    """FR-15: `approved` results become `published`, with one `result.published` event per student listing what was published
    now. When every offering of the cycle is published the cycle moves to `results_published`."""
    cycle = _cycle(db, exam_cycle_id)
    selected = _selection(body)
    _require_evaluation(cycle, retry_of_publish=True)
    moved, skipped = _advance(
        db, actor, cycle, selected, source=rs.APPROVED, target=rs.PUBLISHED, action="exam_result.published"
    )
    if moved:
        db.flush()
        published = [
            r
            for r in db.scalars(
                repo.q(db, ResultRow).where(ResultRow.exam_cycle_id == cycle.id, ResultRow.status == rs.PUBLISHED)
            )
        ]
        refs = _offering_refs(db, {r.course_offering_id for r in published})
        by_student: dict[str, list[ResultRow]] = defaultdict(list)
        for row in published:
            by_student[row.student_id].append(row)
        now = {r.id for r in moved}
        for student_id in sorted({r.student_id for r in moved}):
            rows = sorted(by_student[student_id], key=lambda r: (r.course_offering_id, r.id))
            average = rs.grade_point_average(
                (r.grade_point, _offering_credits(refs, r.course_offering_id)) for r in rows
            )
            base._publish(
                db,
                actor,
                "result.published",
                {
                    "exam_cycle_id": cycle.id,
                    "academic_period_id": cycle.academic_period_id,
                    "student_id": student_id,
                    "courses": [
                        {
                            "result_id": r.id,
                            "course_offering_id": r.course_offering_id,
                            "version": r.version,
                            "weighted_percent": base._num(r.weighted_percent),
                            "grade": r.grade,
                            "grade_point": base._num(r.grade_point),
                            "passed": r.passed,
                        }
                        for r in rows
                        if r.id in now
                    ],
                    "grade_point_average": base._num(average),
                    "published_at": iso(base.clock()),
                },
            )
        if _cycle_complete(db, cycle):
            cycle.status = RESULTS_PUBLISHED
            base._audit(
                db,
                actor,
                "exam_cycle.status_changed",
                "exam_cycle",
                cycle,
                before={"status": EVALUATION},
                after={"status": RESULTS_PUBLISHED},
            )
    db.commit()
    return _summary(cycle.id, *_counts(moved), skipped)


# ---------------------------------------------------------------- reads


def list_results(
    db: Session,
    actor: Actor,
    exam_cycle_id: str | None,
    course_offering_id: str | None,
    student_id: str | None,
    status: str | None,
    include_superseded: bool,
    limit: int,
    offset: int,
) -> dict:
    """The results, for a caller with the organisation-wide key; `result:read-department` alone grants nothing because the
    caller's department is unknown (Q13), so it is refused rather than shown an empty list."""
    if not actor.can(RESULT_READ_ALL):
        raise forbidden(
            "examinations:result:read-department needs the caller's department, which is not known yet (Q13)"
        )
    query = repo.q(db, ResultRow)
    for column, value, field in (
        (ResultRow.exam_cycle_id, exam_cycle_id, "exam_cycle_id"),
        (ResultRow.course_offering_id, course_offering_id, "course_offering_id"),
        (ResultRow.student_id, student_id, "student_id"),
    ):
        if (checked := base._optional_id(value, field)) is not None:
            query = query.where(column == checked)
    state = base._optional_choice(status, "status", rs.RESULT_STATUSES)
    if state is not None:
        query = query.where(ResultRow.status == state)
    elif not include_superseded:
        query = query.where(ResultRow.status != rs.SUPERSEDED)
    rows, total = repo.page(
        db,
        query,
        [ResultRow.exam_cycle_id, ResultRow.course_offering_id, ResultRow.student_id, ResultRow.version],
        limit,
        offset,
    )
    refs = _offering_refs(db, {r.course_offering_id for r in rows})
    return {"items": [result_body(r, refs.get(r.course_offering_id)) for r in rows], "total": total}


def list_my_results(db: Session, actor: Actor, exam_cycle_id: str | None) -> dict:
    """Only published, current versions of the caller's own results, grouped by exam cycle."""
    query = repo.q(db, ResultRow).where(ResultRow.student_id == actor.user_id, ResultRow.status == rs.PUBLISHED)
    if (checked := base._optional_id(exam_cycle_id, "exam_cycle_id")) is not None:
        query = query.where(ResultRow.exam_cycle_id == checked)
    rows = list(db.scalars(query.order_by(ResultRow.exam_cycle_id, ResultRow.course_offering_id)))
    refs = _offering_refs(db, {r.course_offering_id for r in rows})
    grouped: dict[str, list[ResultRow]] = defaultdict(list)
    for row in rows:
        grouped[row.exam_cycle_id].append(row)
    items = []
    for cycle_id in sorted(grouped):
        cycle = repo.get(db, ExamCycleRow, cycle_id)
        average = rs.grade_point_average(
            (r.grade_point, _offering_credits(refs, r.course_offering_id)) for r in grouped[cycle_id]
        )
        item = {
            "exam_cycle_id": cycle_id,
            "grade_point_average": base._num(average),
            "results": [result_body(r, refs.get(r.course_offering_id)) for r in grouped[cycle_id]],
        }
        if cycle is not None:
            item["exam_cycle_name"] = cycle.name
        items.append(item)
    return {"items": items}


# ---------------------------------------------------------------- revision


@base.transactional
def revise_result(db: Session, actor: Actor, result_id: str, body: object) -> dict:
    """FR-17: a published result gets a new version with corrected final marks and a reason; the previous version is kept
    as `superseded`; one `result.revised` event carries the previous and the new values."""
    data = base._object(body, "body", ("reason", "components"))
    reason = base._domain(require_text, data.get("reason"), "reason", max_length=REASON_MAX)
    if "components" not in data:
        raise base.invalid("missing_field", "components is required", "components")
    checked_id = base._domain(require_id, result_id, "result_id")
    row = repo.get(db, ResultRow, checked_id)
    if row is None:
        raise not_found("result_not_found", "result not found")
    cycle = _cycle(db, row.exam_cycle_id)
    db.refresh(row)  # re-read under the cycle lock: a concurrent revision may have superseded it
    if row.status != rs.PUBLISHED:
        raise ExaminationsError(
            409,
            "result_not_published",
            f"only a published result is revised, this one is {row.status}",
            status=row.status,
        )
    papers = _papers_by_offering(db, cycle.id).get(row.course_offering_id, [])
    scheme, every = _scheme_components(db, papers)
    template = {c.code: rs.Component(c.code, c.weightage_percent, c.max_marks, c.pass_marks, None) for c in every}
    parts = base._domain(rs.revise, row.components, data["components"], template)
    outcome = base._domain(rs.compute, parts, scheme.pass_percent, _bands(db, cycle))
    previous = _snapshot(row)
    row.status = rs.SUPERSEDED
    now = base.clock()
    new = ResultRow(
        organisation_id=actor.organisation_id,
        exam_cycle_id=row.exam_cycle_id,
        student_id=row.student_id,
        course_offering_id=row.course_offering_id,
        version=row.version + 1,
        components=outcome.components,
        weighted_percent=outcome.weighted_percent,
        grade=outcome.grade,
        grade_point=outcome.grade_point,
        passed=outcome.passed,
        status=rs.PUBLISHED,
        computed_by=row.computed_by,
        department_approved_by=row.department_approved_by,
        department_approved_at=row.department_approved_at,
        approved_by=row.approved_by,
        approved_at=row.approved_at,
        published_by=row.published_by,
        published_at=row.published_at,
        revision_reason=reason,
        revised_by=actor.user_id,
    )
    db.add(new)
    db.flush()
    base._audit(
        db,
        actor,
        "exam_result.revised",
        "exam_result",
        new,
        before={"version": row.version, **previous},
        after={"version": new.version, **_snapshot(new)},
        reason=reason,
    )
    published = list(
        db.scalars(
            repo.q(db, ResultRow).where(
                ResultRow.exam_cycle_id == cycle.id,
                ResultRow.student_id == row.student_id,
                ResultRow.status == rs.PUBLISHED,
            )
        )
    )
    refs = _offering_refs(db, {r.course_offering_id for r in published})
    average = rs.grade_point_average((r.grade_point, _offering_credits(refs, r.course_offering_id)) for r in published)
    base._publish(
        db,
        actor,
        "result.revised",
        {
            "result_id": new.id,
            "exam_cycle_id": new.exam_cycle_id,
            "student_id": new.student_id,
            "course_offering_id": new.course_offering_id,
            "previous_version": row.version,
            "version": new.version,
            "previous": previous,
            "current": _snapshot(new),
            "grade_point_average": base._num(average),
            "reason": reason,
            "revised_at": iso(now),
        },
    )
    db.commit()
    return result_body(new, refs.get(new.course_offering_id))


__all__ = [
    "approve_results",
    "approve_results_department",
    "compute_results",
    "list_my_results",
    "list_results",
    "publish_results",
    "revise_result",
]
