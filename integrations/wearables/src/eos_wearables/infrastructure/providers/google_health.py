"""Fitbit devices through the Google Health API (the legacy Fitbit Web API is shut down). Google OAuth 2.0 with PKCE.

**Everything specific to the Google Health API here is an assumption** until Rooman has access: all its scopes are
restricted and need Google's privacy and security review, and the draft's "Not verified" list names its endpoints, quotas,
sandbox and webhook verification. What is certain (Google's OAuth endpoints) is the default; the API base URL and scopes
have no default and are required; the resource paths and response shapes are the table below, replaced by recorded
responses the day access is granted. Its webhooks are **not accepted** until their verification is documented: data arrives
by the daily `sync` only."""

from __future__ import annotations

import base64
import json
from datetime import date
from urllib.parse import quote, urlencode

from ...domain.context import Context
from ...domain.errors import AdapterError
from ..http import map_status
from . import base
from .base import Normal, Provider, integer, num, text
from .oauth import token_call

# ASSUMED resource path and item shape per data type (see the module docstring).
PATHS = {
    "daily_summary": "dailySummaries",
    "activity": "activities",
    "sleep": "sleep",
    "heart_rate_variability": "heartRateVariability",
    "body_composition": "bodyComposition",
}


class GoogleHealthProvider(Provider):
    id = "google-health"
    title = "Fitbit (Google Health API)"
    data_types = ("daily_summary", "activity", "sleep", "heart_rate_variability", "body_composition")
    inbound = ("webhook",)
    push = False
    backfill_mode = "pull"
    rate_limit = "not published"
    platform_credential_names = (
        "GOOGLE_HEALTH_CLIENT_ID",
        "GOOGLE_HEALTH_CLIENT_SECRET",
        "GOOGLE_HEALTH_API_BASE_URL",
        "GOOGLE_HEALTH_SCOPES",
    )

    def capabilities(self, ctx: Context | None) -> dict:
        caps = super().capabilities(ctx)
        caps["backfill_days"] = 90
        return caps

    def _call(self, ctx: Context, path: str, params: dict) -> dict:
        if not self.cfg.google_api_base_url:
            raise AdapterError("not_configured", "WEARABLES_GOOGLE_HEALTH_API_BASE_URL is not set")
        token = ctx.secrets.get("access_token")
        if not token:
            raise AdapterError("consent_required", "the athlete's Google link has no token: it must be linked again")
        r = self.http.send(
            "GET", f"{self.cfg.google_api_base_url}{path}", headers={"Authorization": f"Bearer {token}"}, params=params
        )
        if r.status_code == 401:
            raise AdapterError("consent_required", "Google no longer accepts the athlete's token", provider_code="401")
        if r.status_code == 403:
            raise AdapterError(
                "consent_required", "the athlete did not grant this data type to the app", provider_code="403"
            )
        if r.status_code >= 400:
            raise map_status(r)
        try:
            data = r.json() if r.content else {}
        except ValueError as e:
            raise AdapterError("provider_error", "Google answered with something that is not JSON") from e
        if not isinstance(data, dict):
            raise AdapterError("provider_error", "Google answered with an unexpected shape")
        return data

    # --- authorisation (Google's standard OAuth 2.0)
    def begin_authorisation(
        self, ctx: Context, state: str, code_challenge: str, redirect_uri: str, scope_hint: list
    ) -> str:
        if not self.cfg.google_client_id or not self.cfg.google_scopes:
            raise AdapterError("not_configured", "WEARABLES_GOOGLE_HEALTH_CLIENT_ID and _SCOPES are not set")
        q = {
            "client_id": self.cfg.google_client_id, "response_type": "code", "redirect_uri": redirect_uri, "scope": f"openid {self.cfg.google_scopes}",
            "state": state, "code_challenge": code_challenge, "code_challenge_method": "S256", "access_type": "offline", "prompt": "consent",
        }  # fmt: skip
        return f"{self.cfg.google_authorize_url}?{urlencode(q)}"

    def _tokens(self, form: dict) -> dict:
        if not self.cfg.google_client_id or not self.cfg.google_client_secret:
            raise AdapterError("not_configured", "Google client credentials are not set")
        return token_call(
            self.http,
            self.cfg.google_token_url,
            {"client_id": self.cfg.google_client_id, "client_secret": self.cfg.google_client_secret, **form},
            self.clock(),
        )

    def complete_authorisation(self, ctx: Context, code: str, code_verifier: str, redirect_uri: str) -> dict:
        out = self._tokens(
            {
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
            }
        )
        subject = _subject(out["raw"].get("id_token"))
        if not subject:
            raise AdapterError("provider_error", "Google's token answer names no user")
        return {
            "secrets": out["secrets"],
            "provider_subject": subject,
            "granted_scopes": out["granted_scopes"],
            "expires_at": out["expires_at"],
        }

    def refresh_authorisation(self, ctx: Context) -> dict:
        if not ctx.secrets.get("refresh_token"):
            raise AdapterError("consent_required", "the athlete's Google link has no refresh token")
        try:
            out = self._tokens({"grant_type": "refresh_token", "refresh_token": ctx.secrets["refresh_token"]})
        except AdapterError as e:
            if e.code == "auth_failed":
                raise AdapterError(
                    "consent_required",
                    "Google refused the refresh token: the athlete must link again",
                    provider_code=e.provider_code,
                ) from e
            raise
        secrets = {**out["secrets"], "refresh_token": out["secrets"].get("refresh_token", ctx.secrets["refresh_token"])}
        return {"secrets": secrets, "expires_at": out["expires_at"]}

    def revoke_authorisation(self, ctx: Context) -> bool:
        token = ctx.secrets.get("refresh_token") or ctx.secrets.get("access_token")
        if not token:
            return False
        r = self.http.send("POST", self.cfg.google_revoke_url, data={"token": token})
        if r.status_code >= 500 or r.status_code == 429:
            raise map_status(r)
        return r.status_code < 400

    # --- data
    def pull(self, ctx: Context, data_type: str, start: date, end: date) -> list[Normal]:
        if data_type not in PATHS:
            raise AdapterError("unsupported", "Google Health does not offer this data type")
        d = self._call(
            ctx, f"/users/me/{quote(PATHS[data_type])}", {"startDate": start.isoformat(), "endDate": end.isoformat()}
        )
        items = d.get("items") if isinstance(d.get("items"), list) else []
        out = [self.normalise(data_type, x) for x in items[:5000] if isinstance(x, dict)]
        return [r for r in out if r is not None and start <= r.record_date <= end]

    @staticmethod
    def normalise(data_type: str, x: dict) -> Normal | None:
        rid = text(x.get("id"), 120)
        if data_type == "daily_summary":
            d = base.day(x.get("date"))
            return base.daily(
                d, rid or d.isoformat(), "fitbit", steps=integer(x.get("steps"), 1e6), distance_m=num(x.get("distanceMeters"), 1e8),
                active_kcal=num(x.get("activeKilocalories"), 1e6), resting_hr_bpm=integer(x.get("restingHeartRate"), 300),
                avg_hr_bpm=integer(x.get("averageHeartRate"), 300), max_hr_bpm=integer(x.get("maxHeartRate"), 300),
                active_seconds=integer(x.get("activeSeconds"), 1e6), stress_avg=integer(x.get("stressAverage"), 100),
            ) if d else None  # fmt: skip
        if data_type == "activity":
            started = base.when(x.get("startTime"))
            if started is None or not rid:
                return None
            zones = x.get("heartRateZoneSeconds") if isinstance(x.get("heartRateZoneSeconds"), list) else []
            return base.activity(
                rid, "fitbit", started, sport=(text(x.get("sport"), 40) or "other").lower(), duration_s=integer(x.get("durationSeconds"), 1e7),
                distance_m=num(x.get("distanceMeters"), 1e8), kcal=num(x.get("kilocalories"), 1e6), avg_hr_bpm=integer(x.get("averageHeartRate"), 300),
                max_hr_bpm=integer(x.get("maxHeartRate"), 300), training_load=num(x.get("trainingLoad")), hr_zones_s=[integer(z, 1e6) or 0 for z in zones[:10]],
            )  # fmt: skip
        if data_type == "sleep":
            d = base.day(x.get("date"))
            return base.sleep(
                d, rid or d.isoformat(), "fitbit", base.when(x.get("startTime")), base.when(x.get("endTime")), total_s=integer(x.get("totalSeconds"), 1e6),
                deep_s=integer(x.get("deepSeconds"), 1e6), light_s=integer(x.get("lightSeconds"), 1e6), rem_s=integer(x.get("remSeconds"), 1e6),
                awake_s=integer(x.get("awakeSeconds"), 1e6), score=integer(x.get("score"), 100),
            ) if d else None  # fmt: skip
        if data_type == "heart_rate_variability":
            d = base.day(x.get("date"))
            return base.hrv(d, rid or d.isoformat(), "fitbit", num(x.get("rmssd"), 1000)) if d else None
        if data_type == "body_composition":
            measured = base.when(x.get("measuredAt"))
            return (
                base.body(
                    measured,
                    rid or measured.isoformat(),
                    "fitbit",
                    num(x.get("weightKg"), 1000),
                    num(x.get("bodyFatPercent"), 100),
                )
                if measured
                else None
            )
        return None


def _subject(id_token) -> str:
    """`sub` of the OpenID token Google's token endpoint returned over TLS for this code exchange (the standard
    authorisation-code flow: no signature check is needed on a token received directly from the issuer)."""
    if not isinstance(id_token, str) or id_token.count(".") != 2 or len(id_token) > 8192:
        return ""
    try:
        payload = id_token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, UnicodeDecodeError):
        return ""
    return text(claims.get("sub") if isinstance(claims, dict) else None, 80)
