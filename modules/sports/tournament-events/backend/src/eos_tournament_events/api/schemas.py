"""Request bodies, mirroring contracts/openapi.yaml components."""

from __future__ import annotations

import math
from datetime import date
from typing import Annotated, ClassVar, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

TournamentStatus = Literal["draft", "published", "ongoing", "completed", "cancelled"]
Level = Literal["intra_institution", "inter_university", "state", "national", "international"]
Format = Literal["knockout", "league", "round_robin", "heats_and_finals", "other"]
Hosting = Literal["home", "away", "neutral"]
EntryStatus = Literal["pending", "confirmed", "withdrawn"]
FixtureStatus = Literal["scheduled", "in_progress", "completed", "postponed", "cancelled"]
OfficialRole = Literal["referee", "umpire", "judge", "timekeeper", "technical_official", "team_manager"]
TravelMode = Literal["bus", "train", "flight", "own", "none"]
# Ids are UUIDs (contracts/openapi.yaml `format: uuid`), kept as strings; "" or any other text is refused (422).
Uuid = Annotated[
    str, StringConstraints(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
]
Text = Annotated[str, StringConstraints(min_length=1, max_length=5000)]


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


class AtLeastOne(Patch):
    """contracts/openapi.yaml `minProperties: 1`."""

    @model_validator(mode="after")
    def not_empty(self):
        if not self.model_fields_set:
            raise ValueError("send at least one field")
        return self


class TournamentIn(Strict):
    name: str = Field(min_length=1, max_length=200)
    discipline: str = Field(min_length=1, max_length=120)
    discipline_id: Uuid | None = None
    level: Level
    format: Format
    start_date: date
    end_date: date
    venue: str | None = Field(default=None, max_length=300)
    hosting: Hosting | None = None
    registration_closes_on: date | None = None
    description: str | None = Field(default=None, max_length=5000)


class TournamentPatch(Patch):
    NULLABLE = frozenset({"discipline_id", "venue", "hosting", "registration_closes_on", "description"})
    name: str | None = Field(default=None, min_length=1, max_length=200)
    discipline: str | None = Field(default=None, min_length=1, max_length=120)
    discipline_id: Uuid | None = None
    level: Level | None = None
    format: Format | None = None
    start_date: date | None = None
    end_date: date | None = None
    venue: str | None = Field(default=None, max_length=300)
    hosting: Hosting | None = None
    registration_closes_on: date | None = None
    description: str | None = Field(default=None, max_length=5000)


class CancelIn(Strict):
    reason: Text


class EntryIn(Strict):
    category: str = Field(min_length=1, max_length=120)
    team_name: str | None = Field(default=None, max_length=200)
    athlete_ids: list[Uuid]
    status: EntryStatus


class EntryPatch(AtLeastOne):
    NULLABLE = frozenset({"team_name"})
    team_name: str | None = Field(default=None, max_length=200)
    athlete_ids: list[Uuid] | None = None
    status: EntryStatus | None = None


class FixtureIn(Strict):
    round: str = Field(min_length=1, max_length=120)
    category: str | None = Field(default=None, max_length=120)
    entry_ids: list[Uuid]
    scheduled_at: AwareDatetime
    venue: str | None = Field(default=None, max_length=300)
    status: FixtureStatus


class FixturePatch(AtLeastOne):
    NULLABLE = frozenset({"category", "venue"})
    round: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, max_length=120)
    entry_ids: list[Uuid] | None = None
    scheduled_at: AwareDatetime | None = None
    venue: str | None = Field(default=None, max_length=300)
    status: FixtureStatus | None = None


class OfficialIn(Strict):
    name: str = Field(min_length=1, max_length=200)
    user_id: Uuid | None = None
    official_role: OfficialRole
    fixture_id: Uuid | None = None
    confirmed: bool = False


class PlacingIn(Strict):
    entry_id: Uuid
    position: int | None = None
    score: str | None = Field(default=None, max_length=60)
    mark: float | None = None
    unit: str | None = Field(default=None, max_length=20)

    @field_validator("mark")
    @classmethod
    def _finite(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("must be a finite number")
        return value


class ResultIn(Strict):
    placings: list[PlacingIn]
    notes: str | None = Field(default=None, max_length=5000)


class LogisticsIn(Strict):
    travel_mode: TravelMode | None = None
    departure_at: AwareDatetime | None = None
    return_at: AwareDatetime | None = None
    accommodation: str | None = Field(default=None, max_length=2000)
    travelling_count: int | None = None
    contact_person_id: Uuid | None = None
    notes: str | None = Field(default=None, max_length=5000)


def dump(body: BaseModel, *, partial: bool = False) -> dict:
    """Python values (dates stay dates); a partial body keeps only the fields the caller sent."""
    data = body.model_dump(exclude_unset=partial)
    if "placings" in data:
        data["placings"] = [dict(p) for p in data["placings"]]
    return data
