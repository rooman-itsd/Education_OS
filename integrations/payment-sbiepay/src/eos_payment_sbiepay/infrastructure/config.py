"""Adapter settings from PAYMENT_SBIEPAY_* environment variables (documented in config/env.example).
Read on every call so tests and operators can change them without a restart."""

from __future__ import annotations

import os
from dataclasses import dataclass

from eos_core.settings import settings as core_settings

MODES = ("mock", "sandbox", "live")


def _env(key: str, default: str = "") -> str:
    return os.environ.get(f"PAYMENT_SBIEPAY_{key}", default).strip()


@dataclass(frozen=True)
class Config:
    mode: str
    merchant_id: str
    encryption_key: str
    gateway_url: str
    verify_url: str
    refund_url: str
    callback_base_url: str
    allowed_return_hosts: tuple[str, ...]
    notify_secret: str
    session_ttl_minutes: int
    pending_verify_after_minutes: int


class ConfigError(Exception):
    pass


def load() -> Config:
    # An unset mode never falls back to the mock gateway: it must be chosen explicitly.
    mode = _env("MODE", "sandbox").lower()
    if mode not in MODES:
        raise ConfigError(f"PAYMENT_SBIEPAY_MODE must be one of {', '.join(MODES)}")
    if mode == "mock" and not core_settings.dev_mode:
        raise ConfigError("PAYMENT_SBIEPAY_MODE=mock is refused unless EOS_DEV_MODE=true")
    if mode != "mock" and not _env("CALLBACK_BASE_URL"):
        # payment_url and the gateway's return URL must be absolute outside development.
        raise ConfigError("PAYMENT_SBIEPAY_CALLBACK_BASE_URL is required in sandbox and live mode")
    return Config(
        mode=mode,
        merchant_id=_env("MERCHANT_ID"),
        encryption_key=_env("ENCRYPTION_KEY"),
        gateway_url=_env("GATEWAY_URL"),
        verify_url=_env("VERIFY_URL"),
        refund_url=_env("REFUND_URL"),
        callback_base_url=_env("CALLBACK_BASE_URL").rstrip("/"),
        allowed_return_hosts=tuple(h.strip().lower() for h in _env("ALLOWED_RETURN_HOSTS").split(",") if h.strip()),
        notify_secret=_env("NOTIFY_SECRET"),
        session_ttl_minutes=int(_env("SESSION_TTL_MINUTES", "30")),
        pending_verify_after_minutes=int(_env("PENDING_VERIFY_AFTER_MINUTES", "20")),
    )
