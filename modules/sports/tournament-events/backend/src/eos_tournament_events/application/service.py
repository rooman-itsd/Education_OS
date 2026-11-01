"""Use cases of tournament-events (docs/prd.md, contracts/openapi.yaml). Each one applies the domain rules, changes
state, publishes the matching event of contracts/events.yaml through eos_core.events.publish and writes an audit
entry (`_audit`) in the same transaction, then commits once. Permission keys are checked by the API layer
(api/deps.require); which rows a caller may see is decided here.

Who sees what (contracts/permissions.yaml):
- Draft tournaments are visible only to holders of tournament:write. To anyone else a draft, and everything under
  it, answers 404, and lists leave drafts out.
- Athletes see only their own entries: a caller whose only tournament-events access comes from an athlete role is
  `self_only`, and the entry list is narrowed to entries naming one of their athlete ids. Which user is which athlete
  is learnt from athlete-performance's events (application/consumers.py). Tournaments, fixtures, results, officials
  and logistics of a visible tournament are the same for every reader.

Times are UTC and timezone-aware. Tournament dates are the institution's local dates (TOURNAMENT_EVENTS_TIMEZONE):
`today()` is the local date, and a local day becomes a UTC window with `_local_start`.

Known dependencies, not worked around here:
- The audit SDK does not exist (packages/sdk is empty). Until it does, tournament_events_audit_entry stands in for
  it, shaped like platform/audit's Record, as athlete-performance's audit table is."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta, tzinfo

from eos_core import events
from eos_core.db import new_id, utcnow
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import RuleViolationError
from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from ..infrastructure.models import (
    AuditEntry,
    Entry,
    Fixture,
    Logistics,
    Official,
    Result,
    Tournament,
    as_utc,
    iso,
)

MODULE = "tournament-events"
TOURNAMENT_READ = f"{MODULE}:tournament:read"
TOURNAMENT_WRITE = f"{MODULE}:tournament:write"
TOURNAMENT_PUBLISH = f"{MODULE}:tournament:publish"
ENTRY_READ = f"{MODULE}:entry:read"
ENTRY_WRITE = f"{MODULE}:entry:write"
FIXTURE_READ = f"{MODULE}:fixture:read"
FIXTURE_WRITE = f"{MODULE}:fixture:write"
RESULT_READ = f"{MODULE}:result:read"
RESULT_RECORD = f"{MODULE}:result:record"
OFFICIAL_READ = f"{MODULE}:official:read"
OFFICIAL_WRITE = f"{MODULE}:official:write"
LOGISTICS_READ = f"{MODULE}:logistics:read"
LOGISTICS_WRITE = f"{MODULE}:logistics:write"

# Roles whose access is limited to the caller's own entries.
ATHLETE_ROLES = frozenset({"athlete", "tournament-events-athlete"})
# Free text stays out of audit before/after; a change is still named in the summary.
NOT_RECORDED = frozenset({"description", "notes", "reason", "cancellation_reason", "accommodation"})


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
    self_only: bool = False

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


def _check(fn, *args) -> None:
    """Run a domain rule; a violation becomes a 400 with the rule's code."""
    try:
        fn(*args)
    except RuleViolationError as v:
        raise _rule(v) from v


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


def _commit(db: Session, conflict_code: str, conflict_message: str) -> None:
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise _invalid(conflict_code, conflict_message) from e


def _apply(row, data: dict) -> tuple[dict, dict]:
    """Set the fields that change; return (before, after) of those fields only."""
    before, after = {}, {}
    for k, v in data.items():
        current = getattr(row, k)
        if isinstance(current, datetime):
            current = as_utc(current)
        if current != v:
            before[k], after[k] = current, v
            setattr(row, k, v)
    return before, after


def _page(items: list, total: int) -> dict:
    return {"items": items, "total": total}


def _zone() -> tzinfo:
    return load_settings().tz


def today() -> date:
    """The institution's local date now."""
    return as_utc(clock()).astimezone(_zone()).date()


def _local_start(day: date) -> datetime:
    """The UTC instant the institution's local day begins."""
    return datetime.combine(day, time.min, tzinfo=_zone()).astimezone(UTC)


