"""Results of a course offering in an exam cycle (docs/prd.md FR-13 to FR-17, contracts/openapi.yaml), with no I/O.

State machine (decision D4): `computed` to `department_approved` to `approved` to `published`; a revision makes a new
`published` version and turns the previous one `superseded`; a recomputation replaces only `computed` results.

Rules this module settles, each one flagged for the owners in docs/reviewer-decisions.md section 17 because the PRD does
not state it:
- The weighted percentage is the sum of each component's `weightage_percent * final_marks / max_marks`, rounded to two
  places, half up. A component that was not sat (`absent`) adds nothing.
- A result passes when the weighted percentage reaches the scheme's `pass_percent`, every component that has a
  `pass_marks` reaches it (an absent component fails it), and the grading band is a pass band.
- The band of a percentage is the one whose range holds it; where ranges touch (0 to 40 and 40 to 50) the band with the
  higher minimum wins. No band holding the percentage is an error, never a guess.
- The grade point average is weighted by the credits of the course offerings; it is None when a credit is unknown."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from .errors import DomainRuleError
from .grading import Band

COMPUTED, DEPARTMENT_APPROVED, APPROVED, PUBLISHED, SUPERSEDED = (
    "computed",
    "department_approved",
    "approved",
    "published",
    "superseded",
)
RESULT_STATUSES = (COMPUTED, DEPARTMENT_APPROVED, APPROVED, PUBLISHED, SUPERSEDED)  # contract ResultStatus
PIPELINE = (COMPUTED, DEPARTMENT_APPROVED, APPROVED, PUBLISHED)
HUNDRED = Decimal(100)
PLACES = Decimal("0.01")


@dataclass(frozen=True)
class Component:
    """One component of the assessment scheme, with the marks a candidate got in it."""

    code: str
    weightage_percent: Decimal
    max_marks: Decimal
    pass_marks: Decimal | None
    final_marks: Decimal | None  # None when absent
    absent: bool = False


@dataclass(frozen=True)
class Outcome:
    components: list[dict]  # contract ComponentScore
    weighted_percent: Decimal
    grade: str
    grade_point: Decimal
    passed: bool


def _round(value: Decimal) -> Decimal:
    return value.quantize(PLACES, rounding=ROUND_HALF_UP)


def weighted_percent(components: Iterable[Component]) -> Decimal:
    total = Decimal(0)
    for c in components:
        if c.final_marks is not None and c.max_marks > 0:
            total += c.weightage_percent * c.final_marks / c.max_marks
    return _round(total)


def band_for(bands: Iterable[Band], percent: Decimal) -> Band:
    holding = [b for b in bands if b.min_percent <= percent <= b.max_percent]
    if not holding:
        raise DomainRuleError(
            "no_grading_band",
            f"no band of the grading scheme holds {percent}%",
            kind="unprocessable",
            details={"weighted_percent": float(percent)},
        )
    return max(holding, key=lambda b: b.min_percent)


def component_passed(c: Component) -> bool | None:
    """The contract's ComponentScore.passed: None when the component has no minimum."""
    if c.pass_marks is None:
        return None
    return c.final_marks is not None and c.final_marks >= c.pass_marks


def compute(components: list[Component], pass_percent: Decimal, bands: Iterable[Band]) -> Outcome:
    percent = weighted_percent(components)
    band = band_for(bands, percent)
    scores = [
        {
            "component_code": c.code,
            "final_marks": None if c.final_marks is None else float(c.final_marks),
            "max_marks": float(c.max_marks),
            "absent": c.absent,
            "passed": component_passed(c),
        }
        for c in components
    ]
    passed = percent >= pass_percent and band.is_pass and all(s["passed"] is not False for s in scores)
    return Outcome(scores, percent, band.grade, band.grade_point, passed)


def revise(
    previous: list[dict],
    corrections: object,
    scheme: Mapping[str, Component],
) -> list[Component]:
    """The result's components with the corrected final marks (ReviseResultRequest). `scheme` holds the scheme's
    components by code (with no marks); a code the result does not have is a 422, as are marks outside 0 and the
    component's maximum. A corrected component is no longer absent."""
    if not isinstance(corrections, list) or not corrections:
        raise DomainRuleError(
            "invalid_components", "components must be a non-empty list", kind="invalid", field="components"
        )
    fixed: dict[str, Decimal] = {}
    for i, item in enumerate(corrections):
        where = f"components[{i}]"
        if not isinstance(item, dict) or set(item) != {"component_code", "final_marks"}:
            raise DomainRuleError(
                "invalid_components", f"{where} needs component_code and final_marks only", kind="invalid", field=where
            )
        code = item["component_code"]
        marks = item["final_marks"]
        if not isinstance(code, str) or isinstance(marks, bool) or not isinstance(marks, int | float | str | Decimal):
            raise DomainRuleError("invalid_components", f"{where} is malformed", kind="invalid", field=where)
        try:
            value = Decimal(str(marks))
        except ArithmeticError:
            raise DomainRuleError(
                "invalid_components", f"{where}.final_marks must be a number", kind="invalid", field=where
            ) from None
        if code in fixed:
            raise DomainRuleError("duplicate_component", f"{code} appears twice", kind="invalid", field=where)
        if value != value.quantize(PLACES):
            raise DomainRuleError(
                "too_many_decimals", f"{where}.final_marks has at most two decimal places", kind="invalid", field=where
            )
        fixed[code] = value
    known = {p["component_code"] for p in previous}
    for code in fixed:
        if code not in known:
            raise DomainRuleError(
                "unknown_component", f"{code!r} is not a component of this result", kind="unprocessable"
            )
    components: list[Component] = []
    for p in previous:
        base = scheme[p["component_code"]]
        if p["component_code"] in fixed:
            value = fixed[p["component_code"]]
            if value < 0 or value > base.max_marks:
                raise DomainRuleError(
                    "marks_out_of_range",
                    f"{p['component_code']}: final_marks must be between 0 and {base.max_marks.normalize():f}",
                    kind="unprocessable",
                    details={"max_marks": float(base.max_marks)},
                )
            components.append(Component(base.code, base.weightage_percent, base.max_marks, base.pass_marks, value))
        else:
            kept = None if p["final_marks"] is None else Decimal(str(p["final_marks"]))
            components.append(
                Component(
                    base.code, base.weightage_percent, base.max_marks, base.pass_marks, kept, bool(p.get("absent"))
                )
            )
    return components


def grade_point_average(courses: Iterable[tuple[Decimal, Decimal | None]]) -> Decimal | None:
    """Credit-weighted average of (grade_point, credits); None when there are no courses, a credit is unknown or the
    credits add up to nothing."""
    total_points = Decimal(0)
    total_credits = Decimal(0)
    seen = False
    for point, credits in courses:
        seen = True
        if credits is None:
            return None
        total_points += point * credits
        total_credits += credits
    if not seen or total_credits == 0:
        return None
    return _round(total_points / total_credits)
