"""Leave types, leave requests and balances.

A request covers calendar days inside one leave year (HR_PAYROLL_LEAVE_YEAR_START_MONTH). A paid leave type is
limited by the balance: the year's entitlement (a share of it in the year of joining), plus what was carried forward
from the year before up to the type's limit, less what is approved and pending. An unpaid type has no balance; its
approved days are loss of pay in the payroll. Nobody decides their own request, and a request is withdrawn only
before it starts."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import number
from ..infrastructure.config import load_settings
from ..infrastructure.models import Employee, LeaveRequest, LeaveType, PayrollRun
from . import common, employees
from .access import Actor
from .common import audit, get, iso, publish, q, rule, text
from .errors import conflict, forbidden, invalid

# ---------------------------------------------------------------- leave types


def leave_type_dict(t: LeaveType) -> dict:
    return {
        "id": t.id,
        "organisation_id": t.organisation_id,
        "code": t.code,
        "name": t.name,
        "days_per_year": number(Decimal(t.days_per_year)),
        "carry_forward_max": number(Decimal(t.carry_forward_max)),
        "paid": t.paid,
        "half_day_allowed": t.half_day_allowed,
        "applies_to": list(t.applies_to or []),
        "active": t.active,
    }


def list_leave_types(db: Session) -> list[dict]:
    return [leave_type_dict(t) for t in db.scalars(q(db, LeaveType).order_by(LeaveType.code))]


def _leave_type_values(db: Session, t: LeaveType, body: dict) -> None:
    code = text(body["code"]).upper()
    name = text(body["name"])
    if not code:
        raise invalid("invalid_code", "code is required", "code")
    if not name:
        raise invalid("invalid_name", "name is required", "name")
    taken = q(db, LeaveType).where(LeaveType.code == code)
    if t.id:
        taken = taken.where(LeaveType.id != t.id)
    if db.scalar(taken) is not None:
        raise conflict("leave_type_code_taken", "another leave type has this code")
    t.code, t.name = code, name
    t.days_per_year = rule(rules.parse_days, body["days_per_year"], "days_per_year")
    t.carry_forward_max = rule(rules.parse_days, body.get("carry_forward_max") or 0, "carry_forward_max")
    t.paid = bool(body.get("paid", True))
    t.half_day_allowed = bool(body.get("half_day_allowed", True))
    applies = body.get("applies_to")
    t.applies_to = sorted(set(applies or rules.EMPLOYMENT_TYPES))
    t.active = bool(body.get("active", True))


@common.duplicate_is_409("leave_type_code_taken", "another leave type has this code")
def create_leave_type(db: Session, actor: Actor, body: dict) -> dict:
    t = LeaveType(organisation_id=actor.organisation_id)
    _leave_type_values(db, t, body)
    db.add(t)
    audit(db, actor.user_id, "leave_type.created", "leave_type", t)
    db.commit()
    return leave_type_dict(t)


@common.duplicate_is_409("leave_type_code_taken", "another leave type has this code")
def update_leave_type(db: Session, actor: Actor, leave_type_id: str, body: dict) -> dict:
    t = get(db, LeaveType, leave_type_id, "leave type", lock=True)
    _leave_type_values(db, t, body)
    audit(db, actor.user_id, "leave_type.updated", "leave_type", t)
    db.commit()
    return leave_type_dict(t)


# ---------------------------------------------------------------- balances


def balance(db: Session, e: Employee, t: LeaveType, year: int) -> dict:
    """The leave year's balance of one type. Carry-forward is worked out year by year from the year of joining: what a
    year leaves unused, up to the type's limit, opens the next. An unpaid type carries nothing forward."""
    start = load_settings().leave_year_start_month
    used: dict[int, Decimal] = defaultdict(Decimal)
    pending: dict[int, Decimal] = defaultdict(Decimal)
    rows = q(db, LeaveRequest).where(
        LeaveRequest.employee_id == e.id,
        LeaveRequest.leave_type_id == t.id,
        LeaveRequest.status.in_(("approved", "pending")),
    )
    for r in db.scalars(rows):
        bucket = used if r.status == "approved" else pending
        bucket[rules.leave_year(r.from_date, start)] += Decimal(r.days)
    carried = Decimal(0)
    for y in range(rules.leave_year(e.joined_on, start), year):
        entitled_y = rules.entitlement(Decimal(t.days_per_year), e.joined_on, y, start)
        carried = (
            rules.carried_into_next_year(entitled_y, carried, used[y], Decimal(t.carry_forward_max))
            if t.paid
            else Decimal(0)
        )
    entitled = rules.entitlement(Decimal(t.days_per_year), e.joined_on, year, start)
    available = entitled + carried - used[year] - pending[year]
    return {
        "leave_type_id": t.id,
        "name": t.name,
        "code": t.code,
        "paid": t.paid,
        "leave_year": year,
        "entitled": number(entitled),
        "carried_forward": number(carried),
        "taken": number(used[year]),
        "pending": number(pending[year]),
        "available": number(available),
        "_available": available,
    }


def _applicable(t: LeaveType, e: Employee) -> bool:
    return t.active and e.employment_type in (t.applies_to or [])


