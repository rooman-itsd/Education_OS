"""Use cases of maintenance (docs/prd.md). Each one checks permissions and rules, changes state, and publishes the
matching event from contracts/events.yaml to the outbox in the same transaction. Until the audit SDK exists, the
outbox is the audit trail (PRD rule 11)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.orm import Session

from ..domain.rules import (
    FINISHED_STATUSES,
    OPEN_STATUSES,
    RuleViolationError,
    SlaHours,
    add_interval,
    auto_close_due,
    breaches,
    check_assign,
    check_cancel,
    check_close,
    check_editable,
    check_hold,
    check_reopen,
    check_resolve,
    check_start,
    check_target,
    check_work_entry,
    due_times,
    effective_sla,
    format_money,
    initial_status,
    money,
    reopen_status,
    same_target,
    should_raise,
    sort_key,
)
from ..infrastructure import repository as repo
from ..infrastructure.config import ModuleSettings, load_settings
from ..infrastructure.models import Category, Schedule, Ticket, WorkEntry, as_utc, iso

MODULE = "maintenance"
TICKET_CREATE = f"{MODULE}:ticket:create"
TICKET_READ = f"{MODULE}:ticket:read"
TICKET_READ_ALL = f"{MODULE}:ticket:read-all"
TICKET_WORK = f"{MODULE}:ticket:work"
TICKET_MANAGE = f"{MODULE}:ticket:manage"
SCHEDULE_MANAGE = f"{MODULE}:schedule:manage"

SCHEDULER = "scheduler"  # reported_by of tickets a schedule raised on its own


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


class MaintenanceError(Exception):
    """A refusal with an HTTP status and a contract error body ({code, message})."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def body(self) -> dict:
        return {"code": self.code, "message": self.message}


def _not_found(what: str) -> MaintenanceError:
    return MaintenanceError(404, "not_found", f"{what} not found in your organisation")


def _forbidden(message: str) -> MaintenanceError:
    return MaintenanceError(403, "forbidden", message)


def _rule(v: RuleViolationError) -> MaintenanceError:
    return MaintenanceError(v.status, v.code, v.message)


def _publish(db: Session, actor: Actor | None, name: str, organisation_id: str, payload: dict) -> None:
    events.publish(
        db,
        f"{MODULE}.{name}",
        organisation_id,
        {"organisation_id": organisation_id, **payload},
        actor=actor.user_id if actor else None,
    )


def _get(db: Session, model, row_id: str | None, what: str):
    row = repo.get(db, model, row_id)
    if row is None:
        raise _not_found(what)
    return row


# ---------------------------------------------------------------- who may do what


def _is_manager(actor: Actor) -> bool:
    return actor.can(TICKET_MANAGE)


def _has_assignee(t: Ticket) -> bool:
    return bool(t.assignee_id or t.vendor)


def _works_on(actor: Actor, t: Ticket) -> bool:
    """The assigned technician with maintenance:ticket:work, or a manager (who also acts for vendors)."""
    return _is_manager(actor) or (actor.can(TICKET_WORK) and t.assignee_id == actor.user_id)


def _is_reporter(actor: Actor, t: Ticket) -> bool:
    return t.reported_by == actor.user_id


def _visible(actor: Actor, t: Ticket) -> bool:
    return actor.can(TICKET_READ_ALL) or actor.user_id in (t.reported_by, t.assignee_id)


def _ticket_for(db: Session, actor: Actor, ticket_id: str, *, lock: bool = False) -> Ticket:
    t = repo.get_for_update(db, Ticket, ticket_id) if lock else repo.get(db, Ticket, ticket_id)
    if t is None or not _visible(actor, t):
        raise _not_found("ticket")
    return t


def allowed_actions(actor: Actor, t: Ticket, settings: ModuleSettings, now: datetime) -> list[str]:
    manager, works, reporter = _is_manager(actor), _works_on(actor, t), _is_reporter(actor, t)
    can: list[str] = []
    if manager and t.status not in FINISHED_STATUSES:
        can.append("edit")
    if manager and t.status in OPEN_STATUSES:
        can.append("assign")
    if works and ((t.status == "assigned" and _has_assignee(t)) or t.status == "on_hold"):
        can.append("start")
    if works and t.status == "in_progress":
        can += ["hold", "resolve"]
    if (reporter or manager) and t.status == "resolved":
        can.append("close")
    if (reporter or manager) and t.status in ("resolved", "closed") and t.resolved_at:
        if now <= as_utc(t.resolved_at) + timedelta(days=settings.reopen_window_days):
            can.append("reopen")
    if (manager and t.status in OPEN_STATUSES) or (reporter and t.status in ("open", "assigned")):
        can.append("cancel")
    if works and t.status not in FINISHED_STATUSES:
        can.append("log_work")
    return can


