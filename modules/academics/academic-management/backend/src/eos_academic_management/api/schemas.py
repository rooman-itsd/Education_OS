"""Response bodies, mirroring contracts/openapi.yaml components. Types are strict so a drift between the use case
and the contract (a string for a number, a boolean for a count) fails validation instead of being coerced."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr

UUID = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"  # format: uuid


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FacultyLoadOut(Strict):
    """components.schemas.FacultyLoad"""

    faculty_id: StrictStr = Field(pattern=UUID)
    faculty_name: StrictStr
    offerings_count: StrictInt
    contact_hours: StrictInt | StrictFloat
    over_load: StrictBool


class FacultyLoadReportOut(Strict):
    """components.schemas.FacultyLoadReport, the 200 body of GET /faculty-load (operationId getFacultyLoad)."""

    academic_period_id: StrictStr = Field(pattern=UUID)
    academic_period_code: StrictStr
    academic_period_name: StrictStr
    department_id: StrictStr | None = Field(default=None, pattern=UUID)
    max_weekly_contact_hours: StrictInt | StrictFloat
    faculty_count: StrictInt = Field(ge=0)
    over_load_count: StrictInt = Field(ge=0)
    items: list[FacultyLoadOut]


# ---------------------------------------------------------------- request bodies
# Presence and JSON types only. Values (numbers, enums, ranges) are validated by the domain rules, so a broken
# rule answers with the contract's 400 and its code (below_minimum, invalid_choice, ...), as the use cases do.


class CreateTermIn(Strict):
    code: StrictStr = Field(min_length=1, max_length=40)
    name: StrictStr = Field(min_length=1, max_length=200)
    starts_on: date
    ends_on: date


class UpdateTermIn(Strict):
    name: StrictStr | None = Field(default=None, min_length=1, max_length=200)
    starts_on: date | None = None
    ends_on: date | None = None


class CreateProgrammeIn(Strict):
    code: StrictStr = Field(min_length=1, max_length=40)
    name: StrictStr = Field(min_length=1, max_length=200)
    level: Any
    department_id: StrictStr = Field(pattern=UUID)
    duration_terms: Any
    credits_required: Any


class UpdateProgrammeIn(Strict):
    name: StrictStr | None = Field(default=None, min_length=1, max_length=200)
    department_id: StrictStr | None = Field(default=None, pattern=UUID)
    duration_terms: Any = None
    credits_required: Any = None


class CurriculumItemIn(BaseModel):
    """course_code and course_title are read-only in the contract; they are accepted and ignored."""

    model_config = ConfigDict(extra="ignore")
    course_id: StrictStr = Field(pattern=UUID)
    programme_term: Any
    category: Any
    credits: Any


class CreateCurriculumIn(Strict):
    copy_from_curriculum_id: StrictStr | None = Field(default=None, pattern=UUID)
    items: list[CurriculumItemIn] | None = None


class ReplaceCurriculumItemsIn(Strict):
    items: list[CurriculumItemIn]


class CreateCourseIn(Strict):
    code: StrictStr = Field(min_length=1, max_length=40)
    title: StrictStr = Field(min_length=1, max_length=200)
    description: StrictStr | None = None
    credits: Any
    lecture_hours: Any = None
    practical_hours: Any = None
    course_type: Any
    department_id: StrictStr = Field(pattern=UUID)


class UpdateCourseIn(Strict):
    title: StrictStr | None = Field(default=None, min_length=1, max_length=200)
    description: StrictStr | None = None
    credits: Any = None
    lecture_hours: Any = None
    practical_hours: Any = None
    course_type: Any = None
    department_id: StrictStr | None = Field(default=None, pattern=UUID)


class CreateSectionIn(Strict):
    code: StrictStr = Field(min_length=1, max_length=40)
    capacity: Any


class UpdateSectionIn(Strict):
    capacity: Any = None
    status: Any = None


class CreateOfferingIn(Strict):
    course_id: StrictStr = Field(pattern=UUID)
    academic_period_id: StrictStr = Field(pattern=UUID)
    programme_ids: list[Annotated[StrictStr, Field(pattern=UUID)]] | None = None
    sections: list[CreateSectionIn]


class UpdateOfferingIn(Strict):
    programme_ids: list[Annotated[StrictStr, Field(pattern=UUID)]] | None = None


class ChangeOfferingStatusIn(Strict):
    status: Any
    reason: StrictStr | None = None


class CreateFacultyAssignmentIn(Strict):
    faculty_id: StrictStr = Field(pattern=UUID)
    section_id: StrictStr | None = Field(default=None, pattern=UUID)
    role: Any
    contact_hours: Any


def dump(body: BaseModel, *, partial: bool = False) -> dict:
    """The request as a dict; for a PATCH, only the fields the caller sent."""
    return body.model_dump(exclude_unset=partial)
