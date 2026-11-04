"""Grading schemes (contract `GradingScheme`, `GradingBand`; PRD 5.3, FR-3).

Open point, deliberately not decided here: the PRD says the bands "must cover 0 to 100 without gaps or overlaps" but
not whether a band's `max_percent` is inclusive, so whether bands such as 0 to 40 and 40 to 50 touch, or 0 to 39 and 40
to 49 are adjacent, is not defined. Only the rules that do not depend on that are enforced: each band is valid by itself,
the scheme has bands, and the bands lie within 0 to 100. The coverage rule waits for that decision
(docs/reviewer-decisions.md)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from .errors import DomainRuleError
from .values import require_bool, require_number, require_text

HUNDRED = Decimal(100)


@dataclass(frozen=True)
class Band:
    min_percent: Decimal
    max_percent: Decimal
    grade: str
    grade_point: Decimal
    is_pass: bool

    def __post_init__(self) -> None:
        if self.max_percent < self.min_percent:
            raise DomainRuleError(
                "invalid_band", "max_percent must not be below min_percent", kind="invalid", field="max_percent"
            )


def new_band(data: Mapping, index: int = 0) -> Band:
    """A band from a contract `GradingBand` object; every problem names the band's position."""
    where = f"bands[{index}]"
    if not isinstance(data, Mapping):
        raise DomainRuleError("invalid_band", f"{where} must be an object", kind="invalid", field=where)
    try:
        return Band(
            min_percent=require_number(data.get("min_percent"), "min_percent", minimum=0, maximum=HUNDRED),
            max_percent=require_number(data.get("max_percent"), "max_percent", minimum=0, maximum=HUNDRED),
            grade=require_text(data.get("grade"), "grade", max_length=20),
            grade_point=require_number(data.get("grade_point"), "grade_point", minimum=0),
            is_pass=require_bool(data.get("is_pass"), "is_pass"),
        )
    except DomainRuleError as err:
        err.field = f"{where}.{err.field}" if err.field else where
        raise


@dataclass(frozen=True)
class GradingScheme:
    name: str
    bands: tuple[Band, ...]
    is_default: bool = False

    def __post_init__(self) -> None:
        require_text(self.name, "name", max_length=200)
        if not self.bands:
            raise DomainRuleError("no_bands", "a grading scheme needs at least one band", kind="invalid", field="bands")
        grades = [b.grade for b in self.bands]
        if len(set(grades)) != len(grades):
            raise DomainRuleError("duplicate_grade", "a grade appears in two bands", kind="invalid", field="bands")


def new_scheme(name: object, bands: object, *, is_default: bool = False) -> GradingScheme:
    """A grading scheme from a contract `GradingSchemeInput`."""
    if not isinstance(bands, list):
        raise DomainRuleError("invalid_bands", "bands must be a list", kind="invalid", field="bands")
    return GradingScheme(
        name=require_text(name, "name", max_length=200),
        bands=tuple(new_band(b, i) for i, b in enumerate(bands)),
        is_default=is_default,
    )


def ensure_replaceable(*, in_use: bool) -> None:
    """FR-3: a scheme used by a cycle with published results cannot change; a new scheme is needed."""
    if in_use:
        raise DomainRuleError(
            "grading_scheme_in_use",
            "a grading scheme used by a cycle with published results cannot change; create a new one",
            kind="conflict",
        )


def plan_default(schemes: Iterable[tuple[str, bool]], chosen_id: str) -> list[str]:
    """FR-3: one scheme is the organisation default. Given (id, is_default) of the organisation's schemes, the ids whose
    default flag changes when `chosen_id` becomes the default: the previous default is cleared, the chosen one is set."""
    known = dict(schemes)
    if chosen_id not in known:
        raise DomainRuleError("grading_scheme_not_found", "grading scheme not found", kind="not_found")
    return [i for i, flag in known.items() if (i == chosen_id and not flag) or (i != chosen_id and flag)]
