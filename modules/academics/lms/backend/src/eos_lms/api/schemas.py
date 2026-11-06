"""Request bodies, mirroring contracts/openapi.yaml components. The router reads each body as JSON and checks it here,
so a malformed body is the contract's 400 with an ErrorResponse, not FastAPI's 422. Optional fields left out of a PATCH
body keep their stored value, so bodies are dumped with exclude_unset.

Every string, number, list and instant is bounded, so nothing reaches a column or the date arithmetic out of range."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, ClassVar, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    ValidationError,
    model_validator,
)

from ..application.errors import LmsError

# The contract types every id as format: uuid. Checked here so a bad id is a 400, never a stored row.
Uuid = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")]


def in_range(value: datetime) -> datetime:
    """Instants near year 1 or 9999 overflow when shifted to UTC; nothing in lms is that far away. Stored as UTC; an
    instant without an offset is read as UTC."""
    if not 1900 <= value.year <= 9998:
        raise ValueError("must be between the years 1900 and 9998")
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


Instant = Annotated[datetime, AfterValidator(in_range)]
Title = Annotated[str, Field(min_length=1, max_length=200)]
Text = Annotated[str, Field(max_length=20_000)]
LongText = Annotated[str, Field(max_length=100_000)]
Reason = Annotated[str, Field(max_length=2_000)]
Points = Annotated[float, Field(ge=0, le=100_000, allow_inf_nan=False)]
PositivePoints = Annotated[float, Field(gt=0, le=100_000, allow_inf_nan=False)]
SectionIds = Annotated[list[Uuid], Field(max_length=200)]
Url = Annotated[str, Field(min_length=1, max_length=2_000, pattern=r"^https?://[^\s]+$")]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Patch(Strict):
    """A PATCH body. A field may be left out to keep its value; only the fields the contract types as nullable may be
    sent as null (to clear them)."""

    NULLABLE: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="before")
    @classmethod
    def _no_nulls(cls, data):
        if isinstance(data, dict):
            for key, value in data.items():
                if value is None and key in cls.model_fields and key not in cls.NULLABLE:
                    raise ValueError(f"{key} may not be null")
        return data


def parse(model: type[BaseModel], body: object) -> dict:
    """The body checked against `model`, as a dict of the fields that were sent; 400 when it does not fit."""
    if not isinstance(body, dict):
        raise LmsError(400, "invalid_request", "the request body must be a JSON object")
    try:
        parsed = model.model_validate(body)
    except ValidationError as e:
        errors = [
            {"field": ".".join(str(p) for p in err["loc"]), "message": err["msg"]}
            for err in e.errors(include_url=False, include_input=False, include_context=False)
        ]
        first = errors[0] if errors else {"field": "", "message": "invalid"}
        raise LmsError(
            400, "invalid_request", f"{first['field'] or 'body'}: {first['message']}", errors=errors[:20]
        ) from None
    return parsed.model_dump(exclude_unset=True)


# ---------------------------------------------------------------- course spaces and content


class CreateCourseSpaceIn(Strict):
    course_offering_id: Uuid
    title: Title
    description: Text | None = None
    visible_section_ids: SectionIds = []


class UpdateCourseSpaceIn(Patch):
    NULLABLE = frozenset({"description"})
    title: Title | None = None
    description: Text | None = None
    visible_section_ids: SectionIds | None = None


class CourseSpaceStatusIn(Strict):
    status: Literal["active", "archived"]


class ContentUnitIn(Strict):
    title: Title
    position: int | None = Field(default=None, ge=0, le=10_000)
    published: bool = False


class UpdateContentUnitIn(Patch):
    title: Title | None = None
    position: int | None = Field(default=None, ge=0, le=10_000)
    published: bool | None = None


class CourseMaterialIn(Strict):
    material_type: Literal["document", "link", "page"]
    title: Title
    unit_id: Uuid | None = None
    document_id: Uuid | None = None
    url: Url | None = None
    body: LongText | None = None
    visible_section_ids: SectionIds = []
    scheduled_class_id: Uuid | None = None


class UpdateCourseMaterialIn(Patch):
    NULLABLE = frozenset({"unit_id", "scheduled_class_id"})
    title: Title | None = None
    unit_id: Uuid | None = None
    document_id: Uuid | None = None
    url: Url | None = None
    body: LongText | None = None
    visible_section_ids: SectionIds | None = None
    scheduled_class_id: Uuid | None = None


class MaterialStatusIn(Strict):
    status: Literal["published", "unpublished"]


# ---------------------------------------------------------------- assignments and submissions


class LatePolicyIn(Strict):
    accept_late: bool
    late_cutoff_at: Instant | None = None


class AssignmentIn(Strict):
    title: Title
    instructions: Text | None = None
    unit_id: Uuid | None = None
    due_at: Instant
    max_points: PositivePoints
    submission_type: Literal["file", "text", "file_and_text", "none"]
    max_attempts: int = Field(default=1, ge=1, le=100)
    late_policy: LatePolicyIn | None = None
    target_section_ids: SectionIds = []


class UpdateAssignmentIn(Patch):
    NULLABLE = frozenset({"unit_id"})
    title: Title | None = None
    instructions: Text | None = None
    unit_id: Uuid | None = None
    due_at: Instant | None = None
    max_points: PositivePoints | None = None
    submission_type: Literal["file", "text", "file_and_text", "none"] | None = None
    max_attempts: int | None = Field(default=None, ge=1, le=100)
    late_policy: LatePolicyIn | None = None
    target_section_ids: SectionIds | None = None


class WorkStatusIn(Strict):
    status: Literal["published", "closed"]


class SubmissionIn(Strict):
    document_ids: Annotated[list[Uuid], Field(max_length=20)] = []
    text: LongText | None = None


# ---------------------------------------------------------------- quizzes


Index = Annotated[StrictInt, Field(ge=0, le=99)]
# Strict members: JSON true is not the option index 1, and "1" is neither an index nor a boolean.
AnswerKey = list[Index] | StrictBool | list[Annotated[StrictStr, Field(max_length=1_000)]]


class QuestionIn(Strict):
    question_type: Literal["single_choice", "multiple_choice", "true_false", "short_answer", "essay"]
    prompt: Annotated[str, Field(min_length=1, max_length=5_000)]
    options: Annotated[list[Annotated[str, Field(min_length=1, max_length=1_000)]], Field(max_length=20)] | None = None
    answer_key: Annotated[AnswerKey, Field(union_mode="left_to_right")] | None = None
    points: PositivePoints


class QuizSettingsIn(Strict):
    title: Title | None = None
    unit_id: Uuid | None = None
    opens_at: Instant | None = None
    closes_at: Instant | None = None
    time_limit_minutes: int | None = Field(default=None, ge=1, le=10_080)
    attempts_allowed: int | None = Field(default=None, ge=1, le=100)
    attempt_scoring: Literal["highest", "latest"] | None = None
    auto_release: bool | None = None


class QuizIn(QuizSettingsIn):
    title: Title
    opens_at: Instant
    closes_at: Instant
    attempts_allowed: int = Field(default=1, ge=1, le=100)
    attempt_scoring: Literal["highest", "latest"] = "highest"
    auto_release: bool = False
    questions: Annotated[list[QuestionIn], Field(min_length=1, max_length=200)]


class UpdateQuizIn(Patch, QuizSettingsIn):
    NULLABLE = frozenset({"unit_id", "time_limit_minutes"})
    questions: Annotated[list[QuestionIn], Field(min_length=1, max_length=200)] | None = None


class AnswerIn(Strict):
    question_id: Uuid
    selected_options: Annotated[list[Index], Field(max_length=20)] | None = None
    boolean_answer: StrictBool | None = None
    text_answer: Annotated[str, Field(max_length=20_000)] | None = None


class AnswersIn(Strict):
    answers: Annotated[list[AnswerIn], Field(max_length=200)]


class ScoreIn(Strict):
    question_id: Uuid
    points: Points
    comment: Reason | None = None


class ScoresIn(Strict):
    scores: Annotated[list[ScoreIn], Field(min_length=1, max_length=200)]


# ---------------------------------------------------------------- grades


class GradeEntryIn(Strict):
    student_id: Uuid
    points: Points
    feedback: Annotated[str, Field(max_length=5_000)] | None = None
    reason: Reason | None = None


class EnterGradesIn(Strict):
    item_type: Literal["assignment", "quiz"]
    item_id: Uuid
    entries: Annotated[list[GradeEntryIn], Field(min_length=1, max_length=1_000)]


class ReleaseGradesIn(Strict):
    item_type: Literal["assignment", "quiz"]
    item_id: Uuid
    student_ids: Annotated[list[Uuid], Field(max_length=1_000)] | None = None


# ---------------------------------------------------------------- discussions


class ThreadIn(Strict):
    title: Title
    body: Annotated[str, Field(min_length=1, max_length=20_000)]


class PostIn(Strict):
    body: Annotated[str, Field(min_length=1, max_length=20_000)]


class ThreadModerationIn(Strict):
    action: Literal["lock", "unlock", "hide", "unhide"]
    reason: Reason | None = None


class PostModerationIn(Strict):
    action: Literal["hide", "unhide"]
    reason: Reason | None = None
