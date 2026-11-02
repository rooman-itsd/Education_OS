"""Request bodies, mirroring contracts/openapi.yaml components."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from typing import Annotated, ClassVar, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

PlanStatus = Literal["active", "draft", "completed", "archived"]
NewPlanStatus = Literal["active", "draft"]
SessionStatus = Literal["scheduled", "in_progress", "completed", "cancelled"]
Intensity = Literal["low", "medium", "high", "maximum"]
AnnotationCategory = Literal["technical", "tactical", "biomechanical", "praise", "note"]
# Ids are UUIDs (contracts/openapi.yaml `format: uuid`), kept as strings; "" or any other text is refused (422).
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
Uuid = Annotated[str, StringConstraints(pattern=UUID_PATTERN)]
# `format: uri`: an absolute URI (scheme://...), as platform/documents hands out; the file itself is not stored here.
Uri = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9+.-]*://\S+$", max_length=2000)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Text = Annotated[str, StringConstraints(max_length=10000)]


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


class PlanIn(Strict):
    title: Title
    description: Text | None = None
    coach_id: Uuid
    squad_id: Uuid | None = None
    start_date: date
    end_date: date
    status: NewPlanStatus = "active"
    objectives: list[Annotated[str, StringConstraints(max_length=500)]] | None = None


class PlanPatch(Patch):
    NULLABLE = frozenset({"description", "objectives"})
    title: Title | None = None
    description: Text | None = None
    coach_id: Uuid | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: PlanStatus | None = None
    objectives: list[Annotated[str, StringConstraints(max_length=500)]] | None = None


class SessionIn(Strict):
    plan_id: Uuid | None = None
    coach_id: Uuid
    title: Title
    description: Text | None = None
    facility_id: Uuid | None = None
    location: str | None = Field(default=None, max_length=200)
    scheduled_start: AwareDatetime
    scheduled_end: AwareDatetime
    attendee_ids: list[Uuid] | None = None
    drill_ids: list[Uuid] | None = None


class SessionPatch(Patch):
    NULLABLE = frozenset({"description", "facility_id", "location", "notes", "actual_duration_minutes"})
    title: Title | None = None
    description: Text | None = None
    facility_id: Uuid | None = None
    location: str | None = Field(default=None, max_length=200)
    scheduled_start: AwareDatetime | None = None
    scheduled_end: AwareDatetime | None = None
    actual_duration_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    status: SessionStatus | None = None
    attendee_ids: list[Uuid] | None = None
    drill_ids: list[Uuid] | None = None
    notes: Text | None = None


class DrillIn(Strict):
    code: str = Field(min_length=1, max_length=40)
    title: Title
    description: Text | None = None
    category: str = Field(min_length=1, max_length=80)
    intensity: Intensity
    target_focus: str | None = Field(default=None, max_length=300)
    equipment_needed: list[Annotated[str, StringConstraints(max_length=120)]] | None = None
    standard_duration_minutes: int | None = Field(default=None, ge=1, le=24 * 60)


class DrillPatch(Patch):
    NULLABLE = frozenset({"description", "target_focus", "equipment_needed", "standard_duration_minutes"})
    title: Title | None = None
    description: Text | None = None
    category: str | None = Field(default=None, min_length=1, max_length=80)
    intensity: Intensity | None = None
    target_focus: str | None = Field(default=None, max_length=300)
    equipment_needed: list[Annotated[str, StringConstraints(max_length=120)]] | None = None
    standard_duration_minutes: int | None = Field(default=None, ge=1, le=24 * 60)


class VideoIn(Strict):
    session_id: Uuid | None = None
    uploader_id: Uuid
    title: Title
    description: Text | None = None
    video_url: Uri
    thumbnail_url: Uri | None = None
    duration_seconds: float = Field(gt=0)
    resolution: str | None = Field(default=None, max_length=20)
    recorded_at: AwareDatetime

    _duration = field_validator("duration_seconds")(_finite)


class VideoPatch(Patch):
    NULLABLE = frozenset({"description", "thumbnail_url"})
    title: Title | None = None
    description: Text | None = None
    thumbnail_url: Uri | None = None


class AnnotationIn(Strict):
    author_id: Uuid
    start_timestamp: float
    end_timestamp: float | None = None
    content: Text = Field(min_length=1)
    category: AnnotationCategory = "technical"
    drawing_markup: dict | None = None
    tagged_athlete_ids: list[Uuid] | None = None

    _times = field_validator("start_timestamp", "end_timestamp")(_finite)


class AnnotationPatch(Patch):
    NULLABLE = frozenset({"end_timestamp", "drawing_markup"})
    start_timestamp: float | None = None
    end_timestamp: float | None = None
    content: Text | None = Field(default=None, min_length=1)
    category: AnnotationCategory | None = None
    drawing_markup: dict | None = None
    tagged_athlete_ids: list[Uuid] | None = None

    _times = field_validator("start_timestamp", "end_timestamp")(_finite)


class DrillTagIn(Strict):
    drill_id: Uuid
    start_timestamp: float
    end_timestamp: float
    notes: Text | None = None

    _times = field_validator("start_timestamp", "end_timestamp")(_finite)


def dump(body: BaseModel, *, partial: bool = False) -> dict:
    """Python values (dates stay dates, times become UTC); a partial body keeps only the fields the caller sent."""
    data = body.model_dump(exclude_unset=partial)
    return {k: v.astimezone(UTC) if isinstance(v, datetime) else v for k, v in data.items()}
