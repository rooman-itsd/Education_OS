"""Request bodies of contracts/openapi.yaml. Strict: unknown fields are refused, except readOnly fields of a schema
that is both input and output, which are accepted and ignored. Money stays a decimal string here; the domain parses
it exactly. Days are numbers here; the domain checks they come in halves."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MONEY = r"^-?[0-9]+(\.[0-9]{1,2})?$"
ID = Field(min_length=1, max_length=36)
EmploymentType = Literal["permanent", "contract", "visiting", "part_time"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BankAccount(Strict):
    account_holder: str | None = Field(default=None, max_length=200)
    account_number: str | None = Field(default=None, max_length=40)
    account_last4: str | None = None  # readOnly: accepted and ignored
    ifsc: str | None = Field(default=None, max_length=20)


class ExitInput(Strict):
    kind: Literal["resignation", "retirement", "termination", "contract_end", "death"]
    last_working_day: date
    reason: str | None = Field(default=None, max_length=2000)


class EmployeeInput(Strict):
    # readOnly fields of Employee, accepted and ignored
    id: str | None = None
    organisation_id: str | None = None
    status: str | None = None
    pan_masked: str | None = None
    exit: Any = None
    created_at: str | None = None
    employee_code: str = Field(min_length=1, max_length=40)
    user_id: str | None = Field(default=None, max_length=36)
    name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=254, pattern=r"^$|^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=40)
    date_of_birth: date | None = None
    joined_on: date
    employment_type: EmploymentType
    staff_category: Literal["teaching", "non_teaching"] | None = None
    designation: str | None = Field(default=None, max_length=120)
    department_id: str | None = Field(default=None, max_length=36)
    department_name: str | None = Field(default=None, max_length=200)
    reports_to: str | None = Field(default=None, max_length=36)
    bank_account: BankAccount | None = None
    pan: str | None = Field(default=None, max_length=20)


class PayLine(Strict):
    code: str = Field(min_length=1, max_length=20)
    name: str | None = Field(default=None, max_length=120)
    kind: Literal["earning", "deduction"]
    amount: str = Field(pattern=MONEY)


class SalaryInput(Strict):
    organisation_id: str | None = None  # readOnly fields of Salary, accepted and ignored
    employee_id: str | None = None
    gross: str | None = None
    deductions: str | None = None
    net: str | None = None
    set_by: str | None = None
    effective_from: date
    lines: list[PayLine] = Field(min_length=1)


class ServiceRecordInput(Strict):
    kind: Literal[
        "joining",
        "confirmation",
        "promotion",
        "transfer",
        "increment",
        "award",
        "disciplinary",
        "training",
        "exit",
        "other",
    ]
    effective_on: date
    title: str = Field(min_length=1, max_length=300)
    details: str | None = Field(default=None, max_length=5000)
    document_id: str | None = Field(default=None, max_length=100)


class LeaveTypeInput(Strict):
    id: str | None = None  # readOnly fields of LeaveType, accepted and ignored
    organisation_id: str | None = None
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    days_per_year: float = Field(ge=0, le=366)
    carry_forward_max: float = Field(default=0, ge=0, le=366)
    paid: bool = True
    half_day_allowed: bool = True
    applies_to: list[EmploymentType] | None = None
    active: bool = True


class LeaveRequestInput(Strict):
    leave_type_id: str = ID
    from_: date = Field(alias="from")
    to: date
    half_day: Literal["none", "first_half", "second_half"] = "none"
    reason: str | None = Field(default=None, max_length=2000)


class LeaveDecision(Strict):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=2000)


class RunInput(Strict):
    period: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}$")


class PayslipAdjustment(Strict):
    lines: list[PayLine] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=2000)


class RunDecision(Strict):
    decision: Literal["approved", "returned"]
    note: str | None = Field(default=None, max_length=2000)


class MarkPaidInput(Strict):
    paid_on: date
    bank_reference: str | None = Field(default=None, max_length=120)


class AppraisalCycleInput(Strict):
    cycle: str = Field(min_length=1, max_length=20)
    employee_ids: list[str] = Field(min_length=1, max_length=2000)


class AppraisalInput(Strict):
    # readOnly fields of Appraisal, accepted and ignored
    id: str | None = None
    organisation_id: str | None = None
    cycle: str | None = None
    employee_id: str | None = None
    employee_name: str | None = None
    reviewer_id: str | None = None
    status: str | None = None
    completed_at: str | None = None
    created_at: str | None = None
    self_review: str | None = Field(default=None, max_length=20000)
    reviewer_comments: str | None = Field(default=None, max_length=20000)
    rating: int | None = Field(default=None, ge=1, le=5)
    submit: bool = False


def dump(model: BaseModel) -> dict:
    return model.model_dump()


def dump_employee(model: EmployeeInput) -> dict:
    """user_id, bank_account and pan only when the request sent them: absent leaves what is kept unchanged."""
    body = model.model_dump()
    for key in ("user_id", "bank_account", "pan"):
        if key not in model.model_fields_set:
            body.pop(key)
    return body


def dump_leave_request(model: LeaveRequestInput) -> dict:
    body = model.model_dump()
    body["from"] = body.pop("from_")
    return body
