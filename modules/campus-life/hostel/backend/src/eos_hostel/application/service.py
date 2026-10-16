"""Use cases of hostel (docs/prd.md, docs/user-stories.md). Each one checks the domain rules, changes state, writes
an audit entry, and publishes the matching event from contracts/events.yaml to the outbox in the same transaction.
Visits and incidents are personal data: they are audited but never published.

A person is identified by their identity user id (the token subject); "current resident" means the person has an
occupied (checked-in) allocation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import ALLOCATION_TRANSITIONS, LEAVE_TRANSITIONS, Period, RuleViolationError
from ..infrastructure import repository as repo
from ..infrastructure.models import (
    Allocation,
    AuditEntry,
    Hostel,
    Incident,
    LeaveRequest,
    MessMenu,
    Notice,
    Room,
    Visit,
    as_utc,
    iso,
)

MODULE = "hostel"
HOSTEL_READ = "hostel:hostel:read"
HOSTEL_MANAGE = "hostel:hostel:manage"
ALLOCATION_READ = "hostel:allocation:read"
ALLOCATION_MANAGE = "hostel:allocation:manage"
MESS_MANAGE = "hostel:mess:manage"
LEAVE_APPROVE = "hostel:leave:approve"
GATE_RECORD = "hostel:gate:record"
VISITOR_READ = "hostel:visitor:read"
VISITOR_RECORD = "hostel:visitor:record"
INCIDENT_READ = "hostel:incident:read"
INCIDENT_MANAGE = "hostel:incident:manage"
NOTICE_PUBLISH = "hostel:notice:publish"
SELF_READ = "hostel:self:read"
SELF_REQUEST = "hostel:self:request"

# Domain rule code -> HTTP status.
RULE_STATUS = {
    "invalid_status": 409,
    "capacity_below_occupancy": 409,
    "invalid_bed": 422,
    "invalid_dates": 422,
    "id_number_too_long": 422,
    "own_request": 403,
}


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


def today() -> date:
    return clock().date()


@dataclass
class Actor:
    """Who is calling. Built by the API layer from the verified token."""

    user_id: str
    organisation_id: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


class HostelError(Exception):
    """A refusal with an HTTP status and an error body ({code, message})."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def body(self) -> dict:
        return {"code": self.code, "message": self.message}


def _not_found(what: str) -> HostelError:
    return HostelError(404, "not_found", f"{what} not found in your organisation")


def _conflict(code: str, message: str) -> HostelError:
    return HostelError(409, code, message)


def _rule(v: RuleViolationError) -> HostelError:
    return HostelError(RULE_STATUS.get(v.code, 422), v.code, v.message)


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


def _get(db: Session, model, row_id: str, what: str):
    row = repo.get(db, model, row_id)
    if row is None:
        raise _not_found(what)
    return row


# ---------------------------------------------------------------- serialisation


def hostel_dict(h: Hostel) -> dict:
    return {
        "id": h.id,
        "organisation_id": h.organisation_id,
        "name": h.name,
        "occupancy_type": h.occupancy_type,
        "warden_ids": list(h.warden_ids or []),
        "active": h.active,
    }


def room_dict(r: Room, free: list[str]) -> dict:
    return {
        "id": r.id,
        "organisation_id": r.organisation_id,
        "hostel_id": r.hostel_id,
        "number": r.number,
        "floor": r.floor,
        "room_type": r.room_type,
        "capacity": r.capacity,
        "status": r.status,
        "free_beds": free,
    }


def allocation_dict(db: Session, a: Allocation) -> dict:
    room = repo.get(db, Room, a.room_id) if a.room_id else None
    return {
        "id": a.id,
        "organisation_id": a.organisation_id,
        "person_id": a.person_id,
        "person_name": a.person_name,
        "academic_year": a.academic_year,
        "status": a.status,
        "preferred_hostel_id": a.preferred_hostel_id,
        "preferred_room_type": a.preferred_room_type,
        "notes": a.notes,
        "hostel_id": a.hostel_id,
        "room_id": a.room_id,
        "room_number": room.number if room else None,
        "bed": a.bed,
        "from": iso(a.from_date),
        "to": iso(a.to_date),
        "checked_in_at": iso(a.checked_in_at),
        "checked_out_at": iso(a.checked_out_at),
        "condition_notes": a.condition_notes,
        "cancel_reason": a.cancel_reason,
    }


