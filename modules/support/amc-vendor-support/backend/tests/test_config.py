"""AMC_VENDOR_SUPPORT_* settings (config/env.example): defaults, overrides and refused values."""

from pathlib import Path

import pytest
from eos_amc_vendor_support.infrastructure import config


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
    assert s.contract_number_prefix == values[config.CONTRACT_NUMBER_PREFIX_KEY]
    assert s.engagement_number_prefix == values[config.ENGAGEMENT_NUMBER_PREFIX_KEY]
    assert s.expiry_window_days == int(values[config.EXPIRY_WINDOW_DAYS_KEY])
    assert s.default_currency == values[config.DEFAULT_CURRENCY_KEY]


def test_overrides(monkeypatch):
    monkeypatch.setenv(config.ENGAGEMENT_NUMBER_PREFIX_KEY, " VC ")
    monkeypatch.setenv(config.EXPIRY_WINDOW_DAYS_KEY, "90")
    monkeypatch.setenv(config.DEFAULT_CURRENCY_KEY, "AED")
    s = config.load_settings()
    assert (s.engagement_number_prefix, s.expiry_window_days, s.default_currency) == ("VC", 90, "AED")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (config.EXPIRY_WINDOW_DAYS_KEY, "soon"),
        (config.EXPIRY_WINDOW_DAYS_KEY, "0"),
        (config.EXPIRY_WINDOW_DAYS_KEY, "400"),
        (config.DEFAULT_CURRENCY_KEY, "rupees"),
    ],
)
def test_bad_values_are_deployment_errors(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match=key):
        config.load_settings()
