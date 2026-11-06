"""Use cases of sla-management behind contracts/openapi.yaml (docs/prd.md). Each one checks the caller's permission
and the domain rules, changes state and writes an audit entry in the same transaction. Calendars and policies have no
events in contracts/events.yaml; clock events come from the clock engine (engine.py), which helpdesk's events drive
(consumers.py).

Where the contract or PRD leaves a detail open, the choice is noted at the function. The general ones:
- PATCH /calendars/{id} and PATCH /policies/{id} take the contract's input schema with every field optional: only the
  fields sent change, and a full CalendarInput or PolicyInput works too.
- A running clock is reported breached (and at risk) as soon as its due (warning) time passes, worked out when read;
  breached_at is then that due time. The clock.warning-raised, clock.breached and clock.escalated events and the
  escalation records follow when the clock is next checked: on the ticket's next helpdesk event, or by
  check_due_clocks, which the scheduler is to call once PRD open question 1 is settled (until then nothing scheduler
  related is in the contract or consumes_events).
- Warnings, breaches and escalations notify through their events only: the notification SDK does not exist yet.
- A clock's business_minutes_used is live: while it runs, the business time since its run started is added.
- Targets and escalation times are at most 527040 business minutes (a year of round-the-clock time), and a target the
  calendar cannot reach within ten years is refused with 422 target_unreachable, for a policy and for a calendar
  change that would make an active policy's target unreachable.
- Holidays are 2000-01-01 to 2099-12-31; at most 70 working intervals, 1000 holidays and 50 people per escalation
  level are accepted.
- The most overdue clocks are the running breached ones with the earliest due time first; overdue_business_minutes is
  the business time used beyond the target.
- breached_last_24h counts breaches with breached_at in the 24 hours up to now, whatever the clock's state now.
- Cursors are offsets of at most 10**6; a cursor this module did not give out is a 422."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from eos_core.db import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import business_time as bt
from ..domain import clocks as rules
from ..domain import policies as policy_rules
from ..domain.errors import DomainRuleError
from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from ..infrastructure.models import AuditEntry, Calendar, Clock, Policy
from . import engine
from .access import CLOCK_READ, POLICY_MANAGE, Actor, require
from .engine import as_utc, iso
from .errors import SlaManagementError, from_domain

CALENDAR, POLICY = "calendar", "policy"  # audit entities
CALENDAR_FIELDS = ("name", "time_zone", "always_open", "working_hours", "holidays", "active")
POLICY_FIELDS = (
    "name",
    "priority",
    "category_id",
    "calendar_id",
    "response_target_minutes",
    "resolution_target_minutes",
    "warning_percent",
    "pause_on_hold_reasons",
    "escalation_levels",
    "active",
)
SCOPES = ("mine", "all")


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


# ---------------------------------------------------------------- helpers


def _not_found(what: str) -> SlaManagementError:
    return SlaManagementError(404, "not_found", f"{what} not found")


def _conflict(code: str, message: str, field: str | None = None) -> SlaManagementError:
    return SlaManagementError(409, code, message, field=field)


def _invalid(code: str, message: str, field: str | None = None) -> SlaManagementError:
    return SlaManagementError(422, code, message, field=field)


def _domain(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except DomainRuleError as err:
        raise from_domain(err) from err


def _audit(db: Session, actor: Actor, action: str, entity: str, entity_id: str) -> None:
    db.add(
        AuditEntry(
            organisation_id=actor.organisation_id,
            actor=actor.user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            occurred_at=clock(),
        )
    )


def _now() -> datetime:
    return as_utc(clock())


# ---------------------------------------------------------------- serialisation (contract schemas)


def calendar_dict(cal: Calendar) -> dict:
    return {
        "id": cal.id,
        "organisation_id": cal.organisation_id,
        "name": cal.name,
        "time_zone": cal.time_zone,
        "always_open": cal.always_open,
        "working_hours": list(cal.working_hours or []),
        "holidays": list(cal.holidays or []),
        "active": cal.active,
    }


def policy_dict(policy: Policy) -> dict:
    return {
        "id": policy.id,
        "organisation_id": policy.organisation_id,
        "name": policy.name,
        "priority": policy.priority,
        "category_id": policy.category_id,
        "calendar_id": policy.calendar_id,
        "response_target_minutes": policy.response_target_minutes,
        "resolution_target_minutes": policy.resolution_target_minutes,
        "warning_percent": policy.warning_percent,
        "pause_on_hold_reasons": list(policy.pause_on_hold_reasons or []),
        "escalation_levels": list(policy.escalation_levels or []),
        "active": policy.active,
    }


def _flags(c: Clock, now: datetime) -> tuple[bool, bool, datetime | None]:
    """(warned, breached, breached_at) as of now: recorded, or worked out for a running clock."""
    running = c.state == rules.RUNNING
    warn_at, due_at = as_utc(c.warn_at), as_utc(c.due_at)
    late = running and not c.breached and due_at is not None and due_at <= now
    warned = c.warned or (running and warn_at is not None and warn_at <= now)
    return warned, c.breached or late, as_utc(c.breached_at) or (due_at if late else None)


def clock_dict(c: Clock, cal: bt.BusinessCalendar, now: datetime) -> dict:
    warned, breached, breached_at = _flags(c, now)
    return {
        "id": c.id,
        "organisation_id": c.organisation_id,
        "ticket_id": c.ticket_id,
        "ticket_number": c.ticket_number,
        "kind": c.kind,
        "policy_id": c.policy_id,
        "calendar_id": c.calendar_id,
        "priority": c.priority,
        "category_id": c.category_id,
        "queue_id": c.queue_id,
        "assignee_id": c.assignee_id,
        "target_minutes": c.target_minutes,
        "business_minutes_used": engine.live_used(c, cal, now),
        "state": c.state,
        "started_at": iso(c.started_at),
        "warn_at": iso(c.warn_at),
        "due_at": iso(c.due_at),
        "paused_at": iso(c.paused_at),
        "stopped_at": iso(c.stopped_at),
        "outcome": c.outcome,
        "warned": warned,
        "breached": breached,
        "breached_at": iso(breached_at),
    }


def _clock_dicts(db: Session, rows: list[Clock], now: datetime) -> list[dict]:
    calendars = {cid: engine.business_calendar(row) for cid, row in repo.calendars_by_id(db, _ids(rows)).items()}
    return [clock_dict(c, calendars.get(c.calendar_id, engine.FALLBACK_CALENDAR), now) for c in rows]


def _ids(rows: list[Clock]) -> set[str]:
    return {c.calendar_id for c in rows}


# ---------------------------------------------------------------- calendars


def _calendar(db: Session, calendar_id: str, *, lock: bool = False) -> Calendar:
    cal = repo.get(db, Calendar, calendar_id, lock=lock)
    if cal is None:
        raise _not_found("calendar")
    return cal


def _check_reachable(cal: bt.BusinessCalendar, minutes: list[int], field: str) -> None:
    now = _now()
    for value in minutes:
        if not bt.reachable(cal, now, value):
            raise _invalid(
                "target_unreachable",
                f"the calendar does not have {value} business minutes within {bt.HORIZON_DAYS} days",
                field,
            )


def _policy_minutes(policy: Policy | dict) -> list[int]:
    get = policy.get if isinstance(policy, dict) else lambda name: getattr(policy, name)
    return [get("response_target_minutes"), get("resolution_target_minutes")]


def list_calendars(db: Session, actor: Actor, *, active: bool | None) -> list[dict]:
    require(actor, CLOCK_READ, POLICY_MANAGE)
    return [calendar_dict(c) for c in repo.calendars(db, active=active)]


def create_calendar(db: Session, actor: Actor, body: dict) -> dict:
    """POST /calendars."""
    require(actor, POLICY_MANAGE)
    _domain(bt.check_calendar, body["time_zone"], body["always_open"], body["working_hours"], body["holidays"])
    cal = Calendar(organisation_id=actor.organisation_id, **_calendar_values(body))
    db.add(cal)
    db.flush()
    _audit(db, actor, "calendar.created", CALENDAR, cal.id)
    db.commit()
    return calendar_dict(cal)


def _calendar_values(body: dict) -> dict:
    values = {k: body[k] for k in CALENDAR_FIELDS if k in body}
    if "holidays" in values:
        values["holidays"] = [{"date": h["date"].isoformat(), "name": h["name"]} for h in values["holidays"]]
    if "working_hours" in values:
        values["working_hours"] = [dict(i) for i in values["working_hours"]]
    return values


def get_calendar(db: Session, actor: Actor, calendar_id: str) -> dict:
    require(actor, CLOCK_READ, POLICY_MANAGE)
    return calendar_dict(_calendar(db, calendar_id))


def update_calendar(db: Session, actor: Actor, calendar_id: str, body: dict) -> dict:
    """PATCH /calendars/{id}. Deactivating a calendar an active policy uses is a 409. A change of hours, holidays or
    time zone applies to due times computed afterwards; it is a 422 when it would leave an active policy using the
    calendar with a target the calendar cannot reach."""
    require(actor, POLICY_MANAGE)
    cal = _calendar(db, calendar_id, lock=True)
    values = _calendar_values(body)
    merged = {**calendar_dict(cal), **values}
    holidays = [{"date": _date(h["date"]), "name": h["name"]} for h in merged["holidays"]]
    _domain(bt.check_calendar, merged["time_zone"], merged["always_open"], merged["working_hours"], holidays)
    users = repo.active_policies_using(db, cal.id)
    if cal.active and merged["active"] is False and users:
        raise _conflict("calendar_in_use", "an active policy uses this calendar", "active")
    if users and {"time_zone", "always_open", "working_hours", "holidays"} & set(values):
        business = bt.build(merged["time_zone"], merged["always_open"], merged["working_hours"], holidays)
        _check_reachable(business, [m for p in users for m in _policy_minutes(p)], "working_hours")
    for name, value in values.items():
        setattr(cal, name, value)
    _audit(db, actor, "calendar.deactivated" if values.get("active") is False else "calendar.updated", CALENDAR, cal.id)
    db.commit()
    return calendar_dict(cal)


def _date(value: str | date) -> date:
    return date.fromisoformat(value) if isinstance(value, str) else value


# ---------------------------------------------------------------- policies


def _policy(db: Session, policy_id: str) -> Policy:
    policy = repo.get(db, Policy, policy_id, lock=True)
    if policy is None:
        raise _not_found("policy")
    return policy


def _usable_calendar(db: Session, calendar_id: str) -> Calendar:
    """The policy's calendar, locked so it cannot be deactivated meanwhile; 422 when unknown or inactive."""
    cal = repo.get(db, Calendar, calendar_id, lock=True)
    if cal is None:
        raise _invalid("unknown_calendar", "calendar not found", "calendar_id")
    if not cal.active:
        raise _invalid("inactive_calendar", "the calendar is not active", "calendar_id")
    return cal


