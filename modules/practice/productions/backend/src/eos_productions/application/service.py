"""Use cases of productions (docs/prd.md). Each one checks the rules, changes state and publishes the matching
event from contracts/events.yaml to the outbox in the same transaction, so a reader of the event stream sees
exactly what the database holds. The API layer only maps HTTP to these functions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.rules import (
    CALENDAR_STATUSES,
    CANCELLED,
    COMPLETED,
    CONFIRMED,
    DECLINED,
    IN_PREPARATION,
    INVITED,
    LIVE_ROLE_STATUSES,
    OPEN_STATUSES,
    PLANNED,
    PREPARING_STATUSES,
    SCHEDULED,
    TASK_DONE,
    TASK_OPEN,
    WITHDRAWN,
    ProductionRules,
    RuleViolationError,
    check_action,
    check_kind,
    check_response,
    check_role_kind,
    check_schedule,
    check_withdrawal,
    default_call_time,
    is_overdue,
    preparation_is_short,
)
from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from ..infrastructure.models import Production, ProductionRole, ProductionTask, as_utc, iso

MODULE = "productions"
PRODUCTION_READ = f"{MODULE}:production:read"
PRODUCTION_MANAGE = f"{MODULE}:production:manage"
ROLE_READ_OWN = f"{MODULE}:role:read-own"
ROLE_MANAGE = f"{MODULE}:role:manage"
ROLE_RESPOND = f"{MODULE}:role:respond"
TASK_READ = f"{MODULE}:task:read"
TASK_MANAGE = f"{MODULE}:task:manage"


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


class ProductionsError(Exception):
    """A refusal with an HTTP status and a contract error body ({code, message, ...})."""

    def __init__(self, status: int, code: str, message: str, **extra) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra

    def body(self) -> dict:
        return {"code": self.code, "message": self.message, **self.extra}


def _not_found(what: str) -> ProductionsError:
    return ProductionsError(404, "not_found", f"{what} not found in your organisation")


def _rule_error(e: RuleViolationError) -> ProductionsError:
    # A status that forbids the action is a conflict; a bad body is unprocessable.
    http_status = 409 if e.code in ("wrong_status", "already_answered") else 422
    error = ProductionsError(http_status, e.code, e.message)
    # Set rather than passed: a rule's extra carries `status`, which is the row's status, not the HTTP one.
    error.extra = dict(e.extra)
    return error


def _publish(db: Session, actor: Actor | None, name: str, organisation_id: str, payload: dict) -> None:
    events.publish(
        db,
        f"{MODULE}.{name}",
        organisation_id,
        {"organisation_id": organisation_id, **payload},
        actor=actor.user_id if actor else None,
    )


def _settings() -> ProductionRules:
    return load_settings()


# ---------------------------------------------------------------- reading rows


def _production(db: Session, production_id: str, *, lock: bool = False) -> Production:
    row = repo.get_for_update(db, Production, production_id) if lock else repo.get(db, Production, production_id)
    if row is None:
        raise _not_found("production")
    return row


def _counts(db: Session, production: Production) -> dict:
    roles = repo.roles_of(db, production.id)
    tasks = repo.tasks_of(db, production.id)
    return {
        "cast_invited": sum(1 for r in roles if r.status == INVITED),
        "cast_confirmed": sum(1 for r in roles if r.status == CONFIRMED),
        "cast_declined": sum(1 for r in roles if r.status == DECLINED),
        "tasks_open": sum(1 for t in tasks if t.status == TASK_OPEN),
        "tasks_total": len(tasks),
    }


def production_json(db: Session, p: Production, *, counts: bool = True) -> dict:
    data = {
        "id": p.id,
        "organisation_id": p.organisation_id,
        "title": p.title,
        "kind": p.kind,
        "status": p.status,
        "department": p.department,
        "summary": p.summary,
        "venue": p.venue,
        "resource_id": p.resource_id,
        "starts_at": iso(p.starts_at),
        "ends_at": iso(p.ends_at),
        "call_time": iso(p.call_time),
        "lead_user_id": p.lead_user_id,
        "created_by": p.created_by,
        "cancelled_reason": p.cancelled_reason,
        "completed_at": iso(p.completed_at),
        "created_at": iso(p.created_at),
        "updated_at": iso(p.updated_at),
    }
    if counts:
        data["counts"] = _counts(db, p)
    return data


def role_json(r: ProductionRole) -> dict:
    return {
        "id": r.id,
        "production_id": r.production_id,
        "user_id": r.user_id,
        "role_name": r.role_name,
        "kind": r.kind,
        "status": r.status,
        "notes": r.notes,
        "reason": r.reason,
        "responded_at": iso(r.responded_at),
        "created_at": iso(r.created_at),
    }


def task_json(t: ProductionTask) -> dict:
    return {
        "id": t.id,
        "production_id": t.production_id,
        "title": t.title,
        "status": t.status,
        "due_at": iso(t.due_at),
        "assignee_user_id": t.assignee_user_id,
        "position": t.position,
        "completed_at": iso(t.completed_at),
        "completed_by": t.completed_by,
        "created_at": iso(t.created_at),
    }


# ---------------------------------------------------------------- productions


def list_productions(db: Session, filters: dict, page_number: int, page_size: int) -> dict:
    query = repo.production_query(db, filters)
    total = repo.count(db, query)
    rows = repo.page(db, query, page_number, page_size)
    return {
        "items": [production_json(db, p) for p in rows],
        "total": total,
        "page": page_number,
        "page_size": page_size,
    }


def get_production(db: Session, production_id: str) -> dict:
    return production_json(db, _production(db, production_id))


def create_production(db: Session, actor: Actor, body: dict) -> tuple[dict, bool]:
    """Returns (production, created). A repeated client_token from the same caller returns their first one."""
    token = body.get("client_token")
    if existing := repo.find_by_token(db, actor.user_id, token):
        return production_json(db, existing), False

    kind = body.get("kind", "other")
    try:
        check_kind(kind)
    except RuleViolationError as e:
        raise _rule_error(e) from e
    starts_at, ends_at, call_time = _dates(body)
    if starts_at is not None and ends_at is not None:
        try:
            check_schedule(starts_at, ends_at, call_time, _settings())
        except RuleViolationError as e:
            raise _rule_error(e) from e

    production = Production(
        organisation_id=actor.organisation_id,
        title=body["title"].strip(),
        kind=kind,
        status=SCHEDULED if starts_at and ends_at else PLANNED,
        department=body.get("department"),
        summary=body.get("summary"),
        venue=body.get("venue"),
        resource_id=body.get("resource_id"),
        starts_at=starts_at,
        ends_at=ends_at,
        call_time=call_time or (default_call_time(starts_at, _settings()) if starts_at else None),
        lead_user_id=body.get("lead_user_id") or actor.user_id,
        created_by=actor.user_id,
        client_token=token,
    )
    try:
        with db.begin_nested():  # a savepoint, so a lost race does not abandon the whole transaction
            db.add(production)
    except IntegrityError:
        # Two simultaneous calls with the same token: the other one won, hand back what it created.
        if existing := repo.find_by_token(db, actor.user_id, token):
            return production_json(db, existing), False
        raise

    _publish(
        db,
        actor,
        "production.created",
        actor.organisation_id,
        {
            "production_id": production.id,
            "title": production.title,
            "kind": production.kind,
            "department": production.department,
            "lead_user_id": production.lead_user_id,
            "created_by": actor.user_id,
        },
    )
    if production.status == SCHEDULED:
        _publish_scheduled(db, actor, production, None)
    db.commit()
    return production_json(db, production), True


def _dates(body: dict) -> tuple[datetime | None, datetime | None, datetime | None]:
    return as_utc(body.get("starts_at")), as_utc(body.get("ends_at")), as_utc(body.get("call_time"))


EDITABLE = ("title", "kind", "department", "summary", "venue", "resource_id", "lead_user_id")
#: Of those, the ones a production cannot exist without: an explicit null is refused by the API layer (422),
#: never applied. contracts/openapi.yaml marks the other four `[<type>, "null"]`, and those really can be
#: cleared. (Review of #454: `{"kind": null}` reached the NOT NULL column and became a 500.)
NOT_NULLABLE = ("title", "kind", "lead_user_id")


def update_production(db: Session, actor: Actor, production_id: str, body: dict) -> dict:
    production = _production(db, production_id, lock=True)
    try:
        check_action("edit", production.status)
        if "kind" in body and body["kind"] is not None:
            check_kind(body["kind"])
    except RuleViolationError as e:
        raise _rule_error(e) from e

    changed = []
    for key in EDITABLE:
        if key not in body:
            continue
        value = body[key]
        if isinstance(value, str):
            value = value.strip()
        if key in NOT_NULLABLE and not value:
            # The API layer refuses an explicit null or a blank on these (422), so this only catches a direct caller
            # of the service. A production cannot exist without a title, kind or lead, so leave the stored value alone.
            continue
        if getattr(production, key) != value:
            setattr(production, key, value)
            changed.append(key)
    if changed:
        _publish(
            db,
            actor,
            "production.updated",
            production.organisation_id,
            {"production_id": production.id, "changed": sorted(changed)},
        )
    db.commit()
    return production_json(db, production)


def start_preparation(db: Session, actor: Actor, production_id: str) -> dict:
    production = _production(db, production_id, lock=True)
    try:
        check_action("start_preparation", production.status)
    except RuleViolationError as e:
        raise _rule_error(e) from e
    production.status = IN_PREPARATION
    _publish(
        db,
        actor,
        "production.preparation-started",
        production.organisation_id,
        {"production_id": production.id, "title": production.title, "lead_user_id": production.lead_user_id},
    )
    db.commit()
    return production_json(db, production)


def schedule(db: Session, actor: Actor, production_id: str, body: dict) -> tuple[dict, list[str]]:
    """Give a production its dates, or move them. Returns the production and any warnings (PRD rule 7)."""
    production = _production(db, production_id, lock=True)
    settings = _settings()
    starts_at, ends_at, call_time = _dates(body)
    try:
        check_action("schedule", production.status)
        if starts_at is None or ends_at is None:
            raise RuleViolationError("invalid_dates", "a schedule needs both a start and an end")
        check_schedule(starts_at, ends_at, call_time, settings)
    except RuleViolationError as e:
        raise _rule_error(e) from e

    was = as_utc(production.starts_at)
    production.starts_at = starts_at
    production.ends_at = ends_at
    production.call_time = call_time or default_call_time(starts_at, settings)
    if body.get("venue") is not None:
        production.venue = body["venue"]
    if body.get("resource_id") is not None:
        production.resource_id = body["resource_id"]
    production.status = SCHEDULED
    _publish_scheduled(db, actor, production, was)
    db.commit()

    warnings = []
    if preparation_is_short(starts_at, clock(), settings):
        warnings.append(
            f"less than {settings.min_preparation_days} days to prepare; cast and crew may not have time to answer"
        )
    return production_json(db, production), warnings


def _publish_scheduled(db: Session, actor: Actor, production: Production, was: datetime | None) -> None:
    _publish(
        db,
        actor,
        "production.scheduled",
        production.organisation_id,
        {
            "production_id": production.id,
            "title": production.title,
            "starts_at": iso(production.starts_at),
            "ends_at": iso(production.ends_at),
            "call_time": iso(production.call_time),
            "venue": production.venue,
            "from_starts_at": iso(was),
        },
    )


def complete(db: Session, actor: Actor, production_id: str) -> dict:
    production = _production(db, production_id, lock=True)
    try:
        check_action("complete", production.status)
    except RuleViolationError as e:
        raise _rule_error(e) from e
    production.status = COMPLETED
    production.completed_at = clock()
    _publish(
        db,
        actor,
        "production.completed",
        production.organisation_id,
        {
            "production_id": production.id,
            "title": production.title,
            "completed_at": iso(production.completed_at),
            "cast_user_ids": sorted({r.user_id for r in repo.roles_of(db, production.id) if r.status == CONFIRMED}),
        },
    )
    db.commit()
    return production_json(db, production)


def cancel(db: Session, actor: Actor, production_id: str, body: dict) -> dict:
    production = _production(db, production_id, lock=True)
    try:
        check_action("cancel", production.status)
    except RuleViolationError as e:
        raise _rule_error(e) from e
    reason = (body.get("reason") or "").strip() or None
    production.status = CANCELLED
    production.cancelled_reason = reason
    production.cancelled_by = actor.user_id

    live = repo.live_roles_of(db, production.id)
    now = clock()
    for role in live:
        role.status = WITHDRAWN
        role.reason = reason or "the production was cancelled"
        role.responded_at = now
        _publish(
            db,
            actor,
            "role.withdrawn",
            production.organisation_id,
            {
                "production_id": production.id,
                "role_id": role.id,
                "user_id": role.user_id,
                "role_name": role.role_name,
                "withdrawn_by": actor.user_id,
                "reason": role.reason,
            },
        )
    _publish(
        db,
        actor,
        "production.cancelled",
        production.organisation_id,
        {
            "production_id": production.id,
            "title": production.title,
            "reason": reason,
            "cancelled_by": actor.user_id,
            "starts_at": iso(production.starts_at),
            "cast_user_ids": sorted({r.user_id for r in live}),
        },
    )
    db.commit()
    return production_json(db, production)


# ---------------------------------------------------------------- cast and crew


def list_roles(db: Session, actor: Actor, production_id: str) -> list[dict]:
    """The cast and crew, which `production:read` shows to everyone by contract. The private fields are not part of
    that: why someone declined or was withdrawn (`reason`) and the casting `notes` are shown only to a caller who may
    manage roles, and to the person holding the part (review of #454)."""
    _production(db, production_id)
    manager = actor.can(ROLE_MANAGE)
    rows = []
    for r in repo.roles_of(db, production_id):
        row = role_json(r)
        if not manager and r.user_id != actor.user_id:
            row["notes"] = None
            row["reason"] = None
        rows.append(row)
    return rows


def assign_role(db: Session, actor: Actor, production_id: str, body: dict) -> tuple[dict, bool]:
    """Offer a part. Offering the same person the same part again returns the standing offer.
    The production row is locked so a cancel racing this call cannot leave a live part on a cancelled production."""
    production = _production(db, production_id, lock=True)
    kind = body.get("kind", "cast")
    try:
        check_action("assign_role", production.status)
        check_role_kind(kind)
    except RuleViolationError as e:
        raise _rule_error(e) from e

    user_id = body["user_id"]
    role_name = body["role_name"].strip()
    if existing := repo.role_for(db, production_id, user_id, role_name):
        if existing.status in LIVE_ROLE_STATUSES:
            return role_json(existing), False
        # Re-offering a part that was declined or withdrawn opens it again, on the same row.
        existing.status = INVITED
        existing.reason = None
        existing.responded_at = None
        existing.kind = kind
        existing.assigned_by = actor.user_id
        _publish_assigned(db, actor, production, existing)
        db.commit()
        return role_json(existing), True

    role = ProductionRole(
        organisation_id=production.organisation_id,
        production_id=production.id,
        user_id=user_id,
        role_name=role_name,
        kind=kind,
        status=INVITED,
        notes=body.get("notes"),
        assigned_by=actor.user_id,
    )
    try:
        with db.begin_nested():
            db.add(role)
    except IntegrityError:
        # Two leads cast the same person at the same moment; the other one won.
        if existing := repo.role_for(db, production_id, user_id, role_name):
            return role_json(existing), False
        raise
    _publish_assigned(db, actor, production, role)
    db.commit()
    return role_json(role), True


def _publish_assigned(db: Session, actor: Actor, production: Production, role: ProductionRole) -> None:
    _publish(
        db,
        actor,
        "role.assigned",
        production.organisation_id,
        {
            "production_id": production.id,
            "role_id": role.id,
            "user_id": role.user_id,
            "role_name": role.role_name,
            "kind": role.kind,
            "assigned_by": actor.user_id,
        },
    )


def respond(db: Session, actor: Actor, role_id: str, body: dict) -> dict:
    """Accept or decline a part. Only the person it was offered to, and only once: the row is locked, so two
    simultaneous answers cannot both apply (the accept/reject race #317's audit found in workflow)."""
    role = repo.get_for_update(db, ProductionRole, role_id)
    if role is None:
        raise _not_found("part")
    if role.user_id != actor.user_id:
        raise ProductionsError(403, "forbidden", "this part was offered to somebody else")
    production = _production(db, role.production_id)
    try:
        check_response(role.status, production.status)
    except RuleViolationError as e:
        raise _rule_error(e) from e

    decision = body["decision"]
    reason = (body.get("reason") or "").strip() or None
    role.status = CONFIRMED if decision == "accept" else DECLINED
    role.responded_at = clock()
    role.reason = None if decision == "accept" else reason
    payload = {
        "production_id": production.id,
        "role_id": role.id,
        "user_id": role.user_id,
        "role_name": role.role_name,
    }
    if decision == "accept":
        _publish(db, actor, "role.accepted", production.organisation_id, payload)
    else:
        _publish(db, actor, "role.declined", production.organisation_id, {**payload, "reason": reason})
    db.commit()
    return role_json(role)


def withdraw_role(db: Session, actor: Actor, role_id: str, body: dict) -> dict:
    role = repo.get_for_update(db, ProductionRole, role_id)
    if role is None:
        raise _not_found("part")
    production = _production(db, role.production_id)
    try:
        check_withdrawal(role.status)
    except RuleViolationError as e:
        raise _rule_error(e) from e
    reason = (body.get("reason") or "").strip() or None
    role.status = WITHDRAWN
    role.reason = reason
    role.responded_at = clock()
    _publish(
        db,
        actor,
        "role.withdrawn",
        production.organisation_id,
        {
            "production_id": production.id,
            "role_id": role.id,
            "user_id": role.user_id,
            "role_name": role.role_name,
            "withdrawn_by": actor.user_id,
            "reason": reason,
        },
    )
    db.commit()
    return role_json(role)


# ---------------------------------------------------------------- preparation tasks


def list_tasks(db: Session, production_id: str) -> list[dict]:
    _production(db, production_id)
    return [task_json(t) for t in repo.tasks_of(db, production_id)]


def add_task(db: Session, actor: Actor, production_id: str, body: dict) -> dict:
    production = _production(db, production_id, lock=True)
    try:
        check_action("add_task", production.status)
    except RuleViolationError as e:
        raise _rule_error(e) from e
    task = ProductionTask(
        organisation_id=production.organisation_id,
        production_id=production.id,
        title=body["title"].strip(),
        status=TASK_OPEN,
        position=repo.next_position(db, production.id),
        due_at=as_utc(body.get("due_at")),
        assignee_user_id=body.get("assignee_user_id"),
        added_by=actor.user_id,
    )
    db.add(task)
    db.flush()
    _publish(
        db,
        actor,
        "task.added",
        production.organisation_id,
        {
            "production_id": production.id,
            "task_id": task.id,
            "title": task.title,
            "due_at": iso(task.due_at),
            "assignee_user_id": task.assignee_user_id,
            "added_by": actor.user_id,
        },
    )
    db.commit()
    return task_json(task)


def complete_task(db: Session, actor: Actor, task_id: str) -> dict:
    task = repo.get_for_update(db, ProductionTask, task_id)
    if task is None:
        raise _not_found("task")
    if task.status == TASK_DONE:
        return task_json(task)  # doing it twice is not an error
    production = _production(db, task.production_id, lock=True)
    try:
        check_action("complete_task", production.status)
    except RuleViolationError as e:
        raise _rule_error(e) from e
    task.status = TASK_DONE
    task.completed_at = clock()
    task.completed_by = actor.user_id
    db.flush()
    outstanding = len(repo.open_tasks_of(db, task.production_id))
    _publish(
        db,
        actor,
        "task.completed",
        task.organisation_id,
        {
            "production_id": task.production_id,
            "task_id": task.id,
            "title": task.title,
            "completed_by": actor.user_id,
            "outstanding": outstanding,
        },
    )
    db.commit()
    return task_json(task)


# ---------------------------------------------------------------- dashboard widgets


def _calendar_entry(p: Production, confirmed: int) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "kind": p.kind,
        "status": p.status,
        "department": p.department,
        "venue": p.venue,
        "starts_at": iso(p.starts_at),
        "ends_at": iso(p.ends_at),
        "call_time": iso(p.call_time),
        "cast_confirmed": confirmed,
    }


