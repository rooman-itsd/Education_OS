"""The clock engine: starting, pausing, resuming, recalculating, stopping and cancelling clocks, and recording
warnings, breaches and escalations once their time has passed. The helpdesk event consumers (consumers.py) and the
due-clock check (service.check_due_clocks) call it; it never commits, the caller's transaction does.

Every change writes an audit entry and publishes its event from contracts/events.yaml to the outbox in the same
transaction. Times are the ones the caller passes (helpdesk's event times, or the check's "now"), never the time the
code happens to run.

Decisions where the PRD leaves a detail open:
- Before any change at time T, a running clock is first brought up to T (`catch_up`): a warning, breach or escalation
  that fell due before T is recorded with its own due time, then the change applies. So a response clock stopped after
  its due time has outcome breached and its clock.breached event, whether or not a check ran in between.
- breached_at is the due time that passed, and an escalation's sent_at the time its level fell due, so the records are
  the same whether a helpdesk event or the check finds them.
- warning-raised, breached and each escalation level are published at most once per clock, also across pauses,
  reopening and recalculation; a breach stays recorded (PRD main flow 6) even when a new policy moves due_at later.
- A time earlier than the clock's last change (an event delivered out of order) is treated as that change's time, so
  business time used never goes backwards.
- When the calendar cannot reach a target within ten years (domain.business_time.HORIZON_DAYS), for example after the
  calendar lost most of its hours, the due time is that horizon; policy and calendar changes that would cause this are
  refused with 422 in the first place.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from eos_core import events
from eos_core.db import new_id
from sqlalchemy.orm import Session

from ..domain import business_time as bt
from ..domain import clocks as rules
from ..domain.errors import DomainRuleError
from ..infrastructure import repository as repo
from ..infrastructure.models import AuditEntry, Calendar, Clock, Escalation, Policy, TicketRef
from .access import MODULE

log = logging.getLogger("eos.sla_management")

CLOCK = "clock"  # audit entity
FALLBACK_CALENDAR = bt.BusinessCalendar(tz=UTC, always_open=True, hours={}, holidays=frozenset())


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; everything stored is UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | None) -> str | None:
    return None if value is None else as_utc(value).isoformat()


def business_calendar(row: Calendar | None) -> bt.BusinessCalendar:
    """The calendar's business time. A calendar that is missing, or whose time zone the host no longer knows, counts
    every minute in UTC rather than failing every event of the organisation."""
    if row is None:
        return FALLBACK_CALENDAR
    try:
        return bt.build(row.time_zone, row.always_open, row.working_hours or [], row.holidays or [])
    except DomainRuleError:
        log.warning("sla-management: calendar %s cannot be read; counting every minute in UTC", row.id)
        return FALLBACK_CALENDAR


@dataclass
class Run:
    """One transaction's work for one organisation. `source` is what drove it (a helpdesk event name and id, or the
    due-clock check), kept as the audit reason."""

    db: Session
    organisation_id: str
    source: str
    actor: str | None = None
    _calendars: dict[str, bt.BusinessCalendar] = field(default_factory=dict)

    def calendar(self, calendar_id: str) -> bt.BusinessCalendar:
        if calendar_id not in self._calendars:
            self._calendars[calendar_id] = business_calendar(repo.get(self.db, Calendar, calendar_id))
        return self._calendars[calendar_id]

    def audit(self, action: str, clock: Clock, at: datetime, reason: str | None = None) -> None:
        self.db.add(
            AuditEntry(
                organisation_id=self.organisation_id,
                actor=self.actor,
                action=action,
                entity=CLOCK,
                entity_id=clock.id,
                reason=f"{reason}; {self.source}" if reason else self.source,
                occurred_at=at,
            )
        )

    def publish(self, name: str, clock: Clock, payload: dict) -> None:
        events.publish(
            self.db,
            f"{MODULE}.clock.{name}",
            self.organisation_id,
            {"organisation_id": self.organisation_id, "clock_id": clock.id, "ticket_id": clock.ticket_id, **payload},
            actor=self.actor,
        )


# ---------------------------------------------------------------- business time of a clock


def live_used(clock: Clock, cal: bt.BusinessCalendar, at: datetime) -> int:
    """Business minutes counted up to `at`, excluding paused time."""
    if clock.state != rules.RUNNING or clock.run_started_at is None:
        return clock.business_minutes_used or 0
    return (clock.business_minutes_used or 0) + bt.between(cal, as_utc(clock.run_started_at), at)


def _point(cal: bt.BusinessCalendar, start: datetime, minutes: int) -> datetime:
    found = bt.shift(cal, start, minutes)
    if found is None:
        log.warning("sla-management: target beyond the %s-day horizon; due at the horizon", bt.HORIZON_DAYS)
        found = start + timedelta(days=bt.HORIZON_DAYS if minutes > 0 else -bt.HORIZON_DAYS)
    return found


def _next_escalation_at(run: Run, clock: Clock) -> datetime | None:
    level = rules.next_level(clock.escalation_levels or [], clock.escalated_level or 0)
    if level is None or clock.due_at is None:
        return None
    return _point(run.calendar(clock.calendar_id), as_utc(clock.due_at), level["after_breach_minutes"])


def _schedule(run: Run, clock: Clock) -> None:
    """warn_at and due_at of a running clock from the business time used at run_started_at."""
    cal = run.calendar(clock.calendar_id)
    start, used = as_utc(clock.run_started_at), clock.business_minutes_used or 0
    clock.warn_at = _point(cal, start, rules.warning_minutes(clock.target_minutes, clock.warning_percent) - used)
    clock.due_at = _point(cal, start, clock.target_minutes - used)
    clock.next_escalation_at = _next_escalation_at(run, clock) if clock.breached else None


def _not_before(at: datetime, *times: datetime | None) -> datetime:
    known = [as_utc(t) for t in times if t is not None]
    return max([at, *known])


def _copy_policy(clock: Clock, policy: Policy) -> None:
    clock.policy_id = policy.id
    clock.calendar_id = policy.calendar_id
    clock.target_minutes = (
        policy.response_target_minutes if clock.kind == rules.RESPONSE else policy.resolution_target_minutes
    )
    clock.warning_percent = policy.warning_percent
    clock.pause_on_hold_reasons = list(policy.pause_on_hold_reasons or [])
    clock.escalation_levels = [dict(level) for level in policy.escalation_levels or []]


# ---------------------------------------------------------------- warnings, breaches, escalations


def catch_up(run: Run, clock: Clock, at: datetime) -> None:
    """Record what fell due on a running clock up to `at`: the warning, the breach and escalation levels."""
    if clock.state != rules.RUNNING:
        return
    warn_at, due_at = as_utc(clock.warn_at), as_utc(clock.due_at)
    if not clock.warned and warn_at is not None and warn_at <= at:
        clock.warned = True
        run.audit("clock.warning_raised", clock, warn_at)
        run.publish(
            "warning-raised",
            clock,
            {
                "ticket_number": clock.ticket_number,
                "kind": clock.kind,
                "priority": clock.priority,
                "assignee_id": clock.assignee_id,
                "due_at": iso(due_at),
            },
        )
    if not clock.breached and due_at is not None and due_at <= at:
        clock.breached, clock.breached_at = True, due_at
        run.audit("clock.breached", clock, due_at)
        run.publish(
            "breached",
            clock,
            {
                "ticket_number": clock.ticket_number,
                "kind": clock.kind,
                "priority": clock.priority,
                "assignee_id": clock.assignee_id,
                "due_at": iso(due_at),
                "breached_at": iso(due_at),
            },
        )
        clock.next_escalation_at = _next_escalation_at(run, clock)
    while clock.next_escalation_at is not None and as_utc(clock.next_escalation_at) <= at:
        fire_at = as_utc(clock.next_escalation_at)
        level = rules.next_level(clock.escalation_levels or [], clock.escalated_level or 0)
        if level is None:
            clock.next_escalation_at = None
            break
        people = rules.recipients(clock.escalation_levels or [], level["level"], clock.assignee_id)
        run.db.add(
            Escalation(
                id=new_id(),
                organisation_id=run.organisation_id,
                clock_id=clock.id,
                level=level["level"],
                sent_at=fire_at,
                recipient_ids=people,
            )
        )
        clock.escalated_level = level["level"]
        run.audit("clock.escalated", clock, fire_at, f"level {level['level']}")
        run.publish(
            "escalated",
            clock,
            {
                "ticket_number": clock.ticket_number,
                "kind": clock.kind,
                "level": level["level"],
                "recipient_ids": people,
                "escalated_at": iso(fire_at),
            },
        )
        clock.next_escalation_at = _next_escalation_at(run, clock)


# ---------------------------------------------------------------- moves


def start(run: Run, ref: TicketRef, kind: str, policy: Policy, at: datetime) -> Clock:
    """A new running clock of `kind` for the ticket under `policy`, from `at` (PRD main flow 3)."""
    clock = Clock(
        id=new_id(),
        organisation_id=run.organisation_id,
        ticket_id=ref.ticket_id,
        ticket_number=ref.number,
        kind=kind,
        priority=ref.priority,
        category_id=ref.category_id,
        queue_id=ref.queue_id,
        assignee_id=ref.assignee_id,
        business_minutes_used=0,
        run_started_at=at,
        state=rules.RUNNING,
        started_at=at,
        warned=False,
        breached=False,
        escalated_level=0,
    )
    _copy_policy(clock, policy)
    _schedule(run, clock)
    run.db.add(clock)
    run.audit("clock.started", clock, at)
    run.publish(
        "started",
        clock,
        {
            "ticket_number": clock.ticket_number,
            "kind": kind,
            "policy_id": policy.id,
            "priority": clock.priority,
            "target_minutes": clock.target_minutes,
            "started_at": iso(at),
            "warn_at": iso(clock.warn_at),
            "due_at": iso(clock.due_at),
        },
    )
    return clock


def pause(run: Run, clock: Clock, at: datetime) -> bool:
    if not rules.can("pause", clock.state, clock.kind):
        return False
    at = _not_before(at, clock.run_started_at)
    catch_up(run, clock, at)
    clock.business_minutes_used = live_used(clock, run.calendar(clock.calendar_id), at)
    clock.state, clock.paused_at, clock.run_started_at = rules.PAUSED, at, None
    clock.warn_at = clock.due_at = clock.next_escalation_at = None
    run.audit("clock.paused", clock, at)
    run.publish(
        "paused",
        clock,
        {"kind": clock.kind, "paused_at": iso(at), "business_minutes_used": clock.business_minutes_used},
    )
    return True


def resume(run: Run, clock: Clock, at: datetime, *, move: str = "resume") -> bool:
    """Off hold ("resume", from paused) or a reopened ticket ("reopen", a stopped resolution clock). The clock counts
    on from the business time already used, with a new due time."""
    if not rules.can(move, clock.state, clock.kind):
        return False
    at = _not_before(at, clock.paused_at, clock.stopped_at)
    clock.state, clock.paused_at, clock.run_started_at = rules.RUNNING, None, at
    if move == "reopen":
        clock.stopped_at, clock.outcome = None, None
    _schedule(run, clock)
    run.audit("clock.reopened" if move == "reopen" else "clock.resumed", clock, at)
    run.publish(
        "resumed",
        clock,
        {"kind": clock.kind, "resumed_at": iso(at), "warn_at": iso(clock.warn_at), "due_at": iso(clock.due_at)},
    )
    catch_up(run, clock, at)
    return True


def recalculate(run: Run, clock: Clock, policy: Policy, at: datetime) -> bool:
    """A running or paused clock moves to `policy`, keeping the business time used (PRD main flow 6). Running clocks
    get a new due time in the new policy's calendar; paused ones get theirs when resumed."""
    if clock.state not in rules.OPEN_STATES or clock.policy_id == policy.id:
        return False
    previous = clock.policy_id
    running = clock.state == rules.RUNNING
    if running:
        at = _not_before(at, clock.run_started_at)
        catch_up(run, clock, at)
        clock.business_minutes_used = live_used(clock, run.calendar(clock.calendar_id), at)
        clock.run_started_at = at
    _copy_policy(clock, policy)
    if running:
        _schedule(run, clock)
    run.audit("clock.recalculated", clock, at)
    run.publish(
        "recalculated",
        clock,
        {
            "kind": clock.kind,
            "policy_id": policy.id,
            "previous_policy_id": previous,
            "target_minutes": clock.target_minutes,
            "warn_at": iso(clock.warn_at),
            "due_at": iso(clock.due_at),
        },
    )
    if running:
        catch_up(run, clock, at)
    return True


