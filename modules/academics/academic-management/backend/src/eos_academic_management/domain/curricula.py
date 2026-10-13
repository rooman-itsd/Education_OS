"""Curricula (contract `Curriculum`, `CurriculumItem`; PRD FR-4, FR-5)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from .errors import DomainRuleError
from .values import require_choice, require_integer, require_number

CORE, ELECTIVE = "core", "elective"
CURRICULUM_CATEGORIES = (CORE, ELECTIVE)  # contract CurriculumCategory
DRAFT, PUBLISHED = "draft", "published"
CURRICULUM_STATUSES = (DRAFT, PUBLISHED)  # contract CurriculumStatus


@dataclass(frozen=True)
class CurriculumItem:
    course_id: str
    programme_term: int
    category: str
    credits: Decimal


def validate_item(
    *, course_id: str, programme_term: object, category: object, credits: object, duration_terms: object
) -> CurriculumItem:
    """Contract CurriculumItem: programme_term is a term number within the programme (1..duration_terms),
    category is core or elective, credits >= 0. duration_terms is the programme's (contract minimum 1)."""
    duration_terms = require_integer(duration_terms, "duration_terms", minimum=1)
    term = require_integer(programme_term, "programme_term", minimum=1)
    if term > duration_terms:
        raise DomainRuleError(
            "programme_term_out_of_range",
            f"programme_term must be between 1 and the programme's duration_terms ({duration_terms})",
            kind="invalid",
            field="programme_term",
        )
    return CurriculumItem(
        course_id=course_id,
        programme_term=term,
        category=require_choice(category, "category", CURRICULUM_CATEGORIES),
        credits=require_number(credits, "credits", minimum=0),
    )


def total_credits(items: Iterable[CurriculumItem]) -> Decimal:
    return sum((item.credits for item in items), Decimal(0))


def ensure_editable(status: str) -> None:
    """FR-4: published versions are immutable; a change means a new version (PUT /curricula/{id} answers 409)."""
    require_choice(status, "status", CURRICULUM_STATUSES)
    if status == PUBLISHED:
        raise DomainRuleError(
            "curriculum_published", "a published curriculum cannot change; create a new version", kind="conflict"
        )


def ensure_publishable(
    status: str, items: Iterable[CurriculumItem], *, credits_required: object, duration_terms: object
) -> None:
    """FR-5: publishing checks that the items' credits add up to the programme's credits_required (422 when they
    do not; 409 when the curriculum is already published).

    The programme's duration_terms and credits_required can change after items were entered
    (UpdateProgrammeRequest), and items can be built without validate_item, so every item is validated again
    against the programme as it is now, with the same rules and codes as validate_item. publishCurriculum
    declares 422, not 400, for a request that breaks a domain rule, so these failures are "unprocessable" and
    name the item in `field` (items[i].<field>).

    Every item counts, core and elective alike: the PRD does not distinguish them. How electives should count is
    an open question (docs/prd.md section 11, question 2)."""
    if status == PUBLISHED:
        raise DomainRuleError("curriculum_published", "this curriculum is already published", kind="conflict")
    require_choice(status, "status", CURRICULUM_STATUSES)
    terms = require_integer(duration_terms, "duration_terms", minimum=1)
    required = require_number(credits_required, "credits_required", minimum=0)
    checked = []
    for index, item in enumerate(items):
        try:
            checked.append(
                validate_item(
                    course_id=item.course_id,
                    programme_term=item.programme_term,
                    category=item.category,
                    credits=item.credits,
                    duration_terms=terms,
                )
            )
        except DomainRuleError as err:
            raise DomainRuleError(
                err.code, f"item {index}: {err.message}", kind="unprocessable", field=f"items[{index}].{err.field}"
            ) from err
    total = total_credits(checked)
    if total != required:
        raise DomainRuleError(
            "credits_mismatch",
            f"items add up to {total} credits but the programme requires {required}",
            kind="unprocessable",
        )


def next_version(existing_versions: Iterable[object]) -> int:
    """FR-4: curricula of a programme are numbered versions starting at 1 (contract `version`, minimum 1).
    Every entry of the history must be a positive integer; an invalid entry is an error, never skipped."""
    versions = [require_integer(v, "version", minimum=1) for v in existing_versions]
    return max(versions, default=0) + 1
