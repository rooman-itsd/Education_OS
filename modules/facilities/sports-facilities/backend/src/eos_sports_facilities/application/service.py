"""Use cases of sports-facilities (docs/prd.md, contracts/openapi.yaml). Each one applies the domain rules, changes
state, publishes the matching event of contracts/events.yaml through eos_core.events.publish and writes an audit
entry (`_audit`) in the same transaction, then commits once. Permission keys are checked by the API layer
(api/deps.require); every query is scoped to the caller's organisation, so another organisation's ids are 404.

Known dependencies, not worked around here:
- The audit SDK does not exist (packages/sdk is empty). Until it does, sports_facilities_audit_entry stands in for
  it, shaped like platform/audit's Record, as athlete-performance's audit table is."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

from eos_core import events
from eos_core.db import new_id, utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import RuleViolationError, Slot
from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from ..infrastructure.models import AuditEntry, Facility, OperatingHoursSlot, Space, UsageRecord, as_utc, iso

MODULE = "sports-facilities"
FACILITY_READ = f"{MODULE}:facility:read"
FACILITY_WRITE = f"{MODULE}:facility:write"
FACILITY_STATUS = f"{MODULE}:facility:status"
USAGE_READ = f"{MODULE}:usage:read"
USAGE_RECORD = f"{MODULE}:usage:record"

# Free text stays out of audit before/after; a change is still named in the summary.
NOT_RECORDED = frozenset({"description", "group_name"})


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


@dataclass
class Actor:
    """Who is calling. Built by the API layer from the verified token."""

    user_id: str
    organisation_id: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


class ServiceError(Exception):
    """A refusal with an HTTP status and a contract error body ({code, message})."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def body(self) -> dict:
        return {"code": self.code, "message": self.message}


def _not_found(what: str) -> ServiceError:
    return ServiceError(404, "not_found", f"{what} not found in your organisation")


def _invalid(code: str, message: str) -> ServiceError:
    return ServiceError(400, code, message)


def _rule(v: RuleViolationError) -> ServiceError:
    return ServiceError(400, v.code, v.message)


# ---------------------------------------------------------------- helpers


def _clean(d: dict) -> dict:
    """Optional contract fields are left out rather than sent as null."""
    return {k: v for k, v in d.items() if v is not None}


def _publish(db: Session, actor: Actor, name: str, payload: dict) -> None:
    org = actor.organisation_id
    events.publish(db, f"{MODULE}.{name}", org, {"organisation_id": org, **payload}, actor=actor.user_id)


def _json(value):
    if isinstance(value, datetime | date):
        return iso(value)
    return value


def _audit(db: Session, actor: Actor, action: str, entity_type: str, row, *, before=None, after=None) -> None:
    """One audit record per state change, in the same transaction. `before` and `after` are the changed fields only
    (None for a creation's `before`)."""
    db.flush()
    changed = sorted(after) if before is not None and after else []
    summary = f"{entity_type.replace('_', ' ')} {row.id} {action}" + (f": {', '.join(changed)}" if changed else "")

    def recorded(fields):
        return None if fields is None else {k: _json(v) for k, v in fields.items() if k not in NOT_RECORDED}

    db.add(
        AuditEntry(
            organisation_id=actor.organisation_id,
            client_token=new_id(),
            actor=actor.user_id,
            action=f"{entity_type}.{action}",
            entity_type=entity_type,
            entity_id=row.id,
            summary=summary[:300],
            before=recorded(before),
            after=recorded(after),
            occurred_at=clock(),
        )
    )


def _commit(db: Session, duplicate_message: str) -> None:
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise _invalid("duplicate_name", duplicate_message) from e


def _get(db: Session, model, row_id: str | None, what: str):
    row = repo.get(db, model, row_id)
    if row is None:
        raise _not_found(what)
    return row


def _same(a, b) -> bool:
    if isinstance(a, datetime) or isinstance(b, datetime):
        return as_utc(a) == as_utc(b)
    return a == b


