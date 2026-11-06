"""Self-hosted Jitsi with token authentication. There is no meeting API: a room is a name, so "creating" a meeting
picks a random room name, and a join link is minted per person as a short-lived HS256 JWT (docs/prd.md, "Join links").
Attendance and recordings are not available through the port (Jibri recordings stay on the institution's server)."""

from __future__ import annotations

import secrets
from datetime import timedelta
from urllib.parse import quote, urlsplit

import jwt

from ...domain.context import Context
from ...domain.errors import AdapterError
from ...domain.models import CreateMeeting, UpdateMeeting
from ..http import map_status
from .base import Created, Provider, Ref

DEV_SECRET = "mock-jitsi-app-secret-for-development-only"  # mock mode only; sandbox and live need the real one
ROOM_PREFIX_MAX = 40


def base_url(ctx: Context) -> str:
    """The institution's Jitsi base URL from its connection settings: http(s), a host, no credentials, no path tricks.
    Plain http is accepted outside live mode so a local docker-jitsi-meet works."""
    raw = str(ctx.settings.get("base_url", "")).strip().rstrip("/")
    try:
        u = urlsplit(raw)
        port = u.port
    except ValueError:
        u, port = None, None
    if (
        u is None
        or u.scheme not in ("http", "https")
        or not u.hostname
        or u.username
        or u.password
        or u.query
        or u.fragment
    ):
        raise AdapterError("not_configured", "the connection's base_url is not a valid http(s) address")
    if u.scheme == "http" and ctx.mode == "live":
        raise AdapterError("not_configured", "live mode needs an https base_url")
    return f"{u.scheme}://{u.hostname}{f':{port}' if port else ''}{u.path}"


class JitsiProvider(Provider):
    id = "jitsi"
    title = "Jitsi (self-hosted)"
    auth = "jwt_shared_secret"
    inbound = ()
    settings_schema = {
        "type": "object",
        "required": ["base_url", "app_id"],
        "properties": {
            "base_url": {"type": "string", "maxLength": 300},
            "app_id": {"type": "string", "maxLength": 128},
            "room_prefix": {"type": "string", "maxLength": ROOM_PREFIX_MAX, "pattern": "^[a-z0-9\\-]*$"},
            "audience": {"type": "string", "maxLength": 128},
            "xmpp_domain": {"type": "string", "maxLength": 253},
        },
        "additionalProperties": False,
    }
    credential_names = ("app_secret",)

    def _secret(self, ctx: Context) -> str:
        secret = ctx.secrets.get("app_secret")
        if secret:
            return secret
        if ctx.mode == "mock":
            return DEV_SECRET
        raise AdapterError("not_configured", "the connection has no app_secret")

    def _app_id(self, ctx: Context) -> str:
        app = str(ctx.settings.get("app_id", "")).strip()
        if not app or len(app) > 128:
            raise AdapterError("not_configured", "the connection has no app_id")
        return app

    def create(self, ctx: Context, spec: CreateMeeting, host_user: str) -> Created:
        base = base_url(ctx)
        self._app_id(ctx)
        prefix = str(ctx.settings.get("room_prefix", "")).strip()[:ROOM_PREFIX_MAX]
        room = f"{prefix}{'-' if prefix else ''}{secrets.token_hex(12)}"  # random: not guessable, unlike a class name
        # The link without a token cannot enter a room on a server with token authentication; join_link mints the real one.
        return Created(None, f"{base}/{quote(room)}", None, None, [], room_name=room, host_user_id=host_user)

    def update(self, ctx: Context, ref: Ref, change: UpdateMeeting, host_user: str | None) -> Created | None:
        return None  # the schedule is ours alone; the room name and so the link do not change

    def cancel(self, ctx: Context, ref: Ref) -> None:
        return None  # a room cannot be closed; tokens for it stop being minted and the existing ones expire

    def mint(
        self, ctx: Context, ref: Ref, person_id: str, name: str, email: str | None, moderator: bool
    ) -> tuple[str, object]:
        base = base_url(ctx)
        app = self._app_id(ctx)
        now = self.clock()
        end = ref.starts_at + timedelta(minutes=ref.duration_minutes)
        exp = min(now + timedelta(seconds=self.cfg.jitsi_token_ttl_s), end + timedelta(hours=1))
        if exp <= now:
            raise AdapterError("conflict", "the meeting is over; no link can be issued for it")
        host = urlsplit(base).hostname or ""
        user = {"id": person_id, "name": name, "moderator": moderator}
        if email:
            user["email"] = email
        claims = {
            "iss": app,
            "aud": str(ctx.settings.get("audience") or "jitsi"),
            "sub": str(ctx.settings.get("xmpp_domain") or host),
            "room": ref.room_name,
            "nbf": int((now - timedelta(minutes=1)).timestamp()),
            "exp": int(exp.timestamp()),
            "moderator": moderator,
            "context": {"user": user},
        }
        token = jwt.encode(claims, self._secret(ctx), algorithm="HS256")
        return f"{base}/{quote(str(ref.room_name))}?jwt={token}", exp

    def healthcheck(self, ctx: Context) -> dict:
        base = base_url(ctx)
        self._app_id(ctx)
        self._secret(ctx)
        r = self.http.send("GET", f"{base}/")
        if r.status_code >= 500:
            raise map_status(r)
        return {
            "status": "healthy" if r.status_code < 400 else "degraded",
            "detail": f"the Jitsi server answered {r.status_code}",
            "expires_at": None,
        }