# ---------------------------------------------------------------- shapes


def _target(kind: str, target_id: str | None, label: str) -> dict:
    return {"kind": kind, "id": target_id or "", "label": label}


def _ticket_target(t: Ticket) -> dict:
    return _target(t.target_kind, t.target_id, t.target_label)


def _sla(db: Session, category_id: str, settings: ModuleSettings) -> SlaHours:
    category = db.get(Category, category_id)
    return effective_sla(settings.sla, category.sla_override if category else None)


def _breaches(t: Ticket, now: datetime) -> list[str]:
    return breaches(
        status=t.status,
        now=now,
        response_due_at=as_utc(t.response_due_at),
        resolution_due_at=as_utc(t.resolution_due_at),
        started_at=as_utc(t.started_at),
        resolved_at=as_utc(t.resolved_at),
        flagged=(t.response_breached, t.resolution_breached),
    )


def _totals(entries: list[WorkEntry], currency: str) -> tuple[int, dict]:
    minutes = sum(e.minutes or 0 for e in entries if e.kind == "time")
    cost = sum((Decimal(e.cost_amount) for e in entries if e.cost_amount is not None), Decimal("0"))
    return minutes, {"amount": format_money(cost), "currency": currency}


def category_dict(c: Category) -> dict:
    return {
        "id": c.id,
        "organisation_id": c.organisation_id,
        "name": c.name,
        "description": c.description,
        "default_priority": c.default_priority,
        "default_assignee_ids": list(c.default_assignee_ids or []),
        "sla_override": c.sla_override or {},
        "active": c.active,
    }


def entry_dict(e: WorkEntry) -> dict:
    cost = None
    if e.cost_amount is not None:
        cost = {"amount": format_money(Decimal(e.cost_amount)), "currency": e.cost_currency}
    return {
        "id": e.id,
        "ticket_id": e.ticket_id,
        "kind": e.kind,
        "note": e.note,
        "minutes": e.minutes,
        "item_id": e.item_id,
        "item_name": e.item_name,
        "quantity": e.quantity,
        "cost": cost,
        "document_id": e.document_id,
        "recorded_by": e.recorded_by,
        "recorded_at": iso(e.created_at),
    }


def ticket_dict(
    db: Session,
    actor: Actor,
    t: Ticket,
    settings: ModuleSettings | None = None,
    *,
    detail: bool = False,
    category_names: dict[str, str] | None = None,
) -> dict:
    settings = settings or load_settings()
    now = clock()
    entries = repo.entries_of(db, t.id)
    minutes, cost = _totals(entries, settings.default_currency)
    if category_names is not None:
        category_name = category_names.get(t.category_id)
    else:
        category = db.get(Category, t.category_id)
        category_name = category.name if category else None
    out = {
        "id": t.id,
        "organisation_id": t.organisation_id,
        "number": t.number,
        "kind": t.kind,
        "title": t.title,
        "description": t.description,
        "category_id": t.category_id,
        "category_name": category_name,
        "target": _ticket_target(t),
        "priority": t.priority,
        "status": t.status,
        "blocks_use": t.blocks_use,
        "reported_by": t.reported_by,
        "assignee_id": t.assignee_id,
        "vendor": t.vendor,
        "hold_reason": t.hold_reason,
        "schedule_id": t.schedule_id,
        "source": t.source,
        "response_due_at": iso(t.response_due_at),
        "resolution_due_at": iso(t.resolution_due_at),
        "sla_breached": _breaches(t, now),
        "started_at": iso(t.started_at),
        "resolved_at": iso(t.resolved_at),
        "closed_at": iso(t.closed_at),
        "total_minutes": minutes,
        "total_cost": cost,
        "created_at": iso(t.created_at),
        "updated_at": iso(t.updated_at),
        "can": allowed_actions(actor, t, settings, now),
    }
    if detail:
        out |= {
            "photo_document_ids": list(t.photo_document_ids or []),
            "checklist": list(t.checklist or []),
            "resolution": t.resolution,
            "work_entries": [entry_dict(e) for e in entries],
        }
    return out