def menu_dict(m: MessMenu) -> dict:
    return {
        "organisation_id": m.organisation_id,
        "hostel_id": m.hostel_id,
        "date": iso(m.menu_date),
        "meal": m.meal,
        "items": list(m.items or []),
    }


def leave_dict(lv: LeaveRequest) -> dict:
    return {
        "id": lv.id,
        "organisation_id": lv.organisation_id,
        "person_id": lv.person_id,
        "person_name": lv.person_name,
        "hostel_id": lv.hostel_id,
        "from": iso(lv.from_at),
        "to": iso(lv.to_at),
        "destination": lv.destination,
        "reason": lv.reason,
        "contact_phone": lv.contact_phone,
        "status": lv.status,
        "decided_by": lv.decided_by,
        "decision_reason": lv.decision_reason,
        "departed_at": iso(lv.departed_at),
        "departure_recorded_by": lv.departure_recorded_by,
        "returned_at": iso(lv.returned_at),
        "return_recorded_by": lv.return_recorded_by,
    }


def visit_dict(v: Visit) -> dict:
    return {
        "id": v.id,
        "organisation_id": v.organisation_id,
        "hostel_id": v.hostel_id,
        "person_id": v.person_id,
        "visitor_name": v.visitor_name,
        "relation": v.relation,
        "id_document_note": v.id_document_note,
        "in_at": iso(v.in_at),
        "out_at": iso(v.out_at),
        "recorded_by": v.recorded_by,
    }


def incident_dict(i: Incident) -> dict:
    return {
        "id": i.id,
        "organisation_id": i.organisation_id,
        "hostel_id": i.hostel_id,
        "person_id": i.person_id,
        "occurred_at": iso(i.occurred_at),
        "category": i.category,
        "description": i.description,
        "action_taken": i.action_taken,
        "status": i.status,
        "recorded_by": i.recorded_by,
        "closed_at": iso(i.closed_at),
    }


def notice_dict(n: Notice) -> dict:
    return {
        "id": n.id,
        "organisation_id": n.organisation_id,
        "hostel_id": n.hostel_id,
        "title": n.title,
        "body": n.body,
        "expires_at": iso(n.expires_at),
        "published_at": iso(n.published_at),
        "published_by": n.published_by,
        "status": rules.notice_status(as_utc(n.withdrawn_at), as_utc(n.expires_at), clock()),
    }


def _page(items: list[dict], next_cursor: str | None) -> dict:
    return {"items": items, "next_cursor": next_cursor}


# ---------------------------------------------------------------- hostels and rooms


def list_hostels(db: Session, active: bool | None) -> list[dict]:
    return [hostel_dict(h) for h in repo.hostels(db, active)]


def create_hostel(db: Session, actor: Actor, data: dict) -> dict:
    h = Hostel(
        organisation_id=actor.organisation_id,
        name=data["name"],
        occupancy_type=data["occupancy_type"],
        warden_ids=list(data.get("warden_ids") or []),
        active=data.get("active", True),
    )
    db.add(h)
    db.flush()
    _audit(db, actor, "hostel.created", "hostel", h.id, actor.organisation_id)
    db.commit()
    return hostel_dict(h)


def update_hostel(db: Session, actor: Actor, hostel_id: str, data: dict) -> dict:
    h = _get(db, Hostel, hostel_id, "hostel")
    for key in ("name", "occupancy_type", "active"):
        if data.get(key) is not None:
            setattr(h, key, data[key])
    if data.get("warden_ids") is not None:
        h.warden_ids = list(data["warden_ids"])
    _audit(db, actor, "hostel.updated", "hostel", h.id, actor.organisation_id)
    db.commit()
    return hostel_dict(h)


def _held_beds_by_room(db: Session, rooms: list[Room]) -> dict[str, list[str]]:
    held: dict[str, list[str]] = {r.id: [] for r in rooms}
    for a in repo.holding_allocations(db, [r.id for r in rooms], on=today()):
        held[a.room_id].append(a.bed)
    return held


