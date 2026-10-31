"""Request bodies, mirroring contracts/openapi.yaml components. Shape errors (a wrong type, a missing field, an
unknown field, an id that is not a UUID, a time without its offset) are 422; the contract's written rules (usage
window, space of the facility, slot order, period length, at least one field) are checked by the service (400)."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

FacilityType = Literal["ground", "court", "pool", "gym", "track", "hall", "range", "other"]
Status = Literal["operational", "limited", "closed", "under_maintenance"]
Purpose = Literal["training", "competition", "physical_education", "recreation", "event", "maintenance"]
# Ids are UUIDs (contracts/openapi.yaml `format: uuid`), kept as strings; "" or any other text is refused (422).
Uuid = Annotated[
    str, StringConstraints(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
]
HHMM = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Sport = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


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


class FacilityIn(Strict):
    name: Annotated[Name, Field(max_length=200)]
    facility_type: FacilityType
    sports: list[Sport]
    surface: str | None = Field(default=None, max_length=120)
    indoor: bool
    capacity: int | None = Field(default=None, ge=1)
    location: str | None = Field(default=None, max_length=300)
    description: str | None = None


class FacilityPatch(Patch):
    NULLABLE = frozenset({"surface", "capacity", "location", "description"})
    name: Annotated[Name, Field(max_length=200)] | None = None
    facility_type: FacilityType | None = None
    sports: list[Sport] | None = None
    surface: str | None = Field(default=None, max_length=120)
    indoor: bool | None = None
    capacity: int | None = Field(default=None, ge=1)
    location: str | None = Field(default=None, max_length=300)
    description: str | None = None


class SpaceIn(Strict):
    name: Annotated[Name, Field(max_length=120)]
    capacity: int | None = Field(default=None, ge=1)
    sports: list[Sport] = Field(default_factory=list)
    active: bool = True


class SpacePatch(Patch):
    NULLABLE = frozenset({"capacity"})
    name: Annotated[Name, Field(max_length=120)] | None = None
    capacity: int | None = Field(default=None, ge=1)
    sports: list[Sport] | None = None
    active: bool | None = None


class UsageIn(Strict):
    facility_id: Uuid
    space_id: Uuid | None = None
    used_from: AwareDatetime
    used_to: AwareDatetime
    purpose: Purpose
    group_name: str | None = Field(default=None, max_length=200)
    headcount: int | None = Field(default=None, ge=1)
    booking_reference: str | None = Field(default=None, max_length=100)


class SlotIn(Strict):
    day_of_week: int = Field(ge=0, le=6)
    opens_at: str = Field(pattern=HHMM)
    closes_at: str = Field(pattern=HHMM)


class OperatingHoursIn(Strict):
    slots: list[SlotIn]


class StatusIn(Strict):
    status: Status
    reason: str | None = Field(default=None, max_length=500)
    until: AwareDatetime | None = None


def dump(body: BaseModel, *, partial: bool = False) -> dict:
    """Python values (datetimes stay datetimes); a partial body keeps only the fields the caller sent."""
    return body.model_dump(exclude_unset=partial)