def _local_day(at: datetime) -> date:
    return as_utc(at).astimezone(_zone()).date()


def _utc(data: dict, *keys: str) -> dict:
    """Request datetimes (always timezone-aware) normalised to UTC."""
    return {**data, **{k: as_utc(data[k]) for k in keys if data.get(k) is not None}}


# ---------------------------------------------------------------- serialisers


def status_of(t: Tournament, on: date) -> str:
    return rules.effective_status(t.status, t.start_date, t.end_date, on)


def tournament_out(t: Tournament, on: date) -> dict:
    return _clean(
        {
            "id": t.id,
            "organisation_id": t.organisation_id,
            "status": status_of(t, on),
            "created_at": iso(t.created_at),
            "updated_at": iso(t.updated_at),
            "name": t.name,
            "discipline": t.discipline,
            "discipline_id": t.discipline_id,
            "level": t.level,
            "format": t.format,
            "start_date": iso(t.start_date),
            "end_date": iso(t.end_date),
            "venue": t.venue,
            "hosting": t.hosting,
            "registration_closes_on": iso(t.registration_closes_on),
            "description": t.description,
        }
    )


def entry_out(e: Entry) -> dict:
    return _clean(
        {
            "id": e.id,
            "organisation_id": e.organisation_id,
            "created_at": iso(e.created_at),
            "updated_at": iso(e.updated_at),
            "category": e.category,
            "team_name": e.team_name,
            "athlete_ids": list(e.athlete_ids or []),
            "status": e.status,
        }
    )


def fixture_out(f: Fixture) -> dict:
    return _clean(
        {
            "id": f.id,
            "organisation_id": f.organisation_id,
            "created_at": iso(f.created_at),
            "updated_at": iso(f.updated_at),
            "round": f.round,
            "category": f.category,
            "entry_ids": list(f.entry_ids or []),
            "scheduled_at": iso(f.scheduled_at),
            "venue": f.venue,
            "status": f.status,
        }
    )


def official_out(o: Official) -> dict:
    return _clean(
        {
            "id": o.id,
            "organisation_id": o.organisation_id,
            "created_at": iso(o.created_at),
            "updated_at": iso(o.updated_at),
            "name": o.name,
            "user_id": o.user_id,
            "official_role": o.official_role,
            "fixture_id": o.fixture_id,
            "confirmed": o.confirmed,
        }
    )


def result_out(r: Result) -> dict:
    return _clean(
        {
            "fixture_id": r.fixture_id,
            "placings": [_clean(dict(p)) for p in r.placings or []],
            "notes": r.notes,
            "recorded_by": r.recorded_by,
            "recorded_at": iso(r.recorded_at),
        }
    )


LOGISTICS_FIELDS = (
    "travel_mode",
    "departure_at",
    "return_at",
    "accommodation",
    "travelling_count",
    "contact_person_id",
    "notes",
)


def logistics_out(row: Logistics | None) -> dict:
    if row is None:
        return {}
    return _clean({k: _json(as_utc(v) if isinstance(v, datetime) else v) for k, v in _fields(row).items()})


def _fields(row: Logistics) -> dict:
    return {k: getattr(row, k) for k in LOGISTICS_FIELDS}


# ---------------------------------------------------------------- tournaments


def _tournament(db: Session, actor: Actor, tournament_id: str) -> Tournament:
    """The tournament, if the caller may see it: a draft is 404 without tournament:write, so its id is not even
    confirmed."""
    t = repo.get(db, Tournament, tournament_id)
    if t is None or (t.status == rules.DRAFT and not actor.can(TOURNAMENT_WRITE)):
        raise _not_found("tournament")
    return t


def _status_filter(q, status: str, on: date):
    """The effective status as a query: ongoing and completed are published tournaments by their dates."""
    if status in (rules.DRAFT, rules.CANCELLED):
        return q.where(Tournament.status == status)
    q = q.where(Tournament.status == rules.PUBLISHED)
    if status == rules.PUBLISHED:
        return q.where(Tournament.start_date > on)
    if status == rules.ONGOING:
        return q.where(Tournament.start_date <= on, Tournament.end_date >= on)
    return q.where(Tournament.end_date < on)


