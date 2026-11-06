"""Use cases of timetable-attendance (docs/prd.md, contracts/openapi.yaml). Each state change applies the domain rules,
publishes the matching event of contracts/events.yaml through eos_core.events.publish in the same transaction, writes an
audit entry (`_audit`) in that same transaction, then commits once; any failure rolls the whole change back. Permission
keys are checked by the API layer (api/deps.require); the organisation is the caller's, taken from the verified token.

This batch holds the timetable and slot use cases the contract describes: list, create, get, update the details,
replace the slots and list conflicts, and publish and unpublish. Class generation (which needs the organisation's
time zone, see publish_timetable), scheduled classes and attendance follow.

Known dependencies, not worked around here:
- The shared outbox has no `version` column yet (packages/core), so events are published without the envelope version
  declared in contracts/events.yaml.
- The audit SDK does not exist (packages/sdk is empty). Until it does, timetable_attendance_audit_entry stands in for
  it, as academic-management's and helpdesk's audit tables do, shaped like platform/audit's Record so its rows can be
  backfilled with their client_token; it is not the platform audit trail (FR-16).
- The read models (`*_ref`, `section_member`) are filled from other modules' events, which are not wired (PRD Q1, Q2):
  until they are, a slot cannot name any academic-management id, so a timetable can only be created without slots and
  replacing its slots with a non-empty list answers 422 unknown_course_offering. Nothing here works around that.
- No trusted department claim exists (PRD Q9), so department-level authorisation is not enforced: `department_id` is a
  filter and data, never a grant."""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterable
from datetime import date, datetime, time
from typing import Any

from eos_core import events
from eos_core.db import new_id, utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import classes as cl
from ..domain import conflicts as cf
from ..domain import timetables as tt
from ..domain.errors import DomainRuleError
from ..domain.values import require_choice, require_id, require_text
from ..infrastructure import repository as repo
from ..infrastructure.models import AuditEntry, ScheduledClassRow, TimetableRow, TimetableSlotRow, as_utc, iso
from .access import MODULE, Actor
from .errors import TimetableAttendanceError, from_domain, invalid, not_found


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


