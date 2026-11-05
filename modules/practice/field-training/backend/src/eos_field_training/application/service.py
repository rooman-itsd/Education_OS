"""Use cases of field-training (docs/prd.md, docs/user-stories.md). Each one checks the domain rules, changes state,
writes an audit entry, and publishes the matching event from contracts/events.yaml to the outbox in the same
transaction. Log entry text and assessment comments are never published.

A person is identified by their identity user id (the token subject): a trainee by `trainee_id`, a supervisor by
`supervisor_id` and by the person_ids attached to sites and openings. Rows whose seats or status can change under
two concurrent requests are locked (SELECT ... FOR UPDATE), the opening before its placements."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import LOG_TRANSITIONS, OPENING_TRANSITIONS, PLACEMENT_TRANSITIONS, RuleViolationError
from ..infrastructure import repository as repo
from ..infrastructure.models import Assessment, AuditEntry, LogEntry, Opening, Placement, Site, iso

MODULE = "field-training"
SITE_READ = "field-training:site:read"
SITE_MANAGE = "field-training:site:manage"
OPENING_READ = "field-training:opening:read"
OPENING_MANAGE = "field-training:opening:manage"
PLACEMENT_READ = "field-training:placement:read"
PLACEMENT_MANAGE = "field-training:placement:manage"
SUPERVISION_READ = "field-training:supervision:read"
LOG_VERIFY = "field-training:log:verify"
ASSESSMENT_RECORD = "field-training:assessment:record"
SELF_READ = "field-training:self:read"
SELF_APPLY = "field-training:self:apply"
SELF_LOG = "field-training:self:log"

# Domain rule code -> HTTP status.
RULE_STATUS = {
    "invalid_status": 409,
    "no_seats": 409,
    "seats_below_filled": 409,
    "date_outside_placement": 409,
    "date_in_future": 409,
    "day_over_24_hours": 409,
    "invalid_dates": 422,
    "invalid_hours": 422,
}

# Business dates (a placement's period, a log entry's date, "today") follow the Indian calendar. Asia/Kolkata has
# kept UTC+05:30 without daylight saving since 1945, so a fixed offset is exact and needs no time-zone database.
BUSINESS_TZ = timezone(timedelta(hours=5, minutes=30), "Asia/Kolkata")


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


def today() -> date:
    """Today in Asia/Kolkata: the date start, log and due rules are judged against. Timestamps stay UTC."""
    return clock().astimezone(BUSINESS_TZ).date()


@dataclass
class Actor:
    """Who is calling. Built by the API layer from the verified token."""

    user_id: str
    organisation_id: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


class FieldTrainingError(Exception):
    """A refusal with an HTTP status and an error body ({code, message}, the contract's Refusal shape)."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def body(self) -> dict:
        return {"code": self.code, "message": self.message}


def _not_found(what: str) -> FieldTrainingError:
    return FieldTrainingError(404, "not_found", f"{what} not found in your organisation")


def _conflict(code: str, message: str) -> FieldTrainingError:
    return FieldTrainingError(409, code, message)


def _forbidden(code: str, message: str) -> FieldTrainingError:
    return FieldTrainingError(403, code, message)


def _not_own(actor: Actor, trainee_id: str) -> None:
    """Nobody assigns, decides, starts, changes or completes their own placement, whatever else they hold: a user with
    the coordinator role and the trainee role must not approve their own application."""
    if trainee_id == actor.user_id:
        raise _forbidden("own_placement", "you cannot act on your own placement")


def _flush_unique(db: Session, code: str, message: str) -> None:
    """Write now, so a duplicate that slipped past the check (two requests at once) is a 409, not a 500."""
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _conflict(code, message) from None


def _rule(v: RuleViolationError) -> FieldTrainingError:
    return FieldTrainingError(RULE_STATUS.get(v.code, 422), v.code, v.message)


def _check(fn, *args):
    try:
        return fn(*args)
    except RuleViolationError as v:
        raise _rule(v) from v


def _audit(db: Session, actor: Actor | None, action: str, entity: str, entity_id: str, organisation_id: str) -> None:
    db.add(
        AuditEntry(
            organisation_id=organisation_id,
            actor=actor.user_id if actor else None,
            action=action,
            entity=entity,
            entity_id=entity_id,
            occurred_at=clock(),
        )
    )


def _publish(db: Session, actor: Actor | None, name: str, organisation_id: str, payload: dict) -> None:
    events.publish(
        db,
        f"{MODULE}.{name}",
        organisation_id,
        {"organisation_id": organisation_id, **payload},
        actor=actor.user_id if actor else None,
    )


def _get(db: Session, model, row_id: str, what: str, lock: bool = False):
    row = repo.for_update(db, model, row_id) if lock else repo.get(db, model, row_id)
    if row is None:
        raise _not_found(what)
    return row


def _unique(ids: list[str] | None) -> list[str]:
    """Ids in the order given, each once."""
    return list(dict.fromkeys(ids or []))


# ---------------------------------------------------------------- serialisation


def site_dicts(db: Session, rows: list[Site]) -> list[dict]:
    supervisors = repo.site_supervisors(db, [s.id for s in rows])
    return [
        {
            "id": s.id,
            "organisation_id": s.organisation_id,
            "name": s.name,
            "kind": s.kind,
            "address": s.address,
            "contact_name": s.contact_name,
            "contact_email": s.contact_email,
            "supervisor_ids": supervisors[s.id],
            "active": s.active,
        }
        for s in rows
    ]


def opening_dicts(db: Session, rows: list[Opening]) -> list[dict]:
    ids = [o.id for o in rows]
    filled = repo.seats_filled(db, ids)
    supervisors = repo.opening_supervisors(db, ids)
    sites = repo.sites_by_id(db, sorted({o.site_id for o in rows}))
    return [
        {
            "id": o.id,
            "organisation_id": o.organisation_id,
            "site_id": o.site_id,
            "site_name": sites[o.site_id].name if o.site_id in sites else None,
            "title": o.title,
            "discipline": o.discipline,
            "starts_on": iso(o.starts_on),
            "ends_on": iso(o.ends_on),
            "seats": o.seats,
            "seats_filled": filled[o.id],
            "required_hours": rules.to_hours(o.required_minutes),
            "allow_applications": o.allow_applications,
            "eligibility": o.eligibility,
            "supervisor_ids": supervisors[o.id],
            "status": o.status,
        }
        for o in rows
    ]


def placement_dicts(db: Session, rows: list[Placement]) -> list[dict]:
    """Placements with names of their opening and site, hours by log status, and the final outcome."""
    ids = [p.id for p in rows]
    minutes = repo.minutes_by_status(db, ids)
    openings = repo.openings_by_id(db, sorted({p.opening_id for p in rows}))
    sites = repo.sites_by_id(db, sorted({p.site_id for p in rows}))
    finals = repo.final_outcomes(db, ids)
    return [
        {
            "id": p.id,
            "organisation_id": p.organisation_id,
            "opening_id": p.opening_id,
            "opening_title": openings[p.opening_id].title if p.opening_id in openings else None,
            "site_id": p.site_id,
            "site_name": sites[p.site_id].name if p.site_id in sites else None,
            "trainee_id": p.trainee_id,
            "trainee_name": p.trainee_name,
            "supervisor_id": p.supervisor_id,
            "supervisor_name": p.supervisor_name,
            "starts_on": iso(p.starts_on),
            "ends_on": iso(p.ends_on),
            "status": p.status,
            "statement": p.statement,
            "required_hours": rules.to_hours(p.required_minutes),
            "verified_hours": rules.to_hours(minutes[p.id].get("verified")),
            "pending_hours": rules.to_hours(minutes[p.id].get("submitted")),
            "final_outcome": finals.get(p.id),
            "reason": p.reason,
        }
        for p in rows
    ]


def placement_dict(db: Session, p: Placement) -> dict:
    return placement_dicts(db, [p])[0]


def log_dict(e: LogEntry) -> dict:
    return {
        "id": e.id,
        "organisation_id": e.organisation_id,
        "placement_id": e.placement_id,
        "date": iso(e.date),
        "hours": rules.to_hours(e.minutes),
        "activities": e.activities,
        "reflection": e.reflection,
        "status": e.status,
        "submitted_at": iso(e.submitted_at),
        "verified_by": e.verified_by,
        "verified_at": iso(e.verified_at),
        "return_reason": e.return_reason,
    }


def assessment_dict(a: Assessment) -> dict:
    return {
        "id": a.id,
        "organisation_id": a.organisation_id,
        "placement_id": a.placement_id,
        "assessor_id": a.assessor_id,
        "stage": a.stage,
        "outcome": a.outcome,
        "score": a.score,
        "comments": a.comments,
        "recorded_at": iso(a.recorded_at),
    }


def _page(items: list[dict], next_cursor: str | None) -> dict:
    return {"items": items, "next_cursor": next_cursor}


# ---------------------------------------------------------------- sites


def list_sites(db: Session, active: bool | None, q: str | None) -> list[dict]:
    return site_dicts(db, repo.sites(db, active, q))


def get_site(db: Session, site_id: str) -> dict:
    return site_dicts(db, [_get(db, Site, site_id, "site")])[0]


def _site_fields(s: Site, data: dict) -> None:
    s.name = data["name"]
    for key in ("kind", "address", "contact_name", "contact_email"):
        if key in data:
            setattr(s, key, data[key])


def create_site(db: Session, actor: Actor, data: dict) -> dict:
    s = Site(organisation_id=actor.organisation_id, active=data.get("active") is not False)
    _site_fields(s, data)
    db.add(s)
    db.flush()
    repo.replace_site_supervisors(db, s, _unique(data.get("supervisor_ids")))
    _flush_unique(db, "duplicate_supervisor", "a supervisor is listed twice on the site")
    _audit(db, actor, "site.created", "site", s.id, actor.organisation_id)
    db.commit()
    return site_dicts(db, [s])[0]


def update_site(db: Session, actor: Actor, site_id: str, data: dict) -> dict:
    s = _get(db, Site, site_id, "site", lock=True)
    _site_fields(s, data)
    if "supervisor_ids" in data:
        repo.replace_site_supervisors(db, s, _unique(data["supervisor_ids"]))
        _flush_unique(db, "duplicate_supervisor", "a supervisor is listed twice on the site")
    if data.get("active") is not None and data["active"] != s.active:
        _audit(db, actor, "site.activated" if data["active"] else "site.deactivated", "site", s.id, s.organisation_id)
        s.active = data["active"]
    _audit(db, actor, "site.updated", "site", s.id, s.organisation_id)
    db.commit()
    return site_dicts(db, [s])[0]


# ---------------------------------------------------------------- openings


def _visible_opening(db: Session, actor: Actor, opening_id: str) -> Opening:
    """Every opening with opening:read; with only supervision:read, openings at sites the caller supervises."""
    o = _get(db, Opening, opening_id, "opening")
    if actor.can(OPENING_READ):
        return o
    if o.site_id not in set(db.scalars(repo.sites_supervised_by(db, actor.user_id))):
        raise _not_found("opening")
    return o


def list_openings(db: Session, actor: Actor, filters: dict, cursor: str | None, limit: int) -> dict:
    if actor.can(OPENING_READ):
        q = repo.openings_query(db, **filters)
    elif actor.can(SUPERVISION_READ):
        q = repo.openings_query(db, **filters, site_ids=repo.sites_supervised_by(db, actor.user_id))
    else:
        # field-training:self:apply: open openings that accept applications, nothing else.
        q = repo.openings_query(db, **filters, applications_only=True)
    rows, nxt = repo.page(db, q, cursor, limit)
    return _page(opening_dicts(db, rows), nxt)


def get_opening(db: Session, actor: Actor, opening_id: str) -> dict:
    return opening_dicts(db, [_visible_opening(db, actor, opening_id)])[0]


def _active_site(db: Session, site_id: str) -> Site:
    site = _get(db, Site, site_id, "site")
    if not site.active:
        raise _conflict("site_inactive", f"the site {site.name} is inactive")
    return site


def create_opening(db: Session, actor: Actor, data: dict) -> dict:
    _check(rules.check_period, data["starts_on"], data["ends_on"])
    _active_site(db, data["site_id"])
    o = Opening(
        organisation_id=actor.organisation_id,
        site_id=data["site_id"],
        title=data["title"],
        discipline=data.get("discipline"),
        starts_on=data["starts_on"],
        ends_on=data["ends_on"],
        seats=data["seats"],
        required_minutes=_check(rules.to_minutes, data.get("required_hours") or 0),
        allow_applications=bool(data.get("allow_applications")),
        eligibility=data.get("eligibility"),
        status="draft",
    )
    db.add(o)
    db.flush()
    repo.replace_opening_supervisors(db, o, _unique(data.get("supervisor_ids")))
    _flush_unique(db, "duplicate_supervisor", "a supervisor is listed twice on the opening")
    _audit(db, actor, "opening.created", "opening", o.id, actor.organisation_id)
    db.commit()
    return opening_dicts(db, [o])[0]


def update_opening(db: Session, actor: Actor, opening_id: str, data: dict) -> dict:
    o = _get(db, Opening, opening_id, "opening", lock=True)
    if o.status == "cancelled":
        raise _conflict("invalid_status", "a cancelled opening cannot be changed")
    start, end = data["starts_on"], data["ends_on"]
    _check(rules.check_period, start, end)
    if data["site_id"] != o.site_id:
        _active_site(db, data["site_id"])
    _check(rules.check_seats_not_below_filled, data["seats"], repo.seats_filled(db, [o.id])[o.id])
    moved = (start, end, data["site_id"]) != (o.starts_on, o.ends_on, o.site_id)
    if moved:
        if repo.placements_in(db, o.id, ("active", "completed")):
            raise _conflict("period_locked", "the period and site cannot change once a placement has started")
        for p in repo.placements_in(db, o.id, ("requested", "assigned")):
            if p.starts_on < start or p.ends_on > end:
                raise _conflict("period_locked", "a placement in this opening falls outside the new period")
    o.site_id, o.title, o.starts_on, o.ends_on, o.seats = data["site_id"], data["title"], start, end, data["seats"]
    for key in ("discipline", "eligibility"):
        if key in data:
            setattr(o, key, data[key])
    if data.get("allow_applications") is not None:
        o.allow_applications = data["allow_applications"]
    if data.get("required_hours") is not None:
        o.required_minutes = _check(rules.to_minutes, data["required_hours"])
    # Placements that have not started follow the opening's site and requirement.
    for p in repo.placements_in(db, o.id, ("requested", "assigned")):
        p.site_id, p.required_minutes = o.site_id, o.required_minutes
    if "supervisor_ids" in data:
        repo.replace_opening_supervisors(db, o, _unique(data["supervisor_ids"]))
        _flush_unique(db, "duplicate_supervisor", "a supervisor is listed twice on the opening")
    _audit(db, actor, "opening.updated", "opening", o.id, o.organisation_id)
    db.commit()
    return opening_dicts(db, [o])[0]


def _opening_transition(o: Opening, action: str) -> None:
    try:
        o.status = rules.transition(OPENING_TRANSITIONS, action, o.status)
    except RuleViolationError as v:
        raise _rule(v) from v


def publish_opening(db: Session, actor: Actor, opening_id: str) -> dict:
    o = _get(db, Opening, opening_id, "opening", lock=True)
    _opening_transition(o, "publish")
    _publish(
        db,
        actor,
        "opening.published",
        o.organisation_id,
        {
            "opening_id": o.id,
            "site_id": o.site_id,
            "starts_on": iso(o.starts_on),
            "ends_on": iso(o.ends_on),
            "seats": o.seats,
            "allow_applications": o.allow_applications,
        },
    )
    _audit(db, actor, "opening.published", "opening", o.id, o.organisation_id)
    db.commit()
    return opening_dicts(db, [o])[0]


def close_opening(db: Session, actor: Actor, opening_id: str) -> dict:
    o = _get(db, Opening, opening_id, "opening", lock=True)
    _opening_transition(o, "close")
    _publish(db, actor, "opening.closed", o.organisation_id, {"opening_id": o.id})
    _audit(db, actor, "opening.closed", "opening", o.id, o.organisation_id)
    db.commit()
    return opening_dicts(db, [o])[0]


def cancel_opening(db: Session, actor: Actor, opening_id: str, reason: str) -> dict:
    """Withdraws the opening's requested and assigned placements; refused while one is active."""
    o = _get(db, Opening, opening_id, "opening", lock=True)
    if repo.placements_in(db, o.id, ("active",)):
        raise _conflict("placement_active", "an active placement exists in this opening; withdraw or complete it first")
    _opening_transition(o, "cancel")
    o.cancel_reason = reason
    for p in repo.placements_in(db, o.id, ("requested", "assigned")):
        _withdrawn(db, actor, repo.for_update(db, Placement, p.id), reason)
    _publish(db, actor, "opening.cancelled", o.organisation_id, {"opening_id": o.id, "reason": reason})
    _audit(db, actor, "opening.cancelled", "opening", o.id, o.organisation_id)
    db.commit()
    return opening_dicts(db, [o])[0]


# ---------------------------------------------------------------- placements: visibility


def _sees_placement(actor: Actor, p: Placement) -> bool:
    if actor.can(PLACEMENT_READ) or actor.can(PLACEMENT_MANAGE):
        return True
    if actor.can(SUPERVISION_READ) and p.supervisor_id == actor.user_id:
        return True
    return actor.can(SELF_READ) and p.trainee_id == actor.user_id


def _visible_placement(db: Session, actor: Actor, placement_id: str) -> Placement:
    """Someone else's placement the caller has no business with answers 404, the same as another organisation's."""
    p = _get(db, Placement, placement_id, "placement")
    if not _sees_placement(actor, p):
        raise _not_found("placement")
    return p


def list_placements(db: Session, actor: Actor, filters: dict, cursor: str | None, limit: int) -> dict:
    if not actor.can(PLACEMENT_READ):
        # field-training:supervision:read: only the placements the caller supervises.
        if filters.get("supervisor_id") not in (None, actor.user_id):
            return _page([], None)
        filters = {**filters, "supervisor_id": actor.user_id}
    rows, nxt = repo.page(db, repo.placements_query(db, **filters), cursor, limit)
    return _page(placement_dicts(db, rows), nxt)


def get_placement(db: Session, actor: Actor, placement_id: str) -> dict:
    return placement_dict(db, _visible_placement(db, actor, placement_id))


# ---------------------------------------------------------------- placements: changes


def _placement_transition(p: Placement, action: str) -> None:
    try:
        p.status = rules.transition(PLACEMENT_TRANSITIONS, action, p.status)
    except RuleViolationError as v:
        raise _rule(v) from v


def _check_no_overlap(db: Session, trainee_id: str, start: date, end: date, exclude_id: str | None = None) -> None:
    if repo.overlapping(db, trainee_id, start, end, exclude_id) is not None:
        raise _conflict("overlapping_placement", "the trainee already has a placement or application for these dates")


def _check_supervisor(supervisor_id: str | None, trainee_id: str) -> None:
    if supervisor_id is not None and supervisor_id == trainee_id:
        raise FieldTrainingError(422, "invalid_supervisor", "a trainee cannot supervise their own placement")


def _taking(db: Session, opening_id: str) -> Opening:
    """The opening, locked, open and with a seat left: the checks before a placement takes a seat."""
    o = _get(db, Opening, opening_id, "opening", lock=True)
    if o.status != "open":
        raise _conflict("opening_not_open", f"the opening is {o.status}, not open")
    _check(rules.check_seat, o.seats, repo.seats_filled(db, [o.id])[o.id])
    return o


def _check_once_per_opening(db: Session, opening: Opening, trainee_id: str, exclude_id: str | None = None) -> None:
    held = [
        p
        for p in repo.placements_in(db, opening.id, rules.ONE_PER_OPENING)
        if p.trainee_id == trainee_id and p.id != exclude_id
    ]
    if held:
        raise _conflict("already_applied", "the trainee already has a placement or application in this opening")


def _default_supervisor(db: Session, opening: Opening) -> str | None:
    named = repo.opening_supervisors(db, [opening.id])[opening.id]
    return named[0] if named else None


def _assigned(db: Session, actor: Actor, p: Placement) -> None:
    p.decided_by, p.decided_at = actor.user_id, clock()
    _publish(
        db,
        actor,
        "placement.assigned",
        p.organisation_id,
        {
            "placement_id": p.id,
            "opening_id": p.opening_id,
            "site_id": p.site_id,
            "trainee_id": p.trainee_id,
            "supervisor_id": p.supervisor_id,
            "starts_on": iso(p.starts_on),
            "ends_on": iso(p.ends_on),
            "required_hours": rules.to_hours(p.required_minutes),
        },
    )
    _audit(db, actor, "placement.assigned", "placement", p.id, p.organisation_id)


def assign_placement(db: Session, actor: Actor, data: dict) -> dict:
    _not_own(actor, data["trainee_id"])
    o = _taking(db, data["opening_id"])
    start, end = data.get("starts_on") or o.starts_on, data.get("ends_on") or o.ends_on
    _check(rules.check_within, start, end, o.starts_on, o.ends_on)
    trainee_id = data["trainee_id"]
    supervisor_id = data.get("supervisor_id") or _default_supervisor(db, o)
    _check_supervisor(supervisor_id, trainee_id)
    _check_once_per_opening(db, o, trainee_id)
    _check_no_overlap(db, trainee_id, start, end)
    p = Placement(
        organisation_id=actor.organisation_id,
        opening_id=o.id,
        site_id=o.site_id,
        trainee_id=trainee_id,
        supervisor_id=supervisor_id,
        starts_on=start,
        ends_on=end,
        required_minutes=o.required_minutes,
        status="assigned",
    )
    db.add(p)
    db.flush()
    _assigned(db, actor, p)
    db.commit()
    return placement_dict(db, p)


def apply(db: Session, actor: Actor, opening_id: str, statement: str | None) -> dict:
    o = _get(db, Opening, opening_id, "opening")
    if o.status == "open" and not o.allow_applications:
        raise _conflict("applications_not_allowed", "this opening does not take applications")
    o = _taking(db, opening_id)
    if not o.allow_applications:  # changed while waiting for the lock
        raise _conflict("applications_not_allowed", "this opening does not take applications")
    _check_once_per_opening(db, o, actor.user_id)
    _check_no_overlap(db, actor.user_id, o.starts_on, o.ends_on)
    p = Placement(
        organisation_id=actor.organisation_id,
        opening_id=o.id,
        site_id=o.site_id,
        trainee_id=actor.user_id,
        starts_on=o.starts_on,
        ends_on=o.ends_on,
        required_minutes=o.required_minutes,
        status="requested",
        statement=statement,
    )
    db.add(p)
    db.flush()
    _publish(
        db,
        actor,
        "placement.requested",
        p.organisation_id,
        {"placement_id": p.id, "opening_id": o.id, "trainee_id": p.trainee_id},
    )
    _audit(db, actor, "placement.requested", "placement", p.id, p.organisation_id)
    db.commit()
    return placement_dict(db, p)


def decide(db: Session, actor: Actor, placement_id: str, data: dict) -> dict:
    p = _get(db, Placement, placement_id, "placement")
    _not_own(actor, p.trainee_id)
    if data["decision"] == "rejected":
        reason = (data.get("reason") or "").strip()
        if len(reason) < 3:
            raise FieldTrainingError(422, "reason_required", "a reason of at least 3 characters is required to reject")
        p = _get(db, Placement, placement_id, "placement", lock=True)
        _placement_transition(p, "reject")
        p.decided_by, p.decided_at, p.reason = actor.user_id, clock(), reason
        _publish(
            db,
            actor,
            "placement.rejected",
            p.organisation_id,
            {"placement_id": p.id, "trainee_id": p.trainee_id, "reason": reason},
        )
        _audit(db, actor, "placement.rejected", "placement", p.id, p.organisation_id)
        db.commit()
        return placement_dict(db, p)
    if p.status != "requested":
        raise _conflict("invalid_status", f"cannot approve when status is {p.status}")
    o = _taking(db, p.opening_id)  # the opening first, then the placement
    p = _get(db, Placement, placement_id, "placement", lock=True)
    _placement_transition(p, "approve")
    p.supervisor_id = data.get("supervisor_id") or p.supervisor_id or _default_supervisor(db, o)
    _check_supervisor(p.supervisor_id, p.trainee_id)
    _check_no_overlap(db, p.trainee_id, p.starts_on, p.ends_on, exclude_id=p.id)
    _assigned(db, actor, p)
    db.commit()
    return placement_dict(db, p)


def _started(db: Session, actor: Actor | None, p: Placement, on: date) -> None:
    _placement_transition(p, "start")
    p.started_on = on
    _publish(
        db,
        actor,
        "placement.started",
        p.organisation_id,
        {"placement_id": p.id, "trainee_id": p.trainee_id, "supervisor_id": p.supervisor_id, "started_on": iso(on)},
    )
    _audit(db, actor, "placement.started", "placement", p.id, p.organisation_id)


def start_placement(db: Session, actor: Actor, placement_id: str) -> dict:
    p = _get(db, Placement, placement_id, "placement", lock=True)
    _not_own(actor, p.trainee_id)
    _started(db, actor, p, today())
    db.commit()
    return placement_dict(db, p)


def update_placement(db: Session, actor: Actor, placement_id: str, data: dict) -> dict:
    p = _get(db, Placement, placement_id, "placement", lock=True)
    _not_own(actor, p.trainee_id)
    if p.status not in rules.OPEN_PLACEMENT:
        raise _conflict("invalid_status", f"a {p.status} placement cannot be changed")
    if data.get("supervisor_id"):
        _check_supervisor(data["supervisor_id"], p.trainee_id)
    start, end = data.get("starts_on") or p.starts_on, data.get("ends_on") or p.ends_on
    if (start, end) != (p.starts_on, p.ends_on):
        o = _get(db, Opening, p.opening_id, "opening")
        _check(rules.check_within, start, end, o.starts_on, o.ends_on)
        _check_no_overlap(db, p.trainee_id, start, end, exclude_id=p.id)
        first, last = repo.log_dates(db, p.id)
        window = rules.log_window(start, p.started_on, end)
        if first is not None and (first < window[0] or last > window[1]):
            raise _conflict("date_outside_placement", "log entries already fall outside the new dates")
        p.starts_on, p.ends_on = start, end
    if data.get("supervisor_id"):
        p.supervisor_id = data["supervisor_id"]
    _audit(db, actor, "placement.updated", "placement", p.id, p.organisation_id)
    db.commit()
    return placement_dict(db, p)


def complete_placement(db: Session, actor: Actor, placement_id: str, override: bool, reason: str | None) -> dict:
    p = _get(db, Placement, placement_id, "placement", lock=True)
    _not_own(actor, p.trainee_id)
    verified = repo.minutes_by_status(db, [p.id])[p.id].get("verified", 0)
    final = repo.final_outcomes(db, [p.id]).get(p.id)
    refusal = rules.completion_refusal(p.status, final is not None, verified, p.required_minutes, override, reason)
    if refusal:
        raise _conflict(*refusal)
    _placement_transition(p, "complete")
    short = rules.hours_short(verified, p.required_minutes)
    p.hours_overridden, p.completed_at = short, clock()
    if short:
        p.reason = (reason or "").strip()
    _publish(
        db,
        actor,
        "placement.completed",
        p.organisation_id,
        {
            "placement_id": p.id,
            "opening_id": p.opening_id,
            "site_id": p.site_id,
            "trainee_id": p.trainee_id,
            "verified_hours": rules.to_hours(verified),
            "required_hours": rules.to_hours(p.required_minutes),
            "final_outcome": final,
            "hours_overridden": short,
        },
    )
    _audit(db, actor, "placement.completed", "placement", p.id, p.organisation_id)
    db.commit()
    return placement_dict(db, p)


def _withdrawn(db: Session, actor: Actor, p: Placement, reason: str) -> None:
    was_active = p.status == "active"
    _placement_transition(p, "withdraw")
    p.reason = reason
    _publish(
        db,
        actor,
        "placement.withdrawn",
        p.organisation_id,
        {"placement_id": p.id, "trainee_id": p.trainee_id, "was_active": was_active, "reason": reason},
    )
    _audit(db, actor, "placement.withdrawn", "placement", p.id, p.organisation_id)


def withdraw_placement(db: Session, actor: Actor, placement_id: str, reason: str) -> dict:
    p = _get(db, Placement, placement_id, "placement", lock=True)
    own = p.trainee_id == actor.user_id
    if not actor.can(PLACEMENT_MANAGE) and not own:
        raise _not_found("placement")  # field-training:self:apply covers the caller's own placement only
    if own and p.status == "active":
        # An active placement is withdrawn by a coordinator, and not by its own trainee even if they are one.
        raise _forbidden("placement_active", "an active placement is withdrawn by the coordinator")
    _withdrawn(db, actor, p, reason)
    db.commit()
    return placement_dict(db, p)


# ---------------------------------------------------------------- logbook


def list_logs(db: Session, actor: Actor, placement_id: str, status: str | None) -> list[dict]:
    p = _visible_placement(db, actor, placement_id)
    return [log_dict(e) for e in repo.logs(db, p.id, status)]


def _check_entry(db: Session, p: Placement, on: date, minutes: int, exclude_log_id: str | None = None) -> None:
    if p.status != "active":
        raise _conflict("placement_not_active", f"hours are logged on an active placement; this one is {p.status}")
    _check(rules.check_log_date, on, p.starts_on, p.started_on, p.ends_on, today())
    _check(rules.check_day_total, repo.trainee_minutes_on(db, p.trainee_id, on, exclude_log_id), minutes)


def _submitted(db: Session, actor: Actor, e: LogEntry, p: Placement) -> None:
    _publish(
        db,
        actor,
        "log.submitted",
        e.organisation_id,
        {
            "log_id": e.id,
            "placement_id": p.id,
            "trainee_id": p.trainee_id,
            "supervisor_id": p.supervisor_id,
            "date": iso(e.date),
            "hours": rules.to_hours(e.minutes),
        },
    )


def add_log(db: Session, actor: Actor, placement_id: str, data: dict) -> dict:
    p = _get(db, Placement, placement_id, "placement", lock=True)  # one entry at a time keeps the day under 24 hours
    if p.trainee_id != actor.user_id:
        raise _not_found("placement")
    minutes = _check(rules.to_minutes, data["hours"])
    _check_entry(db, p, data["date"], minutes)
    e = LogEntry(
        organisation_id=p.organisation_id,
        placement_id=p.id,
        date=data["date"],
        minutes=minutes,
        activities=data["activities"],
        reflection=data.get("reflection"),
        status="submitted",
        submitted_at=clock(),
    )
    db.add(e)
    db.flush()
    _submitted(db, actor, e, p)
    _audit(db, actor, "log.submitted", "log", e.id, e.organisation_id)
    db.commit()
    return log_dict(e)


def _log_transition(e: LogEntry, action: str) -> None:
    try:
        e.status = rules.transition(LOG_TRANSITIONS, action, e.status)
    except RuleViolationError as v:
        raise _rule(v) from v


def edit_log(db: Session, actor: Actor, log_id: str, data: dict) -> dict:
    e = _get(db, LogEntry, log_id, "log entry")
    p = _get(db, Placement, e.placement_id, "placement", lock=True)
    e = _get(db, LogEntry, log_id, "log entry", lock=True)
    if p.trainee_id != actor.user_id:
        raise _not_found("log entry")
    if e.status == "verified":
        raise _conflict("entry_verified", "a verified entry is locked")
    minutes = _check(rules.to_minutes, data["hours"])
    _check_entry(db, p, data["date"], minutes, exclude_log_id=e.id)
    resubmitted = e.status == "returned"
    _log_transition(e, "edit")
    e.date, e.minutes, e.activities = data["date"], minutes, data["activities"]
    if "reflection" in data:
        e.reflection = data["reflection"]
    if resubmitted:
        e.return_reason, e.submitted_at = None, clock()
        _submitted(db, actor, e, p)
    _audit(db, actor, "log.resubmitted" if resubmitted else "log.edited", "log", e.id, e.organisation_id)
    db.commit()
    return log_dict(e)


def _reviewable(db: Session, actor: Actor, log_id: str) -> tuple[LogEntry, Placement]:
    """The entry, locked, when the caller supervises its placement and it is not their own."""
    e = _get(db, LogEntry, log_id, "log entry", lock=True)
    p = _get(db, Placement, e.placement_id, "placement")
    if p.trainee_id == actor.user_id:
        raise _forbidden("own_entry", "you cannot verify or return your own entry")
    if p.supervisor_id != actor.user_id:
        raise _forbidden("not_supervisor", "you are not the supervisor of this placement")
    if p.status != "active":
        raise _conflict("placement_not_active", f"the placement is {p.status}")
    return e, p


def verify_log(db: Session, actor: Actor, log_id: str) -> dict:
    e, p = _reviewable(db, actor, log_id)
    _log_transition(e, "verify")
    e.verified_by, e.verified_at = actor.user_id, clock()
    _publish(
        db,
        actor,
        "log.verified",
        e.organisation_id,
        {
            "log_id": e.id,
            "placement_id": p.id,
            "trainee_id": p.trainee_id,
            "hours": rules.to_hours(e.minutes),
            "verified_by": actor.user_id,
        },
    )
    _audit(db, actor, "log.verified", "log", e.id, e.organisation_id)
    db.commit()
    return log_dict(e)


def return_log(db: Session, actor: Actor, log_id: str, reason: str) -> dict:
    e, p = _reviewable(db, actor, log_id)
    _log_transition(e, "return")
    e.return_reason = reason
    _publish(
        db, actor, "log.returned", e.organisation_id, {"log_id": e.id, "placement_id": p.id, "trainee_id": p.trainee_id}
    )
    _audit(db, actor, "log.returned", "log", e.id, e.organisation_id)
    db.commit()
    return log_dict(e)


# ---------------------------------------------------------------- assessments


def list_assessments(db: Session, actor: Actor, placement_id: str) -> list[dict]:
    p = _visible_placement(db, actor, placement_id)
    return [assessment_dict(a) for a in repo.assessments(db, p.id)]


def record_assessment(db: Session, actor: Actor, placement_id: str, data: dict) -> dict:
    p = _get(db, Placement, placement_id, "placement", lock=True)
    if p.trainee_id == actor.user_id:
        raise _forbidden("own_placement", "you cannot assess your own placement")
    if p.supervisor_id != actor.user_id:
        raise _forbidden("not_supervisor", "you are not the supervisor of this placement")
    if p.status != "active":
        raise _conflict("placement_not_active", f"only an active placement is assessed; this one is {p.status}")
    if data["stage"] == "final" and p.id in repo.final_outcomes(db, [p.id]):
        raise _conflict("final_recorded", "a final assessment is already recorded")
    a = Assessment(
        organisation_id=p.organisation_id,
        placement_id=p.id,
        assessor_id=actor.user_id,
        stage=data["stage"],
        outcome=data["outcome"],
        score=data.get("score"),
        comments=data.get("comments"),
        recorded_at=clock(),
    )
    db.add(a)
    db.flush()
    _publish(
        db,
        actor,
        "assessment.recorded",
        a.organisation_id,
        {
            "assessment_id": a.id,
            "placement_id": p.id,
            "trainee_id": p.trainee_id,
            "assessor_id": actor.user_id,
            "stage": a.stage,
            "outcome": a.outcome,
        },
    )
    _audit(db, actor, "assessment.recorded", "assessment", a.id, a.organisation_id)
    db.commit()
    return assessment_dict(a)


# ---------------------------------------------------------------- the caller's own (/me)


def my_placements(db: Session, actor: Actor, include_past: bool) -> list[dict]:
    """Active first, then upcoming, then requested; completed, rejected and withdrawn only with include_past."""
    rows = [
        p
        for p in repo.trainee_placements(db, actor.user_id)
        if include_past or p.status in ("active", "assigned", "requested")
    ]
    rows.sort(key=lambda p: rules.my_placement_rank(p.status, p.starts_on))
    return placement_dicts(db, rows)


def my_hours(db: Session, actor: Actor, placement_id: str | None) -> dict:
    """Hours of one of the caller's placements: the given one, else the active one, else the most recent."""
    if placement_id:
        p = _get(db, Placement, placement_id, "placement")
        if p.trainee_id != actor.user_id:
            raise _not_found("placement")
    else:
        mine = [p for p in repo.trainee_placements(db, actor.user_id) if p.status not in ("requested", "rejected")]
        mine.sort(key=lambda p: rules.my_placement_rank(p.status, p.starts_on))
        p = mine[0] if mine else None
    if p is None:
        return {
            "placement_id": None,
            "required_hours": 0.0,
            "verified_hours": 0.0,
            "pending_hours": 0.0,
            "returned_hours": 0.0,
            "by_date": [],
        }
    minutes = repo.minutes_by_status(db, [p.id])[p.id]
    last = today()
    first = last - timedelta(days=rules.HOURS_WINDOW_DAYS - 1)
    daily = repo.daily_minutes(db, p.id, first, last)
    days = [first + timedelta(days=i) for i in range(rules.HOURS_WINDOW_DAYS)]
    return {
        "placement_id": p.id,
        "required_hours": rules.to_hours(p.required_minutes),
        "verified_hours": rules.to_hours(minutes.get("verified")),
        "pending_hours": rules.to_hours(minutes.get("submitted")),
        "returned_hours": rules.to_hours(minutes.get("returned")),
        "by_date": [
            {
                "date": iso(d),
                "verified_hours": rules.to_hours(daily.get((d, "verified"))),
                "pending_hours": rules.to_hours(daily.get((d, "submitted"))),
            }
            for d in days
        ],
    }


def my_trainees(db: Session, actor: Actor, limit: int) -> list[dict]:
    """Active placements the caller supervises that need action, most urgent first."""
    rows = repo.supervised_active(db, actor.user_id)
    ids = [p.id for p in rows]
    awaiting = repo.awaiting_counts(db, ids)
    finals = repo.final_outcomes(db, ids)
    now = today()
    needing = []
    for p in rows:
        due = rules.final_assessment_due(p.ends_on, now, p.id in finals)
        if due or awaiting[p.id]:
            needing.append((rules.urgency(due, awaiting[p.id], p.ends_on), p, due))
    needing.sort(key=lambda t: (t[0], t[1].id))
    needing = needing[:limit]
    dicts = placement_dicts(db, [p for _, p, _ in needing])
    return [
        {"placement": d, "entries_awaiting": awaiting[p.id], "final_assessment_due": due}
        for d, (_, p, due) in zip(dicts, needing, strict=True)
    ]
