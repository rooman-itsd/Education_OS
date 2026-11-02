"""Request bodies, mirroring contracts/openapi.yaml components."""

from __future__ import annotations

import math
from datetime import date
from typing import Annotated, ClassVar, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Goal = Literal["performance", "weight_gain", "weight_loss", "recovery", "maintenance"]
PlanStatus = Literal["draft", "active", "completed", "archived"]
Outcome = Literal["continue", "adjust", "end"]
RecordType = Literal["medical_history", "allergy", "medication", "screening", "vaccination"]
Severity = Literal["minor", "moderate", "severe"]
InjuryContext = Literal["training", "competition", "other"]
InjuryStatus = Literal["active", "recovering", "resolved"]
AppointmentType = Literal["physiotherapy", "medical", "nutrition"]
AppointmentStatus = Literal["scheduled", "completed", "cancelled", "no_show"]
# Ids are UUIDs (contracts/openapi.yaml `format: uuid`), kept as strings; "" or any other text is refused (422).
Uuid = Annotated[
    str, StringConstraints(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
]
Text = Annotated[str, StringConstraints(min_length=1, max_length=200)]


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


class Meal(Strict):
    meal: Text
    items: str = Field(min_length=1)


class _PlanFields(Strict):
    daily_calories: int | None = Field(default=None, ge=0)
    protein_g: float | None = Field(default=None, ge=0)
    carbohydrate_g: float | None = Field(default=None, ge=0)
    fat_g: float | None = Field(default=None, ge=0)

    _macros = field_validator("protein_g", "carbohydrate_g", "fat_g")(_finite)


class PlanIn(_PlanFields):
    athlete_id: Uuid
    title: Text
    goal: Goal
    meals: list[Meal] = Field(default_factory=list)
    start_date: date
    end_date: date | None = None
    review_due_on: date | None = None
    status: PlanStatus


class PlanPatch(_PlanFields, Patch):
    NULLABLE = frozenset({"daily_calories", "protein_g", "carbohydrate_g", "fat_g", "end_date", "review_due_on"})
    athlete_id: Uuid | None = None
    title: Text | None = None
    goal: Goal | None = None
    meals: list[Meal] | None = None
    start_date: date | None = None
    end_date: date | None = None
    review_due_on: date | None = None
    status: PlanStatus | None = None


class ReviewIn(Strict):
    reviewed_on: date
    outcome: Outcome
    body_weight_kg: float | None = Field(default=None, gt=0)
    next_review_on: date | None = None
    notes: str | None = None

    _weight = field_validator("body_weight_kg")(_finite)


class HealthRecordIn(Strict):
    athlete_id: Uuid
    record_type: RecordType
    title: Text
    details: str | None = None
    recorded_on: date


class HealthRecordPatch(Patch):
    NULLABLE = frozenset({"details"})
    athlete_id: Uuid | None = None
    record_type: RecordType | None = None
    title: Text | None = None
    details: str | None = None
    recorded_on: date | None = None


class InjuryIn(Strict):
    athlete_id: Uuid
    body_part: Text
    injury_type: Text | None = None
    severity: Severity
    occurred_on: date
    context: InjuryContext | None = None
    status: InjuryStatus
    expected_return_on: date | None = None
    clinical_notes: str | None = None


class InjuryPatch(Patch):
    NULLABLE = frozenset({"injury_type", "context", "expected_return_on", "clinical_notes"})
    athlete_id: Uuid | None = None
    body_part: Text | None = None
    injury_type: Text | None = None
    severity: Severity | None = None
    occurred_on: date | None = None
    context: InjuryContext | None = None
    status: InjuryStatus | None = None
    expected_return_on: date | None = None
    clinical_notes: str | None = None


class AppointmentIn(Strict):
    athlete_id: Uuid
    practitioner_id: Uuid
    appointment_type: AppointmentType
    injury_id: Uuid | None = None
    scheduled_at: AwareDatetime
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    status: AppointmentStatus
    notes: str | None = None


class AppointmentPatch(Patch):
    NULLABLE = frozenset({"injury_id", "notes"})
    athlete_id: Uuid | None = None
    practitioner_id: Uuid | None = None
    appointment_type: AppointmentType | None = None
    injury_id: Uuid | None = None
    scheduled_at: AwareDatetime | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    status: AppointmentStatus | None = None
    notes: str | None = None


def dump(body: BaseModel, *, partial: bool = False) -> dict:
    """Python values (dates stay dates); a partial body keeps only the fields the caller sent."""
    return body.model_dump(exclude_unset=partial)
