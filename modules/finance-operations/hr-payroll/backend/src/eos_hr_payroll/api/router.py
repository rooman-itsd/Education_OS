"""HTTP surface of contracts/openapi.yaml. The host app mounts `router` under /api/v1/hr-payroll. Handlers only map
HTTP to the application layer; errors render as {"detail": {"code", "message", "field"?}}."""

from __future__ import annotations

from datetime import date
from typing import Any

from eos_core.db import get_db
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..application import access as p
from ..application import appraisals, employees, leave, payroll, reports
from ..application.access import Actor
from ..application.errors import HrPayrollError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["hr-payroll"])

EMPLOYEE_STATUS = "^(active|on_notice|exited)$"
LEAVE_STATUS = "^(pending|approved|rejected|cancelled)$"
APPRAISAL_STATUS = "^(self_review|manager_review|completed)$"


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except HrPayrollError as e:
        raise HTTPException(e.status, e.body()) from e


Limit = Query(default=50, ge=1, le=200)


def _employee_body(raw: Any) -> dict:
    """EmployeeInput, validated here rather than by FastAPI: a validation error never echoes the request back, so a
    bank account number or PAN sent with an invalid body does not come back in the 422 (decided by the owner; #336)."""
    try:
        return s.dump_employee(s.EmployeeInput.model_validate(raw))
    except ValidationError as e:
        errors = [{"type": x["type"], "loc": ["body", *x["loc"]], "msg": x["msg"]} for x in e.errors()]
        raise HTTPException(422, errors) from e


# ---------------------------------------------------------------- employees


@router.get("/employees")
def list_employees(
    status: str | None = Query(default=None, pattern=EMPLOYEE_STATUS),
    department_id: str | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.EMPLOYEE_READ)),
    db: Session = Depends(get_db),
):
    return _run(employees.list_employees, db, status, department_id, q, cursor, limit)


