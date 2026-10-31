"""Domain rules: statuses, scales, rubrics, criterion scores, levels and the progression."""

from datetime import UTC, datetime, timedelta

import pytest
from conftest import CRITERIA, SCALE
from eos_skill_progress.domain import rules
from eos_skill_progress.domain.rules import RuleViolationError, Scored

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def _code(fn, *args) -> str:
    with pytest.raises(RuleViolationError) as e:
        fn(*args)
    return e.value.code


# ---------------------------------------------------------------- statuses


@pytest.mark.parametrize(
    ("current", "new"), [("draft", "active"), ("draft", "archived"), ("active", "archived"), ("archived", "active")]
)
def test_framework_transitions_allowed(current, new):
    rules.check_transition(rules.FRAMEWORK_TRANSITIONS, current, new, "framework")


def test_framework_cannot_go_back_to_draft():
    assert _code(rules.check_transition, rules.FRAMEWORK_TRANSITIONS, "active", "draft", "x") == "invalid_transition"
    assert _code(rules.check_transition, rules.FRAMEWORK_TRANSITIONS, "archived", "draft", "x") == "invalid_transition"


def test_assessment_transitions():
    t = rules.ASSESSMENT_TRANSITIONS
    rules.check_transition(t, "submitted", "verified", "assessment")
    rules.check_transition(t, "submitted", "voided", "assessment")
    rules.check_transition(t, "verified", "voided", "assessment")
    assert _code(rules.check_transition, t, "verified", "submitted", "a") == "invalid_transition"
    assert _code(rules.check_transition, t, "voided", "verified", "a") == "invalid_transition"
    assert _code(rules.check_transition, t, "voided", "submitted", "a") == "invalid_transition"


# ---------------------------------------------------------------- scales


def test_valid_scales():
    rules.check_scale(SCALE)
    rules.check_scale({"type": "pass_fail", "levels": [_lv("fail", 0), _lv("pass", 1)]})
    rules.check_scale({"type": "discrete_stages", "levels": [_lv("a", 1), _lv("b", 2), _lv("c", 3)]})


def _lv(key: str, rank: int, min_score: float | None = None) -> dict:
    out = {"key": key, "label": key.title(), "rank": rank}
    if min_score is not None:
        out["min_score"] = min_score
    return out


@pytest.mark.parametrize(
    ("scale", "code"),
    [
        ({"type": "discrete_stages", "levels": []}, "no_levels"),
        ({"type": "numeric_range", "levels": [_lv("a", 1)]}, "range_required"),
        ({"type": "numeric_range", "min_score": 5, "max_score": 5, "levels": [_lv("a", 1)]}, "invalid_range"),
        ({"type": "pass_fail", "levels": [_lv("pass", 1)]}, "pass_fail_levels"),
        ({"type": "discrete_stages", "levels": [_lv("a", 1), _lv("a", 2)]}, "duplicate_level"),
        ({"type": "discrete_stages", "levels": [_lv("a", 1), _lv("b", 1)]}, "duplicate_level"),
        (
            {"type": "numeric_range", "min_score": 0, "max_score": 10, "levels": [_lv("a", 1, 11)]},
            "level_out_of_range",
        ),
        ({"type": "discrete_stages", "levels": [_lv("a", 1, 50), _lv("b", 2, 40)]}, "level_order"),
        ({"type": "discrete_stages", "min_score": float("nan"), "levels": [_lv("a", 1)]}, "invalid_number"),
    ],
)
def test_invalid_scales(scale, code):
    assert _code(rules.check_scale, scale) == code


# ---------------------------------------------------------------- rubrics


def test_valid_criteria():
    rules.check_criteria(CRITERIA)


@pytest.mark.parametrize(
    ("criteria", "code"),
    [
        ([], "no_criteria"),
        ([{"key": "a", "max_points": 5}, {"key": "a", "max_points": 5}], "duplicate_criterion"),
        ([{"key": "a", "weight": 0, "max_points": 5}], "invalid_weight"),
        ([{"key": "a", "max_points": 0}], "invalid_max_points"),
        ([{"key": "a", "max_points": 5, "levels": [_lv("x", 1, 6)]}], "level_out_of_range"),
    ],
)
def test_invalid_criteria(criteria, code):
    assert _code(rules.check_criteria, criteria) == code


