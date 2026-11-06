"""Zoom: Rooman's Marketplace OAuth app (account-level), or an institution's own Server-to-Server app.

Create, change and cancel a meeting (`/users/{userId}/meetings`, `/meetings/{id}`), attendance from
`/past_meetings/{uuid}/participants`, recordings from `/meetings/{id}/recordings`, and the event webhooks signed with
x-zm-signature, including the endpoint.url_validation handshake. docs/prd.md lists the sources and what is not verified."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from ...domain.context import Context
from ...domain.errors import AdapterError
from ...domain.models import CreateMeeting, UpdateMeeting
from ..http import json_body, map_status, provider_code, seconds_until_midnight_utc
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
    hex_equal,
    json_object,
    parse_time,
    reject,
)

# Zoom's own machine codes (https://developers.zoom.us/docs/api/meetings/ error tables).
USER_NOT_FOUND = {"1001", "1120"}
MEETING_NOT_FOUND = {"3001"}
KIND = {"MP4": "video", "M4A": "audio", "TRANSCRIPT": "transcript", "CC": "transcript", "CHAT": "chat"}
_TOKENS: dict[tuple[str, str], tuple[str, float]] = {}  # (account, client id) -> (access token, expiry); memory only


def _uuid_path(value: str) -> str:
    """Zoom wants a meeting uuid that begins with / or contains // double-encoded in a path."""
    once = quote(value, safe="")
    return quote(once, safe="") if value.startswith("/") or "//" in value else once