def _apply(row, data: dict) -> tuple[dict, dict]:
    """Set the fields that change; return (before, after) of those fields only."""
    before, after = {}, {}
    for k, v in data.items():
        if not _same(getattr(row, k), v):
            before[k], after[k] = getattr(row, k), v
            setattr(row, k, v)
    return before, after


def _page(items: list, total: int) -> dict:
    return {"items": items, "total": total}


def _require_fields(data: dict) -> None:
    if not data:
        raise _invalid("empty_update", "send at least one field to change")


# ---------------------------------------------------------------- serialisers


def facility_out(f: Facility) -> dict:
    return _clean(
        {
            "id": f.id,
            "organisation_id": f.organisation_id,
            "status": f.status,
            "status_reason": f.status_reason,
            "status_until": iso(f.status_until),
            "created_at": iso(f.created_at),
            "updated_at": iso(f.updated_at),
            "name": f.name,
            "facility_type": f.facility_type,
            "sports": list(f.sports or []),
            "surface": f.surface,
            "indoor": f.indoor,
            "capacity": f.capacity,
            "location": f.location,
            "description": f.description,
        }
    )


def space_out(s: Space) -> dict:
    return _clean(
        {
            "id": s.id,
            "organisation_id": s.organisation_id,
            "facility_id": s.facility_id,
            "created_at": iso(s.created_at),
            "updated_at": iso(s.updated_at),
            "name": s.name,
            "capacity": s.capacity,
            "sports": list(s.sports or []),
            "active": s.active,
        }
    )


def usage_out(u: UsageRecord) -> dict:
    return _clean(
        {
            "id": u.id,
            "organisation_id": u.organisation_id,
            "recorded_by": u.recorded_by,
            "created_at": iso(u.created_at),
            "updated_at": iso(u.updated_at),
            "facility_id": u.facility_id,
            "space_id": u.space_id,
            "used_from": iso(u.used_from),
            "used_to": iso(u.used_to),
            "purpose": u.purpose,
            "group_name": u.group_name,
            "headcount": u.headcount,
            "booking_reference": u.booking_reference,
        }
    )


def _hours_out(rows) -> dict:
    return {"slots": [{"day_of_week": r.day_of_week, "opens_at": r.opens_at, "closes_at": r.closes_at} for r in rows]}


# ---------------------------------------------------------------- facilities


def list_facilities(db: Session, filters: dict, limit: int, offset: int) -> dict:
    rows = repo.facilities(db, filters.get("facility_type"), filters.get("status"), filters.get("indoor"))
    sport = (filters.get("sport") or "").strip().casefold()
    if sport:  # sports is a JSON list; matched here so SQLite and Postgres agree (case-insensitive, whole name)
        rows = [f for f in rows if any(s.casefold() == sport for s in f.sports or [])]
    return _page([facility_out(f) for f in rows[offset : offset + limit]], len(rows))


def create_facility(db: Session, actor: Actor, data: dict) -> dict:
    if repo.first_by(db, Facility, name=data["name"]):
        raise _invalid("duplicate_name", f"a facility named {data['name']!r} already exists")
    f = Facility(organisation_id=actor.organisation_id, status=rules.INITIAL_STATUS, **data)
    db.add(f)
    _audit(db, actor, "created", "facility", f, after={**data, "status": f.status})
    _publish(
        db,
        actor,
        "facility.registered",
        {
            "facility_id": f.id,
            "name": f.name,
            "facility_type": f.facility_type,
            "sports": list(f.sports or []),
            "capacity": f.capacity,
        },
    )
    _commit(db, f"a facility named {data['name']!r} already exists")
    return facility_out(f)


def get_facility(db: Session, facility_id: str) -> dict:
    return facility_out(_get(db, Facility, facility_id, "facility"))


def _facility_updated(db: Session, actor: Actor, f: Facility, changed: list[str]) -> None:
    f.updated_at = utcnow()
    _publish(db, actor, "facility.updated", {"facility_id": f.id, "changed_fields": sorted(changed)})


