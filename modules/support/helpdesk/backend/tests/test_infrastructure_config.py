"""Unit tests of the module settings read from HELPDESK_* keys (config/env.example)."""

import pytest
from eos_helpdesk.infrastructure.config import (
    AUTO_CLOSE_DAYS_KEY,
    MAX_ATTACHMENTS_KEY,
    REOPEN_WINDOW_DAYS_KEY,
    TICKET_NUMBER_PREFIX_KEY,
    ModuleSettings,
    load_settings,
)

KEYS = (AUTO_CLOSE_DAYS_KEY, REOPEN_WINDOW_DAYS_KEY, TICKET_NUMBER_PREFIX_KEY, MAX_ATTACHMENTS_KEY)
WHOLE_NUMBER_KEYS = (AUTO_CLOSE_DAYS_KEY, REOPEN_WINDOW_DAYS_KEY, MAX_ATTACHMENTS_KEY)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)


def test_defaults_are_the_env_example_values():
    assert load_settings() == ModuleSettings(
        auto_close_days=7, reopen_window_days=7, ticket_number_prefix="HD", max_attachments=5
    )


def test_values_are_read_from_the_environment(monkeypatch):
    monkeypatch.setenv(AUTO_CLOSE_DAYS_KEY, "10")
    monkeypatch.setenv(REOPEN_WINDOW_DAYS_KEY, " 3 ")
    monkeypatch.setenv(TICKET_NUMBER_PREFIX_KEY, " SUP ")
    monkeypatch.setenv(MAX_ATTACHMENTS_KEY, "0")
    assert load_settings() == ModuleSettings(
        auto_close_days=10, reopen_window_days=3, ticket_number_prefix="SUP", max_attachments=0
    )


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("value", ["", "   "])
def test_a_blank_value_means_the_default(monkeypatch, key, value):
    defaults = load_settings()
    monkeypatch.setenv(key, value)
    assert load_settings() == defaults


@pytest.mark.parametrize("key", WHOLE_NUMBER_KEYS)
@pytest.mark.parametrize("value", ["-1", "1.5", "seven", "7d"])
def test_a_bad_number_is_a_deployment_error(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match=key):
        load_settings()


def test_settings_are_read_on_every_call(monkeypatch):
    assert load_settings().auto_close_days == 7
    monkeypatch.setenv(AUTO_CLOSE_DAYS_KEY, "2")
    assert load_settings().auto_close_days == 2


def test_every_key_is_documented_in_env_example():
    from pathlib import Path

    example = (Path(__file__).resolve().parents[2] / "config" / "env.example").read_text(encoding="utf-8")
    documented = {line.split("=", 1)[0].strip() for line in example.splitlines() if "=" in line and line[:1] != "#"}
    assert set(KEYS) == documented
