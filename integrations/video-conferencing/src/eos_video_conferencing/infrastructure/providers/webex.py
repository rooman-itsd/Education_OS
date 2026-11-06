"""Webex: Rooman's Webex integration (OAuth, an org admin who is also a site admin authorises the meeting scopes).

`/meetings` create, change and cancel; `/meetingParticipants` for attendance; `/recordings`; webhooks signed with
X-Webex-Signature (HMAC-SHA256) or the older X-Spark-Signature (HMAC-SHA1) over the raw body. docs/prd.md says what
is not verified for Webex (endpoint details and event names): each is checked when the adapter meets the real service."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from urllib.parse import quote, urlencode

from ...domain.context import Context
from ...domain.errors import AdapterError
from ...domain.models import CreateMeeting, UpdateMeeting
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
    hex_equal,
    json_object,
    parse_time,
    reject,
)

KIND = {"MP4": "video", "ARF": "video", "MP3": "audio", "M4A": "audio", "VTT": "transcript", "TXT": "transcript"}


def _fmt(d: datetime) -> str:
    return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def series_of(meeting_id: str) -> str:
    """A Webex instance id is "<series id>_I_<n>"; the series is what create returned."""
    return meeting_id.split("_I_", 1)[0]


class WebexProvider(Provider):
    id = "webex"
    title = "Webex"
    auth = "oauth2_authorization_code"
    inbound = ("webhook",)
    settings_schema = {
        "type": "object",
        "properties": {
            "site_url": {"type": "string", "maxLength": 200},
            "connection_key": {"type": "string", "maxLength": 64},
        },
        "additionalProperties": False,
    }
    credential_names = ("access_token", "refresh_token", "webhook_secret")
    platform_credential_names = ("WEBEX_CLIENT_ID", "WEBEX_CLIENT_SECRET")

    def _token(self, ctx: Context) -> str:
        if not ctx.secrets.get("access_token"):
            raise AdapterError("auth_failed", "the connection has no Webex token: authorise it again")
        return ctx.secrets["access_token"]

    def _call(self, ctx: Context, method: str, path: str, **kw) -> dict:
        r = self.http.send(
            method,
            f"{self.cfg.webex_api_base_url}{path}",
            headers={"Authorization": f"Bearer {self._token(ctx)}"},
            **kw,
        )
        if r.status_code < 400:
            return json_body(r)
        if r.status_code == 400 and "host" in r.text.lower() and "email" in r.text.lower():
            raise AdapterError(
                "invalid_request",
                "host_not_licensed: the host is not a Webex user of this site",
                provider_code=provider_code(r),
            )
        raise map_status(r)

    # --- meetings
    def create(self, ctx: Context, spec: CreateMeeting, host_user: str) -> Created:
        body = {
            "title": spec.title,
            "start": _fmt(spec.starts_at),
            "end": _fmt(spec.starts_at + timedelta(minutes=spec.duration_minutes)),
            "timezone": spec.timezone,
            "hostEmail": host_user,
            "enabledAutoRecordMeeting": spec.options.record == "cloud",
            "enabledJoinBeforeHost": spec.options.join_before_host,
            "enableAutomaticLock": spec.options.waiting_room,
            "sendEmail": False,
            "invitees": [{"email": c.email, "coHost": True} for c in spec.co_hosts],
        }
        if ctx.settings.get("site_url"):
            body["siteUrl"] = str(ctx.settings["site_url"])
        d = self._call(ctx, "POST", "/meetings", json=body)
        if not d.get("id") or not d.get("webLink"):
            raise AdapterError("provider_error", "Webex's answer has no meeting id or link")
        tel = d.get("telephony") if isinstance(d.get("telephony"), dict) else {}
        dial = [{"number": str(tel["accessCode"])[:40]}] if tel.get("accessCode") else []
        # The host uses the same link and signs in as host (or enters the host key, which is never returned here).
        return Created(
            str(d["id"]), d["webLink"], d["webLink"], d.get("password") or None, dial, host_user_id=host_user
        )

    def update(self, ctx: Context, ref: Ref, change: UpdateMeeting, host_user: str | None) -> Created | None:
        current = self._call(ctx, "GET", f"/meetings/{quote(str(ref.provider_meeting_id), safe='')}")
        starts = change.starts_at or ref.starts_at
        minutes = change.duration_minutes or ref.duration_minutes
        body = {  # PUT needs the whole schedule
            "title": change.title or current.get("title") or "Meeting",
            "start": _fmt(starts),
            "end": _fmt(starts + timedelta(minutes=minutes)),
            "password": current.get("password"),
            "hostEmail": ref.host_user_id,
            "sendEmail": False,
        }
        if change.options is not None:
            body["enabledJoinBeforeHost"] = change.options.join_before_host
            body["enabledAutoRecordMeeting"] = change.options.record == "cloud"
        self._call(ctx, "PUT", f"/meetings/{quote(str(ref.provider_meeting_id), safe='')}", json=body)
        return None

    def cancel(self, ctx: Context, ref: Ref) -> None:
        self._call(
            ctx,
            "DELETE",
            f"/meetings/{quote(str(ref.provider_meeting_id), safe='')}",
            params={"sendEmail": "false", "hostEmail": str(ref.host_user_id)},
        )

    def attendance(self, ctx: Context, ref: Ref) -> tuple[list[Participant], datetime | None]:
        instance = ref.instance_id
        if not instance:
            d = self._call(
                ctx,
                "GET",
                "/meetings",
                params={"meetingSeriesId": str(ref.provider_meeting_id), "meetingType": "meeting", "state": "ended"},
            )
            ended = [m for m in d.get("items", []) if isinstance(m, dict) and isinstance(m.get("id"), str)]
            if not ended:
                raise AdapterError("not_found", "Webex has no ended instance of this meeting yet")
            instance = sorted(ended, key=lambda m: str(m.get("start", "")))[-1]["id"]
        merged: dict[str, Participant] = {}
        for row in self._call(ctx, "GET", "/meetingParticipants", params={"meetingId": instance, "max": "1000"}).get(
            "items", []
        ):
            if not isinstance(row, dict):
                continue
            email = (row.get("email") or "").strip().lower() or None
            name = str(row.get("displayName") or "")[:200] or None
            p = merged.setdefault(email or f"{row.get('id')}|{name}", Participant(email, name, "attendee", []))
            join, leave = parse_time(row.get("joinedTime")), parse_time(row.get("leftTime"))
            if join:
                p.intervals.append((join, leave))
            if row.get("host"):
                p.role = "host"
            elif row.get("coHost") and p.role != "host":
                p.role = "co_host"
        return list(merged.values()), None

    def recordings(self, ctx: Context, ref: Ref) -> list[RecordingFile]:
        d = self._call(
            ctx,
            "GET",
            "/recordings",
            params={"meetingId": ref.instance_id or str(ref.provider_meeting_id), "max": "100"},
        )
        return [
            RecordingFile(
                str(x["id"])[:256],
                KIND.get(str(x.get("format", "")).upper(), "video"),
                parse_time(x.get("timeRecorded")),
                None,
                count(x.get("sizeBytes")),
            )
            for x in d.get("items", [])
            if isinstance(x, dict) and x.get("id")
        ]

    def download(self, ctx: Context, ref: Ref, rec: RecordingFile) -> tuple[Iterator[bytes], Callable[[], None]]:
        d = self._call(ctx, "GET", f"/recordings/{quote(rec.provider_recording_id, safe='')}")
        links = d.get("temporaryDirectDownloadLinks") if isinstance(d.get("temporaryDirectDownloadLinks"), dict) else {}
        url = links.get("recordingDownloadLink") or links.get("audioDownloadLink")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            raise AdapterError("not_found", "the recording has no download link")
        cm = self.http.stream("GET", url)  # a pre-signed link: no bearer token goes to it
        response = cm.__enter__()
        if response.status_code >= 400:
            response.read()
            err = map_status(response)
            cm.__exit__(None, None, None)
            raise err
        return response.iter_bytes(65536), lambda: cm.__exit__(None, None, None)

    def healthcheck(self, ctx: Context) -> dict:
        self._call(ctx, "GET", "/people/me")
        return {"status": "healthy", "detail": "Webex answered /people/me", "expires_at": None}

    # --- authorisation
    def begin_authorisation(
        self, ctx: Context, state: str, code_challenge: str, redirect_uri: str, scope_hint: list
    ) -> str:
        if not self.cfg.webex_client_id:
            raise AdapterError("not_configured", "VIDEO_CONFERENCING_WEBEX_CLIENT_ID is not set")
        scopes = " ".join(["meeting:schedules_read", "meeting:schedules_write", "meeting:admin_schedule_write", "meeting:participants_read",
                           "meeting:admin_participants_read", "meeting:recordings_read", "meeting:admin_recordings_read", "spark:kms"])  # fmt: skip
        q = {"response_type": "code", "client_id": self.cfg.webex_client_id, "redirect_uri": redirect_uri, "scope": scopes,
             "state": state, "code_challenge": code_challenge, "code_challenge_method": "S256"}  # fmt: skip
        return f"{self.cfg.webex_api_base_url}/authorize?{urlencode(q)}"

    def _tokens(self, form: dict) -> dict:
        if not self.cfg.webex_client_id or not self.cfg.webex_client_secret:
            raise AdapterError("not_configured", "Webex client credentials are not set")
        r = self.http.send(
            "POST",
            f"{self.cfg.webex_api_base_url}/access_token",
            data={**form, "client_id": self.cfg.webex_client_id, "client_secret": self.cfg.webex_client_secret},
        )
        if r.status_code >= 500 or r.status_code == 429:
            raise map_status(r)
        if r.status_code >= 400:
            raise AdapterError(
                "auth_failed", "Webex refused the code or the refresh token", provider_code=provider_code(r)
            )
        body = json_body(r)
        if not isinstance(body.get("access_token"), str):
            raise AdapterError("provider_error", "Webex's token answer has no access token")
        secrets = {"access_token": body["access_token"]}
        if isinstance(body.get("refresh_token"), str):
            secrets["refresh_token"] = body["refresh_token"]
        return {"secrets": secrets, "expires_at": (self.clock() + timedelta(seconds=count(body.get("expires_in")) or 1209600)).isoformat(),
                "granted_scopes": str(body.get("scope", "")).split()[:100]}  # fmt: skip

    def complete_authorisation(self, ctx: Context, code: str, code_verifier: str, redirect_uri: str) -> dict:
        out = self._tokens(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            }
        )
        who = self._call(Context(**{**ctx.__dict__, "secrets": out["secrets"]}), "GET", "/people/me")
        out["provider_subject"] = str(who.get("orgId") or who.get("id") or "")
        return out

    def refresh_authorisation(self, ctx: Context) -> dict:
        if not ctx.secrets.get("refresh_token"):
            raise AdapterError("auth_failed", "the connection has no refresh token: authorise it again")
        out = self._tokens({"grant_type": "refresh_token", "refresh_token": ctx.secrets["refresh_token"]})
        return {"secrets": out["secrets"], "expires_at": out["expires_at"]}

    def revoke_authorisation(self, ctx: Context) -> bool:
        return (
            False  # Webex has no public revoke call for an integration's token; it lapses and the admin removes the app
        )

    # --- webhooks (registered on the connection with its own secret)
    def register_webhooks(self, ctx: Context, target_url: str) -> list[str]:
        secret = ctx.secrets.get("webhook_secret")
        if not secret:
            raise AdapterError("not_configured", "the connection has no webhook_secret")
        ids = []
        for resource, event in (("meetings", "started"), ("meetings", "ended"), ("recordings", "created")):
            d = self._call(
                ctx,
                "POST",
                "/webhooks",
                json={
                    "name": f"eos-{resource}-{event}",
                    "targetUrl": target_url,
                    "resource": resource,
                    "event": event,
                    "secret": secret,
                },
            )
            ids.append(str(d.get("id", "")))
        return ids

    # --- inbound
    def verify_inbound(self, ctx: Context | None, req: InboundRequest) -> dict:
        secret = ctx.secrets.get("webhook_secret") if ctx else None
        if not secret or req.method.upper() != "POST" or json_object(req.raw_body) is None:
            return reject()
        raw = req.raw_body
        ok = False
        sha256 = req.header("x-webex-signature")
        sha1 = req.header("x-spark-signature")
        if sha256:
            ok = hex_equal(hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest(), sha256)
        elif sha1:
            ok = hex_equal(hmac.new(secret.encode(), raw, hashlib.sha1).hexdigest(), sha1)  # noqa: S324  # Webex's older header
        if not ok:
            return reject()
        return accept(body_hash(raw))

    def parse_inbound(self, ctx: Context | None, req: InboundRequest) -> list[ProviderEvent]:
        body = json_object(req.raw_body) or {}
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        resource, event = body.get("resource"), body.get("event")
        at = parse_time(body.get("created")) or (self.clock() if ctx else None)
        if resource == "meetings" and isinstance(data.get("id"), str):
            series = (
                data.get("meetingSeriesId") if isinstance(data.get("meetingSeriesId"), str) else series_of(data["id"])
            )
            kind = {"started": "started", "ended": "ended", "deleted": "deleted"}.get(str(event))
            if kind:
                return [ProviderEvent(kind, series, data["id"], at)]
        if resource == "recordings" and event == "created" and isinstance(data.get("id"), str):
            instance = data.get("meetingId") if isinstance(data.get("meetingId"), str) else None
            if instance:
                return [
                    ProviderEvent(
                        "recording_ready",
                        series_of(instance),
                        instance,
                        at,
                        recording_id=data["id"][:256],
                        recording_kind="video",
                    )
                ]
        return []