def update_facility(db: Session, actor: Actor, facility_id: str, data: dict) -> dict:
    f = _get(db, Facility, facility_id, "facility")
    _require_fields(data)
    if "name" in data and data["name"] != f.name and repo.first_by(db, Facility, name=data["name"]):
        raise _invalid("duplicate_name", f"a facility named {data['name']!r} already exists")
    before, after = _apply(f, data)
    if after:
        _audit(db, actor, "updated", "facility", f, before=before, after=after)
        _facility_updated(db, actor, f, list(after))
        _commit(db, f"a facility named {data.get('name')!r} already exists")
    return facility_out(f)


def set_status(db: Session, actor: Actor, facility_id: str, data: dict) -> dict:
    f = _get(db, Facility, facility_id, "facility")
    until = as_utc(data.get("until"))  # stored as UTC
    if until is not None and until <= clock():
        raise _invalid("until_in_past", "until must be in the future")
    change = {"status": data["status"], "status_reason": data.get("reason"), "status_until": until}
    before, after = _apply(f, change)
    if after:
        f.updated_at = utcnow()
        _audit(db, actor, "status_changed", "facility", f, before=before, after=after)
        _publish(
            db,
            actor,
            "availability.changed",
            {"facility_id": f.id, "status": f.status, "reason": f.status_reason, "until": iso(f.status_until)},
        )
        db.commit()
    return facility_out(f)


# ---------------------------------------------------------------- spaces


def list_spaces(db: Session, facility_id: str, limit: int, offset: int) -> dict:
    _get(db, Facility, facility_id, "facility")
    q = repo.query(db, Space).where(Space.facility_id == facility_id)
    rows, total = repo.page(db, q, (Space.name, Space.id), limit, offset)
    return _page([space_out(s) for s in rows], total)


def create_space(db: Session, actor: Actor, facility_id: str, data: dict) -> dict:
    f = _get(db, Facility, facility_id, "facility")
    if repo.first_by(db, Space, facility_id=f.id, name=data["name"]):
        raise _invalid("duplicate_name", f"this facility already has a space named {data['name']!r}")
    s = Space(organisation_id=actor.organisation_id, facility_id=f.id, **data)
    db.add(s)
    _audit(db, actor, "created", "space", s, after={**data, "facility_id": f.id})
    _facility_updated(db, actor, f, ["spaces"])
    _commit(db, f"this facility already has a space named {data['name']!r}")
    return space_out(s)


def update_space(db: Session, actor: Actor, facility_id: str, space_id: str, data: dict) -> dict:
    f = _get(db, Facility, facility_id, "facility")
    s = repo.space_of(db, f.id, space_id)
    if s is None:
        raise _not_found("space")
    _require_fields(data)
    if "name" in data and data["name"] != s.name and repo.first_by(db, Space, facility_id=f.id, name=data["name"]):
        raise _invalid("duplicate_name", f"this facility already has a space named {data['name']!r}")
    before, after = _apply(s, data)
    if after:
        _audit(db, actor, "updated", "space", s, before=before, after=after)
        _facility_updated(db, actor, f, ["spaces"])
        _commit(db, "this facility already has a space with this name")
    return space_out(s)


# ---------------------------------------------------------------- operating hours


def get_hours(db: Session, facility_id: str) -> dict:
    f = _get(db, Facility, facility_id, "facility")
    return _hours_out(repo.slots(db, f.id))


