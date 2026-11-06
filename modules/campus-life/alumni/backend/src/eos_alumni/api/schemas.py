"""Request bodies of contracts/openapi.yaml. Strict: unknown fields are refused. Lengths of free text match the contract
(and the columns), so an over-long value is 422 before it reaches the database. The fields the contract gives an error
code (full_name, graduation_year, email, phone, linkedin_url, duration_minutes) are checked by the domain rules, so
they answer that code."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SessionMode = Literal["in_person", "online", "phone"]
SHORT = {"max_length": 200}
LONG = {"max_length": 2000}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AlumnusInput(Strict):
    full_name: str
    graduation_year: int
    programme: str | None = Field(default=None, **SHORT)
    current_company: str | None = Field(default=None, **SHORT)
    current_designation: str | None = Field(default=None, **SHORT)
    industry: str | None = Field(default=None, **SHORT)
    city: str | None = Field(default=None, **SHORT)
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    is_mentor: bool = False
    notes: str | None = Field(default=None, **LONG)


class AlumnusUpdate(AlumnusInput):
    """PUT /directory/{id}: a full replace. Every field is sent; one left out is cleared, and is_mentor is required
    so an edit never clears the mentor flag by omission (A8)."""

    is_mentor: bool


class Reason(Strict):
    reason: str | None = Field(default=None, **LONG)


class EndInput(Strict):
    ended_on: date | None = None
    reason: str | None = Field(default=None, **LONG)


class AssignmentInput(Strict):
    mentor_id: str = Field(min_length=1, max_length=36)
    student_id: UUID
    student_name: str | None = Field(default=None, **SHORT)
    started_on: date | None = None
    focus: str | None = Field(default=None, **SHORT)


class SessionInput(Strict):
    scheduled_at: datetime
    duration_minutes: int | None = None
    mode: SessionMode
    location: str | None = Field(default=None, max_length=500)
    topic: str | None = Field(default=None, **SHORT)


class CompleteInput(Strict):
    notes: str | None = Field(default=None, **LONG)


def dump(model: BaseModel) -> dict:
    out = model.model_dump()
    if isinstance(out.get("student_id"), UUID):
        out["student_id"] = str(out["student_id"])  # the canonical lower-case form identity issues
    return out