def schedule_dict(db: Session, s: Schedule, *, detail: bool = False) -> dict:
    open_ticket = repo.ticket_unscoped(db, s.open_ticket_id)
    out = {
        "id": s.id,
        "organisation_id": s.organisation_id,
        "title": s.title,
        "description": s.description,
        "category_id": s.category_id,
        "target": _target(s.target_kind, s.target_id, s.target_label),
        "kind": s.kind,
        "every": s.every,
        "unit": s.unit,
        "next_due_on": s.next_due_on.isoformat(),
        "lead_days": s.lead_days,
        "priority": s.priority,
        "default_assignee_id": s.default_assignee_id,
        "checklist": list(s.checklist or []),
        "active": s.active,
        "open_ticket_id": open_ticket.id if open_ticket and open_ticket.status in OPEN_STATUSES else None,
        "last_completed_on": s.last_completed_on.isoformat() if s.last_completed_on else None,
        "created_at": iso(s.created_at),
    }
    if detail:
        out["recent_tickets"] = [
            {"id": t.id, "number": t.number, "status": t.status, "created_at": iso(t.created_at)}
            for t in repo.tickets_of_schedule(db, s.id)
        ]
    return out


# ---------------------------------------------------------------- categories


def list_categories(db: Session) -> list[dict]:
    return [category_dict(c) for c in repo.all_of(db, Category, Category.name)]


def _check_sla_override(data: dict) -> None:
    for key in ("response_hours", "resolution_hours"):
        for priority in (data.get("sla_override") or {}).get(key) or {}:
            if priority not in ("low", "medium", "high", "urgent"):
                raise MaintenanceError(422, "invalid_sla", f"unknown priority {priority!r} in {key}")


def create_category(db: Session, actor: Actor, data: dict) -> dict:
    if repo.first_by(db, Category, "name", data["name"]):
        raise MaintenanceError(409, "name_taken", "a category with this name already exists")
    _check_sla_override(data)
    c = Category(organisation_id=actor.organisation_id, **data)
    db.add(c)
    db.commit()
    return category_dict(c)


def update_category(db: Session, actor: Actor, category_id: str, data: dict) -> dict:
    c = _get(db, Category, category_id, "category")
    if "name" in data and data["name"] != c.name and repo.first_by(db, Category, "name", data["name"]):
        raise MaintenanceError(409, "name_taken", "a category with this name already exists")
    _check_sla_override(data)
    for key, value in data.items():
        setattr(c, key, value)
    db.commit()
    return category_dict(c)


def _active_category(db: Session, category_id: str) -> Category:
    c = repo.get(db, Category, category_id)
    if c is None or not c.active:
        raise MaintenanceError(422, "unknown_category", "unknown or inactive category")
    return c


# ---------------------------------------------------------------- raising tickets


def _new_ticket(
    db: Session,
    actor: Actor | None,
    *,
    organisation_id: str,
    reported_by: str,
    category: Category,
    kind: str,
    title: str,
    description: str | None,
    target: dict,
    priority: str | None,
    blocks_use: bool,
    settings: ModuleSettings,
    now: datetime,
    photo_document_ids: list | None = None,
    source: dict | None = None,
    schedule_id: str | None = None,
    checklist: list | None = None,
    assignee_id: str | None = None,
) -> Ticket:
    if assignee_id:
        status = "assigned"
    else:
        status, assignee_id = initial_status(category.default_assignee_ids)
    priority = priority or category.default_priority or "medium"
    response_due, resolution_due = due_times(now, priority, effective_sla(settings.sla, category.sla_override))
    t = Ticket(
        organisation_id=organisation_id,
        number=repo.next_number(db, organisation_id, now.year),
        kind=kind,
        title=title,
        description=description,
        category_id=category.id,
        target_kind=target["kind"],
        target_id=target.get("id") or None,
        target_label=target["label"],
        priority=priority,
        status=status,
        blocks_use=blocks_use,
        reported_by=reported_by,
        assignee_id=assignee_id,
        schedule_id=schedule_id,
        source=source,
        photo_document_ids=list(photo_document_ids or []),
        checklist=list(checklist or []),
        response_due_at=response_due,
        resolution_due_at=resolution_due,
        created_at=now,
        updated_at=now,
    )
    db.add(t)
    db.flush()
    _publish(
        db,
        actor,
        "ticket.raised",
        organisation_id,
        {
            "ticket_id": t.id,
            "number": t.number,
            "kind": t.kind,
            "category_id": t.category_id,
            "priority": t.priority,
            "target": _ticket_target(t),
            "blocks_use": t.blocks_use,
            "reported_by": t.reported_by,
            "schedule_id": t.schedule_id,
            "source": t.source,
        },
    )
    if assignee_id:
        _publish(
            db,
            actor,
            "ticket.assigned",
            organisation_id,
            {"ticket_id": t.id, "assignee_id": assignee_id, "vendor_name": None, "previous_assignee_id": None},
        )
    return t


