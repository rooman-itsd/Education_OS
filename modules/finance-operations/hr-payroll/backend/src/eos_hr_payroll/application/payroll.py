"""Monthly payroll runs and payslips.

HR starts a month's run: every employee on the rolls during the month gets a payslip from the salary structure in
effect at the end of their days in the month, in proportion to the paid days (days on the rolls less approved unpaid
leave, the loss of pay). HR adjusts payslips with a reason and submits; someone who did not start, adjust or submit
the run approves it or returns it. Approval locks the run and publishes the payslips to employees; the run is then
marked paid. Totals are exact decimals."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import ZERO, money, number
from ..infrastructure.config import load_settings
from ..infrastructure.models import Employee, PayrollRun, Payslip
from . import common, employees, leave
from .access import Actor
from .common import audit, get, iso, publish, q, rule, text
from .errors import conflict, forbidden, invalid, not_found

# ---------------------------------------------------------------- rendering


def run_dict(r: PayrollRun) -> dict:
    due = rules.due_on(r.period, load_settings().payroll_due_day)
    return {
        "id": r.id,
        "organisation_id": r.organisation_id,
        "period": r.period,
        "status": r.status,
        "employees": r.employees,
        "gross_total": money(r.gross_total),
        "deductions_total": money(r.deductions_total),
        "net_total": money(r.net_total),
        "exceptions": list(r.exceptions or []),
        "prepared_by": r.prepared_by,
        "approved_by": r.approved_by,
        "note": r.note,
        "submitted_at": iso(r.submitted_at),
        "approved_at": iso(r.approved_at),
        "paid_on": iso(r.paid_on),
        "bank_reference": r.bank_reference,
        "due_on": due.isoformat(),
        "late": r.status in rules.OPEN_RUN_STATUSES and common.business_today() > due,
        "updated_at": iso(r.updated_at),
    }


def payslip_dict(p: Payslip) -> dict:
    return {
        "id": p.id,
        "organisation_id": p.organisation_id,
        "run_id": p.run_id,
        "period": p.period,
        "employee_id": p.employee_id,
        "employee_name": p.employee_name,
        "days_in_month": p.days_in_month,
        "paid_days": number(Decimal(p.paid_days)),
        "loss_of_pay_days": number(Decimal(p.loss_of_pay_days)),
        "lines": [{**x, "amount": money(x["amount"])} for x in p.lines or []],
        "gross": money(p.gross),
        "deductions": money(p.deductions),
        "net": money(p.net),
        "adjustments": list(p.adjustments or []),
        "document_id": p.document_id,
    }


# ---------------------------------------------------------------- reading


def list_runs(db: Session, year: int | None) -> list[dict]:
    query = q(db, PayrollRun)
    if year is not None:
        query = query.where(PayrollRun.period.like(f"{year:04d}-%"))
    return [run_dict(r) for r in db.scalars(query.order_by(PayrollRun.period.desc()))]


def current_run(db: Session) -> dict:
    """The run for the current (Indian) month, else the latest one."""
    r = db.scalar(q(db, PayrollRun).where(PayrollRun.period == rules.period_of(common.business_today())))
    if r is None:
        r = db.scalars(q(db, PayrollRun).order_by(PayrollRun.period.desc()).limit(1)).first()
    if r is None:
        raise not_found("payroll run")
    return run_dict(r)


def get_run(db: Session, run_id: str) -> dict:
    return run_dict(get(db, PayrollRun, run_id, "payroll run"))


def list_payslips(db: Session, run_id: str, cursor: str | None, limit: int) -> dict:
    r = get(db, PayrollRun, run_id, "payroll run")
    rows = list(db.scalars(q(db, Payslip).where(Payslip.run_id == r.id).order_by(Payslip.employee_name, Payslip.id)))
    return common.page(rows, cursor, limit, payslip_dict)


def my_payslips(db: Session, actor: Actor) -> list[dict]:
    """The caller's payslips from approved and paid runs, newest first."""
    e = common.require_own_employee(db, actor)
    published = (
        q(db, PayrollRun).where(PayrollRun.status.in_(rules.LOCKED_RUN_STATUSES)).with_only_columns(PayrollRun.id)
    )
    rows = q(db, Payslip).where(Payslip.employee_id == e.id, Payslip.run_id.in_(published))
    return [payslip_dict(p) for p in db.scalars(rows.order_by(Payslip.period.desc()))]


