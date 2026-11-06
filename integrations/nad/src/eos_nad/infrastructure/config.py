"""Deployment settings from NAD_* environment variables (documented in config/env.example). Read on every call so
tests and operators can change them without a restart. Per-institution ids come from the hub connection's settings."""

from __future__ import annotations

import os
from dataclasses import dataclass

from eos_core.settings import settings as core_settings

KNOWN_TEMPLATE_VERSIONS = {"awards": ("1",), "credits": ("1",)}


def _env(key: str, default: str = "") -> str:
    return os.environ.get(f"NAD_{key}", default).strip()


def _int(key: str, default: int, low: int, high: int) -> int:
    try:
        value = int(_env(key, str(default)))
    except ValueError:
        return default
    return min(max(value, low), high)


@dataclass(frozen=True)
class Config:
    awards_template_version: str
    credits_template_version: str
    max_rows_per_file: int
    http_timeout_s: int
    apaar_hash_pepper: str
    awards_api_base_url: str
    abc_api_base_url: str
    dev_mode: bool


def load() -> Config:
    return Config(
        awards_template_version=_env("AWARDS_CSV_TEMPLATE_VERSION", "1"),
        credits_template_version=_env("CREDITS_CSV_TEMPLATE_VERSION", "1"),
        max_rows_per_file=_int("MAX_ROWS_PER_FILE", 5000, 1, 50_000),
        http_timeout_s=_int("HTTP_TIMEOUT_S", 30, 1, 300),
        apaar_hash_pepper=_env("APAAR_HASH_PEPPER"),
        # Read for the day the API channel is built; v1.0 never calls them (docs/prd.md, "Sandbox and mock").
        awards_api_base_url=_env("AWARDS_API_BASE_URL"),
        abc_api_base_url=_env("ABC_API_BASE_URL"),
        dev_mode=bool(core_settings.dev_mode),
    )
