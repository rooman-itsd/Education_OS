"""Microsoft Teams through Graph onlineMeetings: Rooman's multi-tenant Entra app with application permissions, admin
consent per tenant and an application access policy the tenant admin grants (docs/prd.md).

No real-time started/ended events exist: attendance reports appear after the meeting, and recordings and transcripts
arrive as Graph change notifications that need a subscription renewed every few days (<3). Notifications carry a
clientState (a per-subscription secret) and the subscription handshake is the validationToken echo."""

from __future__ import annotations

import re
import secrets
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlencode

from ...domain.context import Context
from ...domain.errors import AdapterError
from ...domain.models import CreateMeeting, UpdateMeeting
from ..crypto import client_state
from ..http import json_body, map_status, provider_code
from .base import (
    Created,
    InboundRequest,
    Participant,
    Provider,
    ProviderEvent,
    RecordingFile,
    Ref,
    accept,
    body_hash,
    count,
    handshake,
    json_object,
    parse_time,
    reject,
)

ROLE = {"organizer": "host", "presenter": "co_host", "attendee": "attendee", "producer": "co_host"}
TENANT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,127}$")  # a tenant id (GUID) or a verified domain
_TOKENS: dict[tuple[str, str], tuple[str, float]] = {}
POLICY_HELP = (
    "access_policy_missing: the tenant admin must run New-CsApplicationAccessPolicy and Grant-CsApplicationAccessPolicy "
    "for this app, then wait up to 30 minutes (docs/prd.md)"
)
MAX_SUBSCRIPTION = timedelta(days=3) - timedelta(minutes=5)  # Graph allows under 3 days for these resources
RESOURCE = "communications/onlineMeetings/getAllRecordings"
_ID = re.compile(r"^[A-Za-z0-9_\-=.:%@+]{1,512}$")


def _u(value: str) -> str:
    return quote(value, safe="@.-_")


def _fmt(d: datetime) -> str:
    return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.0000000Z")


def _tenant(ctx: Context) -> str:
    t = ctx.settings.get("tenant_id", "")
    if not isinstance(t, str) or not TENANT.match(t):
        raise AdapterError("not_configured", "the connection has no valid tenant_id")
    return t