# ---------------------------------------------------------------- computing


def _on_rolls(db: Session, first: date, last: date) -> list[Employee]:
    """Employees who joined by the month's end and had not left before it began."""
    query = q(db, Employee).where(
        Employee.joined_on <= last,
        (Employee.exit_last_working_day.is_(None)) | (Employee.exit_last_working_day >= first),
    )
    return list(db.scalars(query.order_by(Employee.name, Employee.employee_code)))


def _compute(db: Session, run: PayrollRun) -> None:
    first, last = rules.parse_period(run.period)
    days_in_month = last.day
    exceptions: list[dict] = []
    gross_total = deductions_total = net_total = ZERO
    count = 0
    for e in _on_rolls(db, first, last):
        end = min(last, e.exit_last_working_day) if e.exit_last_working_day else last
        structure = employees.structure_on(db, e.id, end)
        if structure is None:
            exceptions.append({"employee_id": e.id, "message": "no salary in effect; no payslip"})
            continue
        if not e.bank_account_last4:
            exceptions.append({"employee_id": e.id, "message": "no bank account"})
        start = max(first, e.joined_on)
        on_rolls = Decimal(rules.employed_days(first, last, e.joined_on, e.exit_last_working_day))
        lop = min(on_rolls, leave.unpaid_days(db, e.id, start, end))
        paid_days = on_rolls - lop
        lines = rules.payslip_lines(structure.lines, days_in_month, paid_days)
        gross, deductions, net = rules.totals(lines)
        db.add(
            Payslip(
                organisation_id=run.organisation_id,
                run_id=run.id,
                employee_id=e.id,
                employee_name=e.name,
                period=run.period,
                days_in_month=days_in_month,
                paid_days=paid_days,
                loss_of_pay_days=lop,
                lines=lines,
                gross=gross,
                deductions=deductions,
                net=net,
                adjustments=[],
            )
        )
        gross_total, deductions_total, net_total = gross_total + gross, deductions_total + deductions, net_total + net
        count += 1
    run.employees, run.exceptions = count, exceptions
    run.gross_total, run.deductions_total, run.net_total = gross_total, deductions_total, net_total


def _retotal(db: Session, run: PayrollRun) -> None:
    db.flush()
    slips = list(db.scalars(q(db, Payslip).where(Payslip.run_id == run.id)))
    run.employees = len(slips)
    run.gross_total = sum((Decimal(p.gross) for p in slips), ZERO)
    run.deductions_total = sum((Decimal(p.deductions) for p in slips), ZERO)
    run.net_total = sum((Decimal(p.net) for p in slips), ZERO)


def _preparer(run: PayrollRun, actor: Actor) -> None:
    if actor.user_id not in (run.preparers or []):
        run.preparers = [*(run.preparers or []), actor.user_id]


@common.duplicate_is_409("run_exists", "a run for this month already exists")
def start_run(db: Session, actor: Actor, period: str) -> dict:
    first, _ = rule(rules.parse_period, period)
    if first > common.business_today():
        raise invalid("period_in_future", "a month's payroll starts in that month or later", "period")
    if db.scalar(q(db, PayrollRun).where(PayrollRun.period == period)) is not None:
        raise conflict("run_exists", "a run for this month already exists")
    now = common.clock()
    run = PayrollRun(
        organisation_id=actor.organisation_id,
        period=period,
        status="computing",
        employees=0,
        gross_total=ZERO,
        deductions_total=ZERO,
        net_total=ZERO,
        exceptions=[],
        prepared_by=actor.user_id,
        preparers=[actor.user_id],
        updated_at=now,
    )
    db.add(run)
    db.flush()
    _compute(db, run)
    run.status = "review"
    audit(db, actor.user_id, "payroll_run.started", "payroll_run", run)
    db.commit()
    return run_dict(run)