def test_rubric_applies_to_its_skill_or_framework():
    assert rules.rubric_applies("s1", "f1", "s1", "f1")
    assert not rules.rubric_applies("s2", "f1", "s1", "f1")  # another skill's rubric, same framework
    assert rules.rubric_applies(None, "f1", "s1", "f1")
    assert not rules.rubric_applies(None, "f2", "s1", "f1")


# ---------------------------------------------------------------- scores and levels


def _scores(technique=8, expression=7, **extra):
    return [
        {"criterion_key": "technique", "points": technique},
        {"criterion_key": "expression", "points": expression, **extra},
    ]


def test_valid_criterion_scores():
    rules.check_criterion_scores(CRITERIA, _scores(level_key="strong"))
    rules.check_criterion_scores(CRITERIA, _scores(technique=0, expression=10))


@pytest.mark.parametrize(
    ("scores", "code"),
    [
        (_scores()[:1], "missing_score"),
        (_scores() + [{"criterion_key": "technique", "points": 1}], "duplicate_score"),
        (_scores() + [{"criterion_key": "timing", "points": 1}], "unknown_criterion"),
        (_scores(technique=11), "points_out_of_range"),
        (_scores(technique=-1), "points_out_of_range"),
        (_scores(level_key="excellent"), "unknown_level"),
    ],
)
def test_invalid_criterion_scores(scores, code):
    assert _code(rules.check_criterion_scores, CRITERIA, scores) == code


def test_level_by_key_or_label_and_score_consistency():
    assert rules.resolve_level(SCALE, 75, "Proficient")["key"] == "proficient"
    assert (
        rules.resolve_level(SCALE, 75, "developing")["label"] == "Developing"
    )  # a lower level is the evaluator's call
    assert _code(rules.resolve_level, SCALE, 65, "Proficient") == "level_score_mismatch"
    assert _code(rules.resolve_level, SCALE, 101, "Expert") == "score_out_of_range"
    assert _code(rules.resolve_level, SCALE, 50, "Master") == "unknown_level"
    open_scale = {"type": "discrete_stages", "levels": [_lv("a", 1)]}
    assert _code(rules.resolve_level, open_scale, -1, "a") == "score_out_of_range"


def test_dates_and_people():
    rules.not_in_future(T0, T0, "assessed_at")
    assert _code(rules.not_in_future, T0 + timedelta(seconds=1), T0, "assessed_at") == "in_future"
    assert _code(rules.not_self_assessment, "u1", "u1") == "self_assessment"


# ---------------------------------------------------------------- progression


def _a(i: int, skill: str, days: int, rank: int, top: bool = False) -> Scored:
    at = T0 + timedelta(days=days)
    return Scored(f"a{i}", skill, at, at, 10.0 * rank, f"L{rank}", rank, top)


def test_first_assessment_is_the_baseline_and_a_higher_rank_advances():
    steps = rules.progression(
        [_a(1, "s", 0, 2), _a(2, "s", 1, 2), _a(3, "s", 2, 3), _a(4, "s", 3, 1), _a(5, "s", 4, 3)]
    )
    kinds = [(s.kind, s.assessment.id) for s in steps if s.kind != rules.ASSESSMENT]
    assert kinds == [(rules.LEVEL_ADVANCED, "a3")]  # a5 only equals the best so far


def test_highest_level_is_a_milestone_once_per_skill_even_on_the_first_assessment():
    steps = rules.progression([_a(1, "s", 0, 4, top=True), _a(2, "s", 1, 4, top=True), _a(3, "t", 2, 1)])
    kinds = [(s.kind, s.assessment.id) for s in steps if s.kind != rules.ASSESSMENT]
    assert kinds == [(rules.MILESTONE, "a1")]


def test_progression_is_in_date_order_whatever_the_input_order_and_per_skill():
    steps = rules.progression([_a(2, "s", 5, 3, top=True), _a(1, "s", 0, 1), _a(3, "t", 1, 2)])
    assert [s.assessment.id for s in steps if s.kind == rules.ASSESSMENT] == ["a1", "a3", "a2"]
    assert [s.kind for s in steps][-2:] == [rules.LEVEL_ADVANCED, rules.MILESTONE]


def test_latest_per_skill_counts_evaluations():
    latest = rules.latest_per_skill([_a(1, "s", 0, 1), _a(2, "s", 2, 3), _a(3, "t", 1, 2)])
    assert latest["s"][0].id == "a2" and latest["s"][1] == 2
    assert latest["t"][0].id == "a3" and latest["t"][1] == 1