def _check_policy(db: Session, values: dict) -> None:
    """Targets, escalation levels, the calendar and whether its hours can reach the targets."""
    _domain(policy_rules.check_targets, values["response_target_minutes"], values["resolution_target_minutes"])
    _domain(policy_rules.check_escalation_levels, values["escalation_levels"], load_settings().max_escalation_levels)
    cal = _usable_calendar(db, values["calendar_id"])
    _check_reachable(engine.business_calendar(cal), _policy_minutes(values), "resolution_target_minutes")


def _duplicate() -> SlaManagementError:
    return _conflict("duplicate_policy", "an active policy already exists for this priority and category", "priority")


def _save(db: Session) -> None:
    """Flush, turning the partial unique index on active (priority, category) into a 409 when a concurrent request
    took the pair first."""
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _duplicate() from None


def _policy_values(body: dict) -> dict:
    values = {k: body[k] for k in POLICY_FIELDS if k in body}
    if "pause_on_hold_reasons" in values:
        values["pause_on_hold_reasons"] = list(dict.fromkeys(values["pause_on_hold_reasons"]))
    if "escalation_levels" in values:
        # Every level stored whole, with the contract's defaults: a PATCH body carries only the keys the caller sent.
        values["escalation_levels"] = [
            {
                "level": level["level"],
                "after_breach_minutes": level["after_breach_minutes"],
                "notify_assignee": level.get("notify_assignee", True),
                "notify_person_ids": list(dict.fromkeys(level.get("notify_person_ids") or [])),
            }
            for level in values["escalation_levels"]
        ]
    if "category_id" in values:
        values["category_key"] = policy_rules.category_key(values["category_id"])
    return values


