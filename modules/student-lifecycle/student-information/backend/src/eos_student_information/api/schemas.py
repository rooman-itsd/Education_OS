"""Pydantic request and response schemas strictly mirroring contracts/openapi.yaml."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


def dump(body: BaseModel) -> dict:
    return body.model_dump(exclude_unset=True, by_alias=True)


PersonStatusType = Literal["pending", "active", "suspended", "graduated", "withdrawn", "alumnus"]
PersonDocumentTypeLiteral = Literal["identity_proof", "address_proof", "photograph", "prior_transcript", "other"]
IdentityCardStatusLiteral = Literal["issued", "revoked", "expired"]


class ContactDetails(Strict):
    email: str | None = None
    phone: str | None = None
    address: str | None = None


class Guardian(Strict):
    name: str = Field(min_length=1)
    relation: str = Field(min_length=1, description="e.g. parent, guardian, sponsor")
    phone: str | None = None
    email: str | None = None


class Source(Strict):
    module: str = Field(min_length=1)
    entity: str = Field(min_length=1)
    id: str = Field(min_length=1)


class PersonInput(Strict):
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    preferred_name: str | None = Field(default=None, max_length=120)
    date_of_birth: date | None = None
    gender: str | None = None
    identity_number: str | None = None
    contact: ContactDetails | None = None
    guardians: list[Guardian] | None = None
    identity_user_id: str | None = None
    source: Source | None = None


class PersonUpdate(Strict):
    first_name: str | None = Field(default=None, min_length=1, max_length=120)
    last_name: str | None = Field(default=None, min_length=1, max_length=120)
    preferred_name: str | None = Field(default=None, max_length=120)
    date_of_birth: date | None = None
    gender: str | None = None
    identity_number: str | None = None
    contact: ContactDetails | None = None
    guardians: list[Guardian] | None = None
    identity_user_id: str | None = None


class StatusChangeInput(Strict):
    status: PersonStatusType
    reason: str = Field(min_length=1)
    effective_date: date | None = None


class PersonDocumentInput(Strict):
    type: PersonDocumentTypeLiteral
    document_id: str = Field(min_length=1)
    label: str | None = None


class IdentityCardInput(Strict):
    expires_at: date | None = None


class RevokeCardInput(Strict):
    reason: str = Field(min_length=1)


class ConflictError(Strict):
    code: Literal["duplicate_identity_number", "active_card_exists", "card_not_active"]
    message: str


class RuleError(Strict):
    code: Literal["status_unchanged"]
    message: str


class Person(Strict):
    id: str
    organisation_id: str
    first_name: str
    last_name: str
    preferred_name: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    identity_number: str | None = None
    contact: ContactDetails | None = None
    guardians: list[Guardian] | None = None
    identity_user_id: str | None = None
    source: Source | None = None
    status: PersonStatusType
    status_effective_date: date | None = None
    created_at: str | None = None
    updated_at: str | None = None


class PersonPage(Strict):
    items: list[Person]
    total: int
    page: int
    page_size: int


class StatusHistoryEntry(Strict):
    id: str
    person_id: str
    organisation_id: str
    status: PersonStatusType
    reason: str
    effective_date: date
    changed_by: str
    changed_at: str | None = None


class PersonDocument(Strict):
    id: str
    person_id: str
    organisation_id: str
    type: PersonDocumentTypeLiteral
    document_id: str
    label: str | None = None
    uploaded_by: str
    uploaded_at: str | None = None


class IdentityCard(Strict):
    id: str
    person_id: str
    organisation_id: str
    card_number: str
    status: IdentityCardStatusLiteral
    expires_at: date | None = None
    document_id: str | None = None
    issued_by: str
    issued_at: str | None = None
    revoked_by: str | None = None
    revoked_at: str | None = None
    revoked_reason: str | None = None
