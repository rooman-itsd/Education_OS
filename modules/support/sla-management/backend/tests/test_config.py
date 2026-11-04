"""SLA_MANAGEMENT_* settings (config/env.example): defaults, overrides and refused values."""

import re
from pathlib import Path

import pytest
from eos_sla_management.infrastructure import config

MODULE = Path(__file__).resolve().parents[2]


def env_example() -> dict[str, str]:
    lines = (MODULE / "config" / "env.example").read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines if line and not line.startswith("#") and "=" in line)


def test_defaults_are_the_env_example_values(monkeypatch):
    values = env_example()
    for key in values:
        monkeypatch.delenv(key, raising=False)
    s = config.load_settings()
    assert s.default_warning_percent == int(values[config.DEFAULT_WARNING_PERCENT_KEY])
    assert s.max_escalation_levels == int(values[config.MAX_ESCALATION_LEVELS_KEY])
    assert s.breach_list_limit == int(values[config.BREACH_LIST_LIMIT_KEY])


def test_env_example_lists_exactly_the_keys_the_module_reads():
    source = (MODULE / "backend" / "src" / "eos_sla_management" / "infrastructure" / "config.py").read_text("utf-8")
    assert set(re.findall(r'"(SLA_MANAGEMENT_[A-Z_]+)"', source)) == set(env_example())


def test_overrides(monkeypatch):
    monkeypatch.setenv(config.DEFAULT_WARNING_PERCENT_KEY, " 90 ")
    monkeypatch.setenv(config.MAX_ESCALATION_LEVELS_KEY, "0")
    monkeypatch.setenv(config.BREACH_LIST_LIMIT_KEY, "50")
    s = config.load_settings()
    assert (s.default_warning_percent, s.max_escalation_levels, s.breach_list_limit) == (90, 0, 50)
    monkeypatch.setenv(config.BREACH_LIST_LIMIT_KEY, "")
    assert config.load_settings().breach_list_limit == 10


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (config.DEFAULT_WARNING_PERCENT_KEY, "most"),
        (config.DEFAULT_WARNING_PERCENT_KEY, "0"),
        (config.DEFAULT_WARNING_PERCENT_KEY, "100"),
        (config.MAX_ESCALATION_LEVELS_KEY, "-1"),
        (config.MAX_ESCALATION_LEVELS_KEY, "11"),
        (config.BREACH_LIST_LIMIT_KEY, "0"),
        (config.BREACH_LIST_LIMIT_KEY, "51"),
        (config.BREACH_LIST_LIMIT_KEY, str(10**30)),
    ],
)
def test_bad_values_are_deployment_errors(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match=key):
        config.load_settings()
