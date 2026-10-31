"""Employees from joining to exit, their salary structures and their service book.

A full bank account number or PAN reaches this layer only to be validated; the last four characters are kept and the
rest is dropped here (decided by the owner; see #336). Nothing below logs, audits, publishes or returns them."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import money
from ..infrastructure.models import Employee, LeaveRequest, PayrollRun, Payslip, SalaryStructure, ServiceRecord
from . import common
from .access import EMPLOYEE_READ, PAYROLL_READ, Actor
from .common import audit, get, is_self, iso, publish, q, rule, text
from .errors import HrPayrollError, conflict, forbidden, invalid

UPDATE_EVENT_FIELDS = ("name", "designation", "department_id", "reports_to")


# ---------------------------------------------------------------- rendering


def employee_dict(e: Employee) -> dict:
    bank = None
    if e.bank_account_last4 or e.bank_ifsc:
        bank = {
            "account_holder": e.bank_account_holder or "",
            "account_last4": e.bank_account_last4 or "",
            "ifsc": e.bank_ifsc or "",
        }
    exit_ = None
    if e.exit_last_working_day is not None:
        exit_ = {"kind": e.exit_kind, "last_working_day": iso(e.exit_last_working_day), "reason": e.exit_reason or ""}
    return {
        "id": e.id,
        "organisation_id": e.organisation_id,
        "employee_code": e.employee_code,
        "user_id": e.user_id,
        "name": e.name,
        "email": e.email,
        "phone": e.phone,
        "date_of_birth": iso(e.date_of_birth),
        "joined_on": iso(e.joined_on),
        "employment_type": e.employment_type,
        "staff_category": e.staff_category,
        "designation": e.designation,
        "department_id": e.department_id,
        "department_name": e.department_name,
        "reports_to": e.reports_to,
        "bank_account": bank,
        "pan_masked": rules.pan_masked(e.pan_last4),
        "status": e.status,
        "exit": exit_,
        "created_at": iso(e.created_at),
    }


def names(db: Session, ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    return {e.id: e.name for e in db.scalars(q(db, Employee).where(Employee.id.in_(ids)))}


# ---------------------------------------------------------------- employees


def list_employees(
    db: Session, status: str | None, department_id: str | None, q_text: str | None, cursor: str | None, limit: int
) -> dict:
    query = q(db, Employee)
    if status:
        query = query.where(Employee.status == status)
    if department_id:
        query = query.where(Employee.department_id == department_id)
    rows = list(db.scalars(query.order_by(Employee.name, Employee.employee_code)))
    if q_text:
        needle = q_text.strip().lower()
        rows = [e for e in rows if needle in e.name.lower() or needle in e.employee_code.lower()]
    return common.page(rows, cursor, limit, employee_dict)


def readable_employee(db: Session, actor: Actor, employee_id: str, permission: str = EMPLOYEE_READ) -> Employee:
    """An employee the caller may see: with the permission, or their own record."""
    e = get(db, Employee, employee_id, "employee")
    if not actor.can(permission) and not is_self(actor, e):
        raise forbidden("you can see only your own record")
    return e


def get_employee(db: Session, actor: Actor, employee_id: str) -> dict:
    return employee_dict(readable_employee(db, actor, employee_id))


def me(db: Session, actor: Actor) -> dict:
    return employee_dict(common.require_own_employee(db, actor))


def _unique(db: Session, e: Employee, column, value, code: str, message: str) -> None:
    if value is None:
        return
    query = q(db, Employee).where(column == value)
    if e.id:
        query = query.where(Employee.id != e.id)
    if db.scalar(query) is not None:
        raise conflict(code, message)


def _bank(e: Employee, body: dict) -> None:
    """bank_account absent: unchanged. null: removed. Without account_number the account kept so far stays (the full
    number is never returned, so an edit cannot send it back)."""
    if "bank_account" not in body:
        return
    bank = body["bank_account"]
    if bank is None:
        e.bank_account_holder = e.bank_account_last4 = e.bank_ifsc = None
        return
    if bank.get("account_number"):
        e.bank_account_last4 = rule(rules.account_last4, bank["account_number"])
    elif not e.bank_account_last4:
        raise invalid("invalid_account_number", "a new bank account needs its account_number", "bank_account")
    if not text(bank.get("ifsc")):
        raise invalid("invalid_ifsc", "a bank account needs its ifsc", "bank_account")
    e.bank_ifsc = rule(rules.check_ifsc, bank["ifsc"])
    e.bank_account_holder = text(bank.get("account_holder")) or None


def _pan(e: Employee, body: dict) -> None:
    """pan absent: unchanged. null or empty: removed. Otherwise validated in full and only its last four kept."""
    if "pan" not in body:
        return
    e.pan_last4 = rule(rules.pan_last4, body["pan"]) if text(body["pan"]) else None


def _values(db: Session, e: Employee, body: dict) -> None:
    code = text(body["employee_code"])
    if not code:
        raise invalid("invalid_employee_code", "employee_code is required", "employee_code")
    name = text(body["name"])
    if not name:
        raise invalid("invalid_name", "name is required", "name")
    _unique(db, e, Employee.employee_code, code, "employee_code_taken", "another employee has this code")
    user_id = (body["user_id"] or None) if "user_id" in body else e.user_id  # absent: the link stays
    _unique(db, e, Employee.user_id, user_id, "user_already_linked", "this user is already linked to an employee")
    manager = body.get("reports_to") or None
    if manager is not None:
        if e.id and manager == e.id:
            raise invalid("invalid_manager", "an employee cannot report to themselves", "reports_to")
        get(db, Employee, manager, "reporting manager")
    dob = body.get("date_of_birth")
    if dob is not None and dob >= body["joined_on"]:
        raise invalid("invalid_date_of_birth", "date_of_birth must be before joined_on", "date_of_birth")
    if e.exit_last_working_day is not None and body["joined_on"] > e.exit_last_working_day:
        raise invalid("invalid_date", "joined_on cannot be after the last working day", "joined_on")
    _bank(e, body)
    _pan(e, body)
    e.employee_code, e.name, e.user_id, e.reports_to = code, name, user_id, manager
    e.email = text(body.get("email"))
    e.phone = text(body.get("phone"))
    e.date_of_birth = dob
    e.joined_on = body["joined_on"]
    e.employment_type = body["employment_type"]
    e.staff_category = body.get("staff_category")
    e.designation = text(body.get("designation"))
    e.department_id = body.get("department_id") or None
    e.department_name = text(body.get("department_name")) or None


def _service_record(db: Session, e: Employee, actor_id: str | None, kind: str, on: date, title: str, details: str = ""):
    record = ServiceRecord(
        organisation_id=e.organisation_id,
        employee_id=e.id,
        kind=kind,
        effective_on=on,
        title=title[:300],
        details=details,
        recorded_by=actor_id,
    )
    db.add(record)
    audit(db, actor_id, "service_record.added", "service_record", record)
    return record


@common.duplicate_is_409("employee_code_taken", "another employee has this code or user")
def create_employee(db: Session, actor: Actor, body: dict) -> dict:
    e = Employee(organisation_id=actor.organisation_id, status="active")
    _values(db, e, body)
    db.add(e)
    audit(db, actor.user_id, "employee.joined", "employee", e)
    _service_record(db, e, actor.user_id, "joining", e.joined_on, f"Joined as {e.designation or 'employee'}")
    publish(
        db,
        "employee.joined",
        e.organisation_id,
        {
            "employee_id": e.id,
            "user_id": e.user_id,
            "employee_code": e.employee_code,
            "name": e.name,
            "email": e.email,
            "designation": e.designation,
            "department_id": e.department_id,
            "staff_category": e.staff_category,
            "joined_on": iso(e.joined_on),
        },
        actor.user_id,
    )
    db.commit()
    return employee_dict(e)


@common.duplicate_is_409("employee_code_taken", "another employee has this code or user")
def update_employee(db: Session, actor: Actor, employee_id: str, body: dict) -> dict:
    e = get(db, Employee, employee_id, "employee", lock=True)
    before = {f: getattr(e, f) for f in UPDATE_EVENT_FIELDS}
    old_department = e.department_name or e.department_id
    _values(db, e, body)
    today = common.business_today()
    if before["department_id"] != e.department_id:
        _service_record(
            db,
            e,
            actor.user_id,
            "transfer",
            today,
            f"Transferred to {e.department_name or e.department_id or 'no department'}",
            f"From {old_department or 'no department'}",
        )
    if before["designation"] != e.designation:
        _service_record(
            db,
            e,
            actor.user_id,
            "other",
            today,
            f"Designation changed to {e.designation or 'none'}",
            f"From {before['designation'] or 'none'}",
        )
    audit(db, actor.user_id, "employee.updated", "employee", e)
    if any(before[f] != getattr(e, f) for f in UPDATE_EVENT_FIELDS):
        publish(
            db,
            "employee.updated",
            e.organisation_id,
            {
                "employee_id": e.id,
                "name": e.name,
                "designation": e.designation,
                "department_id": e.department_id,
                "reports_to": e.reports_to,
            },
            actor.user_id,
        )
    db.commit()
    return employee_dict(e)


# ---------------------------------------------------------------- exits


def _publish_exit(db: Session, e: Employee, actor_id: str | None) -> None:
    """hr-payroll.employee.exited, once: identity disables the user and modules release the employee's assignments."""
    e.status = "exited"
    e.exit_published_at = common.clock()
    publish(
        db,
        "employee.exited",
        e.organisation_id,
        {
            "employee_id": e.id,
            "user_id": e.user_id,
            "kind": e.exit_kind,
            "last_working_day": iso(e.exit_last_working_day),
        },
        actor_id,
    )
    audit(db, actor_id, "employee.exited", "employee", e)


