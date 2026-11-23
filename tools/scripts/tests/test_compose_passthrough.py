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


RUNBOOK = ROOT / "infra" / "runbooks" / "personal-data-breach.md"
CODE_ROOTS = ("platform", "packages")  # retention is a platform concern


def _read_by_code(key: str) -> bool:
    """Whether some backend source reads this environment key (a quoted "KEY" in a .py under src/)."""
    needle = f'"{key}"'
    for top in CODE_ROOTS:
        for path in (ROOT / top).glob("**/src/**/*.py"):
            if needle in path.read_text(encoding="utf-8", errors="ignore"):
                return True
    return False


def test_every_setting_the_breach_runbook_changes_reaches_the_containers():
    """The runbook pauses deletion by editing .env.api and running `up -d` (step 6). A key the code reads but compose
    does not pass would leave deletion running while the responder believes it paused. A key no code reads yet (the
    runbook names notification history pruning before #683 adds it) is skipped."""
    environment = yaml.safe_load(COMPOSE.read_text())["x-app-environment"]
    named = set(re.findall(r"`([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)(?:=[^`]*)?`", RUNBOOK.read_text(encoding="utf-8")))
    keys = {k for k in named if "RETENTION" in k and _read_by_code(k)}
    assert {"AUDIT_RETENTION_ENABLED", "EVENT_BUS_RETENTION_DAYS", "SCHEDULER_RUN_RETENTION_DAYS"} <= keys
    missing = sorted(keys - set(environment))
    assert not missing, f"the breach runbook changes these, but docker-compose.api.yml does not pass them: {missing}"


def test_the_retention_and_terms_settings_default_to_the_codes_own_values():
    """Passing a key through must not change behaviour where .env.api leaves it unset."""
    environment = yaml.safe_load(COMPOSE.read_text())["x-app-environment"]
    expected = {
        "AUDIT_RETENTION_ENABLED": "true",
        "AUDIT_RETENTION_DAYS": "2555",  # eos_audit RETENTION_FLOOR_DAYS
        "EVENT_BUS_RETENTION_DAYS": "30",
        "SCHEDULER_RUN_RETENTION_DAYS": "90",
        "NOTIFICATION_HISTORY_RETENTION_DAYS": "90",  # platform/notification, #683
        "EOS_TERMS_VERSION": "",  # empty: tenancy's DEFAULT_TERMS_VERSION
        "EOS_ORGANISATION_RETENTION_DAYS": "30",  # tenancy DEFAULT_RETENTION_DAYS
    }
    for key, default in expected.items():
        assert environment.get(key) == f"${{{key}:-{default}}}", key
