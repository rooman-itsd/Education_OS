"""Request bodies from contracts/openapi.yaml. Responses are the service's dicts, already in contract shape."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from eos_core.db import utcnow
from pydantic import AwareDatetime, BaseModel, EmailStr, Field, field_validator

ApplicationStatus = Literal[
    "submitted", "under_review", "eligible", "ineligible", "offered", "accepted", "declined", "rejected", "withdrawn"
]


class StatusChangeInput(BaseModel):
    status: ApplicationStatus
    reason: str = Field(min_length=1)


class DocumentVerificationInput(BaseModel):
    verification_status: Literal["verified", "rejected"]
    verification_note: str | None = None


class OfferInput(BaseModel):
    note: str | None = None
    expires_at: AwareDatetime | None = None

    @field_validator("expires_at")
    @classmethod
    def _in_the_future(cls, value):
        if value is not None and value <= utcnow():
            raise ValueError("expires_at must be in the future")
        return value


class MeritScore(BaseModel):
    application_id: UUID
    score: float = Field(allow_inf_nan=False)


class MeritListInput(BaseModel):
    programme_id: UUID
    academic_year: str = Field(min_length=1, max_length=20)
    title: str | None = Field(default=None, max_length=200)
    scores: list[MeritScore] = Field(default_factory=list)


# ---------------------------------------------------------------- public (anonymous applicant)

Name = Annotated[str, Field(min_length=1, max_length=120, pattern=r"\S")]


class ApplicantDetails(BaseModel):
    first_name: Name
    last_name: Name
    email: EmailStr = Field(max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    date_of_birth: date | None = None


class ApplicationInput(BaseModel):
    applicant: ApplicantDetails
    programme_id: UUID
    academic_year: str = Field(min_length=1, max_length=20)
    selection_process_round_id: UUID | None = None
    portfolio_item_id: UUID | None = None


class ApplicationDocumentInput(BaseModel):
    email: EmailStr
    type: Literal["identity_proof", "academic_record", "portfolio_evidence", "other"]
    document_id: str = Field(min_length=1, max_length=64)
    label: str | None = Field(default=None, max_length=200)


class OfferAcceptInput(BaseModel):
    email: EmailStr


class OfferDeclineInput(BaseModel):
    email: EmailStr
    reason: str | None = Field(default=None, max_length=2000)
