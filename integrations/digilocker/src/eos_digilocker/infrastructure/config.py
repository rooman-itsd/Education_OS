"""Deployment settings from DIGILOCKER_* environment variables (documented in config/env.example). Read on every
call so tests and operators can change them without a restart. Per-institution credentials are NOT here: they come
from the hub's secret store with each call (Context.secrets)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from eos_core.settings import settings as core_settings

MODES = ("mock", "sandbox", "live")


def _env(key: str, default: str = "") -> str:
    return os.environ.get(f"DIGILOCKER_{key}", default).strip()


def _int(key: str, default: int, low: int, high: int) -> int:
    try:
        value = int(_env(key, str(default)))
    except ValueError:
        return default
    return min(max(value, low), high)


@dataclass(frozen=True)
class Config:
    live_base_url: str
    sandbox_base_url: str
    requester_client_id: str
    requester_client_secret: str
    sandbox_requester_client_id: str
    sandbox_requester_client_secret: str
    requester_purpose: str
    consent_days: int
    pull_tolerance_s: int
    push_max_age_s: int
    http_timeout_s: int
    max_document_bytes: int
    search_key_pepper: str
    dev_mode: bool

    def base_url(self, mode: str) -> str:
        return {"live": self.live_base_url, "sandbox": self.sandbox_base_url}.get(mode, "").rstrip("/")

    def requester(self, mode: str) -> tuple[str, str] | None:
        """Rooman's requester app for this mode, or None when not configured."""
        if mode == "sandbox":
            pair = (self.sandbox_requester_client_id, self.sandbox_requester_client_secret)
        else:
            pair = (self.requester_client_id, self.requester_client_secret)
        return pair if all(pair) else None


def load() -> Config:
    purpose = _env("REQUESTER_PURPOSE", "educational").lower()
    return Config(
        live_base_url=_env("LIVE_BASE_URL", "https://api.digitallocker.gov.in/public"),
        sandbox_base_url=_env("SANDBOX_BASE_URL"),
        requester_client_id=_env("REQUESTER_CLIENT_ID"),
        requester_client_secret=_env("REQUESTER_CLIENT_SECRET"),
        sandbox_requester_client_id=_env("SANDBOX_REQUESTER_CLIENT_ID"),
        sandbox_requester_client_secret=_env("SANDBOX_REQUESTER_CLIENT_SECRET"),
        requester_purpose=purpose if purpose in ("educational", "verification") else "educational",
        consent_days=_int("CONSENT_DAYS", 30, 1, 365),
        pull_tolerance_s=_int("PULL_TOLERANCE_S", 300, 1, 3600),
        push_max_age_s=_int("PUSH_MAX_AGE_S", 60, 1, 1500),  # DigiLocker refuses ts older than 30 min
        http_timeout_s=_int("HTTP_TIMEOUT_S", 15, 1, 120),
        max_document_bytes=_int("MAX_DOCUMENT_BYTES", 5_242_880, 1024, 52_428_800),
        search_key_pepper=_env("SEARCH_KEY_PEPPER"),
        dev_mode=bool(core_settings.dev_mode),
    )