def list_tournaments(db: Session, actor: Actor, filters: dict, limit: int, offset: int) -> dict:
    on = today()
    q = repo.query(db, Tournament)
    if not actor.can(TOURNAMENT_WRITE):
        q = q.where(Tournament.status != rules.DRAFT)
    if filters.get("status"):
        q = _status_filter(q, filters["status"], on)
    if filters.get("level"):
        q = q.where(Tournament.level == filters["level"])
    # a tournament is in the period when any of its days is
    if filters.get("from"):
        q = q.where(Tournament.end_date >= filters["from"])
    if filters.get("to"):
        q = q.where(Tournament.start_date <= filters["to"])
    rows, total = repo.page(db, q, (Tournament.start_date, Tournament.name, Tournament.id), limit, offset)
    return _page([tournament_out(t, on) for t in rows], total)


def create_tournament(db: Session, actor: Actor, data: dict) -> dict:
    _check(rules.check_tournament_dates, data["start_date"], data["end_date"], data.get("registration_closes_on"))
    t = Tournament(organisation_id=actor.organisation_id, status=rules.DRAFT, **data)
    db.add(t)
    _audit(db, actor, "created", "tournament", t, after={**data, "status": rules.DRAFT})
    _publish(
        db,
        actor,
        "tournament.created",
        {
            "tournament_id": t.id,
            "name": t.name,
            "level": t.level,
            "start_date": iso(t.start_date),
            "end_date": iso(t.end_date),
        },
    )
    db.commit()
    return tournament_out(t, today())


def get_tournament(db: Session, actor: Actor, tournament_id: str) -> dict:
    return tournament_out(_tournament(db, actor, tournament_id), today())


def update_tournament(db: Session, actor: Actor, tournament_id: str, data: dict) -> dict:
    t = _tournament(db, actor, tournament_id)
    on = today()
    _check(rules.check_editable, status_of(t, on))
    merged = {k: data.get(k, getattr(t, k)) for k in ("start_date", "end_date", "registration_closes_on")}
    _check(rules.check_tournament_dates, merged["start_date"], merged["end_date"], merged["registration_closes_on"])
    before, after = _apply(t, data)
    if after:
        _audit(db, actor, "updated", "tournament", t, before=before, after=after)
        db.commit()
    return tournament_out(t, on)


def publish_tournament(db: Session, actor: Actor, tournament_id: str) -> dict:
    t = _tournament(db, actor, tournament_id)
    _check(rules.check_publish, t.status)
    t.status, t.published_at = rules.PUBLISHED, clock()
    _audit(db, actor, "published", "tournament", t, before={"status": rules.DRAFT}, after={"status": t.status})
    payload = {"tournament_id": t.id, "registration_closes_on": iso(t.registration_closes_on)}
    _publish(db, actor, "tournament.published", _clean(payload))
    db.commit()
    return tournament_out(t, today())


def cancel_tournament(db: Session, actor: Actor, tournament_id: str, reason: str) -> dict:
    """Cancelling also cancels every fixture still to be played; entries and results stay as they were."""
    t = _tournament(db, actor, tournament_id)
    on = today()
    was = status_of(t, on)
    _check(rules.check_cancel, was)
    t.status, t.cancelled_at, t.cancellation_reason = rules.CANCELLED, clock(), reason
    _audit(db, actor, "cancelled", "tournament", t, before={"status": was}, after={"status": t.status})
    for f in repo.fixtures_of(db, t.id, rules.OPEN_FIXTURES):
        before = {"status": f.status}
        f.status = rules.CANCELLED
        _audit(db, actor, "cancelled", "fixture", f, before=before, after={"status": f.status})
    _publish(db, actor, "tournament.cancelled", {"tournament_id": t.id, "reason": reason})
    db.commit()
    return tournament_out(t, on)


# ---------------------------------------------------------------- entries


