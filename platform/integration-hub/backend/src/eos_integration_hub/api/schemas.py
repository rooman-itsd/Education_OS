"""Request bodies of contracts/openapi.yaml. Every string and number is bounded; unknown fields are ignored. Enumerated
values that carry a contract error code (mode, adapter, provider) are checked by the use case, so the caller gets
`invalid_mode` rather than a generic validation error."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from ..domain.vocabulary import (
    MAX_CREDENTIAL_VALUE,
    MAX_DISPLAY_NAME,
    MAX_PURPOSE,
    MAX_REASON,
    MAX_URL,
)

PortId = Literal[
    "certificate-issuance",
    "academic-records",
    "regulatory-submission",
    "meetings",
    "wearable-data",
    "inter-institution-records",
]


class ConnectionIn(BaseModel):
    adapter: str = Field(min_length=1, max_length=64)
    provider: str = Field(min_length=1, max_length=64)
    port: PortId
    mode: str = Field(min_length=1, max_length=10)
    display_name: str | None = Field(default=None, max_length=MAX_DISPLAY_NAME)
    settings: dict | None = None


class ConnectionUpdateIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=MAX_DISPLAY_NAME)
    settings: dict | None = None


class CredentialIn(BaseModel):
    value: str = Field(min_length=1, max_length=MAX_CREDENTIAL_VALUE)
    expires_at: datetime | None = None

    def __repr__(self) -> str:  # never print the value
        return "CredentialIn(<value hidden>)"

    __str__ = __repr__


class ModeIn(BaseModel):
    mode: str = Field(min_length=1, max_length=10)
    confirm_live: bool = False


class AuthoriseIn(BaseModel):
    return_url: str | None = Field(default=None, max_length=MAX_URL)


class DisableIn(BaseModel):
    reason: str | None = Field(default=None, max_length=MAX_REASON)


class AccountLinkIn(BaseModel):
    port: PortId
    provider: str = Field(min_length=1, max_length=64)
    purpose: str | None = Field(default=None, max_length=MAX_PURPOSE)
    return_url: str | None = Field(default=None, max_length=MAX_URL)


class RevokeIn(BaseModel):
    reason: str = Field(min_length=3, max_length=MAX_REASON)
