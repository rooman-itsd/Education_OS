"""Module-local configuration: WEARABLES_* keys, documented in config/env.example, read from the environment on every
call so a test or a redeploy never sees a stale value. These are Rooman's developer apps, one per provider and
deployment; each athlete authorises them for their own account. Secrets are out of repr() and `describe()` is the
only thing that may be logged."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..domain.context import MODES
from ..domain.errors import AdapterError

P = "WEARABLES_"
PROVIDERS = ("garmin", "polar", "google-health", "strava")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(P + name, default).strip()


def _int(name: str, default: int, minimum: int = 0, maximum: int = 10**9) -> int:
    raw = _env(name)
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    return min(max(value, minimum), maximum)


@dataclass(frozen=True)
class Config:
    mode: str
    garmin_authorize_url: str
    garmin_token_url: str
    garmin_api_base_url: str
    polar_authorize_url: str
    polar_token_url: str
    polar_api_base_url: str
    google_authorize_url: str
    google_token_url: str
    google_revoke_url: str
    google_api_base_url: str
    google_scopes: str
    strava_authorize_url: str
    strava_token_url: str
    strava_deauthorize_url: str
    strava_api_base_url: str
    strava_subscription_id: str
    retention_days: int
    default_backfill_days: int
    stale_after_days: int
    sync_failure_threshold: int
    http_timeout_s: int
    garmin_client_id: str = ""
    garmin_client_secret: str = field(default="", repr=False)
    polar_client_id: str = ""
    polar_client_secret: str = field(default="", repr=False)
    polar_webhook_signature_key: str = field(default="", repr=False)
    google_client_id: str = ""
    google_client_secret: str = field(default="", repr=False)
    strava_client_id: str = ""
    strava_client_secret: str = field(default="", repr=False)
    strava_verify_token: str = field(default="", repr=False)

    @classmethod
    def load(cls) -> Config:
        mode = _env("MODE", "mock").lower()
        if mode not in MODES:
            raise AdapterError("not_configured", "WEARABLES_MODE must be mock, sandbox or live")
        strava_base = _env("STRAVA_API_BASE_URL", "https://www.strava.com/api/v3").rstrip("/")
        strava_site = strava_base.rsplit("/api/", 1)[0]
        return cls(
            mode=mode,
            garmin_authorize_url=_env("GARMIN_AUTHORIZE_URL", "https://connect.garmin.com/oauth2Confirm"),
            garmin_token_url=_env("GARMIN_TOKEN_URL", "https://connectapi.garmin.com/di-oauth2-service/oauth/token"),
            garmin_api_base_url=_env("GARMIN_API_BASE_URL", "https://apis.garmin.com").rstrip("/"),
            polar_authorize_url=_env("POLAR_AUTHORIZE_URL", "https://flow.polar.com/oauth2/authorization"),
            polar_token_url=_env("POLAR_TOKEN_URL", "https://polarremote.com/v2/oauth2/token"),
            polar_api_base_url=_env("POLAR_API_BASE_URL", "https://www.polaraccesslink.com/v3").rstrip("/"),
            google_authorize_url=_env("GOOGLE_HEALTH_AUTHORIZE_URL", "https://accounts.google.com/o/oauth2/v2/auth"),
            google_token_url=_env("GOOGLE_HEALTH_TOKEN_URL", "https://oauth2.googleapis.com/token"),
            google_revoke_url=_env("GOOGLE_HEALTH_REVOKE_URL", "https://oauth2.googleapis.com/revoke"),
            google_api_base_url=_env("GOOGLE_HEALTH_API_BASE_URL").rstrip("/"),
            google_scopes=_env("GOOGLE_HEALTH_SCOPES"),
            strava_authorize_url=_env("STRAVA_AUTHORIZE_URL", f"{strava_site}/oauth/authorize"),
            strava_token_url=_env("STRAVA_TOKEN_URL", f"{strava_site}/oauth/token"),
            strava_deauthorize_url=_env("STRAVA_DEAUTHORIZE_URL", f"{strava_site}/oauth/deauthorize"),
            strava_api_base_url=strava_base,
            strava_subscription_id=_env("STRAVA_SUBSCRIPTION_ID"),
            retention_days=_int("RETENTION_DAYS", 730, 1, 3650),
            default_backfill_days=_int("DEFAULT_BACKFILL_DAYS", 30, 0, 365),
            stale_after_days=_int("STALE_AFTER_DAYS", 3, 1, 365),
            sync_failure_threshold=_int("SYNC_FAILURE_THRESHOLD", 3, 1, 100),
            http_timeout_s=_int("HTTP_TIMEOUT_S", 15, 1, 120),
            garmin_client_id=_env("GARMIN_CLIENT_ID"),
            garmin_client_secret=_env("GARMIN_CLIENT_SECRET"),
            polar_client_id=_env("POLAR_CLIENT_ID"),
            polar_client_secret=_env("POLAR_CLIENT_SECRET"),
            polar_webhook_signature_key=_env("POLAR_WEBHOOK_SIGNATURE_KEY"),
            google_client_id=_env("GOOGLE_HEALTH_CLIENT_ID"),
            google_client_secret=_env("GOOGLE_HEALTH_CLIENT_SECRET"),
            strava_client_id=_env("STRAVA_CLIENT_ID"),
            strava_client_secret=_env("STRAVA_CLIENT_SECRET"),
            strava_verify_token=_env("STRAVA_VERIFY_TOKEN"),
        )

    def missing_credentials(self, provider: str) -> list[str]:
        needed = {
            "garmin": {"GARMIN_CLIENT_ID": self.garmin_client_id, "GARMIN_CLIENT_SECRET": self.garmin_client_secret},
            "polar": {
                "POLAR_CLIENT_ID": self.polar_client_id,
                "POLAR_CLIENT_SECRET": self.polar_client_secret,
                "POLAR_WEBHOOK_SIGNATURE_KEY": self.polar_webhook_signature_key,
            },
            "google-health": {
                "GOOGLE_HEALTH_CLIENT_ID": self.google_client_id,
                "GOOGLE_HEALTH_CLIENT_SECRET": self.google_client_secret,
                "GOOGLE_HEALTH_API_BASE_URL": self.google_api_base_url,
                "GOOGLE_HEALTH_SCOPES": self.google_scopes,
            },
            "strava": {
                "STRAVA_CLIENT_ID": self.strava_client_id,
                "STRAVA_CLIENT_SECRET": self.strava_client_secret,
                "STRAVA_VERIFY_TOKEN": self.strava_verify_token,
                "STRAVA_SUBSCRIPTION_ID": self.strava_subscription_id,
            },
        }[provider]
        return [P + k for k, v in needed.items() if not v]

    def describe(self) -> str:
        """Safe to log: mode and which providers have their platform credentials, never the credentials."""
        have = {p: not self.missing_credentials(p) for p in PROVIDERS}
        return f"wearables mode={self.mode} credentials={have}"
