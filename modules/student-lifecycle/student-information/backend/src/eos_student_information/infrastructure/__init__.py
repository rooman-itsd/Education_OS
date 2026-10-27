"""Infrastructure models and database mappings for student-information."""

from __future__ import annotations

from .models import MODELS, PREFIX, TABLES, IdentityCard, Person, PersonDocument, StatusHistoryEntry

__all__ = [
    "MODELS",
    "PREFIX",
    "TABLES",
    "IdentityCard",
    "Person",
    "PersonDocument",
    "StatusHistoryEntry",
]
