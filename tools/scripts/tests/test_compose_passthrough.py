"""Every SMTP setting the messaging-providers adapter reads reaches the API container.

A key missing from infra/docker/docker-compose.api.yml is silently unset in a deployment, whatever .env.api says:
the TLS mode (#316 audit, M2) is exactly the kind of setting that must not fall back to a default unnoticed."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "infra" / "docker" / "docker-compose.api.yml"
ADAPTER = ROOT / "integrations" / "messaging-providers"


def _documented_keys() -> set[str]:
    """The adapter's own settings: env.example lines, and every key its config reads from the environment."""
    keys = set(
        re.findall(r"^(MESSAGING_PROVIDERS_SMTP_[A-Z_]+)=", (ADAPTER / "config" / "env.example").read_text(), re.M)
    )
    config = (ADAPTER / "src" / "eos_messaging_providers" / "infrastructure" / "config.py").read_text()
    keys |= set(re.findall(r'"(MESSAGING_PROVIDERS_SMTP_[A-Z_]+)"', config))
    return keys


def test_every_smtp_setting_is_passed_to_the_api_container():
    environment = yaml.safe_load(COMPOSE.read_text())["x-app-environment"]
    keys = _documented_keys()
    assert {"MESSAGING_PROVIDERS_SMTP_HOST", "MESSAGING_PROVIDERS_SMTP_USE_TLS"} <= keys  # the scan finds them
    missing = sorted(keys - set(environment))
    assert not missing, f"set in the adapter but not passed through docker-compose.api.yml: {missing}"


def test_the_implicit_tls_switch_is_passed_through_and_off_by_default():
    environment = yaml.safe_load(COMPOSE.read_text())["x-app-environment"]
    assert environment["MESSAGING_PROVIDERS_SMTP_SSL"] == "${MESSAGING_PROVIDERS_SMTP_SSL:-false}"
