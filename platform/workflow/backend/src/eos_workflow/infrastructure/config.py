"""Module-local configuration. Keys are WORKFLOW_*, documented in config/env.example."""

from __future__ import annotations

import os

DEFAULT_SLA_HOURS = 48
MAX_STEPS = 10
CONTRACT_MAX_PAGE_SIZE = 100


def _int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.environ.get(name, "")
    try:
        value = int(raw) if raw.strip() else default
    except ValueError:
        value = default
    return max(value, minimum)


def default_sla_hours() -> int:
    return _int("WORKFLOW_DEFAULT_SLA_HOURS", DEFAULT_SLA_HOURS, minimum=1)


def max_steps() -> int:
    return _int("WORKFLOW_MAX_STEPS", MAX_STEPS, minimum=1)


def max_page_size() -> int:
    return min(_int("WORKFLOW_MAX_PAGE_SIZE", CONTRACT_MAX_PAGE_SIZE, minimum=1), CONTRACT_MAX_PAGE_SIZE)
