"""REGULATORY_REPORTS_* settings (config/env.example): defaults, overrides and refused values."""

from pathlib import Path

import pytest
from eos_regulatory_reports.infrastructure import config


def test_defaults_are_the_env_example_values(monkeypatch):
    example = Path(__file__).resolve().parents[2] / "config" / "env.example"
    values = dict(
        line.split("=", 1)
        for line in example.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    for key in values:
        monkeypatch.delenv(key, raising=False)
    s = config.load_settings()
    assert s.due_soon_days == int(values[config.DUE_SOON_DAYS_KEY])
    assert s.calendar_max_days == int(values[config.CALENDAR_MAX_DAYS_KEY])


def test_overrides(monkeypatch):
    monkeypatch.setenv(config.DUE_SOON_DAYS_KEY, " 14 ")
    assert config.load_settings().due_soon_days == 14


@pytest.mark.parametrize("value", ["soon", "0", "-3", "100000"])
def test_bad_values_are_deployment_errors(monkeypatch, value):
    monkeypatch.setenv(config.DUE_SOON_DAYS_KEY, value)
    with pytest.raises(ValueError, match=config.DUE_SOON_DAYS_KEY):
        config.load_settings()