def list_policies(
    db: Session, actor: Actor, *, priority: str | None, category_id: str | None, active: bool | None
) -> list[dict]:
    require(actor, CLOCK_READ, POLICY_MANAGE)
    return [policy_dict(p) for p in repo.policies(db, priority=priority, category_id=category_id, active=active)]


def create_policy(db: Session, actor: Actor, body: dict) -> dict:
    """POST /policies. warning_percent defaults to SLA_MANAGEMENT_DEFAULT_WARNING_PERCENT and is stored, so the policy
    shows the value its clocks use. An inactive policy may be created; only active ones count as duplicates."""
    require(actor, POLICY_MANAGE)
    values = _policy_values(body)
    if values.get("warning_percent") is None:
        values["warning_percent"] = load_settings().default_warning_percent
    _check_policy(db, values)
    if values["active"] and repo.active_policy_for(db, values["priority"], values["category_id"]):
        raise _duplicate()
    policy = Policy(organisation_id=actor.organisation_id, **values)
    db.add(policy)
    _save(db)
    _audit(db, actor, "policy.created", POLICY, policy.id)
    db.commit()
    return policy_dict(policy)


def get_policy(db: Session, actor: Actor, policy_id: str) -> dict:
    require(actor, CLOCK_READ, POLICY_MANAGE)
    policy = repo.get(db, Policy, policy_id)
    if policy is None:
        raise _not_found("policy")
    return policy_dict(policy)