def record_exit(db: Session, actor: Actor, employee_id: str, body: dict) -> dict:
    """Resignation, retirement and so on, with the last working day. Dated today or earlier, the employee exits now;
    later, they are on notice until the scheduler job publishes the exit on that day. Leave starting after the last
    working day is cancelled. A recorded exit can be moved while the employee is on notice."""
    from . import leave  # leave imports this module for names

    e = get(db, Employee, employee_id, "employee", lock=True)
    if e.status == "exited":
        raise conflict("employee_exited", "the employee has already exited")
    last_day: date = body["last_working_day"]
    if last_day < e.joined_on:
        raise invalid("invalid_date", "the last working day cannot be before joining", "last_working_day")
    paid_after = db.scalar(
        common.count(db, Payslip)
        .join(PayrollRun, PayrollRun.id == Payslip.run_id)
        .where(
            Payslip.employee_id == e.id,
            PayrollRun.status.in_(rules.LOCKED_RUN_STATUSES),
            PayrollRun.period > rules.period_of(last_day),
        )
    )
    if paid_after:
        raise conflict("period_locked", "an approved payroll run already pays the employee after that day")
    e.exit_kind, e.exit_last_working_day, e.exit_reason = body["kind"], last_day, text(body.get("reason")) or None
    e.status = "on_notice"
    _service_record(
        db, e, actor.user_id, "exit", last_day, f"Exit: {body['kind'].replace('_', ' ')}", e.exit_reason or ""
    )
    audit(db, actor.user_id, "employee.exit_recorded", "employee", e)
    later = q(db, LeaveRequest).where(
        LeaveRequest.employee_id == e.id,
        LeaveRequest.status.in_(("pending", "approved")),
        LeaveRequest.from_date > last_day,
    )
    for request in db.scalars(later):
        leave.cancel_request(db, actor.user_id, request, "cancelled: after the last working day")
    if last_day <= common.business_today():
        _publish_exit(db, e, actor.user_id)
    db.commit()
    return employee_dict(e)


