"""Request bodies of contracts/openapi.yaml. Values the contract gives an error code for (names, titles, URLs, emails,
amounts, positions, criteria, dates, statuses, reasons, the declaration) are checked by the domain rules so the answer
carries that code; here only the shape is checked, and lengths match the columns so an over-long value is 422 before
it reaches the database.

CompanyInput, DriveInput and OpeningInput are also the base of the records they create, so a record read from the API
can be sent back: their extra (read-only) fields are ignored. The other bodies refuse unknown fields."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

ID = {"min_length": 1, "max_length": 36}
Amount = str | int | float | None  # Money is a string; anything else is refused by the rules with invalid_amount


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Record(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Eligibility(Strict):
    programmes: list[str | None] = Field(default_factory=list, max_length=50)
    graduating_years: list[int] = Field(default_factory=list, max_length=20)
    min_cgpa: float | None = None
    max_active_backlogs: int | None = None
    notes: str | None = Field(default=None, max_length=2000)


class CompanyInput(Record):
    name: str | None = Field(default=None, max_length=1000)
    industry: str | None = Field(default=None, max_length=120)
    website: str | None = Field(default=None, max_length=500)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=254)
    contact_phone: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=5000)
    active: bool | None = None


class DriveInput(Record):
    company_id: str = Field(**ID)
    title: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=10000)
    scheduled_on: date
    ends_on: date | None = None
    venue: str | None = Field(default=None, max_length=300)
    registration_closes_on: date | None = None
    rounds: list[str | None] = Field(default_factory=list, max_length=20)
    eligibility: Eligibility | None = None


class OpeningInput(Record):
    company_id: str = Field(**ID)
    drive_id: str | None = Field(default=None, max_length=36)
    title: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=10000)
    location: str | None = Field(default=None, max_length=200)
    ctc_per_annum: Amount = None
    positions: int | None = None
    applications_close_on: date
    eligibility: Eligibility | None = None


class ReasonInput(Strict):
    reason: str | None = Field(default=None, max_length=2000)


class Declaration(Strict):
    programme: str | None = Field(default=None, max_length=200)
    graduating_year: int | None = None
    cgpa: float | None = None
    active_backlogs: int | None = None


class ApplicationInput(Strict):
    opening_id: str = Field(**ID)
    declares_eligible: bool | None = None
    declared: Declaration | None = None


class Offer(Strict):
    ctc_per_annum: Amount = None
    joining_on: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class StatusChange(Strict):
    status: str = Field(max_length=40)
    reason: str | None = Field(default=None, max_length=2000)
    offer: Offer | None = None


def dump(model: BaseModel) -> dict:
    return model.model_dump()
