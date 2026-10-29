"""Domain rules, without HTTP or a database."""

from datetime import UTC, date, datetime

import pytest
from eos_athlete_performance.domain import rules
from eos_athlete_performance.domain.rules import BenchmarkView, RuleViolationError

NOW = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)


def test_not_in_future_accepts_now_and_refuses_later():
    rules.not_in_future(NOW, NOW, "recorded_at")
    rules.not_in_future(date(2026, 10, 29), NOW, "assessed_on")
    with pytest.raises(RuleViolationError) as e:
        rules.not_in_future(date(2026, 10, 30), NOW, "assessed_on")
    assert e.value.code == "in_future"


def test_athlete_disciplines_puts_primary_first_once():
    assert rules.athlete_disciplines("a", ["b", "a", "b"]) == ["a", "b"]
    assert rules.athlete_disciplines("a", None) == ["a"]


@pytest.mark.parametrize(("ids", "code"), [([], "no_metrics"), (["m", "m"], "duplicate_metric")])
def test_fitness_test_metrics(ids, code):
    with pytest.raises(RuleViolationError) as e:
        rules.check_metric_ids(ids)
    assert e.value.code == code


@pytest.mark.parametrize(
    ("measurements", "code"),
    [
        ([], "no_measurements"),
        ([{"metric_id": "x", "value": 1}], "metric_not_in_test"),
        ([{"metric_id": "a", "value": 1}, {"metric_id": "a", "value": 2}], "duplicate_measurement"),
    ],
)
def test_measurements_must_belong_to_the_test_once(measurements, code):
    with pytest.raises(RuleViolationError) as e:
        rules.check_measurements(["a", "b"], measurements)
    assert e.value.code == code


def test_gap_and_status_follow_the_metric_direction():
    assert rules.gap(11.0, 11.5, rules.LOWER) == pytest.approx(0.5)
    assert rules.comparison_status(11.0, 11.5, rules.LOWER) == "meets"
    assert rules.comparison_status(60.0, 65.0, rules.HIGHER) == "below"
    assert rules.comparison_status(65.0, 65.0, rules.HIGHER) == "meets"
    assert rules.comparison_status(None, 65.0, rules.HIGHER) == "no_result"


def test_trend():
    assert rules.trend([12.0], rules.LOWER, 1) == "no_data"
    assert rules.trend([12.0, 11.5], rules.LOWER, 1) == "improving"
    assert rules.trend([50.0, 45.0], rules.HIGHER, 1) == "declining"
    assert rules.trend([100.0, 100.5], rules.HIGHER, 1) == "steady"  # within 1 %


def test_best_benchmark_prefers_the_most_specific_applicable_one():
    general = BenchmarkView("g", "m", None, "state", None)
    any_gender = BenchmarkView("a", "m", "sprints", "state", "any")
    female = BenchmarkView("f", "m", "sprints", "state", "female")
    other_discipline = BenchmarkView("o", "m", "wrestling", "state", "female")
    national = BenchmarkView("n", "m", None, "national", None)
    candidates = [general, any_gender, female, other_discipline, national]
    assert rules.best_benchmark(candidates, ["sprints"], "female", "state") is female
    assert rules.best_benchmark(candidates, ["sprints"], "male", "state") is any_gender
    assert rules.best_benchmark(candidates, ["jumps"], "male", "state") is general
    assert rules.best_benchmark(candidates, ["jumps"], "male", "national") is national
    assert rules.best_benchmark(candidates, ["jumps"], "male", "district") is None