def _live_entries(db: Session, tournament_id: str, category: str, exclude: str | None = None) -> list[Entry]:
    rows = repo.all_by(db, Entry, tournament_id=tournament_id, category=category)
    return [e for e in rows if e.id != exclude and e.status != rules.WITHDRAWN]


def _not_entered_twice(db: Session, t: Tournament, category: str, athlete_ids: list[str], exclude=None) -> None:
    """An athlete has one live entry per category of a tournament."""
    others = [e.athlete_ids or [] for e in _live_entries(db, t.id, category, exclude)]
    taken = rules.already_entered(athlete_ids, others)
    if taken:
        raise _invalid("already_entered", f"athlete {taken} already has an entry in {category!r}")


def _publish_confirmed(db: Session, actor: Actor, e: Entry) -> None:
    payload = {
        "tournament_id": e.tournament_id,
        "entry_id": e.id,
        "category": e.category,
        "athlete_ids": list(e.athlete_ids or []),
    }
    _publish(db, actor, "entry.confirmed", payload)


def list_entries(db: Session, actor: Actor, tournament_id: str, status: str | None, limit: int, offset: int) -> dict:
    t = _tournament(db, actor, tournament_id)
    q = repo.query(db, Entry).where(Entry.tournament_id == t.id)
    if status:
        q = q.where(Entry.status == status)
    if actor.self_only:
        # athlete_ids is a JSON list and containment differs per database: narrow in Python, page in SQL
        own = repo.athletes_of_user(db, actor.user_id)
        mine = [e.id for e in db.scalars(q) if own & set(e.athlete_ids or [])]
        q = q.where(Entry.id.in_(mine))
    rows, total = repo.page(db, q, (Entry.category, Entry.created_at, Entry.id), limit, offset)
    return _page([entry_out(e) for e in rows], total)


def create_entry(db: Session, actor: Actor, tournament_id: str, data: dict) -> dict:
    t = _tournament(db, actor, tournament_id)
    _check(rules.check_entries_open, status_of(t, today()), t.registration_closes_on, today())
    _check(rules.check_new_entry_status, data["status"])
    _check(rules.check_athletes, data["athlete_ids"])
    _not_entered_twice(db, t, data["category"], data["athlete_ids"])
    e = Entry(organisation_id=actor.organisation_id, tournament_id=t.id, created_at=clock(), **data)
    db.add(e)
    _audit(db, actor, "created", "entry", e, after=data)
    if e.status == rules.CONFIRMED:
        _publish_confirmed(db, actor, e)
    db.commit()
    return entry_out(e)


def update_entry(db: Session, actor: Actor, tournament_id: str, entry_id: str, data: dict) -> dict:
    """Confirm or withdraw an entry, or change its team. A confirmed entry whose athletes change is confirmed again
    (entry.confirmed carries the new athlete_ids)."""
    t = _tournament(db, actor, tournament_id)
    e = repo.get(db, Entry, entry_id, tournament_id=t.id)
    if e is None:
        raise _not_found("entry")
    _check(rules.check_editable, status_of(t, today()))
    if e.status == rules.WITHDRAWN and any(getattr(e, k) != v for k, v in data.items()):
        raise _invalid("entry_withdrawn", "a withdrawn entry cannot be changed")
    new_status = data.get("status", e.status)
    _check(rules.check_entry_transition, e.status, new_status)
    if "athlete_ids" in data:
        _check(rules.check_athletes, data["athlete_ids"])
    if new_status != rules.WITHDRAWN:
        _not_entered_twice(db, t, e.category, data.get("athlete_ids", e.athlete_ids or []), exclude=e.id)
    before, after = _apply(e, data)
    if after:
        _audit(db, actor, "updated", "entry", e, before=before, after=after)
        if e.status == rules.CONFIRMED and ("status" in after or "athlete_ids" in after):
            _publish_confirmed(db, actor, e)
        db.commit()
    return entry_out(e)


# ---------------------------------------------------------------- fixtures


def _fixture(db: Session, t: Tournament, fixture_id: str) -> Fixture:
    f = repo.get(db, Fixture, fixture_id, tournament_id=t.id)
    if f is None:
        raise _not_found("fixture")
    return f