def _domain(fn: Callable, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except DomainRuleError as err:
        raise from_domain(err) from err


def transactional(fn: Callable) -> Callable:
    """A state change is all or nothing: whatever raises, nothing of it stays in the session, and so nothing is
    committed later by accident (an audit, event or row written before the failure is rolled back with the rest)."""

    @functools.wraps(fn)
    def wrapper(db: Session, *args, **kwargs):
        try:
            return fn(db, *args, **kwargs)
        except BaseException:
            db.rollback()
            raise

    return wrapper


def _publish(db: Session, actor: Actor, entity_event: str, payload: dict) -> None:
    """contracts/events.yaml: the payload names organisation_id; actor and occurred_at travel on the envelope."""
    events.publish(
        db,
        f"{MODULE}.{entity_event}",
        actor.organisation_id,
        {"organisation_id": actor.organisation_id, **payload},
        actor=actor.user_id,
    )


# Never copied into an audit record's before/after (platform/audit NewRecord: "never the whole entity, never secrets,
# passwords, tokens or full documents"). A timetable has no personal data, so nothing is listed yet.
NOT_RECORDED: frozenset[str] = frozenset()


def _value(value):
    """A JSON value for before/after."""
    if isinstance(value, datetime | date | time):
        return iso(value)
    if isinstance(value, list | tuple):
        return [_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _value(v) for k, v in value.items()}
    return value


def _recorded(fields: dict | None) -> dict | None:
    if fields is None:
        return None
    return {k: _value(v) for k, v in fields.items() if k not in NOT_RECORDED}


def _summary(entity_type: str, row, action: str, changed: Iterable[str] | None) -> str:
    """One line: "timetable Odd term updated: name"."""
    label = getattr(row, "name", None) or row.id
    text = f"{entity_type.replace('_', ' ')} {label} {action.split('.', 1)[1].replace('_', ' ')}"
    if changed:
        text += ": " + ", ".join(sorted(changed))
    return " ".join(text.split())[:300]


def _audit(
    db: Session,
    actor: Actor | None,
    action: str,
    entity_type: str,
    row,
    *,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
    client_token: str | None = None,
) -> AuditEntry:
    """One audit record per state change, in the same transaction, shaped like platform/audit's NewRecord. `before`
    and `after` are the changed fields only (None for a creation's `before`). The row is flushed first so a new one
    has its id.

    `client_token` identifies the logical action; without one, each call is its own action. A token already recorded
    returns the original record and appends nothing. The insert runs in a savepoint, so a concurrent request that
    records the same token first makes this one return that record instead of failing the whole transaction."""
    db.flush()
    token = client_token or new_id()
    existing = repo.audit_entry_by_token(db, row.organisation_id, token)
    if existing is not None:
        return existing
    entry = AuditEntry(
        organisation_id=row.organisation_id,
        client_token=token,
        actor=actor.user_id if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=row.id,
        summary=_summary(entity_type, row, action, after if before is not None else None),
        before=_recorded(before),
        after=_recorded(after),
        reason=reason,
        occurred_at=clock(),
    )
    try:
        with db.begin_nested():
            db.add(entry)
    except IntegrityError as err:
        if not repo.is_audit_token_conflict(err):
            raise
        return repo.audit_entry_by_token(db, row.organisation_id, token)
    return entry


def _apply(row, changes: dict) -> tuple[dict, dict]:
    """Set the fields that differ; (before, after) of those fields only."""
    before, after = {}, {}
    for field, value in changes.items():
        if getattr(row, field) != value:
            before[field], after[field] = getattr(row, field), value
            setattr(row, field, value)
    return before, after


# ---------------------------------------------------------------- request parsing (400 with the contract's body)

SLOT_FIELDS = (
    "day_of_week",
    "start_time",
    "end_time",
    "course_offering_id",
    "section_id",
    "instructor_assignment_id",
    "location_label",
    "effective_from",
    "effective_to",
)


def _object(value: object, field: str, allowed: tuple[str, ...]) -> dict:
    """A request object with no field the contract does not define."""
    if not isinstance(value, dict):
        raise invalid("invalid_body", f"{field} must be an object", field)
    unknown = sorted(set(value) - set(allowed))
    if unknown:
        raise invalid("unknown_field", f"{field} has no field {', '.join(unknown)}", unknown[0])
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise invalid("invalid_text", f"{field} must be a string", field)
    return value


def _parse_time(value: object, field: str) -> time:
    try:
        return time.fromisoformat(_text(value, field))
    except ValueError:
        raise invalid("invalid_time", f"{field} must be a time such as 09:30:00", field) from None


def _parse_date(value: object, field: str) -> date:
    text = _text(value, field)
    try:
        if len(text) != 10:  # date.fromisoformat also accepts compact forms such as 20261109
            raise ValueError(text)
        return date.fromisoformat(text)
    except ValueError:
        raise invalid("invalid_date", f"{field} must be a date such as 2026-11-09", field) from None


def _parse_slot(slot_id: str, item: object, index: int) -> tt.Slot:
    where = f"slots[{index}]"
    data = _object(item, where, SLOT_FIELDS)
    missing = [
        f
        for f in (
            "day_of_week",
            "start_time",
            "end_time",
            "course_offering_id",
            "section_id",
            "instructor_assignment_id",
        )
        if f not in data
    ]
    if missing:
        raise invalid("missing_field", f"{where} needs {', '.join(missing)}", f"{where}.{missing[0]}")
    parsed: dict[str, Any] = dict(data)
    for name in ("start_time", "end_time"):
        parsed[name] = _parse_time(data[name], f"{where}.{name}")
    for name in ("effective_from", "effective_to"):
        if data.get(name) is not None:
            parsed[name] = _parse_date(data[name], f"{where}.{name}")
    if data.get("location_label") is not None:
        _text(data["location_label"], f"{where}.location_label")
    try:
        return tt.new_slot(slot_id, parsed)
    except DomainRuleError as err:
        err.field = f"{where}.{err.field}" if err.field else where
        raise from_domain(err) from err


def _parse_slots(items: object, *, reuse: dict[tuple, str] | None = None) -> list[tt.Slot]:
    """Slots from `TimetableSlotInput` objects. A slot identical to one the timetable already has keeps that slot's id
    (`reuse` maps a slot's content to its id), so replacing the slots with the same ones changes nothing and classes
    generated from a slot stay attached to it."""
    if not isinstance(items, list):
        raise invalid("invalid_body", "slots must be a list", "slots")
    free = dict(reuse or {})
    slots: list[tt.Slot] = []
    for index, item in enumerate(items):
        slot = _parse_slot(new_id(), item, index)
        key = _content(slot)
        if key in free:
            slot = _parse_slot(free.pop(key), item, index)
        slots.append(slot)
    return slots


def _content(slot: tt.Slot) -> tuple:
    return (
        slot.day_of_week,
        slot.start_time,
        slot.end_time,
        slot.course_offering_id,
        slot.section_id,
        slot.instructor_assignment_id,
        slot.location_label,
        slot.effective_from,
        slot.effective_to,
    )


# ---------------------------------------------------------------- rows and bodies


def _slot_domain(row: TimetableSlotRow) -> tt.Slot:
    return tt.Slot(
        id=row.id,
        day_of_week=row.day_of_week,
        start_time=row.start_time,
        end_time=row.end_time,
        course_offering_id=row.course_offering_id,
        section_id=row.section_id,
        instructor_assignment_id=row.instructor_assignment_id,
        location_label=row.location_label,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
    )


def _slot_row(a: Actor, timetable_id: str, slot: tt.Slot) -> TimetableSlotRow:
    return TimetableSlotRow(
        id=slot.id,
        organisation_id=a.organisation_id,
        timetable_id=timetable_id,
        day_of_week=slot.day_of_week,
        start_time=slot.start_time,
        end_time=slot.end_time,
        course_offering_id=slot.course_offering_id,
        section_id=slot.section_id,
        instructor_assignment_id=slot.instructor_assignment_id,
        location_label=slot.location_label,
        effective_from=slot.effective_from,
        effective_to=slot.effective_to,
    )


def _timetable_domain(row: TimetableRow) -> tt.Timetable:
    return tt.Timetable(
        id=row.id,
        academic_period_id=row.academic_period_id,
        name=row.name,
        department_id=row.department_id,
        version=row.version,
        status=row.status,
    )


def _summary_dict(row: TimetableRow, slot_count: int) -> dict:
    """components.schemas.TimetableSummary"""
    return {
        "id": row.id,
        "organisation_id": row.organisation_id,
        "academic_period_id": row.academic_period_id,
        "department_id": row.department_id,
        "name": row.name,
        "version": row.version,
        "status": row.status,
        "published_at": iso(row.published_at),
        "slot_count": slot_count,
    }


def _slot_dict(row: TimetableSlotRow, offerings: dict, assignments: dict) -> dict:
    """components.schemas.TimetableSlot; the cached course and instructor fields appear when the read models know them."""
    body: dict = {
        "id": row.id,
        "day_of_week": row.day_of_week,
        "start_time": iso(row.start_time),
        "end_time": iso(row.end_time),
        "course_offering_id": row.course_offering_id,
        "section_id": row.section_id,
        "instructor_assignment_id": row.instructor_assignment_id,
    }
    if row.location_label is not None:
        body["location_label"] = row.location_label
    for name in ("effective_from", "effective_to"):
        value = getattr(row, name)
        if value is not None:
            body[name] = iso(value)
    offering = offerings.get(row.course_offering_id)
    if offering is not None:
        body["course_code"], body["course_title"] = offering.course_code, offering.course_title
    assignment = assignments.get(row.instructor_assignment_id)
    if assignment is not None:
        body["instructor_id"] = assignment.instructor_id
    return body


def _full_dict(db: Session, row: TimetableRow) -> dict:
    """components.schemas.Timetable: the summary and the slots."""
    slots = repo.slots_of(db, row.id)
    offerings = repo.offering_refs(db, {s.course_offering_id for s in slots})
    assignments = repo.assignment_refs(db, {s.instructor_assignment_id for s in slots})
    return {**_summary_dict(row, len(slots)), "slots": [_slot_dict(s, offerings, assignments) for s in slots]}


def _timetable(db: Session, timetable_id: str, *, lock: bool = False) -> TimetableRow:
    row = repo.timetable_for_update(db, timetable_id) if lock else repo.get(db, TimetableRow, timetable_id)
    if row is None:  # also another organisation's timetable: scoped queries cannot see it
        raise not_found("timetable_not_found", "timetable not found")
    return row


def _check_references(db: Session, timetable: tt.Timetable, slots: list[tt.Slot]) -> None:
    """The slots' academic-management ids must exist in the local read models and agree with each other and with the
    timetable's academic period (contract replaceTimetableSlots: 422)."""
    offerings = repo.offering_refs(db, {s.course_offering_id for s in slots})
    sections = repo.section_refs(db, {s.section_id for s in slots})
    assignments = repo.assignment_refs(db, {s.instructor_assignment_id for s in slots})
    _domain(
        tt.ensure_known_references,
        slots,
        offerings=set(offerings),
        sections={sid: ref.course_offering_id for sid, ref in sections.items()},
        assignments={aid: (ref.course_offering_id, ref.section_id) for aid, ref in assignments.items()},
    )
    _domain(
        tt.ensure_offerings_in_period,
        slots,
        {oid: ref.academic_period_id for oid, ref in offerings.items()},
        timetable.academic_period_id,
    )


# ---------------------------------------------------------------- timetables


def list_timetables(
    db: Session,
    academic_period_id: str | None,
    department_id: str | None,
    status: str | None,
    limit: int,
    offset: int,
) -> dict:
    """GET /timetables: summaries without slots."""
    if academic_period_id is not None:
        _domain(require_id, academic_period_id, "academic_period_id")
    if department_id is not None:
        _domain(require_id, department_id, "department_id")
    if status is not None:
        _domain(require_choice, status, "status", tt.TIMETABLE_STATUSES)
    rows, total = repo.timetables(db, academic_period_id, department_id, status, limit, offset)
    counts = repo.slot_counts(db, [r.id for r in rows])
    return {"items": [_summary_dict(r, counts.get(r.id, 0)) for r in rows], "total": total}


def get_timetable(db: Session, timetable_id: str) -> dict:
    return _full_dict(db, _timetable(db, timetable_id))


@transactional
def create_timetable(db: Session, a: Actor, body: dict) -> dict:
    """POST /timetables (FR-1): a draft for an academic period, optionally for one department, with zero or more
    slots. Publishes timetable.created."""
    data = _object(body, "body", ("academic_period_id", "department_id", "name", "slots"))
    for required in ("academic_period_id", "name"):
        if required not in data:
            raise invalid("missing_field", f"{required} is required", required)
    name = _text(data["name"], "name").strip()
    timetable = _domain(
        tt.Timetable,
        id=new_id(),
        academic_period_id=data["academic_period_id"],
        name=name,
        department_id=data.get("department_id"),
    )
    slots = _parse_slots(data.get("slots", []))
    _domain(tt.ensure_unique_slots, slots)
    _check_references(db, timetable, slots)
    row = TimetableRow(
        id=timetable.id,
        organisation_id=a.organisation_id,
        academic_period_id=timetable.academic_period_id,
        department_id=timetable.department_id,
        name=timetable.name,
        version=0,
        status=tt.DRAFT,
    )
    db.add(row)
    db.flush()
    db.add_all(_slot_row(a, row.id, s) for s in slots)
    _publish(
        db,
        a,
        "timetable.created",
        {
            "timetable_id": row.id,
            "academic_period_id": row.academic_period_id,
            "department_id": row.department_id,
            "name": row.name,
        },
    )
    after = {
        "academic_period_id": row.academic_period_id,
        "department_id": row.department_id,
        "name": row.name,
        "status": row.status,
        "slot_count": len(slots),
    }
    _audit(db, a, "timetable.created", "timetable", row, after=after)
    db.commit()
    return _full_dict(db, row)


@transactional
def update_timetable(db: Session, a: Actor, timetable_id: str, body: dict) -> dict:
    """PATCH /timetables/{id} (FR-2): the name and department of a draft or unpublished timetable. The academic period
    never changes. Publishes timetable.updated and audits only when something changed."""
    data = _object(body, "body", ("name", "department_id"))
    row = _timetable(db, timetable_id, lock=True)
    current = _timetable_domain(row)
    _domain(tt.ensure_editable, current)
    name = _text(data["name"], "name").strip() if "name" in data else row.name
    department_id = data["department_id"] if "department_id" in data else row.department_id
    checked = _domain(
        tt.Timetable,
        id=row.id,
        academic_period_id=row.academic_period_id,
        name=name,
        department_id=department_id,
        version=row.version,
        status=row.status,
    )
    before, after = _apply(row, {"name": checked.name, "department_id": checked.department_id})
    if after:
        _publish(
            db,
            a,
            "timetable.updated",
            {
                "timetable_id": row.id,
                "changed_fields": list(after),
                "slot_count": len(repo.slots_of(db, row.id)),
            },
        )
        _audit(db, a, "timetable.updated", "timetable", row, before=before, after=after)
    db.commit()
    return _full_dict(db, row)


@transactional
def replace_slots(db: Session, a: Actor, timetable_id: str, body: dict) -> dict:
    """PUT /timetables/{id}/slots (FR-2): the complete slot list of a draft or unpublished timetable. This is the one way
    the contract creates, changes and removes slots. A slot identical to an existing one keeps its id. Conflicts are not
    refused here (a draft may have them); GET /conflicts lists them and publishing refuses the blocking ones."""
    data = _object(body, "body", ("slots",))
    if "slots" not in data:
        raise invalid("missing_field", "slots is required", "slots")
    row = _timetable(db, timetable_id, lock=True)
    _domain(tt.ensure_editable, _timetable_domain(row))
    existing = repo.slots_of(db, row.id)
    slots = _parse_slots(data["slots"], reuse={_content(_slot_domain(r)): r.id for r in existing})
    _domain(tt.ensure_unique_slots, slots)
    _check_references(db, _timetable_domain(row), slots)
    keep = {s.id for s in slots}
    removed = [r for r in existing if r.id not in keep]
    have = {r.id for r in existing}
    added = [s for s in slots if s.id not in have]
    if removed or added:
        for gone in removed:
            db.delete(gone)
        db.add_all(_slot_row(a, row.id, s) for s in added)
        db.flush()
        _publish(
            db, a, "timetable.updated", {"timetable_id": row.id, "changed_fields": ["slots"], "slot_count": len(slots)}
        )
        _audit(
            db,
            a,
            "timetable.updated",
            "timetable",
            row,
            before={"slot_count": len(existing)},
            after={"slot_count": len(slots), "slots_added": len(added), "slots_removed": len(removed)},
        )
    db.commit()
    return _full_dict(db, row)


def _conflict_dict(c: cf.Conflict) -> dict:
    """components.schemas.TimetableConflict"""
    body = {
        "kind": c.kind,
        "blocking": c.blocking,
        "slot_id": c.slot_id,
        "other_slot_id": c.other_slot_id,
        "day_of_week": c.day_of_week,
        "overlap_start": iso(c.overlap_start),
        "overlap_end": iso(c.overlap_end),
        "shared_id": c.shared_id,
    }
    if c.other_timetable_id:
        body["other_timetable_id"] = c.other_timetable_id
    return body


def _found_conflicts(db: Session, row: TimetableRow) -> list[cf.Conflict]:
    """The conflicts among the timetable's slots and with the slots of every other published timetable of the same
    academic period."""
    mine = [_slot_domain(r) for r in repo.slots_of(db, row.id)]
    others = [(tid, _slot_domain(r)) for tid, r in repo.published_slots_in_period(db, row.academic_period_id, row.id)]
    assignment_ids = {s.instructor_assignment_id for s in mine} | {s.instructor_assignment_id for _, s in others}
    instructors = {aid: ref.instructor_id for aid, ref in repo.assignment_refs(db, assignment_ids).items()}
    return cf.find_conflicts(mine, instructors, others)


def timetable_conflicts(db: Session, timetable_id: str) -> dict:
    """GET /timetables/{id}/conflicts (FR-4): the conflicts among the timetable's slots and with the slots of every other
    published timetable of the same academic period. Nothing is changed."""
    found = _found_conflicts(db, _timetable(db, timetable_id))
    return {"blocking": bool(cf.blocking(found)), "items": [_conflict_dict(c) for c in found]}


# ---------------------------------------------------------------- publication


@transactional
def publish_timetable(db: Session, a: Actor, timetable_id: str) -> dict:
    """POST /timetables/{id}/publish (FR-3): a draft or unpublished timetable becomes published and its version goes up
    by one. Refused with 409 when it is already published, when a blocking conflict remains (the response lists them),
    or when its academic period is not a known term. Publishes timetable.published and audits it.

    NOT DONE HERE, by decision (docs/reviewer-decisions.md, section 10): the contract says publishing also generates
    the scheduled classes. That needs the organisation's time zone to turn each slot's wall-clock times into instants,
    and no source for it exists yet, so no class is generated and the event reports `scheduled_class_count: 0`.
    `POST /timetables/{id}/generate-classes` is not served either."""
    row = _timetable(db, timetable_id, lock=True)
    timetable = _timetable_domain(row)
    blocking = cf.blocking(_found_conflicts(db, row))
    try:
        plan = tt.plan_publish(timetable, blocking_conflicts=len(blocking))
    except DomainRuleError as err:
        refusal = from_domain(err)
        if err.code == "blocking_conflicts":  # the contract: "Fails with 409 and the conflict list"
            refusal.details["conflicts"] = [_conflict_dict(c) for c in blocking]
        raise refusal from err
    _domain(tt.ensure_known_term, timetable, term_known=repo.term_ref(db, row.academic_period_id) is not None)
    published_at = clock()
    before, after = _apply(
        row, {"status": plan.timetable.status, "version": plan.timetable.version, "published_at": published_at}
    )
    _publish(
        db,
        a,
        "timetable.published",
        {
            "timetable_id": row.id,
            "academic_period_id": row.academic_period_id,
            "department_id": row.department_id,
            "version": row.version,
            "published_at": iso(published_at),
            "scheduled_class_count": 0,
        },
    )
    _audit(db, a, "timetable.published", "timetable", row, before=before, after=after)
    db.commit()
    return _full_dict(db, row)


def _class_domain(row: ScheduledClassRow) -> cl.ScheduledClass:
    return cl.ScheduledClass(
        id=row.id,
        academic_period_id=row.academic_period_id,
        course_offering_id=row.course_offering_id,
        section_id=row.section_id,
        instructor_assignment_id=row.instructor_assignment_id,
        instructor_id=row.instructor_id,
        class_date=row.class_date,
        starts_at=as_utc(row.starts_at),
        ends_at=as_utc(row.ends_at),
        timetable_id=row.timetable_id,
        slot_id=row.slot_id,
        location_label=row.location_label,
        status=row.status,
        cancel_reason=row.cancel_reason,
    )


@transactional
def unpublish_timetable(db: Session, a: Actor, timetable_id: str, body: object) -> dict:
    """POST /timetables/{id}/unpublish (FR-3): a published timetable becomes unpublished; its version stays. Its future
    scheduled classes that have no attendance session are cancelled, each with its own audit entry and
    scheduled-class.cancelled event. Past classes, classes already started, and every class with a session are left
    as they are. The optional `reason` is recorded on the audit entries and on each cancelled class. Publishes
    timetable.unpublished."""
    data = _object({} if body is None else body, "body", ("reason",))
    reason = None if data.get("reason") is None else _domain(require_text, data["reason"], "reason", max_length=500)
    row = _timetable(db, timetable_id, lock=True)
    plan = _domain(tt.plan_unpublish, _timetable_domain(row))
    now = clock()
    class_rows = {r.id: r for r in repo.classes_of_timetable(db, row.id)}
    with_session = repo.class_ids_with_session(db, list(class_rows))
    to_cancel = cl.classes_to_cancel_on_unpublish([_class_domain(r) for r in class_rows.values()], with_session, now)
    before, after = _apply(row, {"status": plan.timetable.status})
    for planned in to_cancel:
        cancelled = _domain(cl.plan_cancel, planned, has_closed_session=False, reason=reason)
        class_row = class_rows[cancelled.id]
        class_before, class_after = _apply(
            class_row, {"status": cancelled.status, "cancel_reason": cancelled.cancel_reason}
        )
        _publish(
            db,
            a,
            "scheduled-class.cancelled",
            {
                "scheduled_class_id": class_row.id,
                "course_offering_id": class_row.course_offering_id,
                "section_id": class_row.section_id,
                "class_date": iso(class_row.class_date),
                "reason": class_row.cancel_reason,
                "cancelled_at": iso(now),
            },
        )
        _audit(
            db,
            a,
            "scheduled-class.cancelled",
            "scheduled_class",
            class_row,
            before=class_before,
            after=class_after,
            reason=reason,
        )
    _publish(
        db,
        a,
        "timetable.unpublished",
        {
            "timetable_id": row.id,
            "academic_period_id": row.academic_period_id,
            "version": row.version,
            "unpublished_at": iso(now),
            "cancelled_class_count": len(to_cancel),
        },
    )
    _audit(
        db,
        a,
        "timetable.unpublished",
        "timetable",
        row,
        before=before,
        after={**after, "cancelled_class_count": len(to_cancel)},
        reason=reason,
    )
    db.commit()
    return _full_dict(db, row)


__all__ = [
    "TimetableAttendanceError",
    "create_timetable",
    "get_timetable",
    "list_timetables",
    "publish_timetable",
    "replace_slots",
    "timetable_conflicts",
    "unpublish_timetable",
    "update_timetable",
]
