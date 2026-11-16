"""RTI_* settings (config/env.example): defaults, overrides and refused values."""

from pathlib import Path

import pytest
from eos_rti.infrastructure import config


def test_defaults_are_the_env_example_values_and_the_timelines_are_empty(monkeypatch):
    example = Path(__file__).resolve().parents[2] / "config" / "env.example"
    values = dict(
        line.split("=", 1)
        for line in example.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    assert set(values) == {
        config.PREFIX_KEY,
        config.CURRENCY_KEY,
        config.NEARING_KEY,
        config.RESPONSE_DAYS_KEY,
        config.APPEAL_WINDOW_KEY,
        config.APPEAL_DECIDE_KEY,
        config.COUNTING_KEY,
    }
    for key in values:
        monkeypatch.delenv(key, raising=False)
    s = config.load_settings()
    assert s.number_prefix == values[config.PREFIX_KEY]
    assert s.default_currency == values[config.CURRENCY_KEY]
    assert s.nearing_days == int(values[config.NEARING_KEY])
    # No statutory value is built in (PRD open question 1): these stay empty until the governance office decides.
    assert (
        values[config.RESPONSE_DAYS_KEY] == values[config.APPEAL_WINDOW_KEY] == values[config.APPEAL_DECIDE_KEY] == ""
    )
    assert (s.timelines.response_days, s.timelines.appeal_window_days, s.timelines.appeal_decide_days) == (None,) * 3
    assert s.timelines.counting == "calendar"


def test_the_example_file_loads_as_it_is(monkeypatch):
    """Setting every key exactly as env.example writes it (empty values included) is a valid configuration."""
    example = Path(__file__).resolve().parents[2] / "config" / "env.example"
    for line in example.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            monkeypatch.setenv(key, value)
    assert config.load_settings().timelines.response_days is None


def test_overrides(monkeypatch):
    monkeypatch.setenv(config.RESPONSE_DAYS_KEY, " 21 ")
    monkeypatch.setenv(config.APPEAL_WINDOW_KEY, "45")
    monkeypatch.setenv(config.APPEAL_DECIDE_KEY, "15")
    monkeypatch.setenv(config.COUNTING_KEY, "Working")
    monkeypatch.setenv(config.PREFIX_KEY, "RTIC1")
    monkeypatch.setenv(config.CURRENCY_KEY, "USD")
    monkeypatch.setenv(config.NEARING_KEY, "3")
    s = config.load_settings()
    assert (s.timelines.response_days, s.timelines.appeal_window_days, s.timelines.appeal_decide_days) == (21, 45, 15)
    assert (s.timelines.counting, s.number_prefix, s.default_currency, s.nearing_days) == ("working", "RTIC1", "USD", 3)


@pytest.mark.parametrize("key", [config.RESPONSE_DAYS_KEY, config.APPEAL_WINDOW_KEY, config.APPEAL_DECIDE_KEY])
@pytest.mark.parametrize("value", ["soon", "0", "-3", "366", "1.5", "١٢", "99999999999999999999"])
def test_bad_timeline_values_are_deployment_errors(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match=key):
        config.load_settings()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (config.NEARING_KEY, "0"),
        (config.NEARING_KEY, "400"),
        (config.PREFIX_KEY, "rti"),
        (config.PREFIX_KEY, "WAY-TOO-LONG-PREFIX"),
        (config.CURRENCY_KEY, "rupees"),
        (config.COUNTING_KEY, "fortnights"),
    ],
)
def test_other_bad_values_are_deployment_errors(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match=key):
        config.load_settings()