def get_hostel(db: Session, hostel_id: str) -> dict:
    h = _get(db, Hostel, hostel_id, "hostel")
    rooms = repo.rooms(db, hostel_id)
    holding = repo.holding_allocations(db, [r.id for r in rooms], on=today())
    return {
        **hostel_dict(h),
        "rooms": len(rooms),
        "beds": sum(r.capacity for r in rooms),
        "beds_occupied": sum(1 for a in holding if a.status == "occupied"),
        "beds_confirmed": sum(1 for a in holding if a.status == "confirmed"),
    }


def _free(r: Room, hostel_active: bool, held: list[str]) -> list[str]:
    """Free beds that can be allocated: none while the room is closed or the hostel inactive."""
    if r.status != "open" or not hostel_active:
        return []
    return rules.free_beds(r.capacity, held)


def list_rooms(db: Session, hostel_id: str, status: str | None, has_free_bed: bool | None) -> list[dict]:
    h = _get(db, Hostel, hostel_id, "hostel")
    rooms = repo.rooms(db, hostel_id, status)
    held = _held_beds_by_room(db, rooms)
    out = [room_dict(r, _free(r, h.active, held[r.id])) for r in rooms]
    if has_free_bed is not None:
        out = [r for r in out if bool(r["free_beds"]) == has_free_bed]
    return out


def add_room(db: Session, actor: Actor, hostel_id: str, data: dict) -> dict:
    h = _get(db, Hostel, hostel_id, "hostel")
    if repo.room_by_number(db, hostel_id, data["number"]):
        raise _conflict("room_exists", f"room {data['number']} already exists in this hostel")
    r = Room(
        organisation_id=actor.organisation_id,
        hostel_id=hostel_id,
        number=data["number"],
        floor=data.get("floor"),
        room_type=data["room_type"],
        capacity=data["capacity"],
        status="open",
    )
    db.add(r)
    db.flush()
    _audit(db, actor, "room.created", "room", r.id, actor.organisation_id)
    db.commit()
    return room_dict(r, _free(r, h.active, []))


def update_room(db: Session, actor: Actor, room_id: str, data: dict) -> dict:
    r = repo.room_for_update(db, room_id)
    if r is None:
        raise _not_found("room")
    held = _held_beds_by_room(db, [r])[r.id]
    if data.get("room_type") is not None:
        r.room_type = data["room_type"]
    if data.get("capacity") is not None:
        try:
            rules.check_capacity_change(data["capacity"], held)
        except RuleViolationError as v:
            raise _rule(v) from v
        r.capacity = data["capacity"]
    new_status = data.get("status")
    if new_status == "closed" and r.status != "closed":
        reason = (data.get("reason") or "").strip()
        if not reason:
            raise HostelError(422, "reason_required", "a reason is required to close a room")
        r.status, r.close_reason = "closed", reason
        _publish(
            db, actor, "room.closed", r.organisation_id, {"room_id": r.id, "hostel_id": r.hostel_id, "reason": reason}
        )
        _audit(db, actor, "room.closed", "room", r.id, r.organisation_id)
    elif new_status == "open" and r.status != "open":
        r.status, r.close_reason = "open", None
        _publish(db, actor, "room.reopened", r.organisation_id, {"room_id": r.id, "hostel_id": r.hostel_id})
        _audit(db, actor, "room.reopened", "room", r.id, r.organisation_id)
    _audit(db, actor, "room.updated", "room", r.id, r.organisation_id)
    db.commit()
    h = repo.get(db, Hostel, r.hostel_id)
    return room_dict(r, _free(r, bool(h and h.active), held))


# ---------------------------------------------------------------- allocations


def list_allocations(db: Session, filters: dict, cursor: str | None, limit: int) -> dict:
    rows, nxt = repo.page(db, repo.allocations_query(db, **filters), cursor, limit)
    return _page([allocation_dict(db, a) for a in rows], nxt)


def get_allocation(db: Session, allocation_id: str) -> dict:
    return allocation_dict(db, _get(db, Allocation, allocation_id, "allocation"))


