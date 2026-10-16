"""Response bodies, mirroring contracts/openapi.yaml components. Types are strict so a drift between the use case
and the contract (a string for a number, a boolean for a count) fails validation instead of being coerced."""

from __future__ import annotations

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
