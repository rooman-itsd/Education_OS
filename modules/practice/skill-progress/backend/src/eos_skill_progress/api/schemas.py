"""Request bodies, mirroring contracts/openapi.yaml components. Shapes and types are checked here (422); the rules
that relate values to each other (scales, rubrics, scores) are the domain's (400 with a code)."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from pydantic import AnyUrl, AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

FrameworkStatus = Literal["active", "draft", "archived"]
NewFrameworkStatus = Literal["active", "draft"]
ScaleType = Literal["discrete_stages", "numeric_range", "pass_fail"]
# Ids are UUIDs (contracts/openapi.yaml `format: uuid`), kept as strings; "" or any other text is refused (422).
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
Uuid = Annotated[str, StringConstraints(pattern=UUID_PATTERN)]
Number = Annotated[float, Field(allow_inf_nan=False)]
Code = Annotated[str, StringConstraints(min_length=1, max_length=60, strip_whitespace=True)]
Title = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Patch(Strict):
    """A partial body. Only the fields in NULLABLE may be set to null explicitly: null on anything else would clear a
    column that cannot be empty, so it is refused (422) instead of a 500."""

    NULLABLE: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def no_explicit_null_on_required_fields(self):
        bad = [k for k in self.model_fields_set if getattr(self, k) is None and k not in self.NULLABLE]
        if bad:
            raise ValueError(f"{', '.join(sorted(bad))} cannot be null")
        return self


class PerformanceLevel(Strict):
    key: Code
    label: Annotated[str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)]
    rank: int
    description: str | None = None
    min_score: Number | None = None


class ProficiencyScale(Strict):
    type: ScaleType
    min_score: Number | None = None
    max_score: Number | None = None
    levels: list[PerformanceLevel] = Field(max_length=50)


class FrameworkIn(Strict):
    code: Code
    title: Title
    description: str | None = None
    status: NewFrameworkStatus = "active"


class FrameworkPatch(Patch):
    NULLABLE = frozenset({"description"})
    title: Title | None = None
    description: str | None = None
    status: FrameworkStatus | None = None


class SkillIn(Strict):
    framework_id: Uuid
    parent_skill_id: Uuid | None = None
    code: Code
    title: Title
    description: str | None = None
    category: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None = None
    level_scale: ProficiencyScale


class SkillPatch(Patch):
    NULLABLE = frozenset({"description", "category"})
    title: Title | None = None
    description: str | None = None
    category: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None = None
    level_scale: ProficiencyScale | None = None


class RubricCriterion(Strict):
    key: Code
    title: Title
    description: str | None = None
    weight: Number = 1.0
    max_points: Number
    levels: list[PerformanceLevel] | None = Field(default=None, max_length=50)


class RubricIn(Strict):
    skill_id: Uuid | None = None
    framework_id: Uuid | None = None
    title: Title
    description: str | None = None
    criteria: list[RubricCriterion] = Field(max_length=100)


class CriterionScore(Strict):
    criterion_key: Code
    points: Number
    level_key: Code | None = None
    notes: str | None = None


class AssessmentIn(Strict):
    learner_id: Uuid
    evaluator_id: Uuid
    skill_id: Uuid
    rubric_id: Uuid
    assessed_at: AwareDatetime | None = None
    criterion_scores: list[CriterionScore] = Field(max_length=100)
    overall_score: Number
    level_achieved: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    feedback: str | None = None
    evidence_urls: list[AnyUrl] | None = Field(default=None, max_length=20)


def _plain(value):
    """Nested models as plain JSON values, optional fields left out rather than stored as null."""
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, AnyUrl):
        return str(value)
    return value


NESTED = ("level_scale", "criteria", "criterion_scores", "evidence_urls")


def dump(body: BaseModel, *, partial: bool = False) -> dict:
    """Python values (datetimes stay datetimes); a partial body keeps only the fields the caller sent."""
    data = body.model_dump(exclude_unset=partial)
    for name in NESTED:
        if data.get(name) is not None:
            data[name] = _plain(data[name])
    return data