class TeamsProvider(Provider):
    id = "teams"
    title = "Microsoft Teams"
    auth = "oauth2_client_credentials"
    inbound = ("webhook",)
    settings_schema = {
        "type": "object",
        "required": ["tenant_id"],
        "properties": {
            "tenant_id": {"type": "string", "maxLength": 128},
            "lobby_bypass_scope": {"enum": ["organization", "organizationAndFederated", "everyone", "invited"]},
        },
        "additionalProperties": False,
    }
    credential_names = ()
    platform_credential_names = ("TEAMS_CLIENT_ID", "TEAMS_CLIENT_SECRET")

    # --- plumbing
    def _token(self, ctx: Context) -> str:
        if not self.cfg.teams_client_id or not self.cfg.teams_client_secret:
            raise AdapterError("not_configured", "Rooman's Microsoft app credentials are not set")
        tenant = _tenant(ctx)
        key = (tenant, self.cfg.teams_client_id)
        cached = _TOKENS.get(key)
        if cached and cached[1] > time.time() + 60:
            return cached[0]
        r = self.http.send(
            "POST",
            f"{self.cfg.teams_login_base_url}/{quote(tenant, safe='')}/oauth2/v2.0/token",
            data={
                "client_id": self.cfg.teams_client_id,
                "client_secret": self.cfg.teams_client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
        )
        if r.status_code >= 500 or r.status_code == 429:
            raise map_status(r)
        if r.status_code >= 400:
            raise AdapterError(
                "auth_failed", "Microsoft refused the app credentials for this tenant", provider_code=provider_code(r)
            )
        body = json_body(r)
        token = body.get("access_token")
        if not isinstance(token, str) or not token:
            raise AdapterError("provider_error", "Microsoft's token answer has no access token")
        _TOKENS[key] = (token, time.time() + (count(body.get("expires_in")) or 3600))
        return token

    def _call(self, ctx: Context, method: str, path: str, *, host_lookup: bool = False, **kw) -> dict:
        r = self.http.send(
            method,
            f"{self.cfg.teams_graph_base_url}{path}",
            headers={"Authorization": f"Bearer {self._token(ctx)}"},
            **kw,
        )
        if r.status_code < 400:
            return json_body(r)
        if r.status_code == 403 and "application access policy" in r.text.lower():
            raise AdapterError("auth_failed", POLICY_HELP, provider_code="access_policy_missing")
        if r.status_code == 404 and host_lookup:
            raise AdapterError(
                "invalid_request",
                "host_not_licensed: the organiser is not a user of this tenant",
                provider_code=provider_code(r),
            )
        raise map_status(r)

    # --- meetings
    def _body(self, ctx: Context, title: str | None, starts: datetime | None, minutes: int | None, o) -> dict:
        b: dict[str, Any] = {}
        if title is not None:
            b["subject"] = title
        if starts is not None and minutes is not None:
            b["startDateTime"], b["endDateTime"] = _fmt(starts), _fmt(starts + timedelta(minutes=minutes))
        if o is not None:
            scope = ctx.settings.get("lobby_bypass_scope", "organization")
            b["lobbyBypassSettings"] = {
                "scope": "invited" if o.waiting_room and scope == "everyone" else scope,
                "isDialInBypassEnabled": False,
            }
            b["allowedPresenters"] = "organization"
            b["recordAutomatically"] = o.record == "cloud"
            b["joinMeetingIdSettings"] = {"isPasscodeRequired": True}
        return b

    def create(self, ctx: Context, spec: CreateMeeting, host_user: str) -> Created:
        body = self._body(ctx, spec.title, spec.starts_at, spec.duration_minutes, spec.options)
        if spec.co_hosts:
            body["participants"] = {"attendees": [{"upn": c.email, "role": "presenter"} for c in spec.co_hosts]}
        d = self._call(ctx, "POST", f"/users/{_u(host_user)}/onlineMeetings", json=body, host_lookup=True)
        if not d.get("id") or not d.get("joinWebUrl"):
            raise AdapterError("provider_error", "Graph's answer has no meeting id or link")
        info = d.get("audioConferencing") if isinstance(d.get("audioConferencing"), dict) else {}
        dial = (
            [{"number": str(info["tollNumber"])[:40], "conference_id": str(info.get("conferenceId", ""))[:20]}]
            if info.get("tollNumber")
            else []
        )
        passcode = (
            (d.get("joinMeetingIdSettings") or {}).get("passcode")
            if isinstance(d.get("joinMeetingIdSettings"), dict)
            else None
        )
        return Created(str(d["id"]), d["joinWebUrl"], None, passcode, dial, host_user_id=host_user)

    def update(self, ctx: Context, ref: Ref, change: UpdateMeeting, host_user: str | None) -> Created | None:
        starts = change.starts_at or ref.starts_at
        minutes = change.duration_minutes or ref.duration_minutes
        timing = change.starts_at is not None or change.duration_minutes is not None
        body = self._body(ctx, change.title, starts if timing else None, minutes if timing else None, change.options)
        if body:
            self._call(
                ctx,
                "PATCH",
                f"/users/{_u(str(ref.host_user_id))}/onlineMeetings/{_u(str(ref.provider_meeting_id))}",
                json=body,
            )
        return None

    def cancel(self, ctx: Context, ref: Ref) -> None:
        self._call(
            ctx, "DELETE", f"/users/{_u(str(ref.host_user_id))}/onlineMeetings/{_u(str(ref.provider_meeting_id))}"
        )

    def attendance(self, ctx: Context, ref: Ref) -> tuple[list[Participant], datetime | None]:
        base = f"/users/{_u(str(ref.host_user_id))}/onlineMeetings/{_u(str(ref.provider_meeting_id))}/attendanceReports"
        reports = [r for r in self._call(ctx, "GET", base).get("value", []) if isinstance(r, dict) and r.get("id")]
        if not reports:
            return [], None
        latest = sorted(reports, key=lambda r: str(r.get("meetingStartDateTime", "")))[-1]
        d = self._call(ctx, "GET", f"{base}/{_u(str(latest['id']))}", params={"$expand": "attendanceRecords"})
        people = []
        for rec in d.get("attendanceRecords", []):
            if not isinstance(rec, dict):
                continue
            ident = rec.get("identity") if isinstance(rec.get("identity"), dict) else {}
            intervals = [
                (parse_time(i.get("joinDateTime")), parse_time(i.get("leaveDateTime")))
                for i in rec.get("attendanceIntervals", [])
                if isinstance(i, dict)
            ]
            people.append(
                Participant(
                    (rec.get("emailAddress") or "").strip().lower() or None,
                    str(ident.get("displayName") or "")[:200] or None,
                    ROLE.get(str(rec.get("role", "")).lower(), "attendee"),
                    [(a, b) for a, b in intervals if a],
                    count(rec.get("totalAttendanceInSeconds")),
                )
            )
        return people, parse_time(d.get("meetingEndDateTime"))

    def _artifacts(self, ctx: Context, ref: Ref, name: str, kind: str, content_key: str) -> list[RecordingFile]:
        d = self._call(
            ctx, "GET", f"/users/{_u(str(ref.host_user_id))}/onlineMeetings/{_u(str(ref.provider_meeting_id))}/{name}"
        )
        return [
            RecordingFile(
                str(x["id"])[:256],
                kind,
                started_at=parse_time(x.get("createdDateTime")),
                download_url=x.get(content_key),
            )
            for x in d.get("value", [])
            if isinstance(x, dict) and x.get("id")
        ]

    def recordings(self, ctx: Context, ref: Ref) -> list[RecordingFile]:
        return self._artifacts(ctx, ref, "recordings", "video", "recordingContentUrl") + self._artifacts(
            ctx, ref, "transcripts", "transcript", "transcriptContentUrl"
        )

    def download(self, ctx: Context, ref: Ref, rec: RecordingFile) -> tuple[Iterator[bytes], Callable[[], None]]:
        name = "recordings" if rec.kind == "video" else "transcripts"
        url = (
            f"{self.cfg.teams_graph_base_url}/users/{_u(str(ref.host_user_id))}/onlineMeetings/"
            f"{_u(str(ref.provider_meeting_id))}/{name}/{_u(rec.provider_recording_id)}/content"
        )
        cm = self.http.stream(
            "GET", url, headers={"Authorization": f"Bearer {self._token(ctx)}"}, follow_redirects=True
        )
        response = cm.__enter__()
        if response.status_code >= 400:
            response.read()
            err = map_status(response)
            cm.__exit__(None, None, None)
            raise err
        return response.iter_bytes(65536), lambda: cm.__exit__(None, None, None)

    def healthcheck(self, ctx: Context) -> dict:
        _tenant(ctx)
        self._token(
            ctx
        )  # the token exchange is the cheap authenticated read; Graph has no meeting-free "who am I" for apps
        return {"status": "healthy", "detail": "Microsoft issued a token for the tenant", "expires_at": None}

    # --- authorisation: the tenant admin's consent; the app credentials are Rooman's
    def begin_authorisation(
        self, ctx: Context, state: str, code_challenge: str, redirect_uri: str, scope_hint: list
    ) -> str:
        if not self.cfg.teams_client_id:
            raise AdapterError("not_configured", "VIDEO_CONFERENCING_TEAMS_CLIENT_ID is not set")
        q = urlencode({"client_id": self.cfg.teams_client_id, "state": state, "redirect_uri": redirect_uri})
        return f"{self.cfg.teams_login_base_url}/{quote(_tenant(ctx), safe='')}/adminconsent?{q}"

    def complete_authorisation(self, ctx: Context, code: str, code_verifier: str, redirect_uri: str) -> dict:
        # Admin consent has no code: the hub passes the callback's `tenant` here. The consent shows in a token.
        if not TENANT.match(code or ""):
            raise AdapterError("invalid_request", "the consent callback names no valid tenant")
        probe = Context(**{**ctx.__dict__, "settings": {**ctx.settings, "tenant_id": code}})
        self._token(probe)
        return {
            "secrets": {},
            "provider_subject": code,
            "granted_scopes": ["OnlineMeetings.ReadWrite.All"],
            "expires_at": None,
        }

    def refresh_authorisation(self, ctx: Context) -> dict:
        return {"secrets": {}, "expires_at": None}  # client credentials: a token is fetched per use

    def revoke_authorisation(self, ctx: Context) -> bool:
        return False  # consent is withdrawn by the tenant admin in Entra; nothing to call

    # --- inbound
    def verify_inbound(self, ctx: Context | None, req: InboundRequest) -> dict:
        token = req.query.get("validationToken")
        if isinstance(token, list):
            token = token[0] if token else None
        if token is not None:
            if (
                not isinstance(token, str)
                or not 1 <= len(token) <= 2048
                or any(ord(c) < 32 or ord(c) == 127 for c in token)
            ):
                return reject(400)
            return handshake(token, "text/plain")
        body = json_object(req.raw_body)
        entries = body.get("value") if body else None
        if req.method.upper() != "POST" or not isinstance(entries, list) or not 1 <= len(entries) <= 200 or ctx is None:
            return reject()
        for n in entries:
            if (
                not isinstance(n, dict)
                or not isinstance(n.get("subscriptionId"), str)
                or not isinstance(n.get("clientState"), str)
            ):
                return reject()
        # Only the shape is judged here. Each notification's clientState is compared with the one derived from its
        # subscription's stored nonce by the adapter (application/adapter.py, _graph_state_ok), which owns the table.
        return accept(body_hash(req.raw_body), ack_status=202)

    def parse_inbound(self, ctx: Context | None, req: InboundRequest) -> list[ProviderEvent]:
        body = json_object(req.raw_body) or {}
        out: list[ProviderEvent] = []
        for n in body.get("value", [])[:200] if isinstance(body.get("value"), list) else []:
            if not isinstance(n, dict):
                continue
            life = n.get("lifecycleEvent")
            sub = n.get("subscriptionId") if isinstance(n.get("subscriptionId"), str) else None
            if life in ("reauthorizationRequired",):
                out.append(ProviderEvent("subscription_renew", subscription_id=sub))
            elif life in ("subscriptionRemoved", "missed"):
                out.append(ProviderEvent("subscription_recreate", subscription_id=sub))
            elif n.get("changeType") == "created" and isinstance(n.get("resource"), str):
                m = re.search(
                    r"onlineMeetings\('?([^')/]+)'?\)/(recordings|transcripts)\('?([^')/]+)'?\)", n["resource"]
                )
                if m and _ID.match(m[1]) and _ID.match(m[3]):
                    out.append(
                        ProviderEvent(
                            "recording_ready",
                            m[1],
                            recording_id=m[3],
                            recording_kind="video" if m[2] == "recordings" else "transcript",
                            subscription_id=sub,
                        )
                    )
        return out

    # --- the recordings subscription
    def ensure_subscription(self, ctx: Context, existing: Any) -> Any:
        """Create (existing is None) or renew (existing is a row with subscription_id and nonce) the subscription.
        Returns {subscription_id, expires_at, resource, nonce}."""
        if not self.cfg.public_base_url:
            raise AdapterError("not_configured", "VIDEO_CONFERENCING_PUBLIC_BASE_URL is not set")
        expires = self.clock() + MAX_SUBSCRIPTION
        if existing is not None:
            self._call(
                ctx,
                "PATCH",
                f"/subscriptions/{_u(existing['subscription_id'])}",
                json={"expirationDateTime": _fmt(expires)},
            )
            return {**existing, "expires_at": expires}
        nonce = secrets.token_hex(16)
        url = f"{self.cfg.public_base_url}/api/v1/integration-hub/inbound/video-conferencing/{ctx.settings.get('connection_key', ctx.connection_id)}"
        d = self._call(
            ctx,
            "POST",
            "/subscriptions",
            json={
                "changeType": "created",
                "notificationUrl": url,
                "lifecycleNotificationUrl": url,
                "resource": RESOURCE,
                "expirationDateTime": _fmt(expires),
                "clientState": client_state(self.cfg, ctx.connection_id, nonce),
                "latestSupportedTlsVersion": "v1_2",
            },
        )
        if not d.get("id"):
            raise AdapterError("provider_error", "Graph's subscription answer has no id")
        return {"subscription_id": str(d["id"]), "expires_at": expires, "resource": RESOURCE, "nonce": nonce}
