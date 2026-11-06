"""Module-local configuration: VIDEO_CONFERENCING_* keys, documented in config/env.example, read from the environment on
every call so a test or a redeploy never sees a stale value. Platform credentials live only in the environment;
the secret fields are out of repr() and `describe()` is the only thing that may be logged."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..domain.context import MODES
from ..domain.errors import AdapterError

P = "VIDEO_CONFERENCING_"
PROVIDERS = ("zoom", "teams", "webex", "jitsi")


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
    zoom_api_base_url: str
    zoom_oauth_base_url: str
    teams_graph_base_url: str
    teams_login_base_url: str
    teams_renew_lead_min: int
    webex_api_base_url: str
    jitsi_token_ttl_s: int
    webhook_tolerance_s: int
    http_timeout_s: int
    attendance_delay_min: int
    zoom_create_limit_per_host_per_day: int
    max_recording_bytes: int
    public_base_url: str
    zoom_client_id: str = ""
    zoom_client_secret: str = field(default="", repr=False)
    zoom_webhook_secret_token: str = field(default="", repr=False)
    teams_client_id: str = ""
    teams_client_secret: str = field(default="", repr=False)
    webex_client_id: str = ""
    webex_client_secret: str = field(default="", repr=False)
    data_key: str = field(default="", repr=False)

    @classmethod
    def load(cls) -> Config:
        mode = _env("MODE", "mock").lower()
        if mode not in MODES:
            raise AdapterError("not_configured", "VIDEO_CONFERENCING_MODE must be mock, sandbox or live")
        return cls(
            mode=mode,
            zoom_api_base_url=_env("ZOOM_API_BASE_URL", "https://api.zoom.us/v2").rstrip("/"),
            zoom_oauth_base_url=_env("ZOOM_OAUTH_BASE_URL", "https://zoom.us/oauth").rstrip("/"),
            teams_graph_base_url=_env("TEAMS_GRAPH_BASE_URL", "https://graph.microsoft.com/v1.0").rstrip("/"),
            teams_login_base_url=_env("TEAMS_LOGIN_BASE_URL", "https://login.microsoftonline.com").rstrip("/"),
            teams_renew_lead_min=_int("TEAMS_SUBSCRIPTION_RENEW_LEAD_MIN", 720, 1, 4000),
            webex_api_base_url=_env("WEBEX_API_BASE_URL", "https://webexapis.com/v1").rstrip("/"),
            jitsi_token_ttl_s=_int("JITSI_TOKEN_TTL_S", 7200, 60, 86400),
            webhook_tolerance_s=_int("WEBHOOK_TOLERANCE_S", 300, 1, 3600),
            http_timeout_s=_int("HTTP_TIMEOUT_S", 15, 1, 120),
            attendance_delay_min=_int("ATTENDANCE_DELAY_MIN", 15, 0, 1440),
            zoom_create_limit_per_host_per_day=_int("ZOOM_CREATE_LIMIT_PER_HOST_PER_DAY", 100, 1, 10000),
            max_recording_bytes=_int("MAX_RECORDING_BYTES", 5 * 1024**3, 1, 10**12),
            public_base_url=_env("PUBLIC_BASE_URL").rstrip("/"),
            zoom_client_id=_env("ZOOM_CLIENT_ID"),
            zoom_client_secret=_env("ZOOM_CLIENT_SECRET"),
            zoom_webhook_secret_token=_env("ZOOM_WEBHOOK_SECRET_TOKEN"),
            teams_client_id=_env("TEAMS_CLIENT_ID"),
            teams_client_secret=_env("TEAMS_CLIENT_SECRET"),
            webex_client_id=_env("WEBEX_CLIENT_ID"),
            webex_client_secret=_env("WEBEX_CLIENT_SECRET"),
            data_key=_env("DATA_KEY"),
        )

    # Platform credentials Rooman holds once for every organisation, per provider (Jitsi has none).
    def missing_credentials(self, provider: str) -> list[str]:
        needed = {
            "zoom": {
                "ZOOM_CLIENT_ID": self.zoom_client_id,
                "ZOOM_CLIENT_SECRET": self.zoom_client_secret,
                "ZOOM_WEBHOOK_SECRET_TOKEN": self.zoom_webhook_secret_token,
            },
            "teams": {"TEAMS_CLIENT_ID": self.teams_client_id, "TEAMS_CLIENT_SECRET": self.teams_client_secret},
            "webex": {"WEBEX_CLIENT_ID": self.webex_client_id, "WEBEX_CLIENT_SECRET": self.webex_client_secret},
            "jitsi": {},
        }[provider]
        return [P + k for k, v in needed.items() if not v]

    def describe(self) -> str:
        """Safe to log: mode and which providers have their platform credentials, never the credentials."""
        have = {p: not self.missing_credentials(p) for p in PROVIDERS}
        return f"video-conferencing mode={self.mode} credentials={have}"