def _possible_duplicates(db: Session, category_id: str, target: dict) -> list[str]:
    key = (target["kind"], target.get("id") or None, target["label"])
    return [
        t.id
        for t in repo.open_tickets_in_category(db, category_id)
        if same_target(key, (t.target_kind, t.target_id, t.target_label))
    ]


def raise_ticket(db: Session, actor: Actor, data: dict) -> dict:
    settings = load_settings()
    category = _active_category(db, data["category_id"])
    target = data["target"]
    try:
        check_target(target["kind"], target.get("id"), target.get("label"))
    except RuleViolationError as v:
        raise _rule(v) from v
    duplicates = _possible_duplicates(db, category.id, target)
    t = _new_ticket(
        db,
        actor,
        organisation_id=actor.organisation_id,
        reported_by=actor.user_id,
        category=category,
        kind=data.get("kind") or "corrective",
        title=data["title"],
        description=data.get("description"),
        target=target,
        priority=data.get("priority"),
        blocks_use=bool(data.get("blocks_use")),
        settings=settings,
        now=clock(),
        photo_document_ids=data.get("photo_document_ids"),
        source=data.get("source"),
    )
    db.commit()
    return {"ticket": ticket_dict(db, actor, t, settings), "possible_duplicates": duplicates}


# ---------------------------------------------------------------- reading tickets


