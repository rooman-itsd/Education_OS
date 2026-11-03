"""Pydantic schemas for portfolio API, matching contracts/openapi.yaml."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ItemTypeInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., max_length=120)
    description: str | None = None
    requires_review: bool = True
    reviewer_person_ids: list[str] = Field(default_factory=list)


class ItemTypePatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, max_length=120)
    description: str | None = None
    requires_review: bool | None = None
    reviewer_person_ids: list[str] | None = None

    @model_validator(mode="before")
    @classmethod
    def check_non_nullable(cls, data):
        if not isinstance(data, dict):
            return data
        if "name" in data and (data["name"] is None or (isinstance(data["name"], str) and not data["name"].strip())):
            raise ValueError("name cannot be null or empty")
        if "requires_review" in data and data["requires_review"] is None:
            raise ValueError("requires_review cannot be null")
        return data


class ItemType(ItemTypeInput):
    id: str
    organisation_id: str
    item_count: int = 0
    created_at: str


class ItemMediaInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_id: str
    caption: str | None = None
    sort_order: int = 0


class ItemMedia(ItemMediaInput):
    id: str
    item_id: str
    uploaded_by: str
    uploaded_at: str


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    decision: Literal["approved", "changes_requested"]
    score: float | None = None
    comments: str | None = None


class Review(ReviewInput):
    id: str
    item_id: str
    organisation_id: str
    reviewer_person_id: str
    reviewed_at: str


class ItemInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type_id: str
    title: str = Field(..., max_length=200)
    owner_person_id: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, str] = Field(default_factory=dict)


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type_id: str | None = None
    title: str | None = Field(default=None, max_length=200)
    owner_person_id: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    attributes: dict[str, str] | None = None

    @model_validator(mode="before")
    @classmethod
    def check_non_nullable(cls, data):
        if not isinstance(data, dict):
            return data
        if "type_id" in data and data["type_id"] is None:
            raise ValueError("type_id cannot be null")
        if "title" in data and (
            data["title"] is None or (isinstance(data["title"], str) and not data["title"].strip())
        ):
            raise ValueError("title cannot be null or empty")
        return data


class Item(ItemInput):
    id: str
    organisation_id: str
    status: str
    media: list[ItemMedia] = Field(default_factory=list)
    reviews: list[Review] = Field(default_factory=list)
    submitted_at: str | None = None
    decided_at: str | None = None
    created_at: str
    updated_at: str
    can: list[str] = Field(default_factory=list)


class ItemPage(BaseModel):
    items: list[Item]
    total: int
    page: int
    page_size: int


class ConflictError(BaseModel):
    code: str
    message: str


class RuleError(BaseModel):
    code: str
    message: str
