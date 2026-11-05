"""Request bodies, mirroring contracts/openapi.yaml components. Money stays a decimal string here and is parsed
exactly (Decimal) in the application layer."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# The contract types every id as format: uuid. Checked here so a bad id is a 422, never a stored row.
Uuid = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")]
# At most 10 integer digits: the money columns are Numeric(12, 2).
Money = Annotated[str, Field(pattern=r"^[0-9]{1,10}(\.[0-9]{1,2})?$", examples=["25.00"])]
Year = Annotated[int, Field(ge=0, le=9999)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


def dump(body: BaseModel) -> dict:
    return body.model_dump(by_alias=True)


class TitleIn(Strict):
    isbn: str | None = Field(default=None, max_length=20)
    title: str = Field(min_length=1, max_length=500)
    authors: list[str] = []
    publisher: str | None = Field(default=None, max_length=200)
    year: Year | None = None
    subjects: list[str] = []
    kind: str = Field(min_length=1, max_length=60)


class TitlePatch(Strict):
    isbn: str | None = Field(default=None, max_length=20)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    authors: list[str] | None = None
    publisher: str | None = Field(default=None, max_length=200)
    year: Year | None = None
    subjects: list[str] | None = None
    kind: str | None = Field(default=None, min_length=1, max_length=60)


class CopyIn(Strict):
    accession_no: str = Field(min_length=1, max_length=60)
    barcode: str = Field(min_length=1, max_length=60)
    location: str | None = Field(default=None, max_length=200)


class CopyPatch(Strict):
    location: str | None = Field(default=None, max_length=200)
    withdrawn: bool | None = None
    reason: str | None = None


class MemberIn(Strict):
    person_id: Uuid
    category: str = Field(min_length=1, max_length=60)


class MemberPatch(Strict):
    category: str | None = Field(default=None, min_length=1, max_length=60)
    blocked: bool | None = None
    reason: str | None = None


class LoanPolicyIn(Strict):
    member_category: str = Field(min_length=1, max_length=60)
    max_loans: int = Field(ge=0, le=100)
    loan_days: int = Field(ge=1, le=365)
    max_renewals: int = Field(ge=0, le=100)
    fine_per_day: Money
    max_unpaid_fines: Money
    hold_days: int = Field(ge=1, le=60)


class IssueIn(Strict):
    barcode: str = Field(min_length=1, max_length=60)
    person_id: Uuid


class ReturnIn(Strict):
    barcode: str = Field(min_length=1, max_length=60)
    damage_note: str | None = None


class LostIn(Strict):
    replacement_amount: Money
    note: str | None = None


class ReceiptIn(Strict):
    receipt_ref: str = Field(min_length=1, max_length=120)


class ReasonIn(Strict):
    reason: str = Field(min_length=3)


class ReserveIn(Strict):
    title_id: Uuid


class DigitalIn(Strict):
    title: str = Field(min_length=1, max_length=500)
    provider: str | None = Field(default=None, max_length=200)
    kind: str | None = Field(default=None, max_length=60)
    url: str = Field(min_length=1, max_length=2000, pattern=r"^https?://")
    access: Literal["open", "campus", "licensed"]
    active: bool = True


class DigitalPatch(Strict):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    provider: str | None = Field(default=None, max_length=200)
    kind: str | None = Field(default=None, max_length=60)
    url: str | None = Field(default=None, min_length=1, max_length=2000, pattern=r"^https?://")
    access: Literal["open", "campus", "licensed"] | None = None
    active: bool | None = None