def publish_due_exits(db: Session) -> int:
    """The scheduler job: every employee on notice whose last working day has come (Indian date) exits now. It runs
    once a day for every organisation (a platform job, in platform scope) and is idempotent: an exit is published once."""
    due = q(db, Employee).where(
        Employee.status == "on_notice", Employee.exit_last_working_day <= common.business_today()
    )
    count = 0
    for e in db.scalars(due.order_by(Employee.organisation_id, Employee.id).with_for_update()):
        _publish_exit(db, e, None)
        count += 1
    db.flush()
    return count


# ---------------------------------------------------------------- salary


def _structure_dict(s: SalaryStructure) -> dict:
    return {
        "organisation_id": s.organisation_id,
        "employee_id": s.employee_id,
        "effective_from": iso(s.effective_from),
        "lines": [{**x, "amount": money(x["amount"])} for x in s.lines or []],
        "gross": money(s.gross),
        "deductions": money(s.deductions),
        "net": money(s.net),
        "set_by": s.set_by,
    }


def structure_on(db: Session, employee_id: str, day: date) -> SalaryStructure | None:
    """The structure in effect on a day: the latest one effective on or before it."""
    query = (
        q(db, SalaryStructure)
        .where(SalaryStructure.employee_id == employee_id, SalaryStructure.effective_from <= day)
        .order_by(SalaryStructure.effective_from.desc())
    )
    return db.scalars(query.limit(1)).first()


