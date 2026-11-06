"""Use cases of examinations for grading schemes, assessment schemes and exam cycles (docs/prd.md FR-1 to FR-3,
contracts/openapi.yaml). Each state change applies the domain rules, writes an audit entry (`_audit`) and, where the
contract names one, publishes the event through eos_core.events.publish, all in one transaction, then commits once; any
failure rolls the whole change back. Permission keys are checked by the API layer (api/deps.require); the organisation
is the caller's, taken from the verified token, and every query is scoped to it (infrastructure/repository.q).

Events: only examinations.exam-cycle.created and examinations.exam-cycle.closed are published. Grading-scheme and
assessment-scheme changes publish nothing: the contract names no event for them.

Known gaps, not worked around here (docs/reviewer-decisions.md section 8 and 10):
- The audit SDK does not exist, so examinations_audit_entry stands in for it, as in the other academic modules.
- Department scope (PRD Q13) is open: a holder of assessment-scheme:write-department or write-all may write any
  scheme; `department_id` is neither read nor granted.
- Locked-marks protection is NOT provided yet. Whether a paper of a scheme has locked marks needs the marks tables,
  which do not exist, so `ensure_editable` is called with `has_locked_marks=False` (only its superseded check is
  effective) and that validation is deferred until marks management is implemented. Meanwhile only a draft scheme can
  be replaced, so an active or superseded scheme is never changed.
- The contract has no 401/403 responses for most operations; this module answers them as deps.py does, and the gap is
  recorded for a contract change."""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from eos_core import events
from eos_core.db import new_id, utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import assessment as asm
from ..domain import cycles as cy
from ..domain import grading as gr
from ..domain.errors import DomainRuleError
from ..domain.values import require_bool, require_choice, require_date, require_id, require_number, require_text
from ..infrastructure import repository as repo
from ..infrastructure.models import (
    AssessmentComponentRow,
    AssessmentSchemeRow,
    AuditEntry,
    ExamCycleRow,
    GradingBandRow,
    GradingSchemeRow,
    iso,
)
from .access import MODULE, Actor
from .errors import ExaminationsError, from_domain, invalid, not_found


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