def _confirmed_by_production(db: Session, rows: list[Production]) -> dict[str, int]:
    ids = {p.id for p in rows}
    counts = dict.fromkeys(ids, 0)
    for role in repo.roles_for(db, ids):
        if role.status == CONFIRMED:
            counts[role.production_id] = counts.get(role.production_id, 0) + 1
    return counts


def calendar(db: Session, start_from: datetime | None, start_to: datetime | None, limit: int) -> dict:
    """productions.calendar: what is on, in a window. Defaults to the organisation's calendar window."""
    settings = _settings()
    start_from = as_utc(start_from) or clock()
    if start_to is None:
        start_to = start_from + timedelta(days=settings.calendar_window_days)
    query = repo.calendar(db, CALENDAR_STATUSES, start_from, as_utc(start_to))
    rows = list(db.scalars(query))
    shown = rows[:limit]
    confirmed = _confirmed_by_production(db, shown)
    return {"items": [_calendar_entry(p, confirmed.get(p.id, 0)) for p in shown], "total": len(rows)}


def upcoming(db: Session, limit: int) -> dict:
    """productions.upcoming: the next scheduled productions, with no end to the window."""
    query = repo.calendar(db, CALENDAR_STATUSES, clock(), None)
    rows = list(db.scalars(query))
    shown = rows[:limit]
    confirmed = _confirmed_by_production(db, shown)
    return {"items": [_calendar_entry(p, confirmed.get(p.id, 0)) for p in shown], "total": len(rows)}


