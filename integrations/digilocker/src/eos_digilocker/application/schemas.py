"""Typed, bounded input of every operation (contracts/ports/*.yaml). A pydantic failure becomes invalid_request;
the detail names the fields, never their values (they may be personal data)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

DOC_KINDS = (
    "degree",
    "provisional_degree",
    "diploma",
    "marksheet",
    "grade_card",
    "transcript",
    "migration_certificate",
    "transfer_certificate",
    "bonafide_certificate",
    "character_certificate",
    "other",
)
SAFE_ID = r"^[A-Za-z0-9._:-]{1,100}$"
CODE = r"^[A-Za-z0-9._-]{1,60}$"

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Scalar = str | int | bool | None | Annotated[float, Field(allow_inf_nan=False)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="ignore", str_max_length=2000)


class AccountLink(Strict):
    id: UUID
    person_id: UUID | None = None
    provider_subject: str | None = Field(default=None, max_length=100)


class Context(Strict):
    """What the hub passes to every operation (adapter.yaml, context)."""

    organisation_id: UUID
    connection_id: UUID
    provider: str = Field(default="digilocker", max_length=40)
    mode: Literal["mock", "sandbox", "live"]
    settings: dict = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict, repr=False)
    account_link: AccountLink | None = None
    delivery_id: UUID | None = None
    attempt: int = Field(default=1, ge=1, le=1000)
    idempotency_key: str | None = Field(default=None, max_length=200)
    deadline: datetime | None = None


class DocTypeSetting(Strict):
    doc_kind: Literal[DOC_KINDS]  # type: ignore[valid-type]
    doc_type: str = Field(pattern=CODE)
    search_fields: list[Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,39}$")]] = Field(
        default_factory=lambda: ["roll_number", "year"], min_length=1, max_length=8
    )
    send_pdf_on_uri_request: bool = False
    has_xml: bool = False


class ConnectionSettings(Strict):
    issuer_id: str = Field(pattern=CODE)
    doc_types: list[DocTypeSetting] = Field(default_factory=list, max_length=50)
    push_enabled: bool = False


class Holder(Strict):
    person_id: UUID
    name: Short
    date_of_birth: date | None = None
    gender: Literal["M", "F", "T"] | None = None
    mobile: str | None = Field(default=None, pattern=r"^\+[1-9][0-9]{7,14}$")
    wallet_account_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._-]{1,100}$")
    search_keys: dict[Annotated[str, StringConstraints(min_length=1, max_length=40)], str | int] = Field(
        min_length=1, max_length=8
    )

    @field_validator("search_keys")
    @classmethod
    def _bounded(cls, v: dict) -> dict:
        for value in v.values():
            if len(str(value)) > 100 or not str(value).strip():
                raise ValueError("search key values must be 1 to 100 characters")
        return v


class IssueInput(Strict):
    issuance_key: str = Field(pattern=SAFE_ID)
    doc_kind: Literal[DOC_KINDS]  # type: ignore[valid-type]
    provider_doc_type: str | None = Field(default=None, pattern=CODE)
    document_id: UUID
    document_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    document_number: str = Field(min_length=1, max_length=60)
    issued_on: date
    valid_from: date | None = None
    valid_to: date | None = None
    title: Short
    holder: Holder
    data: dict[Annotated[str, StringConstraints(min_length=1, max_length=60)], Scalar] | None = Field(
        default=None, max_length=60
    )

    @field_validator("data")
    @classmethod
    def _small(cls, v: dict | None) -> dict | None:
        if v and sum(len(str(x)) for x in v.values()) > 20_000:
            raise ValueError("data is too large")
        return v

    @field_validator("document_number")
    @classmethod
    def _printable(cls, v: str) -> str:
        if not v.strip() or any(ord(c) < 32 for c in v):
            raise ValueError("document_number must be printable")
        return v.strip()


class ReplaceInput(Strict):
    issuance_key: str = Field(pattern=SAFE_ID)
    document_id: UUID
    document_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    reason: Short
    data: dict[Annotated[str, StringConstraints(min_length=1, max_length=60)], Scalar] | None = Field(
        default=None, max_length=60
    )


class WithdrawInput(Strict):
    issuance_key: str = Field(pattern=SAFE_ID)
    reason: Short


class GetIssuanceInput(Strict):
    issuance_key: str = Field(pattern=SAFE_ID)


class FetchInput(Strict):
    account_link_id: UUID
    provider_uri: str | None = Field(default=None, min_length=1, max_length=300)
    lookup: dict[str, str] | None = Field(default=None, max_length=12)
    purpose: Literal["admission_verification", "record_verification"]


class ListHolderInput(Strict):
    account_link_id: UUID


class BeginAuthInput(Strict):
    state: str = Field(min_length=8, max_length=200)
    code_challenge: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")  # S256 only: base64url of a SHA-256
    redirect_uri: str = Field(min_length=8, max_length=500)
    scope_hint: list[Annotated[str, StringConstraints(pattern=CODE)]] = Field(default_factory=list, max_length=20)


class CompleteAuthInput(Strict):
    code: str = Field(min_length=1, max_length=500)
    code_verifier: str = Field(pattern=r"^[A-Za-z0-9._~-]{43,128}$")
    redirect_uri: str = Field(min_length=8, max_length=500)
