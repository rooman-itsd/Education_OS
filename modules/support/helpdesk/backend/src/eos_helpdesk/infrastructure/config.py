"""Module settings from HELPDESK_* environment keys (config/env.example). Read on every call so a deployment or a
test can change them without restarting the module. A bad value is a deployment error (ValueError), never a domain
error that an API layer could report to a caller as their own invalid request."""

from __future__ import annotations

import os
from dataclasses import dataclass

AUTO_CLOSE_DAYS_KEY = "HELPDESK_AUTO_CLOSE_DAYS"
REOPEN_WINDOW_DAYS_KEY = "HELPDESK_REOPEN_WINDOW_DAYS"
TICKET_NUMBER_PREFIX_KEY = "HELPDESK_TICKET_NUMBER_PREFIX"
MAX_ATTACHMENTS_KEY = "HELPDESK_MAX_ATTACHMENTS"

# Defaults are the values in config/env.example.
DEFAULT_AUTO_CLOSE_DAYS = 7
DEFAULT_REOPEN_WINDOW_DAYS = 7
DEFAULT_TICKET_NUMBER_PREFIX = "HD"
DEFAULT_MAX_ATTACHMENTS = 5


@dataclass(frozen=True)
class ModuleSettings:
    auto_close_days: int
    reopen_window_days: int
    ticket_number_prefix: str
    max_attachments: int


def _whole_number(key: str, default: int) -> int:
    """A whole number of at least 0; unset or blank means the default."""
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        raise ValueError(f"{key} must be a whole number, got {raw!r}") from None
    if value < 0:
        raise ValueError(f"{key} must be at least 0, got {raw!r}")
    return value


def _text(key: str, default: str) -> str:
    """Surrounding spaces removed; unset or blank means the default."""
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


def load_settings() -> ModuleSettings:
    return ModuleSettings(
        auto_close_days=_whole_number(AUTO_CLOSE_DAYS_KEY, DEFAULT_AUTO_CLOSE_DAYS),
        reopen_window_days=_whole_number(REOPEN_WINDOW_DAYS_KEY, DEFAULT_REOPEN_WINDOW_DAYS),
        ticket_number_prefix=_text(TICKET_NUMBER_PREFIX_KEY, DEFAULT_TICKET_NUMBER_PREFIX),
        max_attachments=_whole_number(MAX_ATTACHMENTS_KEY, DEFAULT_MAX_ATTACHMENTS),
    )