def request_room(db: Session, actor: Actor, data: dict) -> dict:
    year = data["academic_year"]
    if repo.open_for_year(db, actor.user_id, year):
        raise _conflict("already_requested", f"an open request or allocation already exists for {year}")
    if data.get("preferred_hostel_id"):
        _get(db, Hostel, data["preferred_hostel_id"], "hostel")
    a = Allocation(
        organisation_id=actor.organisation_id,
        person_id=actor.user_id,
        academic_year=year,
        status="requested",
        preferred_hostel_id=data.get("preferred_hostel_id"),
        preferred_room_type=data.get("preferred_room_type"),
        notes=data.get("notes"),
    )
    db.add(a)
    db.flush()
    _publish(
        db,
        actor,
        "allocation.requested",
        a.organisation_id,
        {
            "allocation_id": a.id,
            "person_id": a.person_id,
            "academic_year": year,
            "preferred_room_type": a.preferred_room_type or "",
        },
    )
    _audit(db, actor, "allocation.requested", "allocation", a.id, a.organisation_id)
    db.commit()
    return allocation_dict(db, a)


def _held_period(a: Allocation) -> Period:
    """The dates an allocation holds its bed: an occupied one holds it until check-out, not until its planned to_date."""
    return Period(a.from_date, None if a.status == "occupied" else a.to_date)


def _assign_bed(db: Session, a: Allocation, room_id: str, bed: str, start: date | None, end: date | None) -> Room:
    """Check the bed is allocatable for the period, then put the allocation on it. Locks the room first."""
    room = repo.room_for_update(db, room_id)
    if room is None:
        raise _not_found("room")
    hostel = repo.get(db, Hostel, room.hostel_id)
    if room.status != "open" or hostel is None or not hostel.active:
        raise _conflict("room_closed", "the room is closed or its hostel is inactive")
    try:
        rules.check_bed(room.capacity, bed)
        period = rules.check_period(start or today(), end)
    except RuleViolationError as v:
        raise _rule(v) from v
    for other in repo.holding_allocations(db, [room.id]):
        if other.id != a.id and other.bed == bed and period.overlaps(_held_period(other)):
            raise _conflict("bed_taken", f"bed {bed} is taken for these dates")
    for other in repo.person_holding(db, a.person_id, exclude_id=a.id):
        if period.overlaps(_held_period(other)):
            raise _conflict("person_allocated", "the person already has a bed for these dates")
    a.hostel_id, a.room_id, a.bed = room.hostel_id, room.id, bed
    a.from_date, a.to_date = period.start, period.end
    return room


def _confirmed(db: Session, actor: Actor, a: Allocation, room: Room) -> None:
    _publish(
        db,
        actor,
        "allocation.confirmed",
        a.organisation_id,
        {
            "allocation_id": a.id,
            "person_id": a.person_id,
            "hostel_id": a.hostel_id,
            "room_id": a.room_id,
            "room_type": room.room_type,
            "academic_year": a.academic_year,
            "from": iso(a.from_date),
            "to": iso(a.to_date),
        },
    )
    _audit(db, actor, "allocation.confirmed", "allocation", a.id, a.organisation_id)


def allocate_direct(db: Session, actor: Actor, data: dict) -> dict:
    year = data["academic_year"]
    existing = repo.open_for_year(db, data["person_id"], year)
    if existing is not None and existing.status == "requested":
        # the person's own request must be confirmed (or cancelled), not shadowed by a second row
        raise _conflict(
            "already_requested", f"the person has an open room request for {year}; confirm or cancel it first"
        )
    a = Allocation(
        organisation_id=actor.organisation_id,
        person_id=data["person_id"],
        academic_year=data["academic_year"],
        status="confirmed",
    )
    room = _assign_bed(db, a, data["room_id"], data["bed"], data["from"], data["to"])
    db.add(a)
    db.flush()
    _confirmed(db, actor, a, room)
    db.commit()
    return allocation_dict(db, a)


def _transition(a: Allocation, action: str) -> None:
    try:
        a.status = rules.transition(ALLOCATION_TRANSITIONS, action, a.status)
    except RuleViolationError as v:
        raise _rule(v) from v


def confirm_allocation(db: Session, actor: Actor, allocation_id: str, data: dict) -> dict:
    a = _get(db, Allocation, allocation_id, "allocation")
    if a.status != "requested":
        raise _conflict("invalid_status", f"cannot confirm when status is {a.status}")
    room = _assign_bed(db, a, data["room_id"], data["bed"], data.get("from"), data.get("to"))
    _transition(a, "confirm")
    _confirmed(db, actor, a, room)
    db.commit()
    return allocation_dict(db, a)