def _fmt(d: datetime) -> str:
    return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class ZoomProvider(Provider):
    id = "zoom"
    title = "Zoom"
    auth = "oauth2_authorization_code"
    inbound = ("webhook",)
    settings_schema = {
        "type": "object",
        "properties": {
            "account_id": {"type": "string", "maxLength": 64},
            "host_resolution": {"enum": ["email", "pool"]},
            "host_pool": {"type": "array", "items": {"type": "string", "maxLength": 256}, "maxItems": 50},
        },
        "additionalProperties": False,
    }
    credential_names = ("access_token", "refresh_token", "client_id", "client_secret", "webhook_secret_token")
    platform_credential_names = ("ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET", "ZOOM_WEBHOOK_SECRET_TOKEN")

    # --- plumbing
    def _basic(self, ctx: Context | None) -> str:
        cid = (ctx.secrets.get("client_id") if ctx else None) or self.cfg.zoom_client_id
        sec = (ctx.secrets.get("client_secret") if ctx else None) or self.cfg.zoom_client_secret
        if not cid or not sec:
            raise AdapterError("not_configured", "Zoom client credentials are not set")
        return "Basic " + base64.b64encode(f"{cid}:{sec}".encode()).decode()

    def _token(self, ctx: Context) -> str:
        if ctx.secrets.get("access_token"):
            return ctx.secrets["access_token"]
        # An institution's own Server-to-Server app: client credentials on its connection, an hour-long token, no refresh.
        if ctx.secrets.get("client_id") and ctx.secrets.get("client_secret") and ctx.settings.get("account_id"):
            account = str(ctx.settings["account_id"])
            key = (account, ctx.secrets["client_id"])
            cached = _TOKENS.get(key)
            if cached and cached[1] > time.time() + 30:
                return cached[0]
            r = self.http.send(
                "POST",
                f"{self.cfg.zoom_oauth_base_url}/token?"
                + urlencode({"grant_type": "account_credentials", "account_id": account}),
                headers={"Authorization": self._basic(ctx)},
            )
            if r.status_code >= 400:
                raise AdapterError(
                    "auth_failed", "Zoom refused the Server-to-Server credentials", provider_code=provider_code(r)
                )
            body = json_body(r)
            token = body.get("access_token")
            if not isinstance(token, str) or not token:
                raise AdapterError("provider_error", "Zoom's token answer has no access token")
            _TOKENS[key] = (token, time.time() + int(count(body.get("expires_in")) or 3600))
            return token
        raise AdapterError("auth_failed", "the connection has no Zoom token: authorise it again")

    def _call(self, ctx: Context, method: str, path: str, **kw) -> dict:
        r = self.http.send(
            method, f"{self.cfg.zoom_api_base_url}{path}", headers={"Authorization": f"Bearer {self._token(ctx)}"}, **kw
        )
        if r.status_code < 400:
            return json_body(r)
        code = provider_code(r)
        if code in USER_NOT_FOUND:
            raise AdapterError(
                "invalid_request", "host_not_licensed: the host is not a Zoom user of this account", provider_code=code
            )
        if code in MEETING_NOT_FOUND:
            raise AdapterError("not_found", "Zoom has no such meeting", provider_code=code)
        err = map_status(r)
        if err.code == "throttled" and err.retry_after_s is None:
            # Zoom's daily create/update limit resets at 00:00 UTC; a per-second limit clears within the minute.
            text = r.text.lower()
            err.retry_after_s = seconds_until_midnight_utc(self.clock()) if "day" in text else 60
        raise err

    # --- meetings
    def _settings(self, o, co_hosts: list[str], host_email: str | None) -> dict:
        s: dict[str, Any] = {
            "waiting_room": o.waiting_room,
            "join_before_host": o.join_before_host,
            "auto_recording": o.record,
            "meeting_authentication": o.authenticated_join_only,
            "participant_video": False,
        }
        alt = [e for e in [*co_hosts, host_email] if e]
        if alt:
            s["alternative_hosts"] = ";".join(dict.fromkeys(alt))
        if o.auto_admit_domain:
            s["authentication_domains"] = o.auto_admit_domain
        return s

    def create(self, ctx: Context, spec: CreateMeeting, host_user: str) -> Created:
        body = {
            "topic": spec.title,
            "type": 2,
            "start_time": _fmt(spec.starts_at),
            "duration": spec.duration_minutes,
            "timezone": spec.timezone,
            "settings": self._settings(
                spec.options,
                [c.email for c in spec.co_hosts],
                # Created under a pooled user: the real host becomes alternative host and can start it.
                spec.host.email if host_user != (spec.host.provider_user_id or spec.host.email) else None,
            ),
        }
        d = self._call(ctx, "POST", f"/users/{quote(host_user, safe='@')}/meetings", json=body)
        if not d.get("id") or not d.get("join_url"):
            raise AdapterError("provider_error", "Zoom's answer has no meeting id or link")
        dial = [
            {"number": str(n.get("number", ""))[:40], "country": str(n.get("country_name", ""))[:80]}
            for n in (d.get("settings") or {}).get("global_dial_in_numbers", [])[:20]
            if isinstance(n, dict)
        ]
        return Created(
            provider_meeting_id=str(d["id"]),
            join_url=d["join_url"],
            host_join_url=d.get("start_url"),
            passcode=d.get("password") or None,
            dial_in=dial,
            host_user_id=host_user,
        )

    def update(self, ctx: Context, ref: Ref, change: UpdateMeeting, host_user: str | None) -> Created | None:
        body: dict[str, Any] = {}
        if change.title is not None:
            body["topic"] = change.title
        if change.starts_at is not None:
            body["start_time"] = _fmt(change.starts_at)
        if change.duration_minutes is not None:
            body["duration"] = change.duration_minutes
        settings: dict[str, Any] = {}
        if change.options is not None:
            settings.update(self._settings(change.options, [], None))
        if change.host is not None and change.host.email:
            settings["alternative_hosts"] = (
                change.host.email
            )  # Zoom cannot move ownership; the new host is its alternative
        if settings:
            body["settings"] = settings
        if body:
            self._call(ctx, "PATCH", f"/meetings/{quote(str(ref.provider_meeting_id), safe='')}", json=body)
        return None  # Zoom keeps the join and start links

    def cancel(self, ctx: Context, ref: Ref) -> None:
        self._call(
            ctx,
            "DELETE",
            f"/meetings/{quote(str(ref.provider_meeting_id), safe='')}",
            params={"schedule_for_reminder": "false", "cancel_meeting_reminder": "false"},
        )

    def _instance(self, ctx: Context, ref: Ref) -> str:
        if ref.instance_id:
            return ref.instance_id
        d = self._call(ctx, "GET", f"/past_meetings/{quote(str(ref.provider_meeting_id), safe='')}/instances")
        items = [m for m in d.get("meetings", []) if isinstance(m, dict) and isinstance(m.get("uuid"), str)]
        if not items:
            raise AdapterError("not_found", "Zoom has no past instance of this meeting yet")
        return sorted(items, key=lambda m: str(m.get("start_time", "")))[-1]["uuid"]

    def attendance(self, ctx: Context, ref: Ref) -> tuple[list[Participant], datetime | None]:
        uuid = self._instance(ctx, ref)
        rows: list[dict] = []
        token = ""
        for _ in range(50):  # 50 pages of 300 is far beyond any class; a runaway token chain ends here
            q = {"page_size": "300", **({"next_page_token": token} if token else {})}
            d = self._call(ctx, "GET", f"/past_meetings/{_uuid_path(uuid)}/participants", params=q)
            rows += [r for r in d.get("participants", []) if isinstance(r, dict)]
            token = d.get("next_page_token") or ""
            if not token:
                break
        merged: dict[str, Participant] = {}
        for r in rows:  # one person who rejoined appears once per join: fold them into one participant
            email = (r.get("user_email") or "").strip().lower() or None
            name = (r.get("name") or "").strip()[:200] or None
            key = email or f"{r.get('id') or ''}|{name}"
            join, leave = parse_time(r.get("join_time")), parse_time(r.get("leave_time"))
            p = merged.setdefault(key, Participant(email, name, "attendee", []))
            if join:
                p.intervals.append((join, leave))
            p.total_seconds = (p.total_seconds or 0) + (count(r.get("duration")) or 0)
            if r.get("user_email") and r.get("role") in ("host",):
                p.role = "host"
        return list(merged.values()), None

    def recordings(self, ctx: Context, ref: Ref) -> list[RecordingFile]:
        d = self._call(ctx, "GET", f"/meetings/{quote(str(ref.provider_meeting_id), safe='')}/recordings")
        out = []
        for f in d.get("recording_files", []):
            if not isinstance(f, dict) or not f.get("id") or f.get("status", "completed") != "completed":
                continue
            out.append(
                RecordingFile(
                    provider_recording_id=str(f["id"])[:256],
                    kind=KIND.get(str(f.get("file_type", "")).upper(), "video"),
                    started_at=parse_time(f.get("recording_start")),
                    ended_at=parse_time(f.get("recording_end")),
                    bytes=count(f.get("file_size")),
                    download_url=f.get("download_url") if isinstance(f.get("download_url"), str) else None,
                )
            )
        return out

    def download(self, ctx: Context, ref: Ref, rec: RecordingFile) -> tuple[Iterator[bytes], Callable[[], None]]:
        if not rec.download_url or not rec.download_url.startswith(("https://", "http://")):
            raise AdapterError("not_found", "the recording has no download link")
        host = httpx.URL(rec.download_url).host
        # The bearer token goes only to Zoom (or to the test server a plain-http API base URL names).
        if not any(
            host == d or host.endswith("." + d) for d in ("zoom.us", "zoom.com")
        ) and not self.cfg.zoom_api_base_url.startswith("http://"):
            raise AdapterError("invalid_request", "the recording link is not on a Zoom host")
        cm = self.http.stream("GET", rec.download_url, headers={"Authorization": f"Bearer {self._token(ctx)}"})
        response = cm.__enter__()
        if response.status_code >= 400:
            response.read()
            err = map_status(response)
            cm.__exit__(None, None, None)
            raise err
        return response.iter_bytes(65536), lambda: cm.__exit__(None, None, None)

    def healthcheck(self, ctx: Context) -> dict:
        d = self._call(ctx, "GET", "/users/me")
        return {
            "status": "healthy",
            "detail": "Zoom answered /users/me",
            "expires_at": None,
            "account": d.get("account_id"),
        }

    # --- authorisation (Marketplace OAuth app, authorisation code with PKCE)
    def begin_authorisation(
        self, ctx: Context, state: str, code_challenge: str, redirect_uri: str, scope_hint: list
    ) -> str:
        if not self.cfg.zoom_client_id:
            raise AdapterError("not_configured", "VIDEO_CONFERENCING_ZOOM_CLIENT_ID is not set")
        q = {
            "response_type": "code",
            "client_id": self.cfg.zoom_client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.cfg.zoom_oauth_base_url}/authorize?{urlencode(q)}"

    def _tokens(self, form: dict, ctx: Context) -> dict:
        r = self.http.send(
            "POST", f"{self.cfg.zoom_oauth_base_url}/token", data=form, headers={"Authorization": self._basic(None)}
        )
        if r.status_code >= 500 or r.status_code == 429:
            raise map_status(r)
        if r.status_code >= 400:
            raise AdapterError(
                "auth_failed", "Zoom refused the code or the refresh token", provider_code=provider_code(r)
            )
        body = json_body(r)
        if not isinstance(body.get("access_token"), str):
            raise AdapterError("provider_error", "Zoom's token answer has no access token")
        secrets = {"access_token": body["access_token"]}
        if isinstance(body.get("refresh_token"), str):
            secrets["refresh_token"] = body["refresh_token"]
        ttl = count(body.get("expires_in")) or 3600
        return {
            "secrets": secrets,
            "expires_at": (self.clock() + timedelta(seconds=ttl)).isoformat(),
            "granted_scopes": str(body.get("scope", "")).split()[:100],
        }

    def complete_authorisation(self, ctx: Context, code: str, code_verifier: str, redirect_uri: str) -> dict:
        out = self._tokens(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
            ctx,
        )
        who = self._call(Context(**{**ctx.__dict__, "secrets": out["secrets"]}), "GET", "/users/me")
        out["provider_subject"] = str(who.get("account_id") or who.get("id") or "")
        return out

    def refresh_authorisation(self, ctx: Context) -> dict:
        if not ctx.secrets.get("refresh_token"):
            raise AdapterError("auth_failed", "the connection has no refresh token: authorise it again")
        out = self._tokens({"grant_type": "refresh_token", "refresh_token": ctx.secrets["refresh_token"]}, ctx)
        return {"secrets": out["secrets"], "expires_at": out["expires_at"]}

    def revoke_authorisation(self, ctx: Context) -> bool:
        token = ctx.secrets.get("access_token")
        if not token:
            return False
        r = self.http.send(
            "POST",
            f"{self.cfg.zoom_oauth_base_url}/revoke",
            data={"token": token},
            headers={"Authorization": self._basic(None)},
        )
        if r.status_code >= 500 or r.status_code == 429:
            raise map_status(r)
        return r.status_code < 400

    # --- inbound
    def _secret(self, ctx: Context | None) -> str:
        return (ctx.secrets.get("webhook_secret_token") if ctx else None) or self.cfg.zoom_webhook_secret_token

    def verify_inbound(self, ctx: Context | None, req: InboundRequest) -> dict:
        secret = self._secret(ctx)
        body = json_object(req.raw_body)
        if not secret or body is None or req.method.upper() != "POST":
            return reject()
        if body.get("event") == "endpoint.url_validation":
            plain = (body.get("payload") or {}).get("plainToken")
            if not isinstance(plain, str) or not 1 <= len(plain) <= 256:
                return reject(400)
            enc = hmac.new(secret.encode(), plain.encode(), hashlib.sha256).hexdigest()
            return handshake(json.dumps({"plainToken": plain, "encryptedToken": enc}), "application/json")
        ts = req.header("x-zm-request-timestamp")
        sig = req.header("x-zm-signature")
        if not ts.isdigit() or len(ts) > 12 or not sig.startswith("v0="):
            return reject()
        if abs(self.clock().timestamp() - int(ts)) > self.cfg.webhook_tolerance_s:
            return reject()
        want = "v0=" + hmac.new(secret.encode(), b"v0:" + ts.encode() + b":" + req.raw_body, hashlib.sha256).hexdigest()
        if not hex_equal(want, sig):
            return reject()
        payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
        obj = payload.get("object") if isinstance(payload.get("object"), dict) else {}
        # An app-level URL serves every institution that authorised Rooman's app: the account names the tenant, and
        # the meeting we created names the connection (the adapter resolves it from its own table).
        resolves = {"account_link_subject": str(payload["account_id"])[:64]} if payload.get("account_id") else None
        if resolves is not None and obj.get("id") is not None:
            resolves["provider_meeting_id"] = str(obj["id"])[:64]
        return accept(body_hash(req.raw_body), resolves_to=resolves)

    def parse_inbound(self, ctx: Context | None, req: InboundRequest) -> list[ProviderEvent]:
        body = json_object(req.raw_body) or {}
        event = body.get("event")
        payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
        obj = payload.get("object") if isinstance(payload.get("object"), dict) else {}
        mid = str(obj["id"]) if obj.get("id") is not None else None
        uuid = obj.get("uuid") if isinstance(obj.get("uuid"), str) else None
        ts = count(body.get("event_ts"))
        at = datetime.fromtimestamp(ts / 1000, UTC) if ts and ts < 4_102_444_800_000 else None
        if not mid:
            return []
        if event == "meeting.started":
            return [ProviderEvent("started", mid, uuid, parse_time(obj.get("start_time")) or at)]
        if event == "meeting.ended":
            return [ProviderEvent("ended", mid, uuid, parse_time(obj.get("end_time")) or at)]
        if event == "meeting.deleted":
            return [ProviderEvent("deleted", mid, uuid, at)]
        if event == "recording.completed":
            return [
                ProviderEvent(
                    "recording_ready",
                    mid,
                    uuid,
                    at,
                    recording_id=str(f["id"])[:256],
                    recording_kind=KIND.get(str(f.get("file_type", "")).upper(), "video"),
                )
                for f in obj.get("recording_files", [])
                if isinstance(f, dict) and f.get("id")
            ]
        # meeting.participant_joined / _left: the adapter has no directory to turn a Zoom participant into a person
        # id, so these are acknowledged and left to the attendance report (docs: contract deviations).
        return []