def adjust_payslip(db: Session, actor: Actor, run_id: str, payslip_id: str, lines: list[dict], reason: str) -> dict:
    """New lines for one payslip of a run in review, with a reason (arrears, one-off deductions). Paid and loss of pay
    days stay as computed. Nobody adjusts their own payslip."""
    run = get(db, PayrollRun, run_id, "payroll run", lock=True)
    p = db.scalar(q(db, Payslip).where(Payslip.id == payslip_id, Payslip.run_id == run.id))
    if p is None:
        raise not_found("payslip")
    if run.status != "review":
        raise conflict("run_not_in_review", f"the run is {run.status}; only a run in review is adjusted")
    reason = text(reason)
    if not reason:
        raise invalid("reason_required", "an adjustment needs a reason", "reason")
    e = db.scalar(q(db, Employee).where(Employee.id == p.employee_id))
    if e is not None and common.is_self(actor, e):
        raise forbidden("you cannot adjust your own payslip")
    p.lines = rule(rules.check_lines, lines)
    p.gross, p.deductions, p.net = rules.totals(p.lines)
    p.adjustments = [*(p.adjustments or []), {"reason": reason, "by": actor.user_id, "at": iso(common.clock())}]
    _preparer(run, actor)
    _retotal(db, run)
    run.updated_at = common.clock()
    audit(db, actor.user_id, "payslip.adjusted", "payslip", p)
    db.commit()
    return payslip_dict(p)


def submit_run(db: Session, actor: Actor, run_id: str) -> dict:
    run = get(db, PayrollRun, run_id, "payroll run", lock=True)
    if run.status != "review":
        raise conflict("run_not_in_review", f"the run is {run.status}; only a run in review is submitted")
    if run.employees == 0:
        raise invalid("empty_run", "the run has no payslips")
    _preparer(run, actor)
    run.status, run.prepared_by, run.submitted_at = "submitted", actor.user_id, common.clock()
    run.updated_at = run.submitted_at
    audit(db, actor.user_id, "payroll_run.submitted", "payroll_run", run)
    publish(
        db,
        "payroll-run.submitted",
        run.organisation_id,
        {"run_id": run.id, "period": run.period, "employees": run.employees},
        actor.user_id,
    )
    db.commit()
    return run_dict(run)


def decide_run(db: Session, actor: Actor, run_id: str, decision: str, note: str | None) -> dict:
    """Approve (locks the run; payslips become visible to employees) or return to review with a note. Nobody who
    started, adjusted or submitted the run decides it, and nobody decides a run that holds their own payslip (decided
    by the owner on #336)."""
    run = get(db, PayrollRun, run_id, "payroll run", lock=True)
    if actor.user_id in (run.preparers or []):
        raise forbidden("you prepared this run; someone else decides it")
    own = (
        q(db, Payslip)
        .join(Employee, Employee.id == Payslip.employee_id)
        .where(Payslip.run_id == run.id, Employee.user_id == actor.user_id)
    )
    if db.scalars(own.limit(1)).first() is not None:
        raise conflict("own_payslip_in_run", "the run holds your own payslip; someone else decides it")
    if run.status != "submitted":
        raise conflict("run_not_submitted", f"the run is {run.status}, not submitted")
    note = text(note) or None
    if decision == "returned" and not note:
        raise invalid("note_required", "say why the run is returned", "note")
    run.note, run.updated_at = note, common.clock()
    if decision == "approved":
        run.status, run.approved_by, run.approved_at = "approved", actor.user_id, run.updated_at
        publish(
            db,
            "payroll-run.approved",
            run.organisation_id,
            {"run_id": run.id, "period": run.period, "employees": run.employees, "net_total": money(run.net_total)},
            actor.user_id,
        )
    else:
        run.status = "review"
    audit(db, actor.user_id, f"payroll_run.{decision}", "payroll_run", run)
    db.commit()
    return run_dict(run)


def mark_paid(db: Session, actor: Actor, run_id: str, paid_on: date, bank_reference: str | None) -> dict:
    run = get(db, PayrollRun, run_id, "payroll run", lock=True)
    if run.status != "approved":
        raise conflict("run_not_approved", f"the run is {run.status}; only an approved run is marked paid")
    if paid_on > common.business_today() or paid_on < common.business_date(run.approved_at):
        raise invalid("invalid_date", "paid_on must be between the approval and today", "paid_on")
    run.status, run.paid_on, run.bank_reference = "paid", paid_on, text(bank_reference) or None
    run.updated_at = common.clock()
    audit(db, actor.user_id, "payroll_run.paid", "payroll_run", run)
    publish(
        db,
        "payroll-run.paid",
        run.organisation_id,
        {"run_id": run.id, "period": run.period, "net_total": money(run.net_total), "paid_on": iso(paid_on)},
        actor.user_id,
    )
    db.commit()
    return run_dict(run)