def set_hours(db: Session, actor: Actor, facility_id: str, slots: list[dict]) -> dict:
    f = _get(db, Facility, facility_id, "facility")
    try:
        wanted = rules.check_slots([Slot(**s) for s in slots])
    except RuleViolationError as v:
        raise _rule(v) from v
    current = repo.slots(db, f.id)
    as_slots = [Slot(r.day_of_week, r.opens_at, r.closes_at) for r in current]
    if as_slots != wanted:
        for row in current:
            db.delete(row)
        for s in wanted:
            db.add(
                OperatingHoursSlot(
                    organisation_id=actor.organisation_id,
                    facility_id=f.id,
                    day_of_week=s.day_of_week,
                    opens_at=s.opens_at,
                    closes_at=s.closes_at,
                )
            )
        before = {"slots": [s.__dict__ for s in as_slots]}
        after = {"slots": [s.__dict__ for s in wanted]}
        _audit(db, actor, "hours_set", "facility", f, before=before, after=after)
        _facility_updated(db, actor, f, ["operating_hours"])
        db.commit()
    return _hours_out(repo.slots(db, f.id))


# ---------------------------------------------------------------- usage


def list_usages(db: Session, filters: dict, limit: int, offset: int) -> dict:
    """Records that touch the inclusive local dates from..to, newest first."""
    start, end = rules.local_bounds(filters.get("from"), filters.get("to"), load_settings().tz)
    q = repo.usage_query(db, filters.get("facility_id"), filters.get("purpose"), start, end)
    rows, total = repo.page(db, q, (UsageRecord.used_from.desc(), UsageRecord.id), limit, offset)
    return _page([usage_out(u) for u in rows], total)


def record_usage(db: Session, actor: Actor, data: dict) -> dict:
    data = {**data, "used_from": as_utc(data["used_from"]), "used_to": as_utc(data["used_to"])}  # stored as UTC
    try:
        rules.check_window(data["used_from"], data["used_to"])
    except RuleViolationError as v:
        raise _rule(v) from v
    f = repo.get(db, Facility, data["facility_id"])
    if f is None:
        raise _invalid("unknown_facility", f"facility {data['facility_id']} not found in your organisation")
    if data.get("space_id") and repo.space_of(db, f.id, data["space_id"]) is None:
        raise _invalid("space_not_in_facility", f"space {data['space_id']} is not a space of facility {f.id}")
    u = UsageRecord(organisation_id=actor.organisation_id, recorded_by=actor.user_id, **data)
    db.add(u)
    _audit(db, actor, "recorded", "usage", u, after=data)
    _publish(
        db,
        actor,
        "usage.recorded",
        {
            "usage_id": u.id,
            "facility_id": u.facility_id,
            "space_id": u.space_id,
            "used_from": iso(u.used_from),
            "used_to": iso(u.used_to),
            "purpose": u.purpose,
            "headcount": u.headcount,
        },
    )
    db.commit()
    return usage_out(u)


def get_usage(db: Session, usage_id: str) -> dict:
    return usage_out(_get(db, UsageRecord, usage_id, "usage record"))


# ---------------------------------------------------------------- utilisation


def utilisation(db: Session, facility_id: str, start: date, end: date) -> dict:
    f = _get(db, Facility, facility_id, "facility")
    try:
        rules.check_period(start, end)
    except RuleViolationError as v:
        raise _rule(v) from v
    lo, hi = rules.local_bounds(start, end, load_settings().tz)
    slots = [Slot(r.day_of_week, r.opens_at, r.closes_at) for r in repo.slots(db, f.id)]
    open_hours = rules.hours_open(slots, start, end)
    windows: dict[str, list] = defaultdict(list)
    for u in repo.usages(db, f.id, lo, hi):
        windows[u.purpose].append((as_utc(u.used_from), as_utc(u.used_to)))
    used = rules.hours_in_use([w for ws in windows.values() for w in ws], lo, hi)
    by_purpose = [
        {"purpose": p, "hours": round(rules.hours_in_use(windows[p], lo, hi), 2)}
        for p in rules.PURPOSES
        if windows.get(p)
    ]
    out = {
        "facility_id": f.id,
        "hours_open": round(open_hours, 2),
        "hours_used": round(used, 2),
        "by_purpose": by_purpose,
    }
    if open_hours > 0:
        out["utilisation_pct"] = round(used / open_hours * 100, 2)
    return out