def _domain(fn: Callable, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except DomainRuleError as err:
        raise from_domain(err) from err


# A uniqueness rule of the schema broken by a concurrent request is the contract's 409, not a server error.
CONFLICTS = {
    "default_grading_scheme": ("default_changed", "another request changed the default grading scheme; try again"),
    "active_assessment_scheme": ("active_scheme_changed", "another request changed the active scheme; try again"),
    "assessment_scheme_version": ("version_taken", "another request created a scheme version; try again"),
    "paper_in_session": ("paper_already_scheduled", "another request scheduled a paper of this session; try again"),
    "paper_component": ("paper_exists", "another request created a paper for a component; try again"),
}


def transactional(fn: Callable) -> Callable:
    """A state change is all or nothing: whatever raises, nothing of it stays in the session, and so nothing is
    committed later by accident (an audit, event or row written before the failure is rolled back with the rest)."""

    @functools.wraps(fn)
    def wrapper(db: Session, *args, **kwargs):
        try:
            return fn(db, *args, **kwargs)
        except BaseException as err:
            db.rollback()
            if isinstance(err, IntegrityError):
                for which, (code, message) in CONFLICTS.items():
                    if repo.violates(err, which):
                        raise ExaminationsError(409, code, message) from err
            raise

    return wrapper


def _publish(db: Session, actor: Actor, name: str, payload: dict) -> None:
    """contracts/events.yaml: the payload names organisation_id; actor and occurred_at travel on the envelope."""
    events.publish(
        db,
        f"{MODULE}.{name}",
        actor.organisation_id,
        {"organisation_id": actor.organisation_id, **payload},
        actor=actor.user_id,
    )


# ---------------------------------------------------------------- audit


def _value(value):
    """A JSON value for before/after."""
    if isinstance(value, datetime | date):
        return iso(value)
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")  # 40.00 and 40 are one value
    if isinstance(value, list | tuple):
        return [_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _value(v) for k, v in value.items()}
    return value


def _summary(entity_type: str, row, action: str) -> str:
    label = getattr(row, "name", None) or getattr(row, "code", None) or row.id
    verb = action.split(".", 1)[1].replace("_", " ")
    return f"{entity_type.replace('_', ' ')} {label} {verb}"[:300]


def _audit(
    db: Session,
    actor: Actor,
    action: str,
    entity_type: str,
    row,
    *,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
) -> AuditEntry:
    """One audit record per state change, in the same transaction, shaped like platform/audit's NewRecord. `before`
    and `after` hold the changed fields only. The row is flushed first so a new one has its id."""
    db.flush()
    entry = AuditEntry(
        organisation_id=row.organisation_id,
        client_token=new_id(),
        actor=actor.user_id,
        action=action,
        entity_type=entity_type,
        entity_id=row.id,
        summary=_summary(entity_type, row, action),
        before=None if before is None else _value(before),
        after=None if after is None else _value(after),
        reason=reason,
        occurred_at=clock(),
    )
    db.add(entry)
    return entry


# ---------------------------------------------------------------- request parsing (400 with the contract's body)


def _object(value: object, field: str, allowed: Iterable[str]) -> dict:
    """A request object with no field the contract does not define."""
    if not isinstance(value, dict):
        raise invalid("invalid_body", f"{field} must be an object", field)
    unknown = sorted(set(value) - set(allowed))
    if unknown:
        raise invalid("unknown_field", f"{field} has no field {', '.join(unknown)}", unknown[0])
    return value


def _parse_date(value: object, field: str) -> date:
    if not isinstance(value, str):
        raise invalid("invalid_date", f"{field} must be a date such as 2026-11-09", field)
    try:
        if len(value) != 10:  # date.fromisoformat also accepts compact forms such as 20261109
            raise ValueError(value)
        return date.fromisoformat(value)
    except ValueError:
        raise invalid("invalid_date", f"{field} must be a date such as 2026-11-09", field) from None


def _num(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _optional_choice(value: str | None, field: str, choices: tuple[str, ...]) -> str | None:
    return None if value is None else _domain(require_choice, value, field, choices)


def _optional_id(value: str | None, field: str) -> str | None:
    return None if value is None else _domain(require_id, value, field)


# ---------------------------------------------------------------- grading schemes

GRADING_FIELDS = ("name", "bands")


def _bands_body(row_bands: list[GradingBandRow]) -> list[dict]:
    return [
        {
            "min_percent": _num(b.min_percent),
            "max_percent": _num(b.max_percent),
            "grade": b.grade,
            "grade_point": _num(b.grade_point),
            "is_pass": b.is_pass,
        }
        for b in row_bands
    ]


def _grading_body(db: Session, row: GradingSchemeRow, in_use: set[str] | None = None) -> dict:
    """components.schemas.GradingScheme"""
    used = repo.grading_schemes_in_use(db) if in_use is None else in_use
    return {
        "id": row.id,
        "organisation_id": row.organisation_id,
        "name": row.name,
        "bands": _bands_body(repo.bands_of(db, row.id)),
        "is_default": bool(row.is_default),
        "in_use": row.id in used,
    }


def _band_audit(scheme: gr.GradingScheme) -> list[dict]:
    return [
        {"min_percent": b.min_percent, "max_percent": b.max_percent, "grade": b.grade, "grade_point": b.grade_point}
        | {"is_pass": b.is_pass}
        for b in scheme.bands
    ]


def _grading_row(a: Actor, scheme_id: str, band: gr.Band) -> GradingBandRow:
    return GradingBandRow(
        organisation_id=a.organisation_id,
        grading_scheme_id=scheme_id,
        min_percent=band.min_percent,
        max_percent=band.max_percent,
        grade=band.grade,
        grade_point=band.grade_point,
        is_pass=band.is_pass,
    )


def _parse_grading(body: object) -> gr.GradingScheme:
    data = _object(body, "body", GRADING_FIELDS)
    missing = [f for f in GRADING_FIELDS if f not in data]
    if missing:
        raise invalid("missing_field", f"{', '.join(missing)} is required", missing[0])
    return _domain(gr.new_scheme, data["name"], data["bands"])


def _grading_or_404(db: Session, grading_scheme_id: str) -> GradingSchemeRow:
    row = repo.get(db, GradingSchemeRow, grading_scheme_id)
    if row is None:
        raise not_found("grading_scheme_not_found", "grading scheme not found")
    return row


def list_grading_schemes(db: Session) -> dict:
    rows = repo.grading_schemes(db)
    used = repo.grading_schemes_in_use(db)
    return {"items": [_grading_body(db, r, used) for r in rows], "total": len(rows)}


def get_grading_scheme(db: Session, grading_scheme_id: str) -> dict:
    return _grading_body(db, _grading_or_404(db, grading_scheme_id))


@transactional
def create_grading_scheme(db: Session, actor: Actor, body: object) -> dict:
    scheme = _parse_grading(body)
    row = GradingSchemeRow(id=new_id(), organisation_id=actor.organisation_id, name=scheme.name, is_default=False)
    db.add(row)
    db.flush()
    db.add_all(_grading_row(actor, row.id, b) for b in scheme.bands)
    _audit(
        db,
        actor,
        "grading_scheme.created",
        "grading_scheme",
        row,
        after={"name": scheme.name, "bands": _band_audit(scheme)},
    )
    db.commit()
    return _grading_body(db, row)


@transactional
def replace_grading_scheme(db: Session, actor: Actor, grading_scheme_id: str, body: object) -> dict:
    row = _grading_or_404(db, grading_scheme_id)
    scheme = _parse_grading(body)
    _domain(gr.ensure_replaceable, in_use=repo.grading_scheme_in_use(db, row.id))
    old = repo.bands_of(db, row.id)
    before = {"name": row.name, "bands": _bands_body(old)}
    for band in old:
        db.delete(band)
    db.flush()
    row.name = scheme.name
    db.add_all(_grading_row(actor, row.id, b) for b in scheme.bands)
    _audit(
        db,
        actor,
        "grading_scheme.replaced",
        "grading_scheme",
        row,
        before=before,
        after={"name": scheme.name, "bands": _band_audit(scheme)},
    )
    db.commit()
    return _grading_body(db, row)


@transactional
def set_default_grading_scheme(db: Session, actor: Actor, grading_scheme_id: str) -> dict:
    """FR-3: one default per organisation. The previous default is cleared before the chosen one is set, so the
    partial unique index never sees two. Setting the current default again changes nothing."""
    row = _grading_or_404(db, grading_scheme_id)
    rows = repo.grading_schemes(db)
    changed = set(_domain(gr.plan_default, [(r.id, bool(r.is_default)) for r in rows], row.id))
    if not changed:
        return _grading_body(db, row)
    previous = [r for r in rows if r.id in changed and r.id != row.id]
    for r in previous:
        r.is_default = False
    db.flush()
    row.is_default = True
    for r in previous:
        _audit(
            db,
            actor,
            "grading_scheme.default_cleared",
            "grading_scheme",
            r,
            before={"is_default": True},
            after={"is_default": False},
        )
    _audit(
        db,
        actor,
        "grading_scheme.default_set",
        "grading_scheme",
        row,
        before={"is_default": False},
        after={"is_default": True},
    )
    db.commit()
    return _grading_body(db, row)


# ---------------------------------------------------------------- assessment schemes

ASSESSMENT_FIELDS = ("course_offering_id", "pass_percent", "components")


def _component_body(c: AssessmentComponentRow) -> dict:
    return {
        "id": c.id,
        "code": c.code,
        "name": c.name,
        "kind": c.kind,
        "weightage_percent": _num(c.weightage_percent),
        "max_marks": _num(c.max_marks),
        "pass_marks": _num(c.pass_marks),
    }


def _assessment_body(db: Session, row: AssessmentSchemeRow) -> dict:
    """components.schemas.AssessmentScheme. `department_id` (cached from the course offering) is not served: the
    offering read model is not populated yet (docs/reviewer-decisions.md)."""
    return {
        "id": row.id,
        "organisation_id": row.organisation_id,
        "course_offering_id": row.course_offering_id,
        "version": row.version,
        "status": row.status,
        "pass_percent": _num(row.pass_percent),
        "components": [_component_body(c) for c in repo.components_of(db, row.id)],
    }


def _components_audit(components: Iterable[asm.Component]) -> list[dict]:
    return [
        {
            "code": c.code,
            "name": c.name,
            "kind": c.kind,
            "weightage_percent": c.weightage_percent,
            "max_marks": c.max_marks,
            "pass_marks": c.pass_marks,
        }
        for c in components
    ]


def _parse_assessment(body: object, scheme_id: str, version: int) -> asm.Scheme:
    data = _object(body, "body", ASSESSMENT_FIELDS)
    missing = [f for f in ASSESSMENT_FIELDS if f not in data]
    if missing:
        raise invalid("missing_field", f"{', '.join(missing)} is required", missing[0])
    scheme = _domain(
        asm.new_scheme, scheme_id, data["course_offering_id"], data["pass_percent"], data["components"], version=version
    )
    if not scheme.components:
        raise invalid("no_components", "a scheme needs at least one component", "components")
    for index, c in enumerate(scheme.components):
        if c.weightage_percent <= 0:  # contract: weightage_percent exclusiveMinimum 0
            raise invalid(
                "invalid_weightage", "weightage_percent must be above 0", f"components[{index}].weightage_percent"
            )
    return scheme


def _component_rows(a: Actor, scheme: asm.Scheme, reuse: dict[str, str] | None = None) -> list[AssessmentComponentRow]:
    """Rows for the scheme's components; a component keeps the id it had under the same code (`reuse`)."""
    reuse = reuse or {}
    return [
        AssessmentComponentRow(
            id=reuse.get(c.code) or new_id(),
            organisation_id=a.organisation_id,
            assessment_scheme_id=scheme.id,
            code=c.code,
            name=c.name,
            kind=c.kind,
            weightage_percent=c.weightage_percent,
            max_marks=c.max_marks,
            pass_marks=c.pass_marks,
        )
        for c in scheme.components
    ]


def _assessment_domain(db: Session, row: AssessmentSchemeRow) -> asm.Scheme:
    return asm.Scheme(
        id=row.id,
        course_offering_id=row.course_offering_id,
        version=row.version,
        pass_percent=row.pass_percent,
        components=tuple(
            asm.Component(
                code=c.code,
                name=c.name,
                kind=c.kind,
                weightage_percent=c.weightage_percent,
                max_marks=c.max_marks,
                pass_marks=c.pass_marks,
            )
            for c in repo.components_of(db, row.id)
        ),
        status=row.status,
    )


def _assessment_or_404(db: Session, assessment_scheme_id: str) -> AssessmentSchemeRow:
    row = repo.get(db, AssessmentSchemeRow, assessment_scheme_id)
    if row is None:
        raise not_found("assessment_scheme_not_found", "assessment scheme not found")
    return row


def list_assessment_schemes(
    db: Session, course_offering_id: str | None, status: str | None, limit: int, offset: int
) -> dict:
    query = repo.q(db, AssessmentSchemeRow)
    offering = _optional_id(course_offering_id, "course_offering_id")
    state = _optional_choice(status, "status", asm.SCHEME_STATUSES)
    if offering:
        query = query.where(AssessmentSchemeRow.course_offering_id == offering)
    if state:
        query = query.where(AssessmentSchemeRow.status == state)
    rows, total = repo.page(
        db,
        query,
        [AssessmentSchemeRow.course_offering_id, AssessmentSchemeRow.version, AssessmentSchemeRow.id],
        limit,
        offset,
    )
    return {"items": [_assessment_body(db, r) for r in rows], "total": total}


def get_assessment_scheme(db: Session, assessment_scheme_id: str) -> dict:
    return _assessment_body(db, _assessment_or_404(db, assessment_scheme_id))


@transactional
def create_assessment_scheme(db: Session, actor: Actor, body: object) -> dict:
    """A draft, at the next version of the offering. Earlier versions are kept as they were (FR-2)."""
    scheme = _parse_assessment(body, new_id(), 1)
    existing = repo.schemes_of_offering(db, scheme.course_offering_id)
    scheme = replace(scheme, version=asm.next_version(r.version for r in existing))
    row = AssessmentSchemeRow(
        id=scheme.id,
        organisation_id=actor.organisation_id,
        course_offering_id=scheme.course_offering_id,
        version=scheme.version,
        pass_percent=scheme.pass_percent,
        status=asm.DRAFT,
    )
    db.add(row)
    db.flush()
    db.add_all(_component_rows(actor, scheme))
    _audit(
        db,
        actor,
        "assessment_scheme.created",
        "assessment_scheme",
        row,
        after={
            "course_offering_id": scheme.course_offering_id,
            "version": scheme.version,
            "pass_percent": scheme.pass_percent,
            "components": _components_audit(scheme.components),
        },
    )
    db.commit()
    return _assessment_body(db, row)


@transactional
def replace_assessment_scheme(db: Session, actor: Actor, assessment_scheme_id: str, body: object) -> dict:
    """Replaces a draft in place; its version stays. A scheme that is active or superseded is kept as it was, and a
    new version is created instead (409)."""
    row = _assessment_or_404(db, assessment_scheme_id)
    scheme = _parse_assessment(body, row.id, row.version)
    if scheme.course_offering_id != row.course_offering_id:
        raise invalid(
            "course_offering_immutable", "a scheme cannot move to another course offering", "course_offering_id"
        )
    current = _assessment_domain(db, row)
    # Locked-marks validation is deferred until marks management exists: there are no marks tables to ask, so the
    # flag is False here, never a request value. Only the superseded check of ensure_editable is effective today.
    _domain(asm.ensure_editable, current, has_locked_marks=False)
    if current.status != asm.DRAFT:
        raise ExaminationsError(
            409, "scheme_not_draft", f"only a draft scheme can be replaced, this one is {current.status}"
        )
    old = repo.components_of(db, row.id)
    before = {"pass_percent": row.pass_percent, "components": _components_audit(current.components)}
    keep = {c.code: c.id for c in old}
    for component in old:
        db.delete(component)
    db.flush()
    row.pass_percent = scheme.pass_percent
    db.add_all(_component_rows(actor, scheme, keep))
    _audit(
        db,
        actor,
        "assessment_scheme.replaced",
        "assessment_scheme",
        row,
        before=before,
        after={"pass_percent": scheme.pass_percent, "components": _components_audit(scheme.components)},
    )
    db.commit()
    return _assessment_body(db, row)


@transactional
def activate_assessment_scheme(db: Session, actor: Actor, assessment_scheme_id: str) -> dict:
    """FR-2: weightages must add up to 100; the offering's previous active scheme becomes superseded and is kept.
    The previous one is superseded before the new one is activated, so the partial unique index never sees two."""
    row = _assessment_or_404(db, assessment_scheme_id)
    others = [_assessment_domain(db, r) for r in repo.schemes_of_offering(db, row.course_offering_id) if r.id != row.id]
    plan = _domain(asm.plan_activation, _assessment_domain(db, row), others)
    superseded = [r for r in repo.schemes_of_offering(db, row.course_offering_id) if r.id in plan.superseded_ids]
    for r in superseded:
        r.status = asm.SUPERSEDED
    db.flush()
    row.status = asm.ACTIVE
    for r in superseded:
        _audit(
            db,
            actor,
            "assessment_scheme.superseded",
            "assessment_scheme",
            r,
            before={"status": asm.ACTIVE},
            after={"status": asm.SUPERSEDED, "superseded_by": row.id},
        )
    _audit(
        db,
        actor,
        "assessment_scheme.activated",
        "assessment_scheme",
        row,
        before={"status": asm.DRAFT},
        after={"status": asm.ACTIVE, "supersedes": [r.id for r in superseded]},
    )
    db.commit()
    return _assessment_body(db, row)


# ---------------------------------------------------------------- exam cycles

CREATE_CYCLE_FIELDS = (
    "academic_period_id",
    "code",
    "name",
    "cycle_type",
    "starts_on",
    "ends_on",
    "grading_scheme_id",
    "eligibility_cutoff_date",
    "min_attendance_percent",
    "check_dues",
)
UPDATE_CYCLE_FIELDS = (
    "name",
    "starts_on",
    "ends_on",
    "grading_scheme_id",
    "eligibility_cutoff_date",
    "min_attendance_percent",
    "check_dues",
)
DATE_FIELDS = ("starts_on", "ends_on", "eligibility_cutoff_date")
_PLACEHOLDER = "00000000-0000-0000-0000-000000000000"  # stands in for the grading scheme while the body is checked


def _cycle_body(row: ExamCycleRow) -> dict:
    """components.schemas.ExamCycle"""
    return {
        "id": row.id,
        "organisation_id": row.organisation_id,
        "academic_period_id": row.academic_period_id,
        "code": row.code,
        "name": row.name,
        "cycle_type": row.cycle_type,
        "starts_on": iso(row.starts_on),
        "ends_on": iso(row.ends_on),
        "grading_scheme_id": row.grading_scheme_id,
        "eligibility_cutoff_date": iso(row.eligibility_cutoff_date),
        "min_attendance_percent": _num(row.min_attendance_percent),
        "check_dues": bool(row.check_dues),
        "status": row.status,
    }


def _cycle_domain(row: ExamCycleRow) -> cy.Cycle:
    return cy.Cycle(
        id=row.id,
        academic_period_id=row.academic_period_id,
        code=row.code,
        name=row.name,
        cycle_type=row.cycle_type,
        starts_on=row.starts_on,
        ends_on=row.ends_on,
        grading_scheme_id=row.grading_scheme_id,
        eligibility_cutoff_date=row.eligibility_cutoff_date,
        min_attendance_percent=row.min_attendance_percent,
        check_dues=bool(row.check_dues),
        status=row.status,
    )


def _cycle_or_404(db: Session, exam_cycle_id: str) -> ExamCycleRow:
    row = repo.cycle(db, exam_cycle_id)
    if row is None:
        raise not_found("exam_cycle_not_found", "exam cycle not found")
    return row


def _parse_dates(data: dict) -> dict:
    parsed: dict[str, Any] = dict(data)
    for name in DATE_FIELDS:
        if parsed.get(name) is not None:
            parsed[name] = _parse_date(parsed[name], name)
    return parsed


def list_exam_cycles(
    db: Session,
    academic_period_id: str | None,
    status: str | None,
    cycle_type: str | None,
    limit: int,
    offset: int,
) -> dict:
    query = repo.q(db, ExamCycleRow)
    period = _optional_id(academic_period_id, "academic_period_id")
    state = _optional_choice(status, "status", cy.CYCLE_STATUSES)
    kind = _optional_choice(cycle_type, "cycle_type", cy.CYCLE_TYPES)
    if period:
        query = query.where(ExamCycleRow.academic_period_id == period)
    if state:
        query = query.where(ExamCycleRow.status == state)
    if kind:
        query = query.where(ExamCycleRow.cycle_type == kind)
    rows, total = repo.page(db, query, [ExamCycleRow.created_at.desc(), ExamCycleRow.id], limit, offset)
    return {"items": [_cycle_body(r) for r in rows], "total": total}


def get_exam_cycle(db: Session, exam_cycle_id: str) -> dict:
    return _cycle_body(_cycle_or_404(db, exam_cycle_id))


@transactional
def create_exam_cycle(db: Session, actor: Actor, body: object) -> dict:
    """A draft cycle. Its grading scheme is the one named in the request, else the organisation default; when neither
    exists the request is refused (422), nothing is chosen for the caller. The body is checked first, so a malformed
    request is a 400 whether or not a default exists. `code` is not unique: no uniqueness rule is agreed."""
    data = _parse_dates(_object(body, "body", CREATE_CYCLE_FIELDS))
    named = data.get("grading_scheme_id")
    if named is not None:
        _domain(require_id, named, "grading_scheme_id")
    cycle = _domain(cy.new_cycle, new_id(), data, grading_scheme_id=_PLACEHOLDER)
    if named is not None:
        scheme = repo.get(db, GradingSchemeRow, named)
        if scheme is None:
            raise ExaminationsError(
                422, "unknown_grading_scheme", "grading_scheme_id names no grading scheme", field="grading_scheme_id"
            )
    else:
        scheme = repo.default_grading_scheme(db)
        if scheme is None:
            raise ExaminationsError(
                422,
                "no_grading_scheme",
                "name a grading_scheme_id: the organisation has no default grading scheme",
                field="grading_scheme_id",
            )
    cycle = replace(cycle, grading_scheme_id=scheme.id)
    row = ExamCycleRow(
        id=cycle.id,
        organisation_id=actor.organisation_id,
        academic_period_id=cycle.academic_period_id,
        code=cycle.code,
        name=cycle.name,
        cycle_type=cycle.cycle_type,
        starts_on=cycle.starts_on,
        ends_on=cycle.ends_on,
        grading_scheme_id=cycle.grading_scheme_id,
        eligibility_cutoff_date=cycle.eligibility_cutoff_date,
        min_attendance_percent=cycle.min_attendance_percent,
        check_dues=cycle.check_dues,
        status=cy.DRAFT,
    )
    db.add(row)
    _audit(db, actor, "exam_cycle.created", "exam_cycle", row, after=_cycle_audit(row))
    _publish(
        db,
        actor,
        "exam-cycle.created",
        {
            "exam_cycle_id": row.id,
            "academic_period_id": row.academic_period_id,
            "code": row.code,
            "name": row.name,
            "cycle_type": row.cycle_type,
            "starts_on": iso(row.starts_on),
            "ends_on": iso(row.ends_on),
        },
    )
    db.commit()
    return _cycle_body(row)


def _cycle_audit(row: ExamCycleRow) -> dict:
    body = _cycle_body(row)
    return {k: v for k, v in body.items() if k not in ("id", "organisation_id")}


@transactional
def update_exam_cycle(db: Session, actor: Actor, exam_cycle_id: str, body: object) -> dict:
    """FR-1: only while the cycle is draft or scheduled. `code`, `academic_period_id`, `cycle_type` and `status` are
    not changed here (status has its own operation). The result is checked as a whole, so dates that no longer fit
    together are refused (400)."""
    row = _cycle_or_404(db, exam_cycle_id)
    data = _parse_dates(_object(body, "body", UPDATE_CYCLE_FIELDS))
    current = _cycle_domain(row)
    _domain(cy.ensure_configurable, current)
    changes: dict[str, Any] = {}
    if "name" in data:
        changes["name"] = _domain(require_text, data["name"], "name", max_length=200)
    for name in ("starts_on", "ends_on"):
        if name in data:
            changes[name] = _domain(require_date, data[name], name)
    if "eligibility_cutoff_date" in data:
        value = data["eligibility_cutoff_date"]
        changes["eligibility_cutoff_date"] = (
            None if value is None else _domain(require_date, value, "eligibility_cutoff_date")
        )
    if "min_attendance_percent" in data:
        value = data["min_attendance_percent"]
        changes["min_attendance_percent"] = (
            None if value is None else _domain(require_number, value, "min_attendance_percent", minimum=0, maximum=100)
        )
    if "check_dues" in data:
        changes["check_dues"] = _domain(require_bool, data["check_dues"], "check_dues")
    if "grading_scheme_id" in data:
        scheme_id = _domain(require_id, data["grading_scheme_id"], "grading_scheme_id")
        if repo.get(db, GradingSchemeRow, scheme_id) is None:
            raise invalid("unknown_grading_scheme", "grading_scheme_id names no grading scheme", "grading_scheme_id")
        changes["grading_scheme_id"] = scheme_id
    _domain(replace, current, **changes)  # the cycle as a whole must still be valid
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    for field, value in changes.items():
        if getattr(row, field) != value:
            before[field], after[field] = getattr(row, field), value
            setattr(row, field, value)
    if not after:
        return _cycle_body(row)
    _audit(db, actor, "exam_cycle.updated", "exam_cycle", row, before=before, after=after)
    db.commit()
    return _cycle_body(row)


@transactional
def change_exam_cycle_status(db: Session, actor: Actor, exam_cycle_id: str, body: object) -> dict:
    """PRD section 6: forward, one status at a time. `results_published` is set by publication, so it is refused here.
    Closing publishes examinations.exam-cycle.closed."""
    row = _cycle_or_404(db, exam_cycle_id)
    data = _object(body, "body", ("status",))
    if "status" not in data:
        raise invalid("missing_field", "status is required", "status")
    moved = _domain(cy.plan_status_change, _cycle_domain(row), data["status"])
    previous = row.status
    row.status = moved.status
    _audit(
        db,
        actor,
        "exam_cycle.status_changed",
        "exam_cycle",
        row,
        before={"status": previous},
        after={"status": moved.status},
    )
    if moved.status == cy.CLOSED:
        _publish(
            db,
            actor,
            "exam-cycle.closed",
            {
                "exam_cycle_id": row.id,
                "academic_period_id": row.academic_period_id,
                "closed_at": iso(clock()),
            },
        )
    db.commit()
    return _cycle_body(row)
