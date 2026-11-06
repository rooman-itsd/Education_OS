"""Typed, bounded input. The batch envelope is strict (a failure is invalid_request, naming fields only); the
records inside are parsed leniently, row by row, because the port refuses a whole batch with row errors
([row, field, code]) rather than failing on the first bad value."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

AWARD_KINDS = (
    "degree",
    "provisional_degree",
    "diploma",
    "certificate",
    "marksheet",
    "grade_card",
    "consolidated_marksheet",
)
SAFE_ID = r"^[A-Za-z0-9._:-]{1,100}$"
CODE = r"^[A-Za-z0-9._-]{1,60}$"
SESSION = r"^[0-9]{4}-[0-9]{2}$"
MAX_RECORDS = 20_000

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Num = Annotated[float, Field(allow_inf_nan=False)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="ignore", str_max_length=2000)


class AccountLink(Strict):
    id: UUID
    person_id: UUID | None = None
    provider_subject: str | None = Field(default=None, max_length=100)


class Context(Strict):
    """What the hub passes to every operation (adapter.yaml, context)."""

    organisation_id: UUID
    connection_id: UUID
    provider: str = Field(default="nad", max_length=40)
    mode: Literal["mock", "sandbox", "live"]
    settings: dict = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict, repr=False)
    account_link: AccountLink | None = None
    delivery_id: UUID | None = None
    attempt: int = Field(default=1, ge=1, le=1000)
    idempotency_key: str | None = Field(default=None, max_length=200)
    deadline: datetime | None = None


class AwardTemplate(Strict):
    award_kind: Literal[AWARD_KINDS]  # type: ignore[valid-type]
    template_code: str = Field(pattern=CODE)
    programme_level: str | None = Field(default=None, max_length=40)


class ConnectionSettings(Strict):
    nad_institution_id: str | None = Field(default=None, pattern=CODE)
    abc_institution_id: str | None = Field(default=None, pattern=CODE)
    institution_name: str | None = Field(default=None, min_length=1, max_length=200)
    award_templates: list[AwardTemplate] = Field(default_factory=list, max_length=50)


class Programme(Strict):
    code: str = Field(min_length=1, max_length=40)
    name: Text
    level: str = Field(min_length=1, max_length=40)
    duration_terms: int = Field(ge=1, le=24)
    mode_of_study: str = Field(min_length=1, max_length=40)


class VerifyLearner(Strict):
    person_id: UUID | None = None
    apaar_id: str = Field(pattern=r"^[0-9]{12}$")
    enrolment_number: str | None = Field(default=None, max_length=60)
    name: Text
    date_of_birth: date
    gender: Literal["M", "F", "T"] | None = None


class VerifyInput(Strict):
    learner: VerifyLearner


class PublishAwardsInput(Strict):
    batch_key: str = Field(pattern=SAFE_ID)
    award_kind: Literal[AWARD_KINDS]  # type: ignore[valid-type]
    template_code: str = Field(pattern=CODE)
    programme: Programme
    session: str = Field(pattern=SESSION)
    records: list = Field(min_length=1, max_length=MAX_RECORDS)


class CorrectAwardsInput(PublishAwardsInput):
    reason: Text


class PublishCreditsInput(Strict):
    batch_key: str = Field(pattern=SAFE_ID)
    session: str = Field(pattern=SESSION)
    term: str = Field(min_length=1, max_length=30)
    records: list = Field(min_length=1, max_length=MAX_RECORDS)


class RecordUploadInput(Strict):
    submission_id: UUID
    uploaded_on: date
    uploaded_by: UUID
    portal_reference: str = Field(min_length=1, max_length=100)
    acknowledgement_document_id: UUID | None = None


class GetSubmissionInput(Strict):
    submission_id: UUID


# ---- records, parsed per row (lenient: every field optional here; rules.py reports what is missing or wrong) ----


class Learner(Strict):
    person_id: UUID | None = None
    apaar_id: str | None = Field(default=None, max_length=40)
    enrolment_number: str | None = Field(default=None, max_length=60)
    name: str | None = Field(default=None, max_length=200)
    date_of_birth: date | None = None
    gender: Literal["M", "F", "T"] | None = None
    mother_name: str | None = Field(default=None, max_length=200)
    father_name: str | None = Field(default=None, max_length=200)


class Result(Strict):
    cgpa: Num | None = None
    percentage: Num | None = None
    division: str | None = Field(default=None, max_length=40)
    result_status: str | None = Field(default=None, max_length=30)


class Course(Strict):
    code: str | None = Field(default=None, max_length=30)
    title: str | None = Field(default=None, max_length=200)
    credits: Num | None = None
    grade: str | None = Field(default=None, max_length=10)
    grade_point: Num | None = None
    max_marks: Num | None = None
    marks: Num | None = None


class AwardRecord(Strict):
    learner: Learner | None = None
    award_number: str | None = Field(default=None, max_length=60)
    result: Result | None = None
    courses: list[Course] = Field(default_factory=list, max_length=60)
    term: str | None = Field(default=None, max_length=30)
    issued_on: date | None = None
    document_id: UUID | None = None


class CreditCourse(Strict):
    code: str | None = Field(default=None, max_length=30)
    title: str | None = Field(default=None, max_length=200)
    credits_earned: Num | None = None
    grade: str | None = Field(default=None, max_length=10)
    grade_point: Num | None = None
    completed_on: date | None = None


class CreditRecord(Strict):
    learner: Learner | None = None
    programme_code: str | None = Field(default=None, max_length=40)
    courses: list[CreditCourse] = Field(default_factory=list, max_length=100)