def my_balances(db: Session, actor: Actor) -> list[dict]:
    e = common.require_own_employee(db, actor)
    year = rules.leave_year(common.business_today(), load_settings().leave_year_start_month)
    out = []
    for t in db.scalars(q(db, LeaveType).order_by(LeaveType.code)):
        if _applicable(t, e):
            b = balance(db, e, t, year)
            b.pop("_available")
            out.append(b)
    return out


# ---------------------------------------------------------------- requests


def request_dict(r: LeaveRequest, names: dict[str, str], types: dict[str, str] | None = None) -> dict:
    return {
        "id": r.id,
        "organisation_id": r.organisation_id,
        "employee_id": r.employee_id,
        "employee_name": names.get(r.employee_id, ""),
        "leave_type_id": r.leave_type_id,
        "leave_type_name": (types or {}).get(r.leave_type_id, ""),
        "from": iso(r.from_date),
        "to": iso(r.to_date),
        "half_day": r.half_day,
        "reason": r.reason,
        "days": number(Decimal(r.days)),
        "paid": r.paid,
        "status": r.status,
        "approver_id": r.approver_id,
        "decided_by": r.decided_by,
        "decided_at": iso(r.decided_at),
        "note": r.note,
        "created_at": iso(r.created_at),
    }


def _type_names(db: Session, ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    return {t.id: t.name for t in db.scalars(q(db, LeaveType).where(LeaveType.id.in_(ids)))}


def _render(db: Session, rows: list[LeaveRequest]):
    names = employees.names(db, {r.employee_id for r in rows})
    types = _type_names(db, {r.leave_type_id for r in rows})
    return lambda r: request_dict(r, names, types)


def list_requests(
    db: Session,
    status: str | None,
    employee_id: str | None,
    department_id: str | None,
    start: date | None,
    end: date | None,
    cursor: str | None,
    limit: int,
) -> dict:
    """Requests of the organisation. Pending ones come soonest first (the HR Staff widget), others newest first.
    `pending_total` counts the pending requests that match every filter but status."""
    query = q(db, LeaveRequest)
    if employee_id:
        query = query.where(LeaveRequest.employee_id == employee_id)
    if department_id:
        in_department = q(db, Employee).where(Employee.department_id == department_id).with_only_columns(Employee.id)
        query = query.where(LeaveRequest.employee_id.in_(in_department))
    if start:
        query = query.where(LeaveRequest.to_date >= start)
    if end:
        query = query.where(LeaveRequest.from_date <= end)
    rows = list(db.scalars(query))
    pending_total = sum(1 for r in rows if r.status == "pending")
    if status:
        rows = [r for r in rows if r.status == status]
    if status == "pending":
        rows.sort(key=lambda r: (r.from_date, r.created_at, r.id))
    else:
        rows.sort(key=lambda r: (common.aware(r.created_at), r.id), reverse=True)
    out = common.page(rows, cursor, limit, _render(db, rows))
    return {"items": out["items"], "pending_total": pending_total, "next_cursor": out["next_cursor"]}


def my_requests(db: Session, actor: Actor) -> list[dict]:
    e = common.require_own_employee(db, actor)
    rows = list(db.scalars(q(db, LeaveRequest).where(LeaveRequest.employee_id == e.id)))
    rows.sort(key=lambda r: (r.from_date, common.aware(r.created_at)), reverse=True)
    render = _render(db, rows)
    return [render(r) for r in rows]


def _locked_months(db: Session, start: date, end: date):
    """An approved or paid payroll run for a month the dates touch: its loss of pay can no longer change. Every month
    from the first to the last is checked, not only the two ends; periods are YYYY-MM strings, so a string range
    covers the months in between."""
    query = q(db, PayrollRun).where(
        PayrollRun.period.between(rules.period_of(start), rules.period_of(end)),
        PayrollRun.status.in_(rules.LOCKED_RUN_STATUSES),
    )
    return db.scalars(query.limit(1)).first()


def apply(db: Session, actor: Actor, body: dict) -> dict:
    """The caller applies for leave for themselves. The employee row is locked first, so two requests of one employee
    take turns and the second sees the first in the balance and the overlap check."""
    own = common.require_own_employee(db, actor)
    e = get(db, Employee, own.id, "employee", lock=True)
    if e.status == "exited":
        raise conflict("employee_exited", "you have exited the organisation")
    t = get(db, LeaveType, body["leave_type_id"], "leave type")
    if not _applicable(t, e):
        raise invalid("leave_type_not_applicable", "this leave type is not open to you", "leave_type_id")
    start, end, half = body["from"], body["to"], body.get("half_day") or "none"
    days = rule(rules.leave_days, start, end, half)
    if half != "none" and not t.half_day_allowed:
        raise invalid("half_day_not_allowed", "this leave type is taken in whole days", "half_day")
    if start < common.business_today():
        raise invalid("dates_in_past", "leave cannot start before today", "from")
    if start < e.joined_on:
        raise invalid("before_joining", "leave cannot start before joining", "from")
    if e.exit_last_working_day is not None and end > e.exit_last_working_day:
        raise invalid("after_last_working_day", "leave cannot go past the last working day", "to")
    start_month = load_settings().leave_year_start_month
    year = rules.leave_year(start, start_month)
    if rules.leave_year(end, start_month) != year:
        raise invalid("spans_leave_years", "apply separately for each leave year", "to")
    overlap = q(db, LeaveRequest).where(
        LeaveRequest.employee_id == e.id,
        LeaveRequest.status.in_(("pending", "approved")),
        LeaveRequest.from_date <= end,
        LeaveRequest.to_date >= start,
    )
    if db.scalar(overlap.limit(1)) is not None:
        raise invalid("overlapping_request", "you already have leave on some of these days", "from")
    if t.paid:
        if days > balance(db, e, t, year)["_available"]:
            raise invalid("insufficient_balance", "not enough leave left of this type", "leave_type_id")
    elif _locked_months(db, start, end) is not None:
        raise invalid("period_locked", "the payroll for that month is already approved", "from")
    manager = db.scalar(q(db, Employee).where(Employee.id == e.reports_to)) if e.reports_to else None
    r = LeaveRequest(
        organisation_id=e.organisation_id,
        employee_id=e.id,
        leave_type_id=t.id,
        from_date=start,
        to_date=end,
        half_day=half,
        days=days,
        paid=t.paid,
        reason=text(body.get("reason")),
        status="pending",
        approver_id=manager.user_id if manager else None,
    )
    db.add(r)
    audit(db, actor.user_id, "leave_request.submitted", "leave_request", r)
    publish(
        db,
        "leave-request.submitted",
        r.organisation_id,
        {
            "leave_request_id": r.id,
            "employee_id": e.id,
            "approver_id": r.approver_id,
            "from": iso(start),
            "to": iso(end),
            "days": number(days),
        },
        actor.user_id,
    )
    db.commit()
    return request_dict(r, {e.id: e.name}, {t.id: t.name})


def decide(db: Session, actor: Actor, request_id: str, decision: str, note: str | None) -> dict:
    r = get(db, LeaveRequest, request_id, "leave request", lock=True)
    e = get(db, Employee, r.employee_id, "employee")
    if common.is_self(actor, e):
        raise forbidden("you cannot decide your own leave request")
    if r.status != "pending":
        raise conflict("not_pending", f"the request is {r.status}, not pending")
    if decision == "approved" and not r.paid and _locked_months(db, r.from_date, r.to_date) is not None:
        raise conflict("period_locked", "the payroll for that month is already approved")
    r.status, r.decided_by, r.decided_at, r.note = decision, actor.user_id, common.clock(), text(note) or None
    audit(db, actor.user_id, f"leave_request.{decision}", "leave_request", r)
    if decision == "approved":
        payload = {
            "leave_request_id": r.id,
            "employee_id": e.id,
            "user_id": e.user_id,
            "from": iso(r.from_date),
            "to": iso(r.to_date),
            "half_day": r.half_day,
        }
    else:
        payload = {"leave_request_id": r.id, "employee_id": e.id}
    publish(db, f"leave-request.{decision}", r.organisation_id, payload, actor.user_id)
    db.commit()
    return request_dict(r, {e.id: e.name}, _type_names(db, {r.leave_type_id}))


def cancel_request(db: Session, actor_id: str | None, r: LeaveRequest, note: str | None = None) -> None:
    """Cancel a pending or approved request: its days return to the balance, and scheduling modules may release cover."""
    r.status = "cancelled"
    if note:
        r.note = note
    audit(db, actor_id, "leave_request.cancelled", "leave_request", r)
    publish(
        db,
        "leave-request.cancelled",
        r.organisation_id,
        {"leave_request_id": r.id, "employee_id": r.employee_id, "from": iso(r.from_date), "to": iso(r.to_date)},
        actor_id,
    )


def cancel(db: Session, actor: Actor, request_id: str) -> dict:
    r = get(db, LeaveRequest, request_id, "leave request", lock=True)
    e = get(db, Employee, r.employee_id, "employee")
    if not common.is_self(actor, e):
        raise forbidden("you can cancel only your own leave requests")
    if r.status not in ("pending", "approved"):
        raise conflict("not_cancellable", f"the request is {r.status}")
    if r.from_date <= common.business_today():
        raise conflict("already_started", "leave that has started cannot be withdrawn")
    cancel_request(db, actor.user_id, r)
    db.commit()
    return request_dict(r, {e.id: e.name}, _type_names(db, {r.leave_type_id}))


def unpaid_days(db: Session, employee_id: str, start: date, end: date) -> Decimal:
    """Approved unpaid leave of an employee between two dates, both included: the loss of pay days."""
    rows = q(db, LeaveRequest).where(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status == "approved",
        LeaveRequest.paid.is_(False),
        LeaveRequest.from_date <= end,
        LeaveRequest.to_date >= start,
    )
    total = Decimal(0)
    for r in db.scalars(rows):
        if r.half_day != "none":
            total += rules.HALF
        else:
            total += Decimal((min(r.to_date, end) - max(r.from_date, start)).days + 1)
    return total
