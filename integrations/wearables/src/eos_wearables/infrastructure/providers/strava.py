"""Strava API v3: OAuth 2.0 (scope activity:read_all), activities, and the push subscription.

Strava sends **no signature** on its events. The draft's mitigation, applied here: an event is accepted only when its
subscription_id is ours and its owner_id is an athlete with an active link; nothing in the body is trusted (the event only
says "something changed": the activity is fetched afterwards with the athlete's own token); and a deauthorisation arrives as
an athlete update with `authorized: false`. Strava data is shown only to its athlete (display_to_others_allowed is false).

Rate limits are per app (200 per 15 minutes, 2,000 per day; non-upload reads 100 and 1,000): the gate below stops calling
when a response says the window is used up, and answers throttled until it resets (:00, :15, :30, :45, and midnight UTC)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from urllib.parse import urlencode

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
    const_equal,
    handshake,
    json_any,
    num,
    reject,
    text,
)
from .oauth import token_call

SCOPE = "activity:read_all"
KJ_TO_KCAL = 0.239006
CHALLENGE = re.compile(r"^[A-Za-z0-9._~\-]{1,256}$")
_BLOCKED: dict[str, datetime] = {}  # until when Strava's window is used up (memory only; a restart just asks once more)


def next_window(now: datetime) -> datetime:
    """The next :00, :15, :30 or :45."""
    now = now.astimezone(UTC)
    minute = (now.minute // 15 + 1) * 15
    base_ = now.replace(minute=0, second=0, microsecond=0)
    return base_ + timedelta(minutes=minute)


def next_midnight(now: datetime) -> datetime:
    return datetime.combine(now.astimezone(UTC).date() + timedelta(days=1), time(0), tzinfo=UTC)


def _pair(value: str) -> tuple[int, int] | None:
    parts = value.split(",")
    if len(parts) != 2 or not all(p.strip().isdigit() for p in parts):
        return None
    return int(parts[0]), int(parts[1])


class StravaProvider(Provider):
    id = "strava"
    title = "Strava"
    data_types = ("activity",)
    inbound = ("webhook",)
    rate_limit = "200 per 15 min, 2000 per day per app (non-upload reads 100 and 1000)"
    display_to_others_allowed = False
    backfill_mode = "pull"
    platform_credential_names = (
        "STRAVA_CLIENT_ID",
        "STRAVA_CLIENT_SECRET",
        "STRAVA_VERIFY_TOKEN",
        "STRAVA_SUBSCRIPTION_ID",
    )

    def capabilities(self, ctx: Context | None) -> dict:
        caps = super().capabilities(ctx)
        caps["backfill_days"] = 90  # pulled from the activity list, within the app's rate limit
        return caps

    # --- plumbing
    def _gate(self) -> None:
        until = _BLOCKED.get(self.id)
        now = self.clock()
        if until and until > now:
            raise AdapterError(
                "throttled",
                "Strava's rate-limit window is used up",
                provider_code="strava_window",
                retry_after_s=max(1, int((until - now).total_seconds())),
            )

    def _note_usage(self, r) -> None:
        """Record a used-up window from the usage headers, so the next call is held back without being sent."""
        limit = _pair(r.headers.get("x-readratelimit-limit") or r.headers.get("x-ratelimit-limit") or "")
        usage = _pair(r.headers.get("x-readratelimit-usage") or r.headers.get("x-ratelimit-usage") or "")
        now = self.clock()
        if limit and usage:
            if usage[1] >= limit[1]:
                _BLOCKED[self.id] = next_midnight(now)
            elif usage[0] >= limit[0]:
                _BLOCKED[self.id] = next_window(now)

    def _call(self, ctx: Context, path: str, params: dict | None = None) -> list | dict:
        token = ctx.secrets.get("access_token")
        if not token:
            raise AdapterError("consent_required", "the athlete's Strava link has no token: it must be linked again")
        self._gate()
        r = self.http.send(
            "GET",
            f"{self.cfg.strava_api_base_url}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
        )
        self._note_usage(r)
        if r.status_code == 429:
            now = self.clock()
            until = _BLOCKED.get(self.id)  # the usage headers may already say the day is spent
            if until is None or until <= now:
                until = _BLOCKED[self.id] = next_window(now)
            raise AdapterError(
                "throttled",
                "Strava rate-limited the call",
                provider_code="429",
                retry_after_s=max(1, int((until - now).total_seconds())),
            )
        if r.status_code == 401:
            raise AdapterError("consent_required", "Strava no longer accepts the athlete's token", provider_code="401")
        if r.status_code == 403:
            raise AdapterError(
                "consent_required", "the athlete did not grant this data to the app", provider_code="403"
            )
        if r.status_code >= 400:
            raise map_status(r)
        if r.status_code == 204 or not r.content:
            return []
        try:
            data = r.json()
        except ValueError as e:
            raise AdapterError("provider_error", "Strava answered with something that is not JSON") from e
        if not isinstance(data, (list, dict)):
            raise AdapterError("provider_error", "Strava answered with an unexpected shape")
        return data

    # --- authorisation
    def begin_authorisation(
        self, ctx: Context, state: str, code_challenge: str, redirect_uri: str, scope_hint: list
    ) -> str:
        if not self.cfg.strava_client_id:
            raise AdapterError("not_configured", "WEARABLES_STRAVA_CLIENT_ID is not set")
        q = {
            "client_id": self.cfg.strava_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "approval_prompt": "auto",
            "scope": SCOPE,
            "state": state,
        }
        return f"{self.cfg.strava_authorize_url}?{urlencode(q)}"  # Strava has no PKCE: code_challenge is not used

    def _tokens(self, form: dict) -> dict:
        if not self.cfg.strava_client_id or not self.cfg.strava_client_secret:
            raise AdapterError("not_configured", "Strava client credentials are not set")
        full = {"client_id": self.cfg.strava_client_id, "client_secret": self.cfg.strava_client_secret, **form}
        return token_call(self.http, self.cfg.strava_token_url, full, self.clock(), default_ttl=21600)

    def complete_authorisation(self, ctx: Context, code: str, code_verifier: str, redirect_uri: str) -> dict:
        out = self._tokens({"code": code, "grant_type": "authorization_code"})
        athlete = out["raw"].get("athlete") if isinstance(out["raw"].get("athlete"), dict) else {}
        subject = text(athlete.get("id"), 40)
        if not subject:
            raise AdapterError("provider_error", "Strava's token answer names no athlete")
        scopes = out["granted_scopes"] or [SCOPE]
        if SCOPE not in scopes:
            raise AdapterError("consent_required", "the athlete did not grant activity:read_all")
        return {
            "secrets": out["secrets"],
            "provider_subject": subject,
            "granted_scopes": scopes,
            "expires_at": out["expires_at"],
        }

    def refresh_authorisation(self, ctx: Context) -> dict:
        if not ctx.secrets.get("refresh_token"):
            raise AdapterError("consent_required", "the athlete's Strava link has no refresh token")
        try:
            out = self._tokens({"grant_type": "refresh_token", "refresh_token": ctx.secrets["refresh_token"]})
        except AdapterError as e:
            if e.code == "auth_failed":
                raise AdapterError(
                    "consent_required",
                    "Strava refused the refresh token: the athlete must link again",
                    provider_code=e.provider_code,
                ) from e
            raise
        return {"secrets": out["secrets"], "expires_at": out["expires_at"]}

    def revoke_authorisation(self, ctx: Context) -> bool:
        token = ctx.secrets.get("access_token")
        if not token:
            return False
        r = self.http.send("POST", self.cfg.strava_deauthorize_url, data={"access_token": token})
        if r.status_code >= 500 or r.status_code == 429:
            raise map_status(r)
        return r.status_code < 400

    # --- data
    def pull(self, ctx: Context, data_type: str, start: date, end: date) -> list[Normal]:
        if data_type != "activity":
            raise AdapterError(
                "unsupported", "Strava has activities only: no daily summaries, sleep, HRV or body composition"
            )
        after = int(datetime.combine(start, time(0), tzinfo=UTC).timestamp())
        before = int(datetime.combine(end + timedelta(days=1), time(0), tzinfo=UTC).timestamp())
        out: list[Normal] = []
        for page in range(1, 11):  # ten pages of 100 is far beyond any athlete's week; the chain ends here
            items = self._call(
                ctx, "/athlete/activities", {"after": after, "before": before, "per_page": 100, "page": page}
            )
            if not isinstance(items, list):
                raise AdapterError("provider_error", "Strava's activity list is not a list")
            for a in items:
                rec = self.normalise(a) if isinstance(a, dict) else None
                if rec:
                    out.append(rec)
            if len(items) < 100:
                break
        return out

    @staticmethod
    def normalise(a: dict) -> Normal | None:
        rid = text(a.get("id"), 40)
        started = base.when(a.get("start_date"))
        if not rid or started is None:
            return None
        kj = num(a.get("kilojoules"))
        calories = num(a.get("calories"))
        return base.activity(
            rid, "strava", started,
            sport=(text(a.get("sport_type") or a.get("type"), 40) or "other").lower(),
            duration_s=base.integer(a.get("moving_time") or a.get("elapsed_time"), 1e7),
            distance_m=num(a.get("distance"), 1e8),
            kcal=calories if calories is not None else (round(kj * KJ_TO_KCAL, 1) if kj is not None else None),
            avg_hr_bpm=base.integer(a.get("average_heartrate"), 300),
            max_hr_bpm=base.integer(a.get("max_heartrate"), 300),
            training_load=num(a.get("suffer_score")),
        )  # fmt: skip

    # --- inbound
    def verify_inbound(self, req: InboundRequest, link_of: Callable[[str], dict | None]) -> dict:
        verify = self.cfg.strava_verify_token
        sub_id = self.cfg.strava_subscription_id
        if req.method.upper() == "GET":
            challenge, token = req.q("hub.challenge"), req.q("hub.verify_token")
            if not verify or req.q("hub.mode") != "subscribe" or not token or not const_equal(token, verify):
                return reject(403)
            if not CHALLENGE.match(challenge):
                return reject(400)
            return handshake(json.dumps({"hub.challenge": challenge}))
        body = json_any(req.raw_body)
        if req.method.upper() != "POST" or not isinstance(body, dict) or not sub_id:
            return reject()
        # No signature exists, so identity is established by what only Strava and our own records can tell:
        if str(body.get("subscription_id")) != sub_id or body.get("object_type") not in ("activity", "athlete"):
            return reject()
        owner = body.get("owner_id")
        if (
            isinstance(owner, bool)
            or not isinstance(owner, (int, str))
            or not str(owner).isdigit()
            or len(str(owner)) > 20
        ):
            return reject()
        link = link_of(str(owner))
        if link is None:
            return reject()
        key = f"strava:{sub_id}:{body.get('object_type')}:{text(body.get('object_id'), 40)}:{text(body.get('aspect_type'), 10)}:{text(body.get('event_time'), 20)}"
        return accept(key, {"connection_id": link["connection_id"], "account_link_subject": str(owner)})

    def parse_inbound(self, req: InboundRequest) -> list[InboundEvent]:
        body = json_any(req.raw_body)
        if not isinstance(body, dict) or not isinstance(body.get("owner_id"), (int, str)):
            return []
        subject, aspect = str(body["owner_id"]), body.get("aspect_type")
        if body.get("object_type") == "athlete":
            updates = body.get("updates") if isinstance(body.get("updates"), dict) else {}
            if aspect == "update" and str(updates.get("authorized")).lower() == "false":
                return [InboundEvent("revoked", subject)]
            return []
        oid = text(body.get("object_id"), 40)
        if not oid:
            return []
        if aspect == "delete":
            return [InboundEvent("deleted", subject, ["activity"], record_ids=[oid])]
        if aspect in ("create", "update"):
            ts = base.when(body.get("event_time")) or self.clock()
            # The event names no date for the activity: the window is the week before it, fetched with the athlete's token.
            return [InboundEvent("changed", subject, ["activity"], ts.date() - timedelta(days=7), ts.date())]
        return []
