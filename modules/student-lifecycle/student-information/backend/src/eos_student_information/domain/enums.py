"""Domain enums and status constants (contracts/openapi.yaml)."""

from __future__ import annotations

from enum import StrEnum


class PersonStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    GRADUATED = "graduated"
    WITHDRAWN = "withdrawn"
    ALUMNUS = "alumnus"


class DocumentType(StrEnum):
    IDENTITY_PROOF = "identity_proof"
    ADDRESS_PROOF = "address_proof"
    PHOTOGRAPH = "photograph"
    PRIOR_TRANSCRIPT = "prior_transcript"
    OTHER = "other"


class IdCardStatus(StrEnum):
    ISSUED = "issued"
    REVOKED = "revoked"
    EXPIRED = "expired"


PERSON_STATUSES: tuple[str, ...] = tuple(s.value for s in PersonStatus)
DOCUMENT_TYPES: tuple[str, ...] = tuple(d.value for d in DocumentType)
ID_CARD_STATUSES: tuple[str, ...] = tuple(c.value for c in IdCardStatus)