def my_roles(db: Session, actor: Actor, *, open_only: bool, limit: int) -> dict:
    """productions.my-roles: the caller's own parts. Reads only their own rows, whatever else they may read."""
    statuses = (INVITED,) if open_only else LIVE_ROLE_STATUSES
    roles = repo.roles_of_user(db, actor.user_id, statuses)
    productions = repo.productions_by_id(db, {r.production_id for r in roles})
    items = []
    for role in roles:
        production = productions.get(role.production_id)
        if production is None or production.status not in OPEN_STATUSES:
            continue
        items.append(
            {
                "role_id": role.id,
                "production_id": production.id,
                "role_name": role.role_name,
                "role_kind": role.kind,
                "role_status": role.status,
                "title": production.title,
                "kind": production.kind,
                "status": production.status,
                "venue": production.venue,
                "starts_at": iso(production.starts_at),
                "call_time": iso(production.call_time),
            }
        )
    items.sort(key=lambda row: (row["starts_at"] is None, row["starts_at"] or "", row["title"]))
    return {"items": items[:limit], "total": len(items)}


def in_preparation(db: Session, actor: Actor, *, mine: bool, limit: int) -> dict:
    """productions.in-preparation: what is being got ready, and what is still outstanding on each."""
    rows = list(db.scalars(repo.preparing(db, PREPARING_STATUSES)))
    if mine:
        own = {r.production_id for r in repo.roles_of_user(db, actor.user_id, LIVE_ROLE_STATUSES)}
        rows = [p for p in rows if p.lead_user_id == actor.user_id or p.id in own]
    ids = {p.id for p in rows}
    tasks = repo.tasks_for(db, ids)
    roles = repo.roles_for(db, ids)
    now = clock()

    items = []
    for production in rows:
        own_tasks = [t for t in tasks if t.production_id == production.id]
        open_tasks = [t for t in own_tasks if t.status == TASK_OPEN]
        due = sorted(as_utc(t.due_at) for t in open_tasks if t.due_at is not None)
        items.append(
            {
                "id": production.id,
                "title": production.title,
                "kind": production.kind,
                "status": production.status,
                "department": production.department,
                "starts_at": iso(production.starts_at),
                "lead_user_id": production.lead_user_id,
                "tasks_open": len(open_tasks),
                "tasks_total": len(own_tasks),
                "tasks_overdue": sum(1 for t in open_tasks if is_overdue(as_utc(t.due_at), now)),
                "next_task_due_at": iso(due[0]) if due else None,
                "cast_unanswered": sum(1 for r in roles if r.production_id == production.id and r.status == INVITED),
            }
        )
    # Most pressing first: overdue tasks, then the soonest start, then the most outstanding.
    items.sort(
        key=lambda row: (
            -row["tasks_overdue"],
            row["starts_at"] is None,
            row["starts_at"] or "",
            -row["tasks_open"],
        )
    )
    return {"items": items[:limit], "total": len(items)}