def check_in(db: Session, actor: Actor, allocation_id: str) -> dict:
    a = _get(db, Allocation, allocation_id, "allocation")
    _transition(a, "check_in")
    a.checked_in_at = clock()
    _publish(
        db,
        actor,
        "allocation.occupied",
        a.organisation_id,
        {
            "allocation_id": a.id,
            "person_id": a.person_id,
            "hostel_id": a.hostel_id,
            "checked_in_at": iso(a.checked_in_at),
        },
    )
    _audit(db, actor, "allocation.occupied", "allocation", a.id, a.organisation_id)
    db.commit()
    return allocation_dict(db, a)


def check_out(db: Session, actor: Actor, allocation_id: str, condition_notes: str | None) -> dict:
    a = _get(db, Allocation, allocation_id, "allocation")
    _transition(a, "check_out")
    a.checked_out_at = clock()
    a.condition_notes = condition_notes
    _publish(
        db,
        actor,
        "allocation.vacated",
        a.organisation_id,
        {
            "allocation_id": a.id,
            "person_id": a.person_id,
            "hostel_id": a.hostel_id,
            "checked_out_at": iso(a.checked_out_at),
        },
    )
    _audit(db, actor, "allocation.vacated", "allocation", a.id, a.organisation_id)
    db.commit()
    return allocation_dict(db, a)


def cancel_allocation(db: Session, actor: Actor, allocation_id: str, reason: str) -> dict:
    a = _get(db, Allocation, allocation_id, "allocation")
    if not actor.can(ALLOCATION_MANAGE):
        # hostel:self:request covers the caller's own room request only.
        if a.person_id != actor.user_id:
            raise _not_found("allocation")
        if a.status == "confirmed":
            raise HostelError(403, "forbidden", "only the hostel office or a warden can cancel a confirmed allocation")
    was_confirmed = a.status == "confirmed"
    _transition(a, "cancel")
    a.cancel_reason = reason
    _publish(
        db,
        actor,
        "allocation.cancelled",
        a.organisation_id,
        {
            "allocation_id": a.id,
            "person_id": a.person_id,
            "academic_year": a.academic_year,
            "was_confirmed": was_confirmed,
            "reason": reason,
        },
    )
    _audit(db, actor, "allocation.cancelled", "allocation", a.id, a.organisation_id)
    db.commit()
    return allocation_dict(db, a)


def _current_or_upcoming(db: Session, person_id: str) -> Allocation | None:
    holding = [
        a
        for a in repo.person_allocations(db, person_id)
        if a.status in rules.BED_HOLDING and (a.status == "occupied" or a.to_date is None or a.to_date >= today())
    ]
    holding.sort(key=lambda a: (a.status != "occupied", a.from_date or date.min))
    return holding[0] if holding else None


def my_allocation(db: Session, actor: Actor) -> dict:
    a = _current_or_upcoming(db, actor.user_id)
    if a is None:
        a = next((x for x in repo.person_allocations(db, actor.user_id) if x.status == "requested"), None)
    hostel = repo.get(db, Hostel, a.hostel_id) if a and a.hostel_id else None
    return {"allocation": allocation_dict(db, a) if a else None, "hostel": hostel_dict(hostel) if hostel else None}


# ---------------------------------------------------------------- mess menu


def get_menus(db: Session, hostel_id: str, start: date, end: date) -> list[dict]:
    if end < start:
        raise HostelError(422, "invalid_dates", "to must not be before from")
    _get(db, Hostel, hostel_id, "hostel")
    return [menu_dict(m) for m in repo.menus(db, hostel_id, start, end)]


def set_menus(db: Session, actor: Actor, entries: list[dict]) -> list[dict]:
    out = []
    for e in entries:
        _get(db, Hostel, e["hostel_id"], "hostel")
        row = repo.menu_row(db, e["hostel_id"], e["date"], e["meal"])
        if row is None:
            row = MessMenu(
                organisation_id=actor.organisation_id, hostel_id=e["hostel_id"], menu_date=e["date"], meal=e["meal"]
            )
            db.add(row)
        row.items = list(e["items"])
        row.updated_by = actor.user_id
        db.flush()
        _audit(db, actor, "mess_menu.set", "mess_menu", row.id, actor.organisation_id)
        out.append(row)
    db.commit()
    return [menu_dict(m) for m in out]


