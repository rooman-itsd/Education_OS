"""Domain rules of skill-progress (docs/prd.md). Pure functions over plain values: no framework, no database.

Scales, rubrics and scores are plain dicts shaped like the contract's ProficiencyScale, RubricCriterion and
CriterionScore. Nothing here knows which field (music, dance, clinical practice...) the institution trains."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

DISCRETE = "discrete_stages"
NUMERIC = "numeric_range"
PASS_FAIL = "pass_fail"

# Framework status: which status may follow which. An active framework is not sent back to draft once
# assessments may refer to it; an archived one can be brought back.
FRAMEWORK_TRANSITIONS = {
    "draft": frozenset({"active", "archived"}),
    "active": frozenset({"archived"}),
    "archived": frozenset({"active"}),
}
# Assessment status: submitted -> verified (assessment:approve), submitted | verified -> voided (assessment:delete).
ASSESSMENT_TRANSITIONS = {
    "submitted": frozenset({"verified", "voided"}),
    "verified": frozenset({"voided"}),
    "voided": frozenset(),
}
COUNTED = frozenset({"submitted", "verified"})  # statuses that count towards progress and the timeline

ASSESSMENT = "assessment"
LEVEL_ADVANCED = "level_advanced"
MILESTONE = "milestone_achieved"
# milestone_name of skill-progress.milestone.achieved for each kind of milestone
MILESTONE_NAMES = {LEVEL_ADVANCED: "level_advanced", MILESTONE: "highest_level_reached"}


class RuleViolationError(Exception):
    """A request the rules refuse. The API answers 400 with {code, message}."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _unique(values: Sequence, code: str, what: str) -> None:
    seen = set()
    for v in values:
        if v in seen:
            raise RuleViolationError(code, f"{what} {v!r} appears more than once")
        seen.add(v)


def _finite(value: float | None, what: str) -> None:
    if value is not None and not math.isfinite(value):
        raise RuleViolationError("invalid_number", f"{what} must be a finite number")


# ---------------------------------------------------------------- statuses


def check_transition(table: dict[str, frozenset[str]], current: str, new: str, what: str) -> None:
    if new != current and new not in table.get(current, frozenset()):
        raise RuleViolationError("invalid_transition", f"a {what} cannot go from {current} to {new}")


# ---------------------------------------------------------------- performance levels and scales


def check_levels(levels: Sequence[dict], what: str, low: float | None = None, high: float | None = None) -> None:
    """Keys, labels and ranks are unique; a level's min_score lies within [low, high] and grows with the rank."""
    _unique([lv["key"] for lv in levels], "duplicate_level", f"{what} level key")
    _unique([lv["label"] for lv in levels], "duplicate_level", f"{what} level label")
    _unique([lv["rank"] for lv in levels], "duplicate_level", f"{what} level rank")
    previous = None
    for lv in sorted(levels, key=lambda x: x["rank"]):
        m = lv.get("min_score")
        if m is None:
            continue
        _finite(m, "min_score")
        if (low is not None and m < low) or (high is not None and m > high):
            raise RuleViolationError("level_out_of_range", f"level {lv['key']!r} min_score {m} is outside the range")
        if previous is not None and m <= previous:
            raise RuleViolationError("level_order", "a higher-ranked level must need a higher min_score")
        previous = m


def check_scale(scale: dict) -> None:
    """A proficiency scale (ProficiencyScale): at least one level; pass/fail has exactly two; a numeric range has a
    min_score below its max_score, and every level's min_score lies within it."""
    levels = scale.get("levels") or []
    if not levels:
        raise RuleViolationError("no_levels", "a proficiency scale needs at least one level")
    low, high = scale.get("min_score"), scale.get("max_score")
    _finite(low, "min_score")
    _finite(high, "max_score")
    if scale["type"] == NUMERIC and (low is None or high is None):
        raise RuleViolationError("range_required", "a numeric_range scale needs min_score and max_score")
    if low is not None and high is not None and low >= high:
        raise RuleViolationError("invalid_range", "min_score must be below max_score")
    if scale["type"] == PASS_FAIL and len(levels) != 2:
        raise RuleViolationError("pass_fail_levels", "a pass_fail scale has exactly two levels")
    check_levels(levels, "scale", low, high)


def find_level(levels: Iterable[dict], value: str) -> dict | None:
    """The level whose key or label is `value` (keys first)."""
    levels = list(levels)
    return next((lv for lv in levels if lv["key"] == value), None) or next(
        (lv for lv in levels if lv["label"] == value), None
    )


def top_rank(levels: Iterable[dict]) -> int | None:
    ranks = [lv["rank"] for lv in levels]
    return max(ranks) if ranks else None


# ---------------------------------------------------------------- rubrics


def check_criteria(criteria: Sequence[dict]) -> None:
    """A rubric has at least one criterion; keys are unique; weight and max_points are positive; a criterion's
    levels follow the level rules with min_score within [0, max_points]."""
    if not criteria:
        raise RuleViolationError("no_criteria", "a rubric needs at least one criterion")
    _unique([c["key"] for c in criteria], "duplicate_criterion", "criterion key")
    for c in criteria:
        _finite(c.get("weight"), "weight")
        _finite(c["max_points"], "max_points")
        if c.get("weight", 1.0) <= 0:
            raise RuleViolationError("invalid_weight", f"criterion {c['key']!r} needs a weight above 0")
        if c["max_points"] <= 0:
            raise RuleViolationError("invalid_max_points", f"criterion {c['key']!r} needs max_points above 0")
        if c.get("levels"):
            check_levels(c["levels"], f"criterion {c['key']!r}", 0, c["max_points"])


