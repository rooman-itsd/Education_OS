"""INCIDENT_MANAGEMENT_* settings (config/env.example): defaults, overrides and refused values."""

from pathlib import Path

import pytest
from eos_incident_management.infrastructure import config

EXAMPLE = Path(__file__).resolve().parents[2] / "config" / "env.example"


def example_values() -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in EXAMPLE.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    )


def test_defaults_are_the_env_example_values(monkeypatch):
    values = example_values()
    for key in values:
        monkeypatch.delenv(key, raising=False)
    s = config.load_settings()
    assert s.incident_number_prefix == values[config.INCIDENT_NUMBER_PREFIX_KEY]
    assert s.problem_number_prefix == values[config.PROBLEM_NUMBER_PREFIX_KEY]


def test_env_example_lists_exactly_the_keys_read():
    assert set(example_values()) == {config.INCIDENT_NUMBER_PREFIX_KEY, config.PROBLEM_NUMBER_PREFIX_KEY}


def test_overrides(monkeypatch):
    monkeypatch.setenv(config.INCIDENT_NUMBER_PREFIX_KEY, " IT-INC ")
    monkeypatch.setenv(config.PROBLEM_NUMBER_PREFIX_KEY, "")
    s = config.load_settings()
    assert (s.incident_number_prefix, s.problem_number_prefix) == ("IT-INC", "PRB")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (config.INCIDENT_NUMBER_PREFIX_KEY, "INC 1"),
        (config.INCIDENT_NUMBER_PREFIX_KEY, "-INC"),
        (config.PROBLEM_NUMBER_PREFIX_KEY, "P" * 21),
        (config.PROBLEM_NUMBER_PREFIX_KEY, "PRB/"),
    ],
)
def test_bad_values_are_deployment_errors(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match=key):
        config.load_settings()