def stop(run: Run, clock: Clock, at: datetime) -> bool:
    """The first response (response clock) or resolution (both): outcome met, or breached when the due time passed
    first."""
    if not rules.can("stop", clock.state, clock.kind):
        return False
    at = _not_before(at, clock.run_started_at, clock.paused_at)
    catch_up(run, clock, at)
    clock.business_minutes_used = live_used(clock, run.calendar(clock.calendar_id), at)
    clock.state, clock.stopped_at, clock.outcome = rules.STOPPED, at, rules.outcome(clock.breached)
    clock.paused_at = clock.run_started_at = clock.next_escalation_at = None
    run.audit("clock.stopped", clock, at, clock.outcome)
    run.publish(
        "stopped",
        clock,
        {
            "kind": clock.kind,
            "outcome": clock.outcome,
            "stopped_at": iso(at),
            "business_minutes_used": clock.business_minutes_used,
        },
    )
    return True


def cancel(run: Run, clock: Clock, at: datetime) -> bool:
    """The ticket was cancelled: the clock stops counting and has no outcome. stopped_at records when."""
    if not rules.can("cancel", clock.state, clock.kind):
        return False
    at = _not_before(at, clock.run_started_at, clock.paused_at)
    catch_up(run, clock, at)
    clock.business_minutes_used = live_used(clock, run.calendar(clock.calendar_id), at)
    clock.state, clock.stopped_at, clock.outcome = rules.CANCELLED, at, None
    clock.paused_at = clock.run_started_at = clock.next_escalation_at = None
    run.audit("clock.cancelled", clock, at)
    run.publish("cancelled", clock, {"kind": clock.kind, "cancelled_at": iso(at)})
    return True


# ---------------------------------------------------------------- the due-clock check


def check_due(db: Session, organisation_id: str, now: datetime, limit: int = 500) -> int:
    """Record the warnings, breaches and escalations due by `now` on the organisation's running clocks; returns how
    many clocks were checked. Each clock's ticket is locked first, as a helpdesk event for it would."""
    run = Run(db, organisation_id, "check")
    checked = 0
    for clock in repo.clocks_to_check(db, now, limit):
        repo.ticket_ref(db, organisation_id, clock.ticket_id, create=False)
        db.refresh(clock)
        catch_up(run, clock, now)
        checked += 1
    return checked
