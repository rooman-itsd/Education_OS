"""Request bodies, mirroring contracts/openapi.yaml components."""

from __future__ import annotations

import math
from datetime import date
from typing import ClassVar, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

Category = Literal["individual", "team"]
Direction = Literal["higher_is_better", "lower_is_better"]
Gender = Literal["female", "male", "other", "undisclosed"]
BenchmarkGender = Literal["female", "male", "any"]
AthleteStatus = Literal["active", "inactive", "alumni"]
Context = Literal["training", "trial", "competition"]
ClearanceStatus = Literal["cleared", "restricted", "not_cleared"]
Id = Field(min_length=1, max_length=36)


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


def _finite(value: float | None) -> float | None:
    if value is not None and not math.isfinite(value):
        raise ValueError("must be a finite number")
    return value


class DisciplineIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    category: Category
    description: str | None = None
    active: bool = True


class DisciplinePatch(Patch):
    NULLABLE = frozenset({"description"})
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: Category | None = None
    description: str | None = None
    active: bool | None = None


class MetricIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=30)
    direction: Direction
    discipline_id: str | None = None
    description: str | None = None


class MetricPatch(Patch):
    NULLABLE = frozenset({"discipline_id", "description"})
    name: str | None = Field(default=None, min_length=1, max_length=120)
    unit: str | None = Field(default=None, min_length=1, max_length=30)
    direction: Direction | None = None
    discipline_id: str | None = None
    description: str | None = None


class AthleteIn(Strict):
    user_id: str | None = None
    student_id: str | None = None
    full_name: str = Field(min_length=1, max_length=200)
    date_of_birth: date | None = None
    gender: Gender | None = None
    primary_discipline_id: str = Id
    discipline_ids: list[str] | None = None
    coach_id: str | None = None
    squad: str | None = Field(default=None, max_length=120)
    status: AthleteStatus


class AthletePatch(Patch):
    NULLABLE = frozenset({"user_id", "student_id", "date_of_birth", "gender", "coach_id", "squad"})
    user_id: str | None = None
    student_id: str | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    date_of_birth: date | None = None
    gender: Gender | None = None
    primary_discipline_id: str | None = None
    discipline_ids: list[str] | None = None
    coach_id: str | None = None
    squad: str | None = Field(default=None, max_length=120)
    status: AthleteStatus | None = None


class ResultIn(Strict):
    athlete_id: str = Id
    metric_id: str = Id
    value: float
    recorded_at: AwareDatetime
    context: Context
    notes: str | None = None

    _value = field_validator("value")(_finite)


class ResultPatch(Patch):
    NULLABLE = frozenset({"notes"})
    athlete_id: str | None = None
    metric_id: str | None = None
    value: float | None = None
    recorded_at: AwareDatetime | None = None
    context: Context | None = None
    notes: str | None = None

    _value = field_validator("value")(_finite)


class FitnessTestIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    metric_ids: list[str]
    discipline_id: str | None = None


class FitnessTestPatch(Patch):
    NULLABLE = frozenset({"description", "discipline_id"})
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    metric_ids: list[str] | None = None
    discipline_id: str | None = None


class MeasurementIn(Strict):
    metric_id: str = Id
    value: float

    _value = field_validator("value")(_finite)


class AssessmentIn(Strict):
    athlete_id: str = Id
    fitness_test_id: str = Id
    assessed_on: date
    measurements: list[MeasurementIn]
    notes: str | None = None


class BenchmarkIn(Strict):
    metric_id: str = Id
    discipline_id: str | None = None
    level: str = Field(min_length=1, max_length=60)
    gender: BenchmarkGender | None = None
    age_group: str | None = Field(default=None, max_length=30)
    target_value: float
    source: str | None = Field(default=None, max_length=300)

    _target = field_validator("target_value")(_finite)


class BenchmarkPatch(Patch):
    NULLABLE = frozenset({"discipline_id", "gender", "age_group", "source"})
    metric_id: str | None = None
    discipline_id: str | None = None
    level: str | None = Field(default=None, min_length=1, max_length=60)
    gender: BenchmarkGender | None = None
    age_group: str | None = Field(default=None, max_length=30)
    target_value: float | None = None
    source: str | None = Field(default=None, max_length=300)

    _target = field_validator("target_value")(_finite)


class ClearanceIn(Strict):
    status: ClearanceStatus
    valid_until: date | None = None
    restrictions: str | None = None


def dump(body: BaseModel, *, partial: bool = False) -> dict:
    """Python values (dates stay dates); a partial body keeps only the fields the caller sent."""
    data = body.model_dump(exclude_unset=partial)
    if "measurements" in data:
        data["measurements"] = [dict(m) for m in data["measurements"]]
    return data
