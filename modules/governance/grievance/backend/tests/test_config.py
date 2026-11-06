"""GRIEVANCE_* settings (config/env.example): defaults, overrides and refused values."""

from pathlib import Path

import pytest
from eos_grievance.infrastructure import config


def test_the_env_example_sets_only_the_prefix_and_leaves_the_rest_empty(monkeypatch):
    example = Path(__file__).resolve().parents[2] / "config" / "env.example"
    values = dict(
        line.split("=", 1)
        for line in example.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    expected = {
        config.PREFIX_KEY,
        config.APPEAL_WINDOW_KEY,
        config.DAY_COUNTING_KEY,
        *(config.acknowledge_key(t) for t in ("student_grievance", "ragging", "sexual_harassment")),
        *(config.decide_key(t) for t in ("student_grievance", "ragging", "sexual_harassment")),
    }
    assert set(values) == expected
    for key in values:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(config.PREFIX_KEY, values[config.PREFIX_KEY])
    s = config.load_settings()
    assert s.case_number_prefix == "GRV"
    assert s.appeal_window_days is None and s.day_counting is None
    assert set(s.acknowledge_days.values()) == {None} and set(s.decide_days.values()) == {None}
    assert all(v == "" for k, v in values.items() if k != config.PREFIX_KEY)  # no legal value is shipped


def test_overrides_and_blank_means_not_set(monkeypatch):
    monkeypatch.setenv(config.acknowledge_key("ragging"), " 3 ")
    monkeypatch.setenv(config.decide_key("ragging"), "")
    monkeypatch.setenv(config.APPEAL_WINDOW_KEY, "30")
    monkeypatch.setenv(config.DAY_COUNTING_KEY, "Working")
    monkeypatch.setenv(config.PREFIX_KEY, "SG1")
    s = config.load_settings()
    assert s.acknowledge_days["ragging"] == 3 and s.decide_days["ragging"] is None
    assert s.appeal_window_days == 30 and s.day_counting == "working" and s.case_number_prefix == "SG1"


@pytest.mark.parametrize("value", ["soon", "0", "-3", "3651", "١٢", "1.5"])
def test_bad_day_values_are_deployment_errors(monkeypatch, value):
    for key in (config.APPEAL_WINDOW_KEY, config.acknowledge_key("ragging"), config.decide_key("sexual_harassment")):
        monkeypatch.setenv(key, value)
        with pytest.raises(ValueError, match=key):
            config.load_settings()
        monkeypatch.delenv(key)


@pytest.mark.parametrize(
    ("key", "value"),
    [(config.DAY_COUNTING_KEY, "fortnights"), (config.PREFIX_KEY, "TOO-LONG-PREFIX"), (config.PREFIX_KEY, "a b")],
)
def test_bad_choices_are_deployment_errors(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match=key):
        config.load_settings()