# ---------------------------------------------------------------- leave


def _resident_allocation(db: Session, person_id: str) -> Allocation:
    a = repo.occupied_allocation(db, person_id)
    if a is None:
        raise _conflict("not_resident", "the person is not a current resident")
    return a


def apply_leave(db: Session, actor: Actor, data: dict) -> dict:
    alloc = _resident_allocation(db, actor.user_id)
    start, end = as_utc(data["from"]), as_utc(data["to"])
    try:
        rules.check_leave_window(start, end)
    except RuleViolationError as v:
        raise _rule(v) from v
    for other in repo.blocking_leave(db, actor.user_id):
        if rules.windows_overlap(start, end, as_utc(other.from_at), as_utc(other.to_at)):
            raise _conflict("leave_overlaps", "the dates overlap another leave request")
    lv = LeaveRequest(
        organisation_id=actor.organisation_id,
        person_id=actor.user_id,
        hostel_id=alloc.hostel_id,
        from_at=start,
        to_at=end,
        destination=data["destination"],
        reason=data["reason"],
        contact_phone=data.get("contact_phone"),
        status="requested",
    )
    db.add(lv)
    db.flush()
    _publish(
        db,
        actor,
        "leave.requested",
        lv.organisation_id,
        {"leave_id": lv.id, "person_id": lv.person_id, "hostel_id": lv.hostel_id, "from": iso(start), "to": iso(end)},
    )
    _audit(db, actor, "leave.requested", "leave", lv.id, lv.organisation_id)
    db.commit()
    return leave_dict(lv)


def _leave_transition(lv: LeaveRequest, action: str) -> None:
    try:
        lv.status = rules.transition(LEAVE_TRANSITIONS, action, lv.status)
    except RuleViolationError as v:
        raise _rule(v) from v


def withdraw_leave(db: Session, actor: Actor, leave_id: str) -> dict:
    lv = _get(db, LeaveRequest, leave_id, "leave request")
    if lv.person_id != actor.user_id:
        raise _not_found("leave request")
    _leave_transition(lv, "withdraw")
    _audit(db, actor, "leave.withdrawn", "leave", lv.id, lv.organisation_id)
    db.commit()
    return leave_dict(lv)


def my_leave(db: Session, actor: Actor) -> list[dict]:
    return [leave_dict(lv) for lv in repo.person_leave(db, actor.user_id)]


GATE_VISIBLE = rules.LEAVE_AWAY + ("returned",)


def list_leave(
    db: Session,
    actor: Actor,
    status: str | None,
    hostel_id: str | None,
    overdue: bool | None,
    cursor: str | None,
    limit: int,
) -> dict:
    """Approvers see every leave request. The security desk (gate:record only) sees gate passes: approved, out,
    returned. Pending and refused requests carry the resident's reason and contacts and stay with the approvers."""
    statuses: tuple[str, ...] | None = None
    if not actor.can(LEAVE_APPROVE):
        if status is not None and status not in GATE_VISIBLE:
            raise HostelError(403, "forbidden", f"listing {status} leave requests requires {LEAVE_APPROVE}")
        statuses = (status,) if status else GATE_VISIBLE
        status = None
    q = repo.leave_query(db, clock(), status, hostel_id, overdue, statuses=statuses)
    rows, nxt = repo.page(db, q, cursor, limit)
    return _page([leave_dict(lv) for lv in rows], nxt)


def decide_leave(db: Session, actor: Actor, leave_id: str, decision: str, reason: str | None) -> dict:
    lv = _get(db, LeaveRequest, leave_id, "leave request")
    try:
        rules.check_not_own_decision(lv.person_id, actor.user_id)
    except RuleViolationError as v:
        raise _rule(v) from v
    _leave_transition(lv, "approve" if decision == "approved" else "reject")
    lv.decided_by, lv.decided_at, lv.decision_reason = actor.user_id, clock(), reason
    if decision == "approved":
        payload = {
            "leave_id": lv.id,
            "person_id": lv.person_id,
            "from": iso(lv.from_at),
            "to": iso(lv.to_at),
            "decided_by": actor.user_id,
        }
    else:
        payload = {"leave_id": lv.id, "person_id": lv.person_id, "decided_by": actor.user_id}
    _publish(db, actor, f"leave.{decision}", lv.organisation_id, payload)
    _audit(db, actor, f"leave.{decision}", "leave", lv.id, lv.organisation_id)
    db.commit()
    return leave_dict(lv)