def rubric_applies(
    rubric_skill_id: str | None, rubric_framework_id: str | None, skill_id: str, framework_id: str
) -> bool:
    """A rubric for a skill applies to that skill only; a rubric for a whole framework applies to its skills."""
    if rubric_skill_id is not None:
        return rubric_skill_id == skill_id
    return rubric_framework_id == framework_id


# ---------------------------------------------------------------- assessments


def check_criterion_scores(criteria: Sequence[dict], scores: Sequence[dict]) -> None:
    """Every criterion of the rubric is scored exactly once, with points between 0 and its max_points, and a
    level_key (if given) that is one of the criterion's levels."""
    by_key = {c["key"]: c for c in criteria}
    _unique([s["criterion_key"] for s in scores], "duplicate_score", "criterion")
    for s in scores:
        c = by_key.get(s["criterion_key"])
        if c is None:
            raise RuleViolationError("unknown_criterion", f"criterion {s['criterion_key']!r} is not in the rubric")
        _finite(s["points"], "points")
        if not 0 <= s["points"] <= c["max_points"]:
            raise RuleViolationError(
                "points_out_of_range", f"points for {c['key']!r} must be between 0 and {c['max_points']}"
            )
        if s.get("level_key") is not None and find_level(c.get("levels") or [], s["level_key"]) is None:
            raise RuleViolationError("unknown_level", f"level {s['level_key']!r} is not a level of {c['key']!r}")
    missing = sorted(set(by_key) - {s["criterion_key"] for s in scores})
    if missing:
        raise RuleViolationError("missing_score", f"criterion {missing[0]!r} is not scored")


def resolve_level(scale: dict, overall_score: float, level_achieved: str) -> dict:
    """The skill's level that level_achieved names (by key or label). The overall score lies within the scale's
    range and reaches the level's min_score, if it has one."""
    _finite(overall_score, "overall_score")
    low, high = scale.get("min_score"), scale.get("max_score")
    if (low is not None and overall_score < low) or (high is not None and overall_score > high):
        raise RuleViolationError("score_out_of_range", "overall_score is outside the skill's scale")
    if low is None and overall_score < 0:
        raise RuleViolationError("score_out_of_range", "overall_score cannot be negative")
    level = find_level(scale.get("levels") or [], level_achieved)
    if level is None:
        raise RuleViolationError("unknown_level", f"{level_achieved!r} is not a level of the skill's scale")
    if level.get("min_score") is not None and overall_score < level["min_score"]:
        raise RuleViolationError(
            "level_score_mismatch", f"level {level['label']!r} needs an overall_score of at least {level['min_score']}"
        )
    return level


def not_in_future(value: datetime, now: datetime, what: str) -> None:
    if value > now:
        raise RuleViolationError("in_future", f"{what} cannot be in the future")


def not_self_assessment(learner_id: str, evaluator_id: str, recorded_by: str) -> None:
    """Neither the named evaluator nor whoever records it may be the learner: a learner who also holds an evaluator
    role could otherwise name someone else as evaluator and put their own assessment on record."""
    if learner_id in (evaluator_id, recorded_by):
        raise RuleViolationError("self_assessment", "a learner cannot assess themselves")


# ---------------------------------------------------------------- progression


@dataclass(frozen=True)
class Scored:
    """One counted assessment, as the progression needs it."""

    id: str
    skill_id: str
    assessed_at: datetime
    order: datetime  # when it was recorded: breaks ties between assessments at the same time
    score: float
    level: str
    rank: int
    top: bool  # the level was the highest of the skill's scale when recorded


@dataclass(frozen=True)
class Step:
    kind: str  # ASSESSMENT, LEVEL_ADVANCED or MILESTONE
    assessment: Scored


def progression(assessments: Iterable[Scored]) -> list[Step]:
    """The learner's progression in date order. Every assessment is a step. Per skill, the first assessment sets
    the baseline; a later one whose level ranks above every earlier one advances the level; the first assessment at
    the scale's highest level (the first one included) achieves the milestone, once per skill (again only if the
    scale later gains a higher level and the learner reaches it)."""
    steps: list[Step] = []
    best: dict[str, int] = {}
    topped: dict[str, int] = {}  # skill -> rank of the highest level reached as a milestone
    for a in sorted(assessments, key=lambda x: (x.assessed_at, x.order, x.id)):
        steps.append(Step(ASSESSMENT, a))
        if a.skill_id in best and a.rank > best[a.skill_id]:
            steps.append(Step(LEVEL_ADVANCED, a))
        if a.top and a.rank > topped.get(a.skill_id, a.rank - 1):
            steps.append(Step(MILESTONE, a))
            topped[a.skill_id] = a.rank
        best[a.skill_id] = max(best.get(a.skill_id, a.rank), a.rank)
    return steps


def latest_per_skill(assessments: Iterable[Scored]) -> dict[str, tuple[Scored, int]]:
    """skill id -> (its latest assessment, how many there are)."""
    out: dict[str, tuple[Scored, int]] = {}
    for a in sorted(assessments, key=lambda x: (x.assessed_at, x.order, x.id)):
        count = out[a.skill_id][1] + 1 if a.skill_id in out else 1
        out[a.skill_id] = (a, count)
    return out
