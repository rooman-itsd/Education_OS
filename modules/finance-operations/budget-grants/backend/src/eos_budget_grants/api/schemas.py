"""Request bodies of contracts/openapi.yaml. Strict: unknown fields are refused. Money stays a decimal string here;
the domain parses it exactly."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MONEY = r"^-?[0-9]+(\.[0-9]{1,2})?$"
YEAR = r"^[0-9]{4}-[0-9]{2}$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BudgetHeadInput(Strict):
    id: str | None = None  # readOnly in the contract: accepted and ignored
    organisation_id: str | None = None  # readOnly
    code: str = Field(pattern=r"^[A-Z0-9_]{2,20}$")
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["recurring", "non_recurring"] = "recurring"
    active: bool = True


class BudgetLineInput(Strict):
    budget_head_id: str
    allocated: str = Field(pattern=MONEY)
    note: str | None = None


class BudgetInput(Strict):
    financial_year: str = Field(pattern=YEAR)
    department_id: str | None = None
    title: str | None = Field(default=None, max_length=200)
    lines: list[BudgetLineInput] = Field(min_length=1)


class Decision(Strict):
    decision: Literal["approved", "returned", "rejected"]
    note: str | None = None


class ReappropriationInput(Strict):
    from_line_id: str
    to_line_id: str
    amount: str = Field(pattern=MONEY)
    reason: str = Field(min_length=1)


class ExpenditureInput(Strict):
    line_id: str
    amount: str = Field(pattern=MONEY)
    date: date
    description: str = Field(min_length=1, max_length=300)
    document_id: str | None = None


class Reason(Strict):
    reason: str = Field(min_length=1)


class InvestigatorInput(Strict):
    user_id: str
    name: str | None = None  # readOnly in the contract: accepted and ignored
    role: Literal["principal", "co_investigator"]


class GrantLineInput(Strict):
    budget_head_id: str
    sanctioned: str = Field(pattern=MONEY)


class GrantInput(Strict):
    code: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=300)
    funder: str = Field(min_length=1, max_length=200)
    scheme: str | None = Field(default=None, max_length=200)
    sanction_order_document_id: str | None = None
    sanctioned_amount: str = Field(pattern=MONEY)
    start_date: date
    end_date: date
    department_id: str | None = None
    investigators: list[InvestigatorInput] = Field(min_length=1)
    uc_frequency: Literal["yearly", "half_yearly", "on_completion"] = "yearly"
    lines: list[GrantLineInput] = Field(min_length=1)


class FundsReceivedInput(Strict):
    amount: str = Field(pattern=MONEY)
    received_on: date
    reference: str | None = Field(default=None, max_length=120)


class CloseInput(Strict):
    unspent_action: Literal["returned", "carried_over", "none"]
    note: str | None = None


class CertificateInput(Strict):
    period_from: date
    period_to: date


class SubmittedInput(Strict):
    submitted_on: date | None = None
    reference: str | None = Field(default=None, max_length=120)


def dump(model: BaseModel) -> dict:
    return model.model_dump(mode="python")
