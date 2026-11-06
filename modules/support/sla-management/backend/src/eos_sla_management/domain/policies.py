"""SLA policies (PRD main flow 2): targets, escalation levels and which policy applies to a ticket."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

from .errors import DomainRuleError

PRIORITIES = ("low", "medium", "high", "urgent")
HOLD_REASONS = ("waiting_requester", "waiting_third_party", "waiting_internal")
DEFAULT_PAUSE_REASONS = ("waiting_requester", "waiting_third_party")
# The key that stands for "every category" in the one-active-policy-per-(priority, category) rule.
EVERY_CATEGORY = "*"


def category_key(category_id: str | None) -> str:
    return category_id or EVERY_CATEGORY


def check_targets(response_minutes: int, resolution_minutes: int) -> None:
    """422 when the resolution target is shorter than the response target."""
    if resolution_minutes < response_minutes:
        raise DomainRuleError(
            "resolution_before_response",
            "resolution_target_minutes must not be shorter than response_target_minutes",
            kind="invalid",
            field="resolution_target_minutes",
        )


def check_escalation_levels(levels: Sequence[dict], max_levels: int) -> None:
    """422 for more than max_levels levels, levels not numbered 1, 2, 3 in order, or a level that fires before the
    one above it."""
    if len(levels) > max_levels:
        raise DomainRuleError(
            "too_many_escalation_levels",
            f"a policy has at most {max_levels} escalation levels",
            kind="invalid",
            field="escalation_levels",
        )
    for expected, level in enumerate(levels, start=1):
        if level["level"] != expected:
            raise DomainRuleError(
                "escalation_levels_out_of_order",
                "escalation levels are numbered 1, 2, 3 in order",
                kind="invalid",
                field="escalation_levels",
            )
    times = [level["after_breach_minutes"] for level in levels]
    if times != sorted(times):
        raise DomainRuleError(
            "escalation_times_out_of_order",
            "a level fires no earlier than the level before it",
            kind="invalid",
            field="escalation_levels",
        )


class PolicyLike(Protocol):
    priority: str
    category_id: str | None
    active: bool


def choose[P: PolicyLike](policies: Iterable[P], priority: str, category_id: str | None) -> P | None:
    """The most specific active policy (PRD main flow 3): the one for this category and priority, else the one for
    this priority and every category, else none."""
    candidates = [p for p in policies if p.active and p.priority == priority]
    if category_id is not None:
        specific = next((p for p in candidates if p.category_id == category_id), None)
        if specific is not None:
            return specific
    return next((p for p in candidates if p.category_id is None), None)
