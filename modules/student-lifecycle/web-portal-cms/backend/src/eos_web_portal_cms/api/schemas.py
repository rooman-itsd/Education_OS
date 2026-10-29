"""Request bodies from contracts/openapi.yaml. Responses are the service's dicts, already in contract shape. Bodies are
plain text: nothing here or in the service ever treats them as HTML."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator

PageType = Literal["standard", "landing", "terms"]
Slug = Annotated[str, Field(pattern=r"^[a-z0-9-]{1,120}$")]
Title = Annotated[str, Field(min_length=1, max_length=200, pattern=r"\S")]


class _Update(BaseModel):
    @model_validator(mode="after")
    def _something_changes(self):
        if not self.model_fields_set:
            raise ValueError("send at least one field to change")
        return self

    def changes(self) -> dict:
        """Only the fields sent; an explicit null clears an optional field."""
        return {name: getattr(self, name) for name in self.model_fields_set}


class PageInput(BaseModel):
    slug: Slug
    title: Title
    type: PageType
    body: str = Field(max_length=20000)
    seo_description: str | None = Field(default=None, max_length=300)


class PageUpdate(_Update):
    title: Title | None = None
    type: PageType | None = None
    body: str | None = Field(default=None, max_length=20000)
    seo_description: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _required_stay_set(self):
        for name in ("title", "type", "body"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class AnnouncementInput(BaseModel):
    title: Title
    body: str = Field(max_length=5000)
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None


class AnnouncementUpdate(_Update):
    title: Title | None = None
    body: str | None = Field(default=None, max_length=5000)
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def _required_stay_set(self):
        for name in ("title", "body"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class PublishInput(BaseModel):
    published: bool