def list_tickets(db: Session, actor: Actor, q: dict, page: int, page_size: int) -> dict:
    settings = load_settings()
    now = clock()
    scope = q.get("scope") or "mine"
    tickets = repo.tickets(db)
    if scope == "mine":
        tickets = [t for t in tickets if t.reported_by == actor.user_id]
    elif scope == "assigned":
        tickets = [t for t in tickets if t.assignee_id == actor.user_id]
    elif not actor.can(TICKET_READ_ALL):
        raise _forbidden(f"scope=managed requires {TICKET_READ_ALL}")
    if q.get("status"):
        tickets = [t for t in tickets if t.status in set(q["status"])]
    if q.get("open"):
        tickets = [t for t in tickets if t.status in OPEN_STATUSES]
    if q.get("priority"):
        tickets = [t for t in tickets if t.priority in set(q["priority"])]
    for key, attr in (
        ("kind", "kind"),
        ("category_id", "category_id"),
        ("target_kind", "target_kind"),
        ("target_id", "target_id"),
        ("assignee_id", "assignee_id"),
    ):
        if q.get(key):
            tickets = [t for t in tickets if getattr(t, attr) == q[key]]
    if q.get("sla_breached") is not None:
        tickets = [t for t in tickets if bool(_breaches(t, now)) == q["sla_breached"]]
    if q.get("q"):
        needle = q["q"].lower()
        tickets = [t for t in tickets if needle in f"{t.number} {t.title} {t.target_label}".lower()]
    tickets.sort(key=lambda t: sort_key(t.priority, bool(_breaches(t, now)), as_utc(t.created_at)))
    total = len(tickets)
    names = {c.id: c.name for c in repo.all_of(db, Category)}
    chunk = tickets[(page - 1) * page_size : page * page_size]
    return {
        "items": [ticket_dict(db, actor, t, settings, category_names=names) for t in chunk],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_ticket(db: Session, actor: Actor, ticket_id: str) -> dict:
    return ticket_dict(db, actor, _ticket_for(db, actor, ticket_id), detail=True)


# ---------------------------------------------------------------- triage and assignment


def update_ticket(db: Session, actor: Actor, ticket_id: str, data: dict) -> dict:
    settings = load_settings()
    t = _ticket_for(db, actor, ticket_id, lock=True)
    try:
        check_editable(t.status)
        if "target" in data:
            target = data.pop("target")
            check_target(target["kind"], target.get("id"), target.get("label"))
            t.target_kind, t.target_id, t.target_label = target["kind"], target.get("id") or None, target["label"]
    except RuleViolationError as v:
        raise _rule(v) from v
    if "category_id" in data:
        t.category_id = _active_category(db, data.pop("category_id")).id
    old_priority = t.priority
    for key in ("title", "description", "priority", "blocks_use"):
        if key in data:
            setattr(t, key, data[key])
    if t.priority != old_priority:
        sla = _sla(db, t.category_id, settings)
        created = as_utc(t.created_at)
        t.response_due_at = due_times(created, t.priority, sla)[0]
        t.resolution_due_at = due_times(created, t.priority, sla, t.held_minutes)[1]
        _publish(
            db,
            actor,
            "ticket.priority-changed",
            t.organisation_id,
            {
                "ticket_id": t.id,
                "from": old_priority,
                "to": t.priority,
                "response_due_at": iso(t.response_due_at),
                "resolution_due_at": iso(t.resolution_due_at),
            },
        )
    t.updated_at = clock()
    db.commit()
    return ticket_dict(db, actor, t, settings)


def assign_ticket(db: Session, actor: Actor, ticket_id: str, data: dict) -> dict:
    t = _ticket_for(db, actor, ticket_id, lock=True)
    try:
        t.status = check_assign(t.status)
    except RuleViolationError as v:
        raise _rule(v) from v
    previous = t.assignee_id
    vendor = data.get("vendor")
    t.assignee_id = None if vendor else data.get("assignee_id")
    t.vendor = vendor
    if data.get("note"):
        _add_entry(db, actor, t, {"kind": "note", "note": f"Assigned: {data['note']}"})
    t.updated_at = clock()
    _publish(
        db,
        actor,
        "ticket.assigned",
        t.organisation_id,
        {
            "ticket_id": t.id,
            "assignee_id": t.assignee_id,
            "vendor_name": vendor["name"] if vendor else None,
            "previous_assignee_id": previous,
        },
    )
    db.commit()
    return ticket_dict(db, actor, t)


# ---------------------------------------------------------------- doing the work


def _require_worker(actor: Actor, t: Ticket) -> None:
    if not _works_on(actor, t):
        raise _forbidden(f"only the assignee with {TICKET_WORK}, or {TICKET_MANAGE}, can do this")


def _flag_breach(db: Session, actor: Actor | None, t: Ticket, which: str) -> None:
    """Publish maintenance.ticket.sla-breached once per target (rule 2)."""
    attr = f"{which}_breached"
    if getattr(t, attr):
        return
    setattr(t, attr, True)
    due = t.response_due_at if which == "response" else t.resolution_due_at
    _publish(
        db,
        actor,
        "ticket.sla-breached",
        t.organisation_id,
        {
            "ticket_id": t.id,
            "number": t.number,
            "which": which,
            "due_at": iso(due),
            "priority": t.priority,
            "assignee_id": t.assignee_id,
        },
    )


def start_ticket(db: Session, actor: Actor, ticket_id: str) -> dict:
    t = _ticket_for(db, actor, ticket_id, lock=True)
    _require_worker(actor, t)
    now = clock()
    resuming = t.status == "on_hold"
    try:
        t.status = check_start(t.status, _has_assignee(t))
    except RuleViolationError as v:
        raise _rule(v) from v
    if resuming and t.held_since:
        paused = now - as_utc(t.held_since)
        t.held_minutes += int(paused.total_seconds() // 60)
        t.resolution_due_at = as_utc(t.resolution_due_at) + paused  # time on hold does not count
    t.hold_reason, t.held_since = None, None
    if t.started_at is None:
        t.started_at = now
        if now > as_utc(t.response_due_at):
            _flag_breach(db, actor, t, "response")
    t.updated_at = now
    _publish(
        db,
        actor,
        "ticket.started",
        t.organisation_id,
        {"ticket_id": t.id, "target": _ticket_target(t), "blocks_use": t.blocks_use, "started_by": actor.user_id},
    )
    db.commit()
    return ticket_dict(db, actor, t)


def hold_ticket(db: Session, actor: Actor, ticket_id: str, reason: str, note: str | None) -> dict:
    t = _ticket_for(db, actor, ticket_id, lock=True)
    _require_worker(actor, t)
    try:
        t.status = check_hold(t.status, reason)
    except RuleViolationError as v:
        raise _rule(v) from v
    now = clock()
    t.hold_reason, t.held_since, t.updated_at = reason, now, now
    if note:
        _add_entry(db, actor, t, {"kind": "note", "note": f"On hold: {note}"})
    _publish(db, actor, "ticket.put-on-hold", t.organisation_id, {"ticket_id": t.id, "reason": reason})
    db.commit()
    return ticket_dict(db, actor, t)


def resolve_ticket(db: Session, actor: Actor, ticket_id: str, data: dict) -> dict:
    settings = load_settings()
    t = _ticket_for(db, actor, ticket_id, lock=True)
    _require_worker(actor, t)
    try:
        t.status = check_resolve(t.status, data.get("note"))
    except RuleViolationError as v:
        raise _rule(v) from v
    now = clock()
    usable = data.get("target_usable", True)
    t.resolution = {"note": data["note"], "root_cause": data.get("root_cause"), "target_usable": usable}
    if data.get("checklist") is not None:
        t.checklist = data["checklist"]
    t.resolved_at, t.updated_at = now, now
    if now > as_utc(t.resolution_due_at):
        _flag_breach(db, actor, t, "resolution")
    if t.schedule_id:
        s = db.get(Schedule, t.schedule_id)
        if s is not None:
            s.last_completed_on = now.date()
            if s.open_ticket_id == t.id:
                s.open_ticket_id = None
    minutes, cost = _totals(repo.entries_of(db, t.id), settings.default_currency)
    _publish(
        db,
        actor,
        "ticket.resolved",
        t.organisation_id,
        {
            "ticket_id": t.id,
            "target": _ticket_target(t),
            "blocks_use": t.blocks_use,
            "target_usable": usable,
            "total_minutes": minutes,
            "total_cost": cost,
            "resolved_by": actor.user_id,
        },
    )
    db.commit()
    return ticket_dict(db, actor, t, settings)


def _close(db: Session, actor: Actor | None, t: Ticket, closed_by: str, rating: int | None, feedback: str | None):
    t.status = check_close(t.status)
    now = clock()
    t.closed_at, t.updated_at, t.rating, t.feedback = now, now, rating, feedback
    _publish(
        db, actor, "ticket.closed", t.organisation_id, {"ticket_id": t.id, "closed_by": closed_by, "rating": rating}
    )


def close_ticket(db: Session, actor: Actor, ticket_id: str, data: dict) -> dict:
    t = _ticket_for(db, actor, ticket_id, lock=True)
    reporter = _is_reporter(actor, t)
    if not (reporter or _is_manager(actor)):
        raise _forbidden(f"only the reporter or {TICKET_MANAGE} can close a ticket")
    try:
        _close(db, actor, t, "reporter" if reporter else "manager", data.get("rating"), data.get("feedback"))
    except RuleViolationError as v:
        raise _rule(v) from v
    db.commit()
    return ticket_dict(db, actor, t)


def reopen_ticket(db: Session, actor: Actor, ticket_id: str, reason: str) -> dict:
    settings = load_settings()
    t = _ticket_for(db, actor, ticket_id, lock=True)
    if not (_is_reporter(actor, t) or _is_manager(actor)):
        raise _forbidden(f"only the reporter or {TICKET_MANAGE} can reopen a ticket")
    now = clock()
    try:
        check_reopen(t.status, as_utc(t.resolved_at), now, settings.reopen_window_days)
    except RuleViolationError as v:
        raise _rule(v) from v
    t.status = reopen_status(_has_assignee(t))
    t.resolved_at, t.closed_at, t.resolution, t.updated_at = None, None, None, now
    _add_entry(db, actor, t, {"kind": "note", "note": f"Reopened: {reason}"})
    if t.schedule_id:
        s = db.get(Schedule, t.schedule_id)
        if s is not None and s.open_ticket_id is None:
            s.open_ticket_id = t.id
    _publish(
        db,
        actor,
        "ticket.reopened",
        t.organisation_id,
        {
            "ticket_id": t.id,
            "target": _ticket_target(t),
            "blocks_use": t.blocks_use,
            "reason": reason,
            "reopened_by": actor.user_id,
        },
    )
    db.commit()
    return ticket_dict(db, actor, t, settings)


def cancel_ticket(db: Session, actor: Actor, ticket_id: str, reason: str, duplicate_of: str | None) -> dict:
    t = _ticket_for(db, actor, ticket_id, lock=True)
    manager = _is_manager(actor)
    if not (manager or _is_reporter(actor, t)):
        raise _forbidden(f"only the reporter or {TICKET_MANAGE} can cancel a ticket")
    try:
        t.status = check_cancel(t.status, manager=manager)
    except RuleViolationError as v:
        raise _rule(v) from v
    if duplicate_of and (duplicate_of == t.id or repo.get(db, Ticket, duplicate_of) is None):
        raise MaintenanceError(422, "invalid_duplicate", "duplicate_of must be another ticket in your organisation")
    t.updated_at = clock()
    _add_entry(db, actor, t, {"kind": "note", "note": f"Cancelled: {reason}"})
    if t.schedule_id:
        s = db.get(Schedule, t.schedule_id)
        if s is not None and s.open_ticket_id == t.id:
            s.open_ticket_id = None
    _publish(
        db,
        actor,
        "ticket.cancelled",
        t.organisation_id,
        {"ticket_id": t.id, "target": _ticket_target(t), "reason": reason, "duplicate_of": duplicate_of},
    )
    db.commit()
    return ticket_dict(db, actor, t)


# ---------------------------------------------------------------- work log


def _add_entry(db: Session, actor: Actor, t: Ticket, data: dict, cost: Decimal | None = None) -> WorkEntry:
    e = WorkEntry(
        organisation_id=t.organisation_id,
        ticket_id=t.id,
        position=repo.next_position(db, t.id),
        kind=data["kind"],
        note=data.get("note"),
        minutes=data.get("minutes"),
        item_id=data.get("item_id"),
        item_name=data.get("item_name"),
        quantity=data.get("quantity"),
        cost_amount=cost,
        cost_currency=data["cost"]["currency"] if cost is not None else None,
        document_id=data.get("document_id"),
        recorded_by=actor.user_id,
        created_at=clock(),
    )
    db.add(e)
    db.flush()
    return e


def list_entries(db: Session, actor: Actor, ticket_id: str) -> list[dict]:
    t = _ticket_for(db, actor, ticket_id)
    return [entry_dict(e) for e in repo.entries_of(db, t.id)]


def add_entry(db: Session, actor: Actor, ticket_id: str, data: dict) -> dict:
    settings = load_settings()
    t = _ticket_for(db, actor, ticket_id, lock=True)
    cost = None
    try:
        check_editable(t.status)
        check_work_entry(data["kind"], data, can_work=_works_on(actor, t))
        if data.get("cost"):
            if not _works_on(actor, t):
                raise RuleViolationError("forbidden", "only people who work on the ticket can log a cost", 403)
            cost = money(data["cost"]["amount"], data["cost"]["currency"])
            if data["cost"]["currency"] != settings.default_currency:
                raise RuleViolationError(
                    "currency_mismatch", f"costs are recorded in {settings.default_currency} in this organisation"
                )
    except RuleViolationError as v:
        raise _rule(v) from v
    e = _add_entry(db, actor, t, data, cost)
    t.updated_at = clock()
    db.commit()
    return entry_dict(e)


# ---------------------------------------------------------------- preventive schedules


def _has_open_ticket(db: Session, s: Schedule) -> bool:
    t = repo.ticket_unscoped(db, s.open_ticket_id)
    return t is not None and t.status in OPEN_STATUSES


def raise_from_schedule(db: Session, actor: Actor | None, s: Schedule, settings: ModuleSettings) -> Ticket:
    """Raise the ticket for the schedule's next due date, then move the due date on by one interval from the
    scheduled date (rule 7). The caller has checked there is no open ticket."""
    category = db.get(Category, s.category_id)
    due_on = s.next_due_on
    t = _new_ticket(
        db,
        actor,
        organisation_id=s.organisation_id,
        reported_by=actor.user_id if actor else SCHEDULER,
        category=category,
        kind=s.kind,
        title=s.title,
        description=f"{s.description or ''}\nDue on {due_on.isoformat()}.".strip(),
        target=_target(s.target_kind, s.target_id, s.target_label),
        priority=s.priority,
        blocks_use=False,
        settings=settings,
        now=clock(),
        schedule_id=s.id,
        checklist=[{"step": step, "done": False} for step in (s.checklist or [])],
        assignee_id=s.default_assignee_id,
    )
    s.open_ticket_id = t.id
    s.next_due_on = add_interval(due_on, s.every, s.unit)
    return t


def list_schedules(db: Session, q: dict) -> list[dict]:
    out = repo.schedules(db)
    if q.get("active") is not None:
        out = [s for s in out if s.active == q["active"]]
    if q.get("target_kind"):
        out = [s for s in out if s.target_kind == q["target_kind"]]
    if q.get("target_id"):
        out = [s for s in out if s.target_id == q["target_id"]]
    if q.get("due_before"):
        out = [s for s in out if s.next_due_on < q["due_before"]]
    return [schedule_dict(db, s) for s in out]


def _apply_schedule_fields(db: Session, s: Schedule, data: dict, settings: ModuleSettings) -> None:
    try:
        if "target" in data:
            target = data.pop("target")
            check_target(target["kind"], target.get("id"), target.get("label"))
            s.target_kind, s.target_id, s.target_label = target["kind"], target.get("id") or None, target["label"]
        if "category_id" in data:
            s.category_id = _active_category(db, data.pop("category_id")).id
        for key, value in data.items():
            setattr(s, key, value)
        if s.lead_days is None:
            s.lead_days = settings.default_lead_days
        add_interval(s.next_due_on, s.every, s.unit)  # validates the interval
    except RuleViolationError as v:
        raise _rule(v) from v


def create_schedule(db: Session, actor: Actor, data: dict) -> dict:
    settings = load_settings()
    s = Schedule(organisation_id=actor.organisation_id, created_at=clock(), updated_at=clock())
    _apply_schedule_fields(db, s, dict(data), settings)
    db.add(s)
    db.flush()
    _publish(
        db,
        actor,
        "schedule.created",
        s.organisation_id,
        {
            "schedule_id": s.id,
            "target": _target(s.target_kind, s.target_id, s.target_label),
            "every": s.every,
            "unit": s.unit,
            "next_due_on": s.next_due_on.isoformat(),
        },
    )
    db.commit()
    return schedule_dict(db, s)


def get_schedule(db: Session, schedule_id: str) -> dict:
    return schedule_dict(db, _get(db, Schedule, schedule_id, "schedule"), detail=True)


def _deactivated(db: Session, actor: Actor, s: Schedule, deleted: bool) -> None:
    _publish(
        db,
        actor,
        "schedule.deactivated",
        s.organisation_id,
        {"schedule_id": s.id, "target": _target(s.target_kind, s.target_id, s.target_label), "deleted": deleted},
    )


def update_schedule(db: Session, actor: Actor, schedule_id: str, data: dict) -> dict:
    s = _get(db, Schedule, schedule_id, "schedule")
    was_active = s.active
    _apply_schedule_fields(db, s, dict(data), load_settings())
    s.updated_at = clock()
    if was_active and not s.active:
        _deactivated(db, actor, s, deleted=False)
    db.commit()
    return schedule_dict(db, s)


def delete_schedule(db: Session, actor: Actor, schedule_id: str) -> None:
    s = _get(db, Schedule, schedule_id, "schedule")
    _deactivated(db, actor, s, deleted=True)
    db.delete(s)  # tickets it raised stay; their schedule_id is a plain reference
    db.commit()


def raise_now(db: Session, actor: Actor, schedule_id: str) -> dict:
    s = _get(db, Schedule, schedule_id, "schedule")
    if _has_open_ticket(db, s):
        raise MaintenanceError(409, "open_ticket_exists", "the schedule already has an open ticket")
    t = raise_from_schedule(db, actor, s, load_settings())
    db.commit()
    return ticket_dict(db, actor, t)


# ---------------------------------------------------------------- widget summary


def summary(db: Session, actor: Actor) -> dict:
    now = clock()
    tickets = repo.tickets(db)
    if not actor.can(TICKET_READ_ALL):
        tickets = [t for t in tickets if t.assignee_id == actor.user_id]
    open_ = [t for t in tickets if t.status in OPEN_STATUSES]
    due_7 = 0
    if actor.can(SCHEDULE_MANAGE) or actor.can(TICKET_READ_ALL):
        horizon: date = (now + timedelta(days=7)).date()
        due_7 = sum(1 for s in repo.schedules(db) if s.active and s.next_due_on <= horizon)
    return {
        "open": len(open_),
        "unassigned": sum(1 for t in open_ if t.status == "open"),
        "in_progress": sum(1 for t in open_ if t.status == "in_progress"),
        "on_hold": sum(1 for t in open_ if t.status == "on_hold"),
        "urgent_open": sum(1 for t in open_ if t.priority == "urgent"),
        "sla_breached_open": sum(1 for t in open_ if _breaches(t, now)),
        "resolved_awaiting_confirmation": sum(1 for t in tickets if t.status == "resolved"),
        "preventive_due_7_days": due_7,
    }


# ---------------------------------------------------------------- used by the scheduler sweeps


def flag_breaches(db: Session, t: Ticket, now: datetime) -> int:
    """Flag targets that have passed while their timer runs. Returns how many were newly flagged."""
    flagged = 0
    if t.status == "on_hold":
        return 0
    if t.started_at is None and not t.response_breached and now > as_utc(t.response_due_at):
        _flag_breach(db, None, t, "response")
        flagged += 1
    if t.resolved_at is None and not t.resolution_breached and now > as_utc(t.resolution_due_at):
        _flag_breach(db, None, t, "resolution")
        flagged += 1
    return flagged


def auto_close(db: Session, t: Ticket, now: datetime, settings: ModuleSettings) -> bool:
    if t.status != "resolved" or not t.resolved_at:
        return False
    if not auto_close_due(as_utc(t.resolved_at), now, settings.auto_close_days):
        return False
    _close(db, None, t, "auto", None, None)
    return True


def schedule_due(db: Session, s: Schedule, today: date) -> bool:
    return should_raise(
        active=s.active,
        has_open_ticket=_has_open_ticket(db, s),
        next_due_on=s.next_due_on,
        lead_days=s.lead_days,
        today=today,
    )