def get_salary(db: Session, actor: Actor, employee_id: str) -> dict:
    """The structure in effect today, else the next one to take effect. Salary data is for the employee and holders of
    hr-payroll:payroll:read only."""
    e = readable_employee(db, actor, employee_id, PAYROLL_READ)
    s = structure_on(db, e.id, common.business_today())
    if s is None:
        upcoming = q(db, SalaryStructure).where(SalaryStructure.employee_id == e.id)
        s = db.scalars(upcoming.order_by(SalaryStructure.effective_from).limit(1)).first()
    if s is None:
        raise HrPayrollError(404, "no_salary", "no salary has been set for this employee")
    return _structure_dict(s)


def locked_from(db: Session, period: str, statuses=("submitted", *rules.LOCKED_RUN_STATUSES)) -> PayrollRun | None:
    """A run for `period` or later that pay changes can no longer reach: submitted, approved or paid."""
    query = q(db, PayrollRun).where(PayrollRun.period >= period, PayrollRun.status.in_(statuses))
    return db.scalars(query.order_by(PayrollRun.period).limit(1)).first()


def set_salary(db: Session, actor: Actor, employee_id: str, body: dict) -> dict:
    """A structure from its effective date; earlier ones are kept. A second structure on the same date replaces it.
    Nobody sets their own salary. A month whose run is submitted, approved or paid is not changed: corrections go into
    a later month as arrears or deductions."""
    e = get(db, Employee, employee_id, "employee", lock=True)
    if is_self(actor, e):
        raise forbidden("you cannot set your own salary")
    if e.status == "exited":
        raise conflict("employee_exited", "the employee has exited")
    effective: date = body["effective_from"]
    if effective < e.joined_on:
        raise invalid("invalid_date", "effective_from cannot be before joining", "effective_from")
    locked = locked_from(db, rules.period_of(effective))
    if locked is not None:
        raise conflict(
            "period_locked", f"the payroll for {locked.period} is {locked.status}; set it from a later month"
        )
    lines = rule(rules.check_lines, body["lines"])
    gross, deductions, net = rules.totals(lines)
    s = db.scalar(
        q(db, SalaryStructure).where(SalaryStructure.employee_id == e.id, SalaryStructure.effective_from == effective)
    )
    action = "salary.revised"
    if s is None:
        s = SalaryStructure(organisation_id=e.organisation_id, employee_id=e.id, effective_from=effective)
        db.add(s)
        action = "salary.set"
    s.lines, s.gross, s.deductions, s.net, s.set_by = lines, gross, deductions, net, actor.user_id
    audit(db, actor.user_id, action, "salary_structure", s)
    db.commit()
    return _structure_dict(s)


# ---------------------------------------------------------------- service book


def _record_dict(r: ServiceRecord) -> dict:
    return {
        "id": r.id,
        "organisation_id": r.organisation_id,
        "employee_id": r.employee_id,
        "kind": r.kind,
        "effective_on": iso(r.effective_on),
        "title": r.title,
        "details": r.details,
        "document_id": r.document_id,
        "recorded_by": r.recorded_by,
        "recorded_at": iso(r.created_at),
    }


def list_service_records(db: Session, actor: Actor, employee_id: str) -> list[dict]:
    e = readable_employee(db, actor, employee_id)
    rows = q(db, ServiceRecord).where(ServiceRecord.employee_id == e.id)
    return [_record_dict(r) for r in db.scalars(rows.order_by(ServiceRecord.effective_on, ServiceRecord.created_at))]


def add_service_record(db: Session, actor: Actor, employee_id: str, body: dict) -> dict:
    e = get(db, Employee, employee_id, "employee")
    title = text(body["title"])
    if not title:
        raise invalid("invalid_title", "title is required", "title")
    r = _service_record(db, e, actor.user_id, body["kind"], body["effective_on"], title, text(body.get("details")))
    r.document_id = body.get("document_id") or None
    db.commit()
    return _record_dict(r)
