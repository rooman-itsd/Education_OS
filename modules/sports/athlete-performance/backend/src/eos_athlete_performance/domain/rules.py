"""Domain rules of athlete-performance (docs/prd.md). Pure functions over plain values: no framework, no database."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

HIGHER = "higher_is_better"
LOWER = "lower_is_better"
# Athlete fields whose change publishes athlete-performance.athlete.updated (contracts/events.yaml).
TRACKED_ATHLETE_FIELDS = frozenset(
    {"primary_discipline_id", "discipline_ids", "coach_id", "squad", "status", "user_id"}
)


class RuleViolationError(Exception):
    """A request the rules refuse. The API answers 400 with {code, message}."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def not_in_future(value: date | datetime, now: datetime, what: str) -> None:
    """A date may be one day ahead of today in UTC: it is already that day in timezones east of UTC (IST until 05:30)."""
    later = value > now if isinstance(value, datetime) else value > (now + timedelta(days=1)).date()
    if later:
        raise RuleViolationError("in_future", f"{what} cannot be in the future")


def athlete_disciplines(primary: str, others: Iterable[str] | None) -> list[str]:
    """The primary discipline first, then the others once each."""
    out = [primary]
    for d in others or []:
        if d not in out:
            out.append(d)
    return out


def check_metric_ids(metric_ids: Sequence[str]) -> None:
    if not metric_ids:
        raise RuleViolationError("no_metrics", "a fitness test needs at least one metric")
    if len(set(metric_ids)) != len(metric_ids):
        raise RuleViolationError("duplicate_metric", "a metric appears more than once in the fitness test")


def check_measurements(test_metric_ids: Sequence[str], measurements: Sequence[dict]) -> None:
    """Each measurement is for a metric of the test, at most once."""
    if not measurements:
        raise RuleViolationError("no_measurements", "an assessment needs at least one measurement")
    seen: set[str] = set()
    for m in measurements:
        if m["metric_id"] not in test_metric_ids:
            raise RuleViolationError("metric_not_in_test", f"metric {m['metric_id']} is not part of this fitness test")
        if m["metric_id"] in seen:
            raise RuleViolationError("duplicate_measurement", f"metric {m['metric_id']} is measured more than once")
        seen.add(m["metric_id"])


def gap(latest: float, target: float, direction: str) -> float:
    """Distance to the target, positive when the target is met or beaten."""
    return latest - target if direction == HIGHER else target - latest


def comparison_status(latest: float | None, target: float, direction: str) -> str:
    if latest is None:
        return "no_result"
    return "meets" if gap(latest, target, direction) >= 0 else "below"


def trend(values: Sequence[float], direction: str, steady_percent: float) -> str:
    """Latest value against the one before it. A change within steady_percent of the earlier value is steady."""
    if len(values) < 2:
        return "no_data"
    previous, latest = values[-2], values[-1]
    if abs(latest - previous) <= abs(previous) * steady_percent / 100:
        return "steady"
    return "improving" if gap(latest, previous, direction) > 0 else "declining"


@dataclass(frozen=True)
class BenchmarkView:
    id: str
    metric_id: str
    discipline_id: str | None
    level: str
    gender: str | None


def applies_to(b: BenchmarkView, disciplines: Iterable[str], gender: str | None) -> bool:
    """A benchmark applies to an athlete when its discipline (if any) is one of theirs and its gender (if any) is
    theirs or 'any'. Age groups are shown but not matched: the athlete's age group is the institution's call."""
    if b.discipline_id and b.discipline_id not in set(disciplines):
        return False
    return b.gender in (None, "any") or b.gender == gender


def best_benchmark(
    candidates: Iterable[BenchmarkView], disciplines: Sequence[str], gender: str | None, level: str | None = None
) -> BenchmarkView | None:
    """The most specific applicable benchmark: a discipline match beats none, a gender match beats 'any'.
    Among equals the most recently created wins (candidates come oldest first)."""
    best, best_score = None, -1
    for b in candidates:
        if level is not None and b.level != level:
            continue
        if not applies_to(b, disciplines, gender):
            continue
        score = (2 if b.discipline_id else 0) + (1 if b.gender not in (None, "any") else 0)
        if score >= best_score:
            best, best_score = b, score
    return best


def changed(before: dict, after: dict) -> list[str]:
    return sorted(k for k in after if before.get(k) != after[k])
