"""Domain models and rules for student-information."""

from __future__ import annotations

from .enums import DOCUMENT_TYPES, ID_CARD_STATUSES, PERSON_STATUSES, DocumentType, IdCardStatus, PersonStatus
from .rules import RuleViolationError, generate_card_number, validate_status_change

__all__ = [
    "DOCUMENT_TYPES",
    "ID_CARD_STATUSES",
    "PERSON_STATUSES",
    "DocumentType",
    "IdCardStatus",
    "PersonStatus",
    "RuleViolationError",
    "generate_card_number",
    "validate_status_change",
]
