"""What every provider client implements. Providers know a vendor's API and nothing about tables, tenancy or the hub:
the adapter (application/adapter.py) validates, persists, audits and turns the answers into port results."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ...domain.context import Context
from ...domain.errors import AdapterError
from ...domain.models import CreateMeeting, UpdateMeeting
from ..config import Config
from ..http import Http

Clock = Callable[[], datetime]
MAX_INBOUND_BYTES = 1024 * 1024


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class Ref:
    """A stored meeting, as much of it as a provider call needs."""

    provider_meeting_id: str | None
    host_user_id: str | None
    instance_id: str | None
    room_name: str | None
    starts_at: datetime
    duration_minutes: int
    status: str
    ended_at: datetime | None = None
    join_url: str | None = None
    host_join_url: str | None = None


@dataclass
class Created:
    provider_meeting_id: str | None
    join_url: str
    host_join_url: str | None = None
    passcode: str | None = None
    dial_in: list[dict] = field(default_factory=list)
    room_name: str | None = None
    host_user_id: str | None = None


@dataclass
class Participant:
    email: str | None
    display_name: str | None
    role: str  # host | co_host | attendee
    intervals: list[tuple[datetime, datetime | None]]
    total_seconds: int | None = None  # the provider's own total, when it gives one


@dataclass
class RecordingFile:
    provider_recording_id: str
    kind: str  # video | audio | transcript | chat
    started_at: datetime | None = None
    ended_at: datetime | None = None
    bytes: int | None = None
    expires_at: datetime | None = None
    download_url: str | None = None


@dataclass
class ProviderEvent:
    """A verified provider callback, reduced to what the adapter acts on. kind is one of started, ended, deleted,
    recording_ready, subscription_renew, subscription_recreate."""

    kind: str
    provider_meeting_id: str | None = None
    instance_id: str | None = None
    at: datetime | None = None
    recording_id: str | None = None
    recording_kind: str | None = None
    subscription_id: str | None = None


@dataclass
class InboundRequest:
    method: str
    path_suffix: str
    query: dict[str, Any]
    headers: dict[str, str]
    raw_body: bytes
    connection_id: str | None = None

    def header(self, name: str) -> str:
        want = name.lower()
        for k, v in self.headers.items():
            if k.lower() == want:
                return str(v)
        return ""


def accept(dedupe_key: str | None = None, *, resolves_to: dict | None = None, ack_status: int = 200) -> dict:
    return {"verdict": "accept", "dedupe_key": dedupe_key, "resolves_to": resolves_to, "ack_status": ack_status}


def reject(status: int = 401) -> dict:
    return {"verdict": "reject", "reject_status": status}


def handshake(body: str | bytes, content_type: str, status: int = 200) -> dict:
    return {
        "verdict": "handshake",
        "handshake_response": {"status": status, "content_type": content_type, "body": body},
    }


def body_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_object(raw: bytes) -> dict | None:
    """The body as a JSON object, or None; a body that is too large, not UTF-8 or not an object is simply not ours."""
    if len(raw) > MAX_INBOUND_BYTES:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError):
        return None
    return data if isinstance(data, dict) else None


def hex_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.strip().lower().encode(), b.strip().lower().encode())


def parse_time(value: Any) -> datetime | None:
    """An ISO 8601 date-time from a provider, as UTC; None when absent or unreadable (a provider's slip is not ours)."""
    if not isinstance(value, str) or not value or len(value) > 64:
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC)


def count(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or value in (float("inf"), float("-inf")) or value < 0:
        return None
    return int(value)


class Provider:
    """Every method raises AdapterError; nothing returns an error value."""

    id = ""
    title = ""
    auth = ""
    link_scope = "organisation"
    inbound: tuple[str, ...] = ("webhook",)
    settings_schema: dict = {"type": "object", "properties": {}, "additionalProperties": False}
    credential_names: tuple[str, ...] = ()
    platform_credential_names: tuple[str, ...] = ()
    capabilities_data: dict = {}

    def __init__(self, cfg: Config, http: Http, clock: Clock = utcnow) -> None:
        self.cfg, self.http, self.clock = cfg, http, clock

    # --- meetings
    def create(self, ctx: Context, spec: CreateMeeting, host_user: str) -> Created:
        raise AdapterError("unsupported", "this provider does not create meetings")

    def update(self, ctx: Context, ref: Ref, change: UpdateMeeting, host_user: str | None) -> Created | None:
        raise AdapterError("unsupported", "this provider does not change meetings")

    def cancel(self, ctx: Context, ref: Ref) -> None:
        raise AdapterError("unsupported", "this provider does not cancel meetings")

    def attendance(self, ctx: Context, ref: Ref) -> tuple[list[Participant], datetime | None]:
        """Participants, and when the meeting ended if the provider says so (None: unknown)."""
        raise AdapterError("unsupported", "this provider has no attendance report")

    def recordings(self, ctx: Context, ref: Ref) -> list[RecordingFile]:
        raise AdapterError("unsupported", "this provider has no recordings through the port")

    def download(self, ctx: Context, ref: Ref, rec: RecordingFile) -> tuple[Iterator[bytes], Callable[[], None]]:
        """(chunks, close). The caller calls close() when it is done, also on failure."""
        raise AdapterError("unsupported", "this provider has no recordings through the port")

    def healthcheck(self, ctx: Context) -> dict:
        raise NotImplementedError

    # --- authorisation
    def begin_authorisation(
        self, ctx: Context, state: str, code_challenge: str, redirect_uri: str, scope_hint: list
    ) -> str:
        raise AdapterError("unsupported", "this provider has no authorisation step")

    def complete_authorisation(self, ctx: Context, code: str, code_verifier: str, redirect_uri: str) -> dict:
        raise AdapterError("unsupported", "this provider has no authorisation step")

    def refresh_authorisation(self, ctx: Context) -> dict:
        raise AdapterError("unsupported", "this provider has no authorisation step")

    def revoke_authorisation(self, ctx: Context) -> bool:
        return False

    # --- inbound
    def verify_inbound(self, ctx: Context | None, req: InboundRequest) -> dict:
        return reject()

    def parse_inbound(self, ctx: Context | None, req: InboundRequest) -> list[ProviderEvent]:
        return []

    # --- subscriptions the provider makes us keep alive (Graph); a no-op for the others
    def ensure_subscription(self, ctx: Context, existing: Any) -> Any:
        return None