def _check_fixture(db: Session, t: Tournament, entry_ids: list[str], category: str | None, at: datetime) -> None:
    """Entries once each, from this tournament, not withdrawn, of the fixture's category; the time on one of the
    tournament's days."""
    _check(rules.check_fixture_entries, entry_ids)
    found = repo.entries_by_id(db, t.id, entry_ids)
    for entry_id in entry_ids:
        e = found.get(entry_id)
        if e is None:
            raise _invalid("unknown_entry", f"entry {entry_id} not found in this tournament")
        if e.status == rules.WITHDRAWN:
            raise _invalid("entry_withdrawn", f"entry {entry_id} was withdrawn")
        if category and e.category != category:
            raise _invalid("category_mismatch", f"entry {entry_id} is in {e.category!r}, not {category!r}")
    _check(rules.check_within_dates, _local_day(at), t.start_date, t.end_date)


def _publish_scheduled(db: Session, actor: Actor, t: Tournament, f: Fixture) -> None:
    payload = {
        "tournament_id": t.id,
        "fixture_id": f.id,
        "scheduled_at": iso(f.scheduled_at),
        "venue": f.venue or t.venue,
    }
    _publish(db, actor, "fixture.scheduled", _clean(payload))


def list_fixtures(db: Session, actor: Actor, tournament_id: str, filters: dict, limit: int, offset: int) -> dict:
    t = _tournament(db, actor, tournament_id)
    q = repo.query(db, Fixture).where(Fixture.tournament_id == t.id)
    if filters.get("status"):
        q = q.where(Fixture.status == filters["status"])
    if filters.get("from"):
        q = q.where(Fixture.scheduled_at >= _local_start(filters["from"]))
    if filters.get("to"):
        q = q.where(Fixture.scheduled_at < _local_start(filters["to"] + timedelta(days=1)))
    rows, total = repo.page(db, q, (Fixture.scheduled_at, Fixture.id), limit, offset)
    return _page([fixture_out(f) for f in rows], total)


def schedule_fixture(db: Session, actor: Actor, tournament_id: str, data: dict) -> dict:
    t = _tournament(db, actor, tournament_id)
    _check(rules.check_schedulable, status_of(t, today()))
    _check(rules.check_new_fixture_status, data["status"])
    data = _utc(data, "scheduled_at")
    _check_fixture(db, t, data["entry_ids"], data.get("category"), data["scheduled_at"])
    f = Fixture(organisation_id=actor.organisation_id, tournament_id=t.id, **data)
    db.add(f)
    _audit(db, actor, "scheduled", "fixture", f, after=data)
    _publish_scheduled(db, actor, t, f)
    db.commit()
    return fixture_out(f)


def get_fixture(db: Session, actor: Actor, tournament_id: str, fixture_id: str) -> dict:
    return fixture_out(_fixture(db, _tournament(db, actor, tournament_id), fixture_id))


def update_fixture(db: Session, actor: Actor, tournament_id: str, fixture_id: str, data: dict) -> dict:
    """Reschedule, postpone, start or cancel a fixture. A new time or venue, or a postponed fixture scheduled again,
    publishes fixture.scheduled."""
    t = _tournament(db, actor, tournament_id)
    f = _fixture(db, t, fixture_id)
    _check(rules.check_running, status_of(t, today()))
    _check(rules.check_fixture_editable, f.status)
    if "status" in data:
        _check(rules.check_fixture_transition, f.status, data["status"])
    data = _utc(data, "scheduled_at")
    if {"entry_ids", "category", "scheduled_at"} & set(data):
        _check_fixture(
            db,
            t,
            data.get("entry_ids", f.entry_ids or []),
            data.get("category", f.category),
            data.get("scheduled_at", as_utc(f.scheduled_at)),
        )
    was = f.status
    before, after = _apply(f, data)
    if after:
        _audit(db, actor, "updated", "fixture", f, before=before, after=after)
        rescheduled = {"scheduled_at", "venue"} & set(after) or (was == rules.POSTPONED and f.status == rules.SCHEDULED)
        if rescheduled and f.status in (rules.SCHEDULED, rules.POSTPONED):
            _publish_scheduled(db, actor, t, f)
        db.commit()
    return fixture_out(f)