def _returned(db: Session, actor: Actor, lv: LeaveRequest, action: str) -> dict:
    """Shared end of the gate-in and the warden's return: record who and when, publish, audit."""
    _leave_transition(lv, action)
    lv.returned_at, lv.return_recorded_by = clock(), actor.user_id
    _publish(
        db,
        actor,
        "leave.returned",
        lv.organisation_id,
        {"leave_id": lv.id, "person_id": lv.person_id, "returned_at": iso(lv.returned_at)},
    )
    _audit(db, actor, f"leave.{action}", "leave", lv.id, lv.organisation_id)
    db.commit()
    return leave_dict(lv)


def mark_returned(db: Session, actor: Actor, leave_id: str) -> dict:
    """The warden marks a return the gate did not record (approved or out -> returned)."""
    return _returned(db, actor, _get(db, LeaveRequest, leave_id, "leave request"), "return")


def gate_out(db: Session, actor: Actor, leave_id: str) -> dict:
    """Security records the resident leaving through the gate on an approved pass (approved -> out)."""
    lv = _get(db, LeaveRequest, leave_id, "leave request")
    _leave_transition(lv, "gate_out")
    lv.departed_at, lv.departure_recorded_by = clock(), actor.user_id
    _publish(
        db,
        actor,
        "leave.departed",
        lv.organisation_id,
        {"leave_id": lv.id, "person_id": lv.person_id, "hostel_id": lv.hostel_id, "departed_at": iso(lv.departed_at)},
    )
    _audit(db, actor, "leave.gate_out", "leave", lv.id, lv.organisation_id)
    db.commit()
    return leave_dict(lv)


def gate_in(db: Session, actor: Actor, leave_id: str) -> dict:
    """Security records the resident coming back through the gate (out -> returned)."""
    return _returned(db, actor, _get(db, LeaveRequest, leave_id, "leave request"), "gate_in")


# ---------------------------------------------------------------- visits


def record_visit(db: Session, actor: Actor, data: dict) -> dict:
    try:
        rules.check_id_document_note(data.get("id_document_note"))
    except RuleViolationError as v:
        raise _rule(v) from v
    alloc = _resident_allocation(db, data["person_id"])
    v = Visit(
        organisation_id=actor.organisation_id,
        hostel_id=alloc.hostel_id,
        person_id=data["person_id"],
        visitor_name=data["visitor_name"],
        relation=data.get("relation"),
        id_document_note=data.get("id_document_note"),
        in_at=clock(),
        recorded_by=actor.user_id,
    )
    db.add(v)
    db.flush()
    _audit(db, actor, "visit.in", "visit", v.id, v.organisation_id)
    db.commit()
    return visit_dict(v)


def visit_out(db: Session, actor: Actor, visit_id: str) -> dict:
    v = _get(db, Visit, visit_id, "visit")
    if v.out_at is not None:
        raise _conflict("already_out", "the visitor has already left")
    v.out_at = clock()
    _audit(db, actor, "visit.out", "visit", v.id, v.organisation_id)
    db.commit()
    return visit_dict(v)


def list_visits(
    db: Session, hostel_id: str | None, person_id: str | None, on: date | None, cursor: str | None, limit: int
) -> dict:
    q = repo.visits_query(db, hostel_id, person_id)
    if on is not None:
        rows = [v for v in db.scalars(q) if as_utc(v.in_at).date() == on]
        offset = repo.decode_cursor(cursor)
        chunk = rows[offset : offset + limit]
        nxt = repo.encode_cursor(offset + limit) if len(rows) > offset + limit else None
        return _page([visit_dict(v) for v in chunk], nxt)
    rows, nxt = repo.page(db, q, cursor, limit)
    return _page([visit_dict(v) for v in rows], nxt)


def my_visits(db: Session, actor: Actor) -> list[dict]:
    return [visit_dict(v) for v in repo.person_visits(db, actor.user_id)]


# ---------------------------------------------------------------- incidents