@router.post("/employees", status_code=201)
def create_employee(
    body: Any = Body(...), a: Actor = Depends(require(p.EMPLOYEE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(employees.create_employee, db, a, _employee_body(body))


@router.get("/employees/{employee_id}")
def get_employee(
    employee_id: str, a: Actor = Depends(require(p.EMPLOYEE_READ, p.SELF_USE)), db: Session = Depends(get_db)
):
    return _run(employees.get_employee, db, a, employee_id)


@router.put("/employees/{employee_id}")
def update_employee(
    employee_id: str,
    body: Any = Body(...),
    a: Actor = Depends(require(p.EMPLOYEE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(employees.update_employee, db, a, employee_id, _employee_body(body))


@router.post("/employees/{employee_id}/exit")
def record_exit(
    employee_id: str, body: s.ExitInput, a: Actor = Depends(require(p.EMPLOYEE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(employees.record_exit, db, a, employee_id, s.dump(body))


@router.get("/employees/{employee_id}/salary")
def get_salary(
    employee_id: str, a: Actor = Depends(require(p.PAYROLL_READ, p.SELF_USE)), db: Session = Depends(get_db)
):
    return _run(employees.get_salary, db, a, employee_id)


@router.put("/employees/{employee_id}/salary")
def set_salary(
    employee_id: str, body: s.SalaryInput, a: Actor = Depends(require(p.PAYROLL_PREPARE)), db: Session = Depends(get_db)
):
    return _run(employees.set_salary, db, a, employee_id, s.dump(body))


@router.get("/employees/{employee_id}/service-records")
def list_service_records(
    employee_id: str, a: Actor = Depends(require(p.EMPLOYEE_READ, p.SELF_USE)), db: Session = Depends(get_db)
):
    return _run(employees.list_service_records, db, a, employee_id)


@router.post("/employees/{employee_id}/service-records", status_code=201)
def add_service_record(
    employee_id: str,
    body: s.ServiceRecordInput,
    a: Actor = Depends(require(p.EMPLOYEE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(employees.add_service_record, db, a, employee_id, s.dump(body))


# ---------------------------------------------------------------- leave


@router.get("/leave-types")
def list_leave_types(
    a: Actor = Depends(require(p.SELF_USE, p.LEAVE_TYPE_MANAGE, p.LEAVE_APPROVE)), db: Session = Depends(get_db)
):
    return _run(leave.list_leave_types, db)


@router.post("/leave-types", status_code=201)
def create_leave_type(
    body: s.LeaveTypeInput, a: Actor = Depends(require(p.LEAVE_TYPE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(leave.create_leave_type, db, a, s.dump(body))


@router.put("/leave-types/{leave_type_id}")
def update_leave_type(
    leave_type_id: str,
    body: s.LeaveTypeInput,
    a: Actor = Depends(require(p.LEAVE_TYPE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(leave.update_leave_type, db, a, leave_type_id, s.dump(body))


@router.get("/leave-requests")
def list_leave_requests(
    status: str | None = Query(default=None, pattern=LEAVE_STATUS),
    employee_id: str | None = None,
    department_id: str | None = None,
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = None,
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.LEAVE_APPROVE)),
    db: Session = Depends(get_db),
):
    return _run(leave.list_requests, db, status, employee_id, department_id, from_, to, cursor, limit)


@router.post("/leave-requests", status_code=201)
def apply_for_leave(body: s.LeaveRequestInput, a: Actor = Depends(require(p.SELF_USE)), db: Session = Depends(get_db)):
    return _run(leave.apply, db, a, s.dump_leave_request(body))


@router.post("/leave-requests/{request_id}/decision")
def decide_leave(
    request_id: str, body: s.LeaveDecision, a: Actor = Depends(require(p.LEAVE_APPROVE)), db: Session = Depends(get_db)
):
    return _run(leave.decide, db, a, request_id, body.decision, body.note)


@router.post("/leave-requests/{request_id}/cancel")
def cancel_leave(request_id: str, a: Actor = Depends(require(p.SELF_USE)), db: Session = Depends(get_db)):
    return _run(leave.cancel, db, a, request_id)


# ---------------------------------------------------------------- payroll


@router.get("/payroll-runs")
def list_runs(
    year: int | None = Query(default=None, ge=1900, le=9999),
    a: Actor = Depends(require(p.PAYROLL_READ)),
    db: Session = Depends(get_db),
):
    return _run(payroll.list_runs, db, year)


@router.post("/payroll-runs", status_code=202)
def start_run(body: s.RunInput, a: Actor = Depends(require(p.PAYROLL_PREPARE)), db: Session = Depends(get_db)):
    return _run(payroll.start_run, db, a, body.period)


@router.get("/payroll-runs/current")
def current_run(a: Actor = Depends(require(p.PAYROLL_READ)), db: Session = Depends(get_db)):
    return _run(payroll.current_run, db)


@router.get("/payroll-runs/{run_id}")
def get_run(run_id: str, a: Actor = Depends(require(p.PAYROLL_READ)), db: Session = Depends(get_db)):
    return _run(payroll.get_run, db, run_id)


@router.get("/payroll-runs/{run_id}/payslips")
def list_payslips(
    run_id: str,
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.PAYROLL_READ)),
    db: Session = Depends(get_db),
):
    return _run(payroll.list_payslips, db, run_id, cursor, limit)


@router.put("/payroll-runs/{run_id}/payslips/{payslip_id}")
def adjust_payslip(
    run_id: str,
    payslip_id: str,
    body: s.PayslipAdjustment,
    a: Actor = Depends(require(p.PAYROLL_PREPARE)),
    db: Session = Depends(get_db),
):
    lines = [line.model_dump() for line in body.lines]
    return _run(payroll.adjust_payslip, db, a, run_id, payslip_id, lines, body.reason)


@router.post("/payroll-runs/{run_id}/submit")
def submit_run(run_id: str, a: Actor = Depends(require(p.PAYROLL_PREPARE)), db: Session = Depends(get_db)):
    return _run(payroll.submit_run, db, a, run_id)


@router.post("/payroll-runs/{run_id}/decision")
def decide_run(
    run_id: str, body: s.RunDecision, a: Actor = Depends(require(p.PAYROLL_APPROVE)), db: Session = Depends(get_db)
):
    return _run(payroll.decide_run, db, a, run_id, body.decision, body.note)


@router.post("/payroll-runs/{run_id}/mark-paid")
def mark_paid(
    run_id: str, body: s.MarkPaidInput, a: Actor = Depends(require(p.PAYROLL_APPROVE)), db: Session = Depends(get_db)
):
    return _run(payroll.mark_paid, db, a, run_id, body.paid_on, body.bank_reference)


# ---------------------------------------------------------------- appraisals


@router.get("/appraisals")
def list_appraisals(
    cycle: str | None = None,
    status: str | None = Query(default=None, pattern=APPRAISAL_STATUS),
    a: Actor = Depends(require(p.APPRAISAL_REVIEW)),
    db: Session = Depends(get_db),
):
    return _run(appraisals.list_appraisals, db, cycle, status)


@router.post("/appraisals", status_code=201)
def open_cycle(
    body: s.AppraisalCycleInput, a: Actor = Depends(require(p.EMPLOYEE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(appraisals.open_cycle, db, a, body.cycle, body.employee_ids)


@router.get("/appraisals/{appraisal_id}")
def get_appraisal(
    appraisal_id: str, a: Actor = Depends(require(p.APPRAISAL_REVIEW, p.SELF_USE)), db: Session = Depends(get_db)
):
    return _run(appraisals.get_appraisal, db, a, appraisal_id)


@router.put("/appraisals/{appraisal_id}")
def save_appraisal(
    appraisal_id: str,
    body: s.AppraisalInput,
    a: Actor = Depends(require(p.APPRAISAL_REVIEW, p.SELF_USE)),
    db: Session = Depends(get_db),
):
    return _run(appraisals.save, db, a, appraisal_id, s.dump(body))


# ---------------------------------------------------------------- self-service


@router.get("/me")
def me(a: Actor = Depends(require(p.SELF_USE)), db: Session = Depends(get_db)):
    return _run(employees.me, db, a)


@router.get("/me/leave-balances")
def my_leave_balances(a: Actor = Depends(require(p.SELF_USE)), db: Session = Depends(get_db)):
    return _run(leave.my_balances, db, a)


@router.get("/me/leave-requests")
def my_leave_requests(a: Actor = Depends(require(p.SELF_USE)), db: Session = Depends(get_db)):
    return _run(leave.my_requests, db, a)


@router.get("/me/payslips")
def my_payslips(a: Actor = Depends(require(p.SELF_USE)), db: Session = Depends(get_db)):
    return _run(payroll.my_payslips, db, a)


@router.get("/me/appraisals")
def my_appraisals(a: Actor = Depends(require(p.SELF_USE)), db: Session = Depends(get_db)):
    return _run(appraisals.my_appraisals, db, a)


# ---------------------------------------------------------------- reports


@router.get("/reports/joinings-and-exits")
def joinings_and_exits(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = None,
    a: Actor = Depends(require(p.REPORT_READ)),
    db: Session = Depends(get_db),
):
    return _run(reports.joinings_and_exits, db, from_, to)