# ---------------------------------------------------------------- results


def get_result(db: Session, actor: Actor, tournament_id: str, fixture_id: str) -> dict:
    f = _fixture(db, _tournament(db, actor, tournament_id), fixture_id)
    r = repo.first_by(db, Result, fixture_id=f.id)
    if r is None:
        raise _not_found("result")
    return result_out(r)


def record_result(db: Session, actor: Actor, tournament_id: str, fixture_id: str, data: dict) -> dict:
    """Record (or correct) a fixture's result; the fixture becomes completed. result.recorded names the athletes
    behind each entry so athlete-performance can record competition results."""
    t = _tournament(db, actor, tournament_id)
    f = _fixture(db, t, fixture_id)
    now = clock()
    _check(rules.check_running, status_of(t, today()))
    _check(rules.check_result_allowed, f.status, as_utc(f.scheduled_at), now)
    placings = [_clean(p) for p in data["placings"]]
    _check(rules.check_placings, placings, f.entry_ids or [])
    entries = repo.entries_by_id(db, t.id, [p["entry_id"] for p in placings])

    values = {"placings": placings, "notes": data.get("notes")}
    r = repo.first_by(db, Result, fixture_id=f.id)
    if r is None:
        r = Result(organisation_id=actor.organisation_id, tournament_id=t.id, fixture_id=f.id, **values)
        db.add(r)
        action, before, after = "recorded", None, values
    else:
        action = "corrected"
        before, after = _apply(r, values)
        if not after:
            return result_out(r)  # the same result again (a retry): nothing changes, nothing is published
    r.recorded_by, r.recorded_at = actor.user_id, now
    _audit(db, actor, action, "result", r, before=before, after=after)
    if f.status != rules.COMPLETED:
        was = f.status
        f.status = rules.COMPLETED
        _audit(db, actor, "completed", "fixture", f, before={"status": was}, after={"status": f.status})
    out = [
        _clean(
            {
                "entry_id": p["entry_id"],
                "athlete_ids": list(entries[p["entry_id"]].athlete_ids or []),
                "position": p.get("position"),
                "mark": p.get("mark"),
                "unit": p.get("unit"),
            }
        )
        for p in placings
    ]
    _publish(db, actor, "result.recorded", {"tournament_id": t.id, "fixture_id": f.id, "placings": out})
    _commit(db, "conflict", "the result was recorded by someone else at the same time; try again")
    return result_out(r)


# ---------------------------------------------------------------- officials


def list_officials(db: Session, actor: Actor, tournament_id: str, limit: int, offset: int) -> dict:
    t = _tournament(db, actor, tournament_id)
    q = repo.query(db, Official).where(Official.tournament_id == t.id)
    rows, total = repo.page(db, q, (Official.created_at, Official.id), limit, offset)
    return _page([official_out(o) for o in rows], total)


def assign_official(db: Session, actor: Actor, tournament_id: str, data: dict) -> dict:
    t = _tournament(db, actor, tournament_id)
    _check(rules.check_running, status_of(t, today()))
    if data.get("fixture_id") and repo.get(db, Fixture, data["fixture_id"], tournament_id=t.id) is None:
        raise _invalid("unknown_fixture", f"fixture {data['fixture_id']} not found in this tournament")
    for o in repo.all_by(db, Official, tournament_id=t.id, fixture_id=data.get("fixture_id")):
        same_person = o.user_id == data["user_id"] if data.get("user_id") else o.name == data["name"]
        if same_person and o.official_role == data["official_role"]:
            raise _invalid("already_assigned", "this official already has this role here")
    o = Official(organisation_id=actor.organisation_id, tournament_id=t.id, created_at=clock(), **data)
    db.add(o)
    # the official's name is a person's name: named in the row, not copied into the audit trail
    _audit(db, actor, "assigned", "official", o, after={k: v for k, v in data.items() if k != "name"})
    payload = {
        "tournament_id": t.id,
        "official_id": o.id,
        "fixture_id": o.fixture_id,
        "official_role": o.official_role,
    }
    _publish(db, actor, "official.assigned", _clean(payload))
    db.commit()
    return official_out(o)