def _incident_hostel(db: Session, person_id: str) -> str:
    """The resident's current hostel, else the hostel of their latest allocation."""
    a = repo.occupied_allocation(db, person_id)
    if a is None:
        a = next((x for x in repo.person_allocations(db, person_id) if x.hostel_id), None)
    if a is None:
        raise _conflict("not_resident", "the person has no hostel allocation")
    return a.hostel_id


def record_incident(db: Session, actor: Actor, data: dict) -> dict:
    i = Incident(
        organisation_id=actor.organisation_id,
        person_id=data["person_id"],
        hostel_id=_incident_hostel(db, data["person_id"]),
        occurred_at=as_utc(data["occurred_at"]),
        category=data["category"],
        description=data["description"],
        action_taken=data.get("action_taken"),
        status="open",
        recorded_by=actor.user_id,
    )
    db.add(i)
    db.flush()
    _audit(db, actor, "incident.recorded", "incident", i.id, i.organisation_id)
    db.commit()
    return incident_dict(i)


def update_incident(db: Session, actor: Actor, incident_id: str, data: dict) -> dict:
    i = _get(db, Incident, incident_id, "incident")
    if data.get("action_taken") is not None:
        i.action_taken = data["action_taken"]
    status = data.get("status")
    if status == "closed" and i.status != "closed":
        i.status, i.closed_at = "closed", clock()
        _audit(db, actor, "incident.closed", "incident", i.id, i.organisation_id)
    elif status == "open" and i.status != "open":
        i.status, i.closed_at = "open", None
        _audit(db, actor, "incident.reopened", "incident", i.id, i.organisation_id)
    _audit(db, actor, "incident.updated", "incident", i.id, i.organisation_id)
    db.commit()
    return incident_dict(i)


def list_incidents(
    db: Session, hostel_id: str | None, person_id: str | None, status: str | None, cursor: str | None, limit: int
) -> dict:
    rows, nxt = repo.page(db, repo.incidents_query(db, hostel_id, person_id, status), cursor, limit)
    return _page([incident_dict(i) for i in rows], nxt)


# ---------------------------------------------------------------- notices


def list_notices(db: Session, hostel_id: str | None) -> list[dict]:
    return [notice_dict(n) for n in repo.notices(db, hostel_id)]


def publish_notice(db: Session, actor: Actor, data: dict) -> dict:
    if data.get("hostel_id"):
        _get(db, Hostel, data["hostel_id"], "hostel")
    expires = as_utc(data.get("expires_at"))
    if expires is not None and expires <= clock():
        raise HostelError(422, "invalid_dates", "expires_at must be in the future")
    n = Notice(
        organisation_id=actor.organisation_id,
        hostel_id=data.get("hostel_id"),
        title=data["title"],
        body=data["body"],
        expires_at=expires,
        published_at=clock(),
        published_by=actor.user_id,
    )
    db.add(n)
    db.flush()
    _publish(
        db,
        actor,
        "notice.published",
        n.organisation_id,
        {"notice_id": n.id, "hostel_id": n.hostel_id, "title": n.title},
    )
    _audit(db, actor, "notice.published", "notice", n.id, n.organisation_id)
    db.commit()
    return notice_dict(n)


def withdraw_notice(db: Session, actor: Actor, notice_id: str) -> dict:
    n = _get(db, Notice, notice_id, "notice")
    status = rules.notice_status(as_utc(n.withdrawn_at), as_utc(n.expires_at), clock())
    if status != "current":
        raise _conflict("invalid_status", f"cannot withdraw a notice that is {status}")
    n.withdrawn_at, n.withdrawn_by = clock(), actor.user_id
    _audit(db, actor, "notice.withdrawn", "notice", n.id, n.organisation_id)
    db.commit()
    return notice_dict(n)


def my_notices(db: Session, actor: Actor, limit: int) -> list[dict]:
    a = _current_or_upcoming(db, actor.user_id)
    hostel_id = a.hostel_id if a else None
    now = clock()
    out = []
    for n in repo.candidate_notices_for(db, hostel_id):
        if not rules.notice_visible_to(n.hostel_id, hostel_id):
            continue
        if rules.notice_status(as_utc(n.withdrawn_at), as_utc(n.expires_at), now) != "current":
            continue
        out.append(notice_dict(n))
        if len(out) >= limit:
            break
    return out
