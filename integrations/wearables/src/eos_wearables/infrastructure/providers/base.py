"""What every provider client implements. Providers know a vendor's API and nothing about tables, tenancy or the hub: the
adapter (application/adapter.py) validates, persists, audits and turns the answers into port results.

Everything a provider returns is normalised here to the port's `records` shapes in fixed units (metres, seconds,
kilograms, beats per minute, kilocalories); a value that is missing, negative, NaN or infinite becomes None."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from ...domain.context import Context
from ...domain.errors import AdapterError
from ..config import Config
from ..http import Http

Clock = Callable[[], datetime]
MAX_INBOUND_BYTES = 1024 * 1024
DURATION = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$")


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class Normal:
    """One normalised record: the port's shape for `data_type` in `fields`."""

    data_type: str
    provider_record_id: str
    record_date: date
    fields: dict[str, Any]


@dataclass
class InboundEvent:
    """A verified provider callback reduced to what the adapter acts on. kind is one of:
    data (records pushed by the provider: stored as they are), changed (a ping: the hub runs sync), deleted (a record the
    provider removed), revoked (the athlete disconnected on the provider's side), narrowed (the athlete withdrew some
    permissions)."""

    kind: str
    subject: str
    data_types: list[str] = field(default_factory=list)
    start: date | None = None
    end: date | None = None
    records: list[Normal] = field(default_factory=list)
    record_ids: list[str] = field(default_factory=list)


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

    def q(self, name: str) -> str:
        v = self.query.get(name)
        v = v[0] if isinstance(v, list) and v else v
        return v if isinstance(v, str) else ""


def accept(dedupe_key: str | None = None, resolves_to: dict | None = None) -> dict:
    return {"verdict": "accept", "dedupe_key": dedupe_key, "resolves_to": resolves_to}


def reject(status: int = 401) -> dict:
    return {"verdict": "reject", "reject_status": status}


def handshake(body: str, content_type: str = "application/json", status: int = 200) -> dict:
    return {
        "verdict": "handshake",
        "handshake_response": {"status": status, "content_type": content_type, "body": body},
    }


def body_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_any(raw: bytes) -> Any:
    """The body parsed, or None when it is too large, not UTF-8 or not JSON."""
    if len(raw) > MAX_INBOUND_BYTES:
        return None
    try:
        return json.loads(raw)
    except (ValueError, RecursionError):
        return None


def hex_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.strip().lower().encode(), b.strip().lower().encode())


def const_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


# --- normalisation helpers --------------------------------------------------------------------------------------


def num(v: Any, hi: float = 1e9) -> float | None:
    """A finite, non-negative number, else None (booleans are not numbers)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, str):
        try:
            v = float(v)
        except ValueError:
            return None
    if not isinstance(v, (int, float)) or v != v or v in (float("inf"), float("-inf")) or v < 0 or v > hi:
        return None
    return float(v)


def integer(v: Any, hi: float = 1e9) -> int | None:
    n = num(v, hi)
    return None if n is None else int(round(n))


def seconds(v: Any) -> int | None:
    """Seconds from a number or an ISO 8601 duration ("PT45M12S")."""
    if isinstance(v, str):
        m = DURATION.match(v)
        if not m or not any(m.groups()):
            return integer(v, 1e7)
        d, h, mi, s = (float(g) if g else 0.0 for g in m.groups())
        return int(d * 86400 + h * 3600 + mi * 60 + s)
    return integer(v, 1e7)


def when(v: Any) -> datetime | None:
    """A date-time (ISO 8601, or epoch seconds) as UTC; None when absent or unreadable."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(v, UTC) if v == v and 0 < v < 4_102_444_800 else None
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(v, str) or not v or len(v) > 64:
        return None
    try:
        d = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC)


def day(v: Any) -> date | None:
    if isinstance(v, str) and len(v) >= 10:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None
    d = when(v)
    return d.date() if d else None