def remove_official(db: Session, actor: Actor, tournament_id: str, official_id: str) -> None:
    t = _tournament(db, actor, tournament_id)
    o = repo.get(db, Official, official_id, tournament_id=t.id)
    if o is None:
        raise _not_found("official")
    _check(rules.check_running, status_of(t, today()))
    before = {"official_role": o.official_role, "fixture_id": o.fixture_id, "user_id": o.user_id}
    _audit(db, actor, "removed", "official", o, before=_clean(before), after={})
    db.delete(o)
    db.commit()


# ---------------------------------------------------------------- logistics


def get_logistics(db: Session, actor: Actor, tournament_id: str) -> dict:
    t = _tournament(db, actor, tournament_id)
    return logistics_out(repo.first_by(db, Logistics, tournament_id=t.id))


def set_logistics(db: Session, actor: Actor, tournament_id: str, data: dict) -> dict:
    """PUT replaces the logistics: a field left out is cleared."""
    t = _tournament(db, actor, tournament_id)
    _check(rules.check_running, status_of(t, today()))
    values = _utc({k: data.get(k) for k in LOGISTICS_FIELDS}, "departure_at", "return_at")
    _check(rules.check_travel, values["departure_at"], values["return_at"], values["travelling_count"])
    row = repo.first_by(db, Logistics, tournament_id=t.id)
    if row is None:
        row = Logistics(organisation_id=actor.organisation_id, tournament_id=t.id, **values)
        db.add(row)
        before, after = None, _clean(values)
    else:
        before, after = _apply(row, values)
        if not after:
            return logistics_out(row)
    _audit(db, actor, "set", "logistics", row, before=before, after=after)
    _commit(db, "conflict", "the logistics were set by someone else at the same time; try again")
    return logistics_out(row)


# ---------------------------------------------------------------- calendar


def calendar(db: Session, start: date, end: date) -> dict:
    """Published tournaments (ongoing and completed included) that have a day in the period, and their fixtures
    (cancelled ones left out) whose time falls on a local day of the period. Drafts and cancelled tournaments are
    never on the calendar. A tournament runs from the local start of its first day to the local start of the day
    after its last."""
    window = (_local_start(start), _local_start(end + timedelta(days=1)))
    tq = repo.query(db, Tournament).where(
        Tournament.status == rules.PUBLISHED, Tournament.start_date <= end, Tournament.end_date >= start
    )
    items = [
        _clean(
            {
                "kind": "tournament",
                "id": t.id,
                "tournament_id": t.id,
                "title": t.name,
                "starts_at": _local_start(t.start_date),
                "ends_at": _local_start(t.end_date + timedelta(days=1)),
                "venue": t.venue,
            }
        )
        for t in db.scalars(tq)
    ]
    fq = (
        repo.query(db, Fixture)
        .add_columns(Tournament.name, Tournament.venue)
        .join(
            Tournament,
            and_(Tournament.id == Fixture.tournament_id, Tournament.organisation_id == Fixture.organisation_id),
        )
        .where(
            Tournament.status == rules.PUBLISHED,
            Fixture.status != rules.CANCELLED,
            Fixture.scheduled_at >= window[0],
            Fixture.scheduled_at < window[1],
        )
    )
    for f, name, venue in db.execute(fq):
        title = f"{name}: {f.round}" + (f" ({f.category})" if f.category else "")
        items.append(
            _clean(
                {
                    "kind": "fixture",
                    "id": f.id,
                    "tournament_id": f.tournament_id,
                    "title": title,
                    "starts_at": as_utc(f.scheduled_at),
                    "venue": f.venue or venue,
                }
            )
        )
    items.sort(key=lambda i: (i["starts_at"], i["kind"] != "tournament", i["id"]))
    return {"items": [{**i, **{k: iso(i[k]) for k in ("starts_at", "ends_at") if k in i}} for i in items]}
