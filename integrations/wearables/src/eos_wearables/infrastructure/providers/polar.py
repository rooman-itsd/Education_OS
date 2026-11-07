"""Polar AccessLink v3: OAuth 2.0 (tokens do not expire), user registration with our member id, exercises, daily activity
and sleep from the non-transactional endpoints, and the one app-level webhook signed with HMAC-SHA256.

Polar offers no HRV or body-composition data through this adapter and no history before the link (it keeps about 30 days of
exercises and 28 of daily activity, which a first sync reads). docs/prd.md lists what is not verified."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable
from datetime import date, timedelta
from urllib.parse import quote, urlencode

from ...domain.context import Context
from ...domain.errors import AdapterError
from ..http import map_status
from . import base
from .base import (
    InboundEvent,
    InboundRequest,
    Normal,
    Provider,
    accept,
    body_hash,
    hex_equal,
    integer,
    json_any,
    num,
    reject,
    text,
)
from .oauth import basic, token_call

EVENTS = {"EXERCISE": "activity", "SLEEP": "sleep", "ACTIVITY_SUMMARY": "daily_summary"}


class PolarProvider(Provider):
    id = "polar"
    title = "Polar AccessLink"
    data_types = ("daily_summary", "activity", "sleep")
    inbound = ("webhook",)
    push = True  # a ping per new record; the hub then runs sync
    rate_limit = "500 + 20 per user per 15 min, 5000 + 100 per user per 24 h"
    platform_credential_names = ("POLAR_CLIENT_ID", "POLAR_CLIENT_SECRET", "POLAR_WEBHOOK_SIGNATURE_KEY")

    # --- plumbing
    def _call(self, ctx: Context, method: str, path: str, **kw) -> dict | list:
        token = ctx.secrets.get("access_token")
        if not token:
            raise AdapterError("consent_required", "the athlete's Polar link has no token: it must be linked again")
        r = self.http.send(
            method,
            f"{self.cfg.polar_api_base_url}{path}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            **kw,
        )
        if r.status_code == 401:
            raise AdapterError("consent_required", "Polar no longer accepts the athlete's token", provider_code="401")
        if r.status_code == 403:
            raise AdapterError(
                "consent_required", "the athlete did not grant this data to the app", provider_code="403"
            )
        if r.status_code == 204:
            return []
        if r.status_code >= 400:
            raise map_status(r)
        if not r.content:
            return []
        try:
            data = r.json()
        except ValueError as e:
            raise AdapterError("provider_error", "Polar answered with something that is not JSON") from e
        if not isinstance(data, (list, dict)):
            raise AdapterError("provider_error", "Polar answered with an unexpected shape")
        return data

    # --- authorisation
    def begin_authorisation(
        self, ctx: Context, state: str, code_challenge: str, redirect_uri: str, scope_hint: list
    ) -> str:
        if not self.cfg.polar_client_id:
            raise AdapterError("not_configured", "WEARABLES_POLAR_CLIENT_ID is not set")
        q = {
            "response_type": "code",
            "client_id": self.cfg.polar_client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": "accesslink.read_all",
        }
        return f"{self.cfg.polar_authorize_url}?{urlencode(q)}"

    def complete_authorisation(self, ctx: Context, code: str, code_verifier: str, redirect_uri: str) -> dict:
        if not self.cfg.polar_client_id or not self.cfg.polar_client_secret:
            raise AdapterError("not_configured", "Polar client credentials are not set")
        out = token_call(
            self.http, self.cfg.polar_token_url, {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
            self.clock(), headers={"Authorization": basic(self.cfg.polar_client_id, self.cfg.polar_client_secret), "Accept": "application/json"},
        )  # fmt: skip
        subject = text(out["raw"].get("x_user_id"), 40)
        if not subject:
            raise AdapterError("provider_error", "Polar's token answer names no user")
        return {
            "secrets": {"access_token": out["secrets"]["access_token"]},
            "provider_subject": subject,
            "granted_scopes": ["accesslink.read_all"],
            "expires_at": None,
        }

    def refresh_authorisation(self, ctx: Context) -> dict:
        return {"secrets": {}, "expires_at": None}  # Polar's tokens do not expire

    def register_user(self, ctx: Context, person_id: str, provider_subject: str | None) -> None:
        """POST /v3/users with our member id; Polar answers 409 when the user is already registered, which is success."""
        token = ctx.secrets.get("access_token")
        if not token:
            raise AdapterError("consent_required", "the athlete's Polar link has no token")
        r = self.http.send(
            "POST",
            f"{self.cfg.polar_api_base_url}/users",
            json={"member-id": person_id},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        if r.status_code in (200, 201, 409):
            return
        if r.status_code in (401, 403):
            raise AdapterError(
                "consent_required", "Polar refused to register the athlete", provider_code=str(r.status_code)
            )
        raise map_status(r)

    def revoke_authorisation(self, ctx: Context) -> bool:
        subject = (ctx.account_link or {}).get("provider_subject")
        token = ctx.secrets.get("access_token")
        if not subject or not token:
            return False
        r = self.http.send(
            "DELETE",
            f"{self.cfg.polar_api_base_url}/users/{quote(str(subject), safe='')}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code >= 500 or r.status_code == 429:
            raise map_status(r)
        return r.status_code in (200, 204)

    # --- data
    def pull(self, ctx: Context, data_type: str, start: date, end: date) -> list[Normal]:
        if data_type == "activity":
            data = self._call(ctx, "GET", "/exercises", params={"zones": "true"})
            items = data if isinstance(data, list) else []
            recs = [self._exercise(x) for x in items if isinstance(x, dict)]
        elif data_type == "daily_summary":
            lo = max(start, end - timedelta(days=27))  # Polar serves the last 28 days
            data = self._call(ctx, "GET", "/users/activities", params={"from": lo.isoformat(), "to": end.isoformat()})
            recs = [self._daily(x) for x in (data if isinstance(data, list) else []) if isinstance(x, dict)]
        elif data_type == "sleep":
            data = self._call(ctx, "GET", "/users/sleep")
            nights = data.get("nights") if isinstance(data, dict) else None
            recs = [self._sleep(x) for x in (nights if isinstance(nights, list) else []) if isinstance(x, dict)]
        else:
            raise AdapterError("unsupported", "Polar offers no heart-rate variability or body composition here")
        return [r for r in recs if r is not None and start <= r.record_date <= end]

    @staticmethod
    def _exercise(x: dict) -> Normal | None:
        rid, started = text(x.get("id"), 60), base.when(x.get("start_time_utc") or x.get("start_time"))
        if not rid or started is None:
            return None
        hr = x.get("heart_rate") if isinstance(x.get("heart_rate"), dict) else {}
        zones = x.get("heart_rate_zones") if isinstance(x.get("heart_rate_zones"), list) else []
        ordered = sorted((z for z in zones if isinstance(z, dict)), key=lambda z: integer(z.get("index"), 20) or 0)
        return base.activity(
            rid, "polar", started,
            sport=(text(x.get("sport"), 40) or "other").lower(),
            duration_s=base.seconds(x.get("duration")),
            distance_m=num(x.get("distance"), 1e8),
            kcal=num(x.get("calories"), 1e6),
            avg_hr_bpm=integer(hr.get("average"), 300),
            max_hr_bpm=integer(hr.get("maximum"), 300),
            training_load=num(x.get("training_load")),
            hr_zones_s=[base.seconds(z.get("in-zone")) or 0 for z in ordered][:10],
        )  # fmt: skip

    @staticmethod
    def _daily(x: dict) -> Normal | None:
        d = base.day(x.get("start_time"))
        if d is None:
            return None
        return base.daily(
            d, d.isoformat(), "polar", steps=integer(x.get("steps"), 1e6), distance_m=num(x.get("distance_from_steps"), 1e8),
            active_kcal=num(x.get("active_calories"), 1e6), active_seconds=base.seconds(x.get("active_duration")),
        )  # fmt: skip

    @staticmethod
    def _sleep(x: dict) -> Normal | None:
        d = base.day(x.get("date"))
        if d is None:
            return None
        deep, light, rem = (integer(x.get(k), 1e6) for k in ("deep_sleep", "light_sleep", "rem_sleep"))
        total = (
            sum(v for v in (deep, light, rem) if v is not None)
            if any(v is not None for v in (deep, light, rem))
            else None
        )
        return base.sleep(
            d, d.isoformat(), "polar", base.when(x.get("sleep_start_time")), base.when(x.get("sleep_end_time")),
            total_s=total, deep_s=deep, light_s=light, rem_s=rem, awake_s=integer(x.get("total_interruption_duration"), 1e6),
            score=integer(x.get("sleep_score"), 100),
        )  # fmt: skip

    # --- inbound
    def verify_inbound(self, req: InboundRequest, link_of: Callable[[str], dict | None]) -> dict:
        key = self.cfg.polar_webhook_signature_key
        sig = req.header("polar-webhook-signature")
        body = json_any(req.raw_body)
        if not key or not sig or req.method.upper() != "POST" or not isinstance(body, dict):
            return reject()
        if not hex_equal(hmac.new(key.encode(), req.raw_body, hashlib.sha256).hexdigest(), sig):
            return reject()
        link = link_of(str(body.get("user_id"))) if body.get("user_id") is not None else None
        resolves = (
            {"connection_id": link["connection_id"], "account_link_subject": str(body["user_id"])} if link else None
        )
        return accept(body_hash(req.raw_body), resolves)

    def parse_inbound(self, req: InboundRequest) -> list[InboundEvent]:
        body = json_any(req.raw_body)
        if not isinstance(body, dict) or body.get("user_id") is None:
            return []  # a PING carries no user: acknowledged, nothing to do
        kind = EVENTS.get(str(body.get("event")))
        ts = base.when(body.get("timestamp")) or self.clock()
        if not kind:
            return []
        end = ts.date()
        return [InboundEvent("changed", str(body["user_id"]), [kind], end - timedelta(days=1), end)]
