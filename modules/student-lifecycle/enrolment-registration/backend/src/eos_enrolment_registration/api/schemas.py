"""Request bodies from contracts/openapi.yaml. Responses are the service's dicts, already in contract shape."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field

RegistrationType = Literal["regular", "supplementary", "backlog"]
Reason = Annotated[str, Field(min_length=1, max_length=1000, pattern=r"\S")]


class EnrolmentInput(BaseModel):
    person_id: UUID
    student_name: str = Field(min_length=1, max_length=200, pattern=r"\S")
    programme_id: UUID
    start_academic_period_id: UUID
    source_application_id: UUID | None = None


class ReasonInput(BaseModel):
    reason: Reason


class WindowInput(BaseModel):
    opens_at: AwareDatetime
    closes_at: AwareDatetime


class RegistrationInput(BaseModel):
    programme_enrolment_id: UUID
    course_offering_id: UUID
    section_id: UUID
    academic_period_id: UUID
    registration_type: RegistrationType = "regular"


class BulkRegistrationInput(BaseModel):
    programme_enrolment_ids: list[UUID] = Field(min_length=1, max_length=500)
    course_offering_id: UUID
    section_id: UUID
    academic_period_id: UUID
    registration_type: RegistrationType = "regular"

    def unique_ids(self) -> list[str]:
        """Request order, duplicates dropped (the contract says uniqueItems)."""
        return list(dict.fromkeys(str(i) for i in self.programme_enrolment_ids))


class SectionChangeInput(BaseModel):
    to_section_id: UUID
    effective_on: date