def iso(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


def text(v: Any, n: int = 60) -> str:
    return str(v).strip()[:n] if isinstance(v, (str, int)) and not isinstance(v, bool) else ""


def daily(d: date, rid: str, source: str, **kw) -> Normal:
    f = {"date": d.isoformat(), "steps": None, "distance_m": None, "active_kcal": None, "resting_hr_bpm": None,
         "avg_hr_bpm": None, "max_hr_bpm": None, "active_seconds": None, "stress_avg": None, "source": source}  # fmt: skip
    f.update(kw)
    return Normal("daily_summary", rid, d, f)


def activity(rid: str, source: str, started: datetime, **kw) -> Normal:
    f = {"provider_activity_id": rid, "sport": "other", "started_at": iso(started), "duration_s": None, "distance_m": None,
         "kcal": None, "avg_hr_bpm": None, "max_hr_bpm": None, "training_load": None, "hr_zones_s": [], "source": source}  # fmt: skip
    f.update(kw)
    return Normal("activity", rid, started.date(), f)


def sleep(d: date, rid: str, source: str, started: datetime | None, ended: datetime | None, **kw) -> Normal:
    f = {"date": d.isoformat(), "started_at": iso(started), "ended_at": iso(ended), "total_s": None, "deep_s": None,
         "light_s": None, "rem_s": None, "awake_s": None, "score": None, "source": source}  # fmt: skip
    f.update(kw)
    return Normal("sleep", rid, d, f)


def hrv(d: date, rid: str, source: str, rmssd: float | None) -> Normal:
    return Normal("heart_rate_variability", rid, d, {"date": d.isoformat(), "rmssd_ms": rmssd, "source": source})


def body(measured: datetime, rid: str, source: str, weight_kg: float | None, fat_pct: float | None) -> Normal:
    return Normal("body_composition", rid, measured.date(), {"measured_at": iso(measured), "weight_kg": weight_kg,
                                                              "body_fat_pct": fat_pct, "source": source})  # fmt: skip


def days(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


class Provider:
    """Every method raises AdapterError; nothing returns an error value."""

    id = ""
    title = ""
    auth = "oauth2_authorization_code"
    link_scope = "person"
    inbound: tuple[str, ...] = ("webhook",)
    data_types: tuple[str, ...] = ()
    settings_schema: dict = {
        "type": "object",
        "properties": {
            "data_types": {
                "type": "array",
                "items": {"enum": ["daily_summary", "activity", "sleep", "heart_rate_variability", "body_composition"]},
                "maxItems": 5,
            },
            "share_with_coaches": {"type": "boolean"},
            "strava_shared_display_approved": {"type": "boolean"},
            "garmin_tier": {"enum": ["starter", "enterprise"]},
        },
        "additionalProperties": False,
    }
    credential_names: tuple[str, ...] = ("access_token", "refresh_token")
    platform_credential_names: tuple[str, ...] = ()
    push = False
    backfill_mode: str | None = (
        None  # "pull": history is read with sync; "request": the provider is asked and pushes it
    )
    rate_limit = ""
    display_to_others_allowed = True

    def __init__(self, cfg: Config, http: Http, clock: Clock = utcnow) -> None:
        self.cfg, self.http, self.clock = cfg, http, clock

    def capabilities(self, ctx: Context | None) -> dict:
        return {
            "data_types": list(self.data_types),
            "push": self.push,
            "backfill_days": 0,
            "rate_limit": self.rate_limit,
            "requires_mobile_app": False,
            "display_to_others_allowed": self.display_to_others_allowed,
        }

    # --- authorisation
    def begin_authorisation(
        self, ctx: Context, state: str, code_challenge: str, redirect_uri: str, scope_hint: list
    ) -> str:
        raise AdapterError("unsupported", "this provider has no authorisation step")

    def complete_authorisation(self, ctx: Context, code: str, code_verifier: str, redirect_uri: str) -> dict:
        raise AdapterError("unsupported", "this provider has no authorisation step")

    def refresh_authorisation(self, ctx: Context) -> dict:
        raise AdapterError("unsupported", "this provider has no refresh step")

    def revoke_authorisation(self, ctx: Context) -> bool:
        return False

    def register_user(self, ctx: Context, person_id: str, provider_subject: str | None) -> None:
        return None

    # --- data
    def pull(self, ctx: Context, data_type: str, start: date, end: date) -> list[Normal]:
        raise AdapterError("unsupported", "this provider does not offer this data type")

    def backfill(self, ctx: Context, data_types: list[str], start: date, end: date) -> bool:
        raise AdapterError("unsupported", "this provider offers no history before the link was made")

    def healthcheck(self, ctx: Context) -> dict:
        return {"status": "healthy", "detail": "no provider call is made for this provider", "expires_at": None}

    # --- inbound
    def verify_inbound(self, req: InboundRequest, link_of: Callable[[str], dict | None]) -> dict:
        return reject()

    def parse_inbound(self, req: InboundRequest) -> list[InboundEvent]:
        return []
