"""Exam cycles (contract `ExamCycle`; PRD 5.1, section 6, FR-1): the configuration of one examination series and its
lifecycle.

The lifecycle is applied as section 6 states it: forward, one status at a time, `draft` to `scheduled` to `in_progress` to
`evaluation` to `results_published` to `closed`. The PRD does not say whether a cycle can be closed or moved back from
any other status, so those moves are refused rather than assumed (docs/reviewer-decisions.md)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from .errors import DomainRuleError
from .values import require_bool, require_choice, require_date, require_id, require_number, require_text

DRAFT, SCHEDULED, IN_PROGRESS, EVALUATION, RESULTS_PUBLISHED, CLOSED = (
    "draft",
    "scheduled",
    "in_progress",
    "evaluation",
    "results_published",
    "closed",
)
CYCLE_STATUSES = (
    DRAFT,
    SCHEDULED,
    IN_PROGRESS,
    EVALUATION,
    RESULTS_PUBLISHED,
    CLOSED,
)  # contract ExamCycleStatus, in order
CONFIGURABLE = (DRAFT, SCHEDULED)  # FR-1
CYCLE_TYPES = ("internal", "mid_term", "end_term", "supplementary")  # contract CycleType
HUNDRED = Decimal(100)


@dataclass(frozen=True)
class Cycle:
    id: str
    academic_period_id: str
    code: str
    name: str
    cycle_type: str
    starts_on: date
    ends_on: date
    grading_scheme_id: str
    eligibility_cutoff_date: date | None = None
    min_attendance_percent: Decimal | None = None
    check_dues: bool = False
    status: str = DRAFT

    def __post_init__(self) -> None:
        require_id(self.id, "id")
        require_id(self.academic_period_id, "academic_period_id")
        require_id(self.grading_scheme_id, "grading_scheme_id")
        require_text(self.code, "code", max_length=40)
        require_text(self.name, "name", max_length=200)
        require_choice(self.cycle_type, "cycle_type", CYCLE_TYPES)
        require_choice(self.status, "status", CYCLE_STATUSES)
        require_date(self.starts_on, "starts_on")
        require_date(self.ends_on, "ends_on")
        if self.ends_on < self.starts_on:
            raise DomainRuleError(
                "invalid_cycle_dates", "ends_on must not be before starts_on", kind="invalid", field="ends_on"
            )
        if self.eligibility_cutoff_date is not None:
            require_date(self.eligibility_cutoff_date, "eligibility_cutoff_date")
        if self.min_attendance_percent is not None and not 0 <= self.min_attendance_percent <= HUNDRED:
            raise DomainRuleError(
                "invalid_percent",
                "min_attendance_percent must be between 0 and 100",
                kind="invalid",
                field="min_attendance_percent",
            )
        require_bool(self.check_dues, "check_dues")


def new_cycle(cycle_id: str, data: Mapping, *, grading_scheme_id: str) -> Cycle:
    """A draft cycle from a contract `CreateExamCycleRequest`. The grading scheme is resolved by the caller (the one
    named in the request, else the organisation default); this module does not choose one."""
    percent = data.get("min_attendance_percent")
    return Cycle(
        id=cycle_id,
        academic_period_id=require_id(data.get("academic_period_id"), "academic_period_id"),
        code=require_text(data.get("code"), "code", max_length=40),
        name=require_text(data.get("name"), "name", max_length=200),
        cycle_type=require_choice(data.get("cycle_type"), "cycle_type", CYCLE_TYPES),
        starts_on=require_date(data.get("starts_on"), "starts_on"),
        ends_on=require_date(data.get("ends_on"), "ends_on"),
        grading_scheme_id=grading_scheme_id,
        eligibility_cutoff_date=(
            None
            if data.get("eligibility_cutoff_date") is None
            else require_date(data["eligibility_cutoff_date"], "eligibility_cutoff_date")
        ),
        min_attendance_percent=(
            None if percent is None else require_number(percent, "min_attendance_percent", minimum=0, maximum=HUNDRED)
        ),
        check_dues=require_bool(data.get("check_dues", False), "check_dues"),
    )


def ensure_configurable(cycle: Cycle) -> None:
    """FR-1: configuration (and what hangs on it: papers, sessions) can change while the cycle is `draft` or `scheduled`."""
    if cycle.status not in CONFIGURABLE:
        raise DomainRuleError(
            "cycle_not_configurable",
            f"a cycle can be changed while draft or scheduled, this one is {cycle.status}",
            kind="conflict",
            details={"status": cycle.status},
        )


def plan_status_change(cycle: Cycle, to_status: object, *, by_publication: bool = False) -> Cycle:
    """Section 6: the cycle after moving to `to_status`, which must be the next status. `results_published` is set by
    publication, not by a status change (contract changeExamCycleStatus), so it needs `by_publication`."""
    target = require_choice(to_status, "status", CYCLE_STATUSES)
    if target == RESULTS_PUBLISHED and not by_publication:
        raise DomainRuleError(
            "results_published_by_publication",
            "results_published is set by publishing results, not by a status change",
            kind="conflict",
        )
    index = CYCLE_STATUSES.index(cycle.status)
    expected = CYCLE_STATUSES[index + 1] if index + 1 < len(CYCLE_STATUSES) else None
    if target != expected:
        raise DomainRuleError(
            "invalid_status_transition",
            f"a {cycle.status} cycle can only move to {expected}"
            if expected
            else "a closed cycle cannot change status",
            kind="conflict",
            details={"from": cycle.status, "to": target, "allowed": expected},
        )
    return replace(cycle, status=target)