def update_policy(db: Session, actor: Actor, policy_id: str, body: dict) -> dict:
    """PATCH /policies/{id}. Running clocks keep the targets they started with. A policy that is or becomes active
    must not share its priority and category with another active one (409) and needs an active calendar (422)."""
    require(actor, POLICY_MANAGE)
    policy = _policy(db, policy_id)
    values = _policy_values(body)
    if "warning_percent" in values and values["warning_percent"] is None:
        del values["warning_percent"]
    merged = {**policy_dict(policy), **values}
    if merged["active"]:
        _check_policy(db, merged)
        if repo.active_policy_for(db, merged["priority"], merged["category_id"], other_than=policy.id):
            raise _duplicate()
    else:
        _domain(policy_rules.check_targets, merged["response_target_minutes"], merged["resolution_target_minutes"])
        _domain(
            policy_rules.check_escalation_levels, merged["escalation_levels"], load_settings().max_escalation_levels
        )
        if repo.get(db, Calendar, merged["calendar_id"]) is None:
            raise _invalid("unknown_calendar", "calendar not found", "calendar_id")
    for name, value in values.items():
        setattr(policy, name, value)
    _save(db)
    _audit(db, actor, "policy.deactivated" if values.get("active") is False else "policy.updated", POLICY, policy.id)
    db.commit()
    return policy_dict(policy)


# ---------------------------------------------------------------- clocks


