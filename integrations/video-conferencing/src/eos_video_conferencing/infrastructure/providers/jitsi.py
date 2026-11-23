"""Self-hosted Jitsi with token authentication. There is no meeting API: a room is a name, so "creating" a meeting
picks a random room name, and a join link is minted per person as a short-lived HS256 JWT (docs/prd.md, "Join links").
Attendance and recordings are not available through the port (Jibri recordings stay on the institution's server)."""

from __future__ import annotations

import ipaddress
import secrets
import socket
from datetime import timedelta
from urllib.parse import quote, urlsplit

import jwt
from eos_core import settings as core_settings

from ...domain.context import Context
from ...domain.errors import AdapterError
from ...domain.models import CreateMeeting, UpdateMeeting
from ..http import map_status
from .base import Created, Provider, Ref

DEV_SECRET = "mock-jitsi-app-secret-for-development-only"  # mock mode only; sandbox and live need the real one
ROOM_PREFIX_MAX = 40


_BLOCKED_MESSAGE = "the connection's base_url must not point to a local, private or metadata address"
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_SIX_TO_FOUR = ipaddress.ip_network("2002::/16")


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True for anything that is not a globally routable unicast address: loopback, private, link-local (cloud metadata),
    shared address space 100.64.0.0/10 (Alibaba's metadata address is in it), reserved, multicast and unspecified. An
    IPv6 address that carries an IPv4 one (mapped, NAT64, 6to4) is judged by the IPv4 address it carries."""
    if isinstance(ip, ipaddress.IPv6Address):
        carried = ip.ipv4_mapped
        if carried is None and ip in _NAT64:
            carried = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        if carried is None and ip in _SIX_TO_FOUR:
            carried = ipaddress.IPv4Address((int(ip) >> 80) & 0xFFFFFFFF)
        if carried is not None and _is_blocked_ip(carried):
            return True
    return not ip.is_global or ip.is_multicast


def _validate_host(hostname: str, port: int | None = None) -> str | None:
    """Refuse a host that is, or resolves to, a blocked address. Returns the validated address to connect to, so the
    request goes where the check looked (a second lookup could answer differently: DNS rebinding), or None when there
    is nothing to pin: an address literal is connected to as it is, and a development name (`.example`, `.test`, in
    dev mode only) is never resolved."""
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        if _is_blocked_ip(ip):
            raise AdapterError("not_configured", _BLOCKED_MESSAGE)
        return None

    if core_settings.settings.dev_mode and hostname.lower().endswith((".example", ".test")):
        return None

    try:
        addrs = socket.getaddrinfo(hostname, port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise AdapterError("not_configured", "the connection's base_url host could not be resolved") from e

    found: list[str] = []
    for addr in addrs:
        try:
            ip = ipaddress.ip_address(addr[4][0].split("%", 1)[0])
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            raise AdapterError("not_configured", _BLOCKED_MESSAGE)
        found.append(str(ip))
    if not found:
        raise AdapterError("not_configured", "the connection's base_url host could not be resolved")
    return found[0]


def _split_base(ctx: Context):
    """The institution's Jitsi base URL from its connection settings, parsed: https, a host, no credentials, no path
    tricks. Nothing is resolved here."""
    raw = str(ctx.settings.get("base_url", "")).strip().rstrip("/")
    try:
        u = urlsplit(raw)
        port = u.port
    except ValueError:
        u, port = None, None
    if u is None or u.scheme != "https" or not u.hostname or u.username or u.password or u.query or u.fragment:
        raise AdapterError("not_configured", "the connection's base_url is not a valid https address")
    return u, port


def base_url(ctx: Context) -> str:
    """The institution's Jitsi base URL, checked: https, a host, no credentials, and no address a server must not call."""
    u, port = _split_base(ctx)
    _validate_host(u.hostname, port)
    return f"{u.scheme}://{u.hostname}{f':{port}' if port else ''}{u.path}"


def checked_request_target(ctx: Context) -> tuple[str, dict]:
    """The URL for a request the server makes to the institution's Jitsi, and the arguments that pin it. The host is
    resolved once, here; the request is sent to the address that passed the check, with the original name as Host and as
    the TLS server name, so the certificate is still checked against the name and a second lookup cannot redirect it."""
    u, port = _split_base(ctx)
    pinned = _validate_host(u.hostname, port)
    name = f"{u.hostname}{f':{port}' if port else ''}"
    if pinned is None:
        return f"{u.scheme}://{name}{u.path}", {"follow_redirects": False}
    address = f"[{pinned}]" if ":" in pinned else pinned
    return (
        f"{u.scheme}://{address}{f':{port}' if port else ''}{u.path}",
        {"headers": {"Host": name}, "extensions": {"sni_hostname": u.hostname}, "follow_redirects": False},
    )


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
        if ctx.mode == "mock" and core_settings.settings.dev_mode:
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
        target, pin = checked_request_target(ctx)
        self._app_id(ctx)
        self._secret(ctx)
        r = self.http.send("GET", f"{target}/", **pin)
        if r.status_code >= 500:
            raise map_status(r)
        return {
            "status": "healthy" if r.status_code < 400 else "degraded",
            "detail": "Jitsi server is reachable"
            if r.status_code < 400
            else "Jitsi server returned unexpected response",
            "expires_at": None,
        }
