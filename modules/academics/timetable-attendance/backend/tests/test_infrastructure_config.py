"""The TIMETABLE_ATTENDANCE_* settings of config/env.example."""

from pathlib import Path

import pytest
from eos_timetable_attendance.infrastructure import config as cfg

KEYS = (
    cfg.MARKING_OPENS_BEFORE_MINUTES_KEY,
    cfg.MARKING_WINDOW_HOURS_KEY,
    cfg.CORRECTION_WINDOW_DAYS_KEY,
    cfg.SHORTAGE_THRESHOLD_PERCENT_KEY,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)


def test_defaults_are_the_documented_values():
    s = cfg.load_settings()
    assert (s.marking_opens_before_minutes, s.marking_window_hours, s.correction_window_days) == (15, 24, 7)
    assert s.shortage_threshold_percent == 75
    assert (s.policy.marking_window_hours, s.policy.shortage_threshold_percent) == (24, 75)


def test_the_four_keys_are_the_ones_in_env_example_and_prefixed():
    text = (Path(__file__).resolve().parents[2] / "config" / "env.example").read_text(encoding="utf-8")
    documented = {line.split("=")[0] for line in text.splitlines() if line.startswith("TIMETABLE_ATTENDANCE_")}
    assert documented == set(KEYS)
    for key, default in zip(
        KEYS,
        (
            cfg.DEFAULT_MARKING_OPENS_BEFORE_MINUTES,
            cfg.DEFAULT_MARKING_WINDOW_HOURS,
            cfg.DEFAULT_CORRECTION_WINDOW_DAYS,
            cfg.DEFAULT_SHORTAGE_THRESHOLD_PERCENT,
        ),
        strict=True,
    ):
        assert f"{key}={default}" in text.splitlines()


def test_values_are_read_on_every_call(monkeypatch):
    monkeypatch.setenv(cfg.MARKING_WINDOW_HOURS_KEY, " 48 ")
    monkeypatch.setenv(cfg.SHORTAGE_THRESHOLD_PERCENT_KEY, "80")
    assert (cfg.load_settings().marking_window_hours, cfg.load_settings().shortage_threshold_percent) == (48, 80)
    monkeypatch.setenv(cfg.MARKING_WINDOW_HOURS_KEY, "")
    assert cfg.load_settings().marking_window_hours == 24  # blank means the default


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (cfg.MARKING_WINDOW_HOURS_KEY, "soon"),
        (cfg.CORRECTION_WINDOW_DAYS_KEY, "1.5"),
        (cfg.MARKING_OPENS_BEFORE_MINUTES_KEY, "-1"),
        (cfg.SHORTAGE_THRESHOLD_PERCENT_KEY, "101"),
        (cfg.SHORTAGE_THRESHOLD_PERCENT_KEY, "-5"),
    ],
)
def test_a_bad_value_is_a_deployment_error_not_a_request_error(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        cfg.load_settings()
