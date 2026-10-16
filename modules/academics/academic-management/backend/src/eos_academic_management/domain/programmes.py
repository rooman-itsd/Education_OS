"""Programmes (contract `Programme`; PRD FR-3)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .values import require_choice, require_integer, require_number

PROGRAMME_LEVELS = ("certificate", "diploma", "undergraduate", "postgraduate", "doctoral", "other")  # ProgrammeLevel
ACTIVE, ARCHIVED = "active", "archived"
PROGRAMME_STATUSES = (ACTIVE, ARCHIVED)  # contract ProgrammeStatus


@dataclass(frozen=True)
class ProgrammeShape:
    """The validated, rule-bearing fields of a programme. code, name and department_id are carried unchanged:
    the contract sets no constraint on them beyond being present."""

    level: str
    duration_terms: int
    credits_required: Decimal


def validate_programme(*, level: object, duration_terms: object, credits_required: object) -> ProgrammeShape:
    """FR-3 and contract CreateProgrammeRequest: level is a ProgrammeLevel, duration_terms >= 1,
    credits_required >= 0."""
    return ProgrammeShape(
        level=require_choice(level, "level", PROGRAMME_LEVELS),
        duration_terms=require_integer(duration_terms, "duration_terms", minimum=1),
        credits_required=require_number(credits_required, "credits_required", minimum=0),
    )


def archive(status: str) -> str:
    """POST /programmes/{id}/archive. The contract defines no conflict response for it, so archiving an
    archived programme is a no-op."""
    require_choice(status, "status", PROGRAMME_STATUSES)
    return ARCHIVED
