"""Pydantic schemas for selection-process API, matching contracts/openapi.yaml."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class Source(BaseModel):
    model_config = ConfigDict(extra="ignore")

    module: str
    entity: str
    id: str


class ProcessTypeInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., max_length=120)
    description: str | None = None


class ProcessType(ProcessTypeInput):
    id: str
    organisation_id: str
    process_count: int = 0
    created_at: str


class StageInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., max_length=120)
    sequence: int = Field(..., ge=1)
    description: str | None = None


class Stage(StageInput):
    id: str
    process_id: str


class PanelInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., max_length=120)
    stage_id: str | None = None
    member_person_ids: list[str] = Field(..., min_length=1)


class Panel(PanelInput):
    id: str
    process_id: str


class ProcessInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type_id: str
    title: str = Field(..., max_length=200)
    academic_year: str | None = None
    context: Source | None = None
    stages: list[StageInput] = Field(default_factory=list)


class ProcessUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = Field(default=None, max_length=200)
    academic_year: str | None = None


class Process(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    organisation_id: str
    type_id: str
    title: str
    academic_year: str | None = None
    context: dict[str, Any] | None = None
    status: Literal["draft", "open", "closed"]
    stages: list[Stage] = Field(default_factory=list)
    panels: list[Panel] = Field(default_factory=list)
    candidate_count: int = 0
    created_at: str
    updated_at: str


class ProcessPage(BaseModel):
    items: list[Process]
    total: int
    page: int
    page_size: int


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    outcome: Literal["advance", "hold", "reject"]
    score: float | None = None
    comments: str | None = None


class Decision(DecisionInput):
    id: str
    candidate_id: str
    stage_id: str
    panel_id: str | None = None
    decided_by: str
    decided_at: str


class CandidateInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    person_id: str
    source: Source | None = None


class Candidate(CandidateInput):
    id: str
    process_id: str
    organisation_id: str
    status: Literal["registered", "in_progress", "selected", "waitlisted", "rejected", "withdrawn"]
    current_stage_id: str | None = None
    decisions: list[Decision] = Field(default_factory=list)
    registered_at: str
    decided_at: str | None = None


class CandidatePage(BaseModel):
    items: list[Candidate]
    total: int
    page: int
    page_size: int


class FinalizeInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    outcome: Literal["selected", "waitlisted", "rejected"]
    comments: str | None = None


class ConflictError(BaseModel):
    code: str
    message: str

