"""Garmin Connect Developer Program (Health and Activity APIs), OAuth 2.0 with PKCE (S256). Business approval required.

Garmin **pushes** summaries (Business Starter: push only, no history) or pings us to pull (Business Enterprise: pull and a
month or more of history); the tier is the connection setting `garmin_tier`. Pushed entries are matched to an active link
by Garmin's user id. docs/prd.md says what is not verified: Garmin documents notification signing inside the program, so
until the program approves Rooman a push is trusted only as far as that match goes (README, "Garmin")."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from urllib.parse import urlencode

from ...domain.context import Context
from ...domain.errors import AdapterError
from ..http import json_body, map_status
from . import base
from .base import (
    InboundEvent,
    InboundRequest,
    Normal,
    Provider,
    accept,
    body_hash,
    integer,
    json_any,
    num,
    reject,
    text,
)
from .oauth import token_call

# Garmin's response keys for each of the port's data types.
KEYS = {
    "dailies": "daily_summary",
    "activities": "activity",
    "sleeps": "sleep",
    "hrv": "heart_rate_variability",
    "bodyComps": "body_composition",
}
PERMISSIONS = {
    "ACTIVITY_EXPORT": ["activity"],
    "HEALTH_EXPORT": ["daily_summary", "sleep", "heart_rate_variability", "body_composition"],
}
MAX_PULL_DAYS = 31


def tier(ctx: Context | None) -> str:
    return "enterprise" if ctx and ctx.settings.get("garmin_tier") == "enterprise" else "starter"


class GarminProvider(Provider):
    id = "garmin"
    title = "Garmin Connect"
    data_types = ("daily_summary", "activity", "sleep", "heart_rate_variability", "body_composition")
    inbound = ("webhook",)
    push = True
    backfill_mode = "request"
    rate_limit = "not published; data is pushed, so it costs no calls"
    platform_credential_names = ("GARMIN_CLIENT_ID", "GARMIN_CLIENT_SECRET")

    def capabilities(self, ctx: Context | None) -> dict:
        caps = super().capabilities(ctx)
        caps["backfill_days"] = 30 if tier(ctx) == "enterprise" else 0
        return caps

    # --- plumbing
    def _call(self, ctx: Context, method: str, path: str, **kw):
        token = ctx.secrets.get("access_token")
        if not token:
            raise AdapterError("consent_required", "the athlete's Garmin link has no token: it must be linked again")
        r = self.http.send(
            method, f"{self.cfg.garmin_api_base_url}{path}", headers={"Authorization": f"Bearer {token}"}, **kw
        )
        if r.status_code == 401:
            raise AdapterError("consent_required", "Garmin no longer accepts the athlete's token", provider_code="401")
        if r.status_code == 403:
            raise AdapterError(
                "consent_required", "the athlete did not grant this data to the app", provider_code="403"
            )
        if r.status_code >= 400:
            raise map_status(r)
        return r

    # --- authorisation
    def begin_authorisation(
        self, ctx: Context, state: str, code_challenge: str, redirect_uri: str, scope_hint: list
    ) -> str:
        if not self.cfg.garmin_client_id:
            raise AdapterError("not_configured", "WEARABLES_GARMIN_CLIENT_ID is not set")
        q = {
            "client_id": self.cfg.garmin_client_id, "response_type": "code", "redirect_uri": redirect_uri, "state": state,
            "code_challenge": code_challenge, "code_challenge_method": "S256",
        }  # fmt: skip
        return f"{self.cfg.garmin_authorize_url}?{urlencode(q)}"

    def _tokens(self, form: dict) -> dict:
        if not self.cfg.garmin_client_id or not self.cfg.garmin_client_secret:
            raise AdapterError("not_configured", "Garmin client credentials are not set")
        return token_call(
            self.http,
            self.cfg.garmin_token_url,
            {"client_id": self.cfg.garmin_client_id, "client_secret": self.cfg.garmin_client_secret, **form},
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
        who = self._call(Context(**{**ctx.__dict__, "secrets": out["secrets"]}), "GET", "/wellness-api/rest/user/id")
        subject = text(json_body(who).get("userId"), 80)
        if not subject:
            raise AdapterError("provider_error", "Garmin's answer names no user")
        return {
            "secrets": out["secrets"],
            "provider_subject": subject,
            "granted_scopes": out["granted_scopes"],
            "expires_at": out["expires_at"],
        }

    def refresh_authorisation(self, ctx: Context) -> dict:
        if not ctx.secrets.get("refresh_token"):
            raise AdapterError("consent_required", "the athlete's Garmin link has no refresh token")
        try:
            out = self._tokens({"grant_type": "refresh_token", "refresh_token": ctx.secrets["refresh_token"]})
        except AdapterError as e:
            if e.code == "auth_failed":
                raise AdapterError(
                    "consent_required",
                    "Garmin refused the refresh token: the athlete must link again",
                    provider_code=e.provider_code,
                ) from e
            raise
        return {"secrets": out["secrets"], "expires_at": out["expires_at"]}

    def revoke_authorisation(self, ctx: Context) -> bool:
        token = ctx.secrets.get("access_token")
        if not token:
            return False
        r = self.http.send(
            "DELETE",
            f"{self.cfg.garmin_api_base_url}/wellness-api/rest/user/registration",
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code >= 500 or r.status_code == 429:
            raise map_status(r)
        return r.status_code in (200, 204)

    # --- data
    def pull(self, ctx: Context, data_type: str, start: date, end: date) -> list[Normal]:
        if data_type not in self.data_types:
            raise AdapterError("unsupported", "Garmin does not offer this data type")
        if tier(ctx) != "enterprise":
            return []  # Business Starter is push only: nothing to pull, the data arrives by itself
        key = next(k for k, v in KEYS.items() if v == data_type)
        out: list[Normal] = []
        for d in base.days(
            max(start, end - timedelta(days=MAX_PULL_DAYS - 1)), end
        ):  # Garmin limits a pull to 24 hours
            lo = int(datetime.combine(d, time(0), tzinfo=UTC).timestamp())
            r = self._call(
                ctx,
                "GET",
                f"/wellness-api/rest/{key}",
                params={"uploadStartTimeInSeconds": lo, "uploadEndTimeInSeconds": lo + 86399},
            )
            data = r.json() if r.content else []
            for item in data if isinstance(data, list) else []:
                rec = self.normalise(key, item) if isinstance(item, dict) else None
                if rec:
                    out.append(rec)
        return out

    def backfill(self, ctx: Context, data_types: list[str], start: date, end: date) -> bool:
        if tier(ctx) != "enterprise":
            raise AdapterError(
                "unsupported", "Garmin Business Starter offers no history: only data from now on is pushed"
            )
        lo = int(
            datetime.combine(max(start, end - timedelta(days=89)), time(0), tzinfo=UTC).timestamp()
        )  # 90 days at most
        hi = int(datetime.combine(end, time(23, 59, 59), tzinfo=UTC).timestamp())
        for dt in data_types or list(self.data_types):
            key = next((k for k, v in KEYS.items() if v == dt), None)
            if key is None:
                continue
            try:
                self._call(
                    ctx,
                    "GET",
                    f"/wellness-api/rest/backfill/{key}",
                    params={"summaryStartTimeInSeconds": lo, "summaryEndTimeInSeconds": hi},
                )
            except AdapterError as e:
                if e.provider_code != "409":  # 409: the same range was already requested
                    raise
        return True

    @staticmethod
    def normalise(key: str, x: dict) -> Normal | None:
        rid = text(x.get("summaryId"), 120)
        if key == "dailies":
            d = base.day(x.get("calendarDate"))
            if d is None:
                return None
            return base.daily(
                d, rid or d.isoformat(), "garmin", steps=integer(x.get("steps"), 1e6), distance_m=num(x.get("distanceInMeters"), 1e8),
                active_kcal=num(x.get("activeKilocalories"), 1e6), resting_hr_bpm=integer(x.get("restingHeartRateInBeatsPerMinute"), 300),
                avg_hr_bpm=integer(x.get("averageHeartRateInBeatsPerMinute"), 300), max_hr_bpm=integer(x.get("maxHeartRateInBeatsPerMinute"), 300),
                active_seconds=integer(x.get("activeTimeInSeconds"), 1e6), stress_avg=integer(x.get("averageStressLevel"), 100),
            )  # fmt: skip
        if key == "activities":
            started = base.when(x.get("startTimeInSeconds"))
            if started is None or not rid:
                return None
            return base.activity(
                rid, "garmin", started, sport=(text(x.get("activityType"), 40) or "other").lower(), duration_s=integer(x.get("durationInSeconds"), 1e7),
                distance_m=num(x.get("distanceInMeters"), 1e8), kcal=num(x.get("activeKilocalories"), 1e6),
                avg_hr_bpm=integer(x.get("averageHeartRateInBeatsPerMinute"), 300), max_hr_bpm=integer(x.get("maxHeartRateInBeatsPerMinute"), 300),
            )  # fmt: skip
        if key == "sleeps":
            d = base.day(x.get("calendarDate"))
            started = base.when(x.get("startTimeInSeconds"))
            if d is None:
                return None
            dur = integer(x.get("durationInSeconds"), 1e6)
            score = x.get("overallSleepScore")
            return base.sleep(
                d, rid or d.isoformat(), "garmin", started, started + timedelta(seconds=dur) if started and dur else None, total_s=dur,
                deep_s=integer(x.get("deepSleepDurationInSeconds"), 1e6), light_s=integer(x.get("lightSleepDurationInSeconds"), 1e6),
                rem_s=integer(x.get("remSleepInSeconds"), 1e6), awake_s=integer(x.get("awakeDurationInSeconds"), 1e6),
                score=integer(score.get("value") if isinstance(score, dict) else score, 100),
            )  # fmt: skip
        if key == "hrv":
            d = base.day(x.get("calendarDate"))
            return base.hrv(d, rid or d.isoformat(), "garmin", num(x.get("lastNightAvg"), 1000)) if d else None
        if key == "bodyComps":
            measured = base.when(x.get("measurementTimeInSeconds"))
            grams = num(x.get("weightInGrams"), 1e6)
            if measured is None:
                return None
            return base.body(
                measured,
                rid or measured.isoformat(),
                "garmin",
                round(grams / 1000, 3) if grams is not None else None,
                num(x.get("bodyFatInPercent"), 100),
            )
        return None

    # --- inbound
    def _entries(self, body: dict):
        for key in (*KEYS, "deregistrations", "userPermissionsChange"):
            items = body.get(key)
            if isinstance(items, list):
                for item in items[:1000]:
                    if isinstance(item, dict) and item.get("userId") is not None:
                        yield key, text(item["userId"], 80), item

    def verify_inbound(self, req: InboundRequest, link_of: Callable[[str], dict | None]) -> dict:
        body = json_any(req.raw_body)
        if req.method.upper() != "POST" or not isinstance(body, dict):
            return reject()
        subjects = {s for _k, s, _i in self._entries(body)}
        known = {s: link_of(s) for s in subjects}
        if not subjects or not any(known.values()):
            return reject()  # nobody in it has an active link
        links = [v for v in known.values() if v]
        resolves = (
            {"connection_id": links[0]["connection_id"], "account_link_subject": next(s for s, v in known.items() if v)}
            if len(subjects) == 1
            else None
        )
        return accept(body_hash(req.raw_body), resolves)

    def parse_inbound(self, req: InboundRequest) -> list[InboundEvent]:
        body = json_any(req.raw_body)
        if not isinstance(body, dict):
            return []
        out: list[InboundEvent] = []
        pushed: dict[str, list[Normal]] = {}
        for key, subject, item in self._entries(body):
            if key == "deregistrations":
                out.append(InboundEvent("revoked", subject))
            elif key == "userPermissionsChange":
                perms = item.get("permissions") if isinstance(item.get("permissions"), list) else []
                granted = sorted({t for p in perms if isinstance(p, str) for t in PERMISSIONS.get(p, [])})
                out.append(InboundEvent("narrowed", subject, granted))
            else:
                rec = self.normalise(key, item)
                if rec:
                    pushed.setdefault(subject, []).append(rec)
        for subject, recs in pushed.items():
            dates = [r.record_date for r in recs]
            out.append(InboundEvent("data", subject, sorted({r.data_type for r in recs}), min(dates), max(dates), recs))
        return out
