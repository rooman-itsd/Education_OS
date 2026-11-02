"""Module-local configuration. Keys are AUDIT_*, documented in config/env.example. Read from the environment on
every call so a test or a redeploy never sees a stale value."""

from __future__ import annotations

import logging
import os

log = logging.getLogger("eos.audit")

# The retention floor. docs/prd.md proposes seven years, "configurable upward only": a lower configured value
# would delete records accreditation may still need, so it is raised to the floor rather than honoured. Erring
# towards keeping a record is the safe direction; deleting one cannot be undone.
RETENTION_FLOOR_DAYS = 2555
# The contract caps a page at 200 (contracts/openapi.yaml); configuration may only lower it.
CONTRACT_MAX_PAGE_SIZE = 200


def _int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.environ.get(name, "")
    try:
        value = int(raw) if raw.strip() else default
    except ValueError:
        value = default
    return max(value, minimum)


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    return default if not raw else raw in {"1", "true", "yes", "on"}


def retention_days() -> int:
    days = _int("AUDIT_RETENTION_DAYS", RETENTION_FLOOR_DAYS, minimum=1)
    if days < RETENTION_FLOOR_DAYS:
        log.warning("AUDIT_RETENTION_DAYS=%s is below the floor; keeping %s days", days, RETENTION_FLOOR_DAYS)
        return RETENTION_FLOOR_DAYS
    return days


def retention_enabled() -> bool:
    return _bool("AUDIT_RETENTION_ENABLED", True)


def max_payload_bytes() -> int:
    return _int("AUDIT_MAX_PAYLOAD_BYTES", 16384, minimum=1)


def max_page_size() -> int:
    return min(_int("AUDIT_MAX_PAGE_SIZE", CONTRACT_MAX_PAGE_SIZE, minimum=1), CONTRACT_MAX_PAGE_SIZE)