def list_clocks(
    db: Session,
    actor: Actor,
    *,
    states: list[str] | None,
    kind: str | None,
    breached: bool | None,
    at_risk: bool | None,
    priority: str | None,
    category_id: str | None,
    assignee: str | None,
    ticket_number: str | None,
    cursor: str | None,
    limit: int,
) -> dict:
    """GET /clocks, soonest due first; paused, stopped and cancelled clocks (no due time) last. assignee=me means the
    caller."""
    require(actor, CLOCK_READ)
    try:
        offset = repo.decode_cursor(cursor)
    except ValueError:
        raise _invalid("invalid_cursor", "cursor is not valid", "cursor") from None
    now = _now()
    rows, more = repo.clock_page(
        db,
        now=now,
        states=states,
        kind=kind,
        breached=breached,
        at_risk=at_risk,
        priority=priority,
        category_id=category_id,
        assignee_id=actor.user_id if assignee == "me" else assignee,
        ticket_number=ticket_number,
        offset=offset,
        limit=limit,
    )
    return {"items": _clock_dicts(db, rows, now), "next_cursor": repo.encode_cursor(offset + limit) if more else None}


def get_clock(db: Session, actor: Actor, clock_id: str) -> dict:
    """GET /clocks/{id} with its escalations, lowest level first."""
    require(actor, CLOCK_READ)
    c = repo.get(db, Clock, clock_id)
    if c is None:
        raise _not_found("clock")
    [body] = _clock_dicts(db, [c], _now())
    body["escalations"] = [
        {
            "id": e.id,
            "clock_id": e.clock_id,
            "level": e.level,
            "sent_at": iso(e.sent_at),
            "recipient_ids": list(e.recipient_ids or []),
        }
        for e in repo.escalations(db, c.id)
    ]
    return body


def ticket_sla(db: Session, actor: Actor, ticket_id: str) -> dict:
    """GET /tickets/{ticket_id}: the response clock, then the resolution clock. 404 when the ticket is unknown or not
    tracked."""
    require(actor, CLOCK_READ)
    rows = repo.clocks_of_ticket(db, ticket_id)
    if not rows:
        raise _not_found("ticket")
    return {"ticket_id": ticket_id, "ticket_number": rows[0].ticket_number, "clocks": _clock_dicts(db, rows, _now())}


def breach_stats(db: Session, actor: Actor, *, scope: str | None, limit: int | None) -> dict:
    """GET /stats/breaches, behind the widget sla-management.breaches. scope defaults to all; limit to
    SLA_MANAGEMENT_BREACH_LIST_LIMIT."""
    require(actor, CLOCK_READ)
    scope = scope or "all"
    limit = limit or load_settings().breach_list_limit
    now = _now()
    assignee = actor.user_id if scope == "mine" else None
    breached_open, at_risk, recent = repo.breach_counts(
        db, now=now, since=now - timedelta(hours=24), assignee_id=assignee
    )
    rows = repo.most_overdue(db, now=now, assignee_id=assignee, limit=limit)
    calendars = {cid: engine.business_calendar(row) for cid, row in repo.calendars_by_id(db, _ids(rows)).items()}
    overdue = []
    for c in rows:
        used = engine.live_used(c, calendars.get(c.calendar_id, engine.FALLBACK_CALENDAR), now)
        overdue.append(
            {
                "clock_id": c.id,
                "ticket_id": c.ticket_id,
                "ticket_number": c.ticket_number,
                "kind": c.kind,
                "priority": c.priority,
                "assignee_id": c.assignee_id,
                "due_at": iso(c.due_at),
                "overdue_business_minutes": max(used - c.target_minutes, 0),
            }
        )
    return {
        "scope": scope,
        "breached_open": breached_open,
        "at_risk": at_risk,
        "breached_last_24h": recent,
        "most_overdue": overdue,
    }


def check_due_clocks(db: Session, organisation_id: str, now: datetime | None = None) -> int:
    """Record the warnings, breaches and escalations due on the organisation's running clocks and publish their
    events; returns how many clocks were checked. Not an API operation: the scheduler job of PRD open question 1 calls
    it once that is settled. Runs in the organisation's scope and commits."""
    checked = engine.check_due(db, organisation_id, as_utc(now) if now else _now())
    db.commit()
    return checked
