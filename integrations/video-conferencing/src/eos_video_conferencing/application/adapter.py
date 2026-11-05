"""The meetings port and the Adapter contract (contracts/ports/meetings.yaml, adapter.yaml) over four providers.

Every operation takes the hub's call context and an input object and returns a Result: an output, or an error from the
contract's one vocabulary. Nothing raises to the caller and nothing is a 500: input is validated and bounded first,
provider failures are mapped, and a bug is reported as a generic provider_error and logged without its data.

State lives in this module's own tables (meeting key -> provider meeting, attendance, recordings, Graph subscriptions,
the per-host Zoom quota) under row-level security; every state change writes an audit entry in the same transaction.
The adapter publishes no events of its own (contracts/events.yaml): the hub publishes the port's notifications."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import uuid
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from eos_core.db import SessionLocal, scoped
from eos_core.tenant import organisation_scope, platform_scope
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import __version__
from ..domain.context import Context, Result
from ..domain.errors import AdapterError
from ..domain.models import (
    CancelMeeting,
    CreateMeeting,
    FetchAttendance,
    ImportRecording,
    JoinLink,
    MeetingRef,
    UpdateMeeting,
    parse,
)
from ..infrastructure import crypto
from ..infrastructure.config import PROVIDERS as PROVIDER_IDS
from ..infrastructure.config import Config
from ..infrastructure.http import Http, seconds_until_midnight_utc
from ..infrastructure.models import (
    Attendance,
    AuditEntry,
    GraphSubscription,
    HostQuota,
    Meeting,
    Recording,
    aware,
    iso,
)
from ..infrastructure.providers import PROVIDERS
from ..infrastructure.providers.base import InboundRequest, Participant, Provider, ProviderEvent, Ref, utcnow
from ..infrastructure.providers.mock import MockProvider

log = logging.getLogger("eos.video_conferencing")

CAPABILITIES = {
    "zoom": dict(
        scheduled_meetings=True,
        host_specific_link=True,
        waiting_room=True,
        cloud_recording=True,
        attendance_report=True,
        realtime_participant_events=False,
        max_participants=0,
        max_duration_minutes=1440,
    ),  # fmt: skip
    "teams": dict(
        scheduled_meetings=True,
        host_specific_link=False,
        waiting_room=True,
        cloud_recording=True,
        attendance_report=True,
        realtime_participant_events=False,
        max_participants=1000,
        max_duration_minutes=1440,
    ),  # fmt: skip
    "webex": dict(
        scheduled_meetings=True,
        host_specific_link=False,
        waiting_room=True,
        cloud_recording=True,
        attendance_report=True,
        realtime_participant_events=False,
        max_participants=0,
        max_duration_minutes=1440,
    ),  # fmt: skip
    "jitsi": dict(
        scheduled_meetings=False,
        host_specific_link=False,
        waiting_room=False,
        cloud_recording=False,
        attendance_report=False,
        realtime_participant_events=False,
        max_participants=0,
        max_duration_minutes=1440,
    ),  # fmt: skip
}  # max_participants 0: depends on the institution's plan or server; create_limit_per_host_per_day 0: unknown
MAX_RAW_BODY = 1024 * 1024


class DocumentSink(Protocol):
    """platform/documents, reached through packages/sdk once the SDK ships one. Consumes the chunks as a stream and
    returns the new document's id."""

    def store(self, *, organisation_id: str, name: str, content_type: str, chunks: Iterable[bytes]) -> str: ...


class _NoDocuments:
    def store(self, *, organisation_id: str, name: str, content_type: str, chunks: Iterable[bytes]) -> str:
        raise AdapterError("not_configured", "no documents service is wired to this adapter")


def _id(value: Any) -> str:
    return str(value)


class VideoConferencingAdapter:
    name = "video-conferencing"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] = SessionLocal,
        client_factory=None,
        clock: Callable[[], datetime] = utcnow,
        documents: DocumentSink | None = None,
        config: Callable[[], Config] = Config.load,
    ) -> None:
        self._session_factory = session_factory
        self._client_factory = client_factory
        self.clock = clock
        self.documents: DocumentSink = documents or _NoDocuments()
        self._config = config

    # ------------------------------------------------------------------ identity

    def describe(self) -> dict:
        cfg = self._config()
        providers = []
        for pid, cls in PROVIDERS.items():
            p = cls(cfg, Http(self._client_factory, cfg.http_timeout_s))
            providers.append(
                {
                    "provider": pid,
                    "title": p.title,
                    "ports": ["meetings"],
                    "modes": ["mock", "sandbox", "live"],
                    "auth": p.auth,
                    "link_scope": p.link_scope,
                    "inbound": list(p.inbound),
                    "settings_schema": p.settings_schema,
                    "credential_names": list(p.credential_names),
                    "platform_credential_names": [f"{'VIDEO_CONFERENCING_'}{n}" for n in p.platform_credential_names],
                }
            )
        return {
            "adapter": self.name,
            "version": __version__,
            "ports": [{"port": "meetings", "version": 1}],
            "providers": providers,
        }

    # ------------------------------------------------------------------ plumbing

    def _provider(self, ctx: Context) -> tuple[Provider, Config]:
        cfg = self._config()
        cls = PROVIDERS.get(ctx.provider)
        if cls is None:
            raise AdapterError("not_configured", "this adapter has no such provider")
        provider: Provider = cls(cfg, Http(self._client_factory, cfg.http_timeout_s), self.clock)
        if (ctx.mode or cfg.mode) == "mock":
            provider = MockProvider(provider)
        return provider, cfg

    def _cfg_for_store(self, ctx: Context) -> Config:
        cfg = self._config()
        return cfg if ctx.mode is None else _with_mode(cfg, ctx.mode)

    @contextmanager
    def _db(self, organisation_id: str | None) -> Iterator[Session]:
        """A session pinned to one organisation (row-level security on Postgres, scoped() on SQLite)."""
        session = self._session_factory()
        if organisation_id:
            session.info["organisation_id"] = organisation_id
        try:
            with organisation_scope(organisation_id):
                yield session
        finally:
            session.close()

    def _run(self, ctx: Any, fn: Callable[[Context], dict | tuple[dict, str | None]]) -> Result:
        try:
            c = Context.coerce(ctx)
            out = fn(c)
            if isinstance(out, tuple):
                return Result(output=out[0], provider_reference=out[1])
            return Result(output=out)
        except AdapterError as e:
            return Result.failure(e)
        except Exception:  # a bug, not a provider answer: say so generically and keep the data out of the log
            log.exception("video-conferencing: unexpected failure")
            return Result.failure(AdapterError("provider_error", "the adapter failed unexpectedly"))

    def _audit(
        self, db: Session, ctx: Context, action: str, entity: str, entity_id: str, org: str | None = None
    ) -> None:
        db.add(
            AuditEntry(
                organisation_id=org or ctx.organisation_id,
                actor=ctx.delivery_id and str(ctx.delivery_id)[:36],
                action=action,
                entity=entity,
                entity_id=entity_id,
                occurred_at=self.clock(),
            )  # fmt: skip
        )

    def _meeting(self, db: Session, key: str, provider: str | None = None) -> Meeting:
        q = scoped(db, select(Meeting).where(Meeting.meeting_key == key), Meeting)
        m = db.scalar(q)
        if m is None or m.status == "creating" or (provider and m.provider != provider):
            raise AdapterError("not_found", "no meeting with this key")
        return m

    def _ref(self, cfg: Config, m: Meeting) -> Ref:
        return Ref(
            m.provider_meeting_id, m.host_user_id, m.provider_instance_id, m.room_name, aware(m.starts_at), m.duration_minutes,
            m.status, aware(m.ended_at), crypto.unseal(cfg, m.join_url), crypto.unseal(cfg, m.host_join_url),
        )  # fmt: skip

    # ------------------------------------------------------------------ Adapter contract

    def capabilities(self, ctx: Any, input: dict | None = None) -> Result:
        def run(c: Context):
            if c.provider not in CAPABILITIES:
                raise AdapterError("not_configured", "this adapter has no such provider")
            caps = dict(CAPABILITIES[c.provider])
            caps["create_limit_per_host_per_day"] = (
                self._config().zoom_create_limit_per_host_per_day if c.provider == "zoom" else 0
            )
            return {"port": "meetings", "capabilities": caps}

        return self._run(ctx, run)

    def healthcheck(self, ctx: Any, input: dict | None = None) -> Result:
        def run(c: Context):
            provider, _ = self._provider(c)
            try:
                return provider.healthcheck(c)
            except AdapterError as e:
                if e.code == "auth_failed":
                    return {"status": "auth_failed", "detail": e.detail, "expires_at": None}
                if e.code in ("transport_unavailable", "provider_error"):
                    return {"status": "unreachable", "detail": e.detail, "expires_at": None}
                if e.code == "throttled":
                    return {"status": "degraded", "detail": e.detail, "expires_at": None}
                raise

        return self._run(ctx, run)

    def begin_authorisation(self, ctx: Any, input: dict) -> Result:
        def run(c: Context):
            args = _auth_input(input, ("state", "code_challenge", "redirect_uri"))
            provider, _ = self._provider(c)
            return {
                "authorize_url": provider.begin_authorisation(
                    c, args["state"], args["code_challenge"], args["redirect_uri"], args["scope_hint"]
                )
            }

        return self._run(ctx, run)

    def complete_authorisation(self, ctx: Any, input: dict) -> Result:
        def run(c: Context):
            args = _auth_input(input, ("code", "code_verifier", "redirect_uri"))
            provider, _ = self._provider(c)
            return provider.complete_authorisation(c, args["code"], args["code_verifier"], args["redirect_uri"])

        return self._run(ctx, run)

    def refresh_authorisation(self, ctx: Any, input: dict | None = None) -> Result:
        return self._run(ctx, lambda c: self._provider(c)[0].refresh_authorisation(c))

    def revoke_authorisation(self, ctx: Any, input: dict | None = None) -> Result:
        return self._run(ctx, lambda c: {"revoked": self._provider(c)[0].revoke_authorisation(c)})

    # ------------------------------------------------------------------ meetings port

    def create_meeting(self, ctx: Any, input: dict) -> Result:
        return self._run(ctx, lambda c: self._create(c, parse(CreateMeeting, input)))

    def _output(self, cfg: Config, m: Meeting) -> dict:
        return {
            "meeting_id": m.id,
            "provider_meeting_id": m.provider_meeting_id,
            "join_url": crypto.unseal(cfg, m.join_url),
            "host_join_url": crypto.unseal(cfg, m.host_join_url),
            "passcode": crypto.unseal(cfg, m.passcode),
            "dial_in": [],
        }

    def _create(self, c: Context, spec: CreateMeeting):
        provider, _ = self._provider(c)
        cfg = self._cfg_for_store(c)
        host_user = (
            spec.host.provider_user_id or spec.host.email or (str(spec.host.person_id) if spec.host.person_id else None)
        )
        if host_user is None:
            raise AdapterError("invalid_request", "the host needs an email or a provider_user_id")
        if c.provider != "jitsi" and not (spec.host.provider_user_id or spec.host.email):
            raise AdapterError("invalid_request", "the host needs an email or a provider_user_id")
        with self._db(c.organisation_id) as db:
            existing = db.scalar(scoped(db, select(Meeting).where(Meeting.meeting_key == spec.meeting_key), Meeting))
            if existing is not None:
                return self._existing(cfg, existing, c)
            if c.provider == "zoom":
                host_user = self._pick_zoom_host(db, c, cfg, host_user)
            row = Meeting(
                id=str(spec.meeting_id or uuid.uuid4()), organisation_id=c.organisation_id, connection_id=c.connection_id,
                meeting_key=spec.meeting_key, caller_module=spec.caller_module, provider=c.provider, host_user_id=host_user,
                status="creating", starts_at=spec.starts_at, duration_minutes=spec.duration_minutes,
            )  # fmt: skip
            db.add(row)
            try:
                db.commit()  # reserved: a concurrent create of the same key now collides here, before any provider call
            except IntegrityError:
                db.rollback()
                again = db.scalar(scoped(db, select(Meeting).where(Meeting.meeting_key == spec.meeting_key), Meeting))
                if again is None:
                    raise AdapterError("conflict", "the meeting id is already in use") from None
                return self._existing(cfg, again, c)
            row_id = row.id
        try:
            created = provider.create(c, spec, host_user)
        except BaseException:
            with self._db(c.organisation_id) as db:
                gone = db.get(Meeting, row_id)
                if gone is not None and gone.status == "creating":
                    db.delete(gone)
                    db.commit()
            raise
        with self._db(c.organisation_id) as db:
            m = db.get(Meeting, row_id)
            m.provider_meeting_id = created.provider_meeting_id
            m.room_name = created.room_name
            m.host_user_id = created.host_user_id or host_user
            m.join_url = crypto.seal(cfg, created.join_url)
            m.host_join_url = crypto.seal(cfg, created.host_join_url)
            m.passcode = crypto.seal(cfg, created.passcode)
            m.status = "scheduled"
            if c.provider == "zoom":
                self._count_call(db, c, m.host_user_id)
            self._audit(db, c, "meeting.created", "meeting", m.id)
            db.commit()
            out = self._output(cfg, m)
        out["dial_in"] = created.dial_in
        if c.provider == "teams":
            self._ensure_subscription(c, provider, cfg)
        return out, created.provider_meeting_id

    def _existing(self, cfg: Config, m: Meeting, c: Context) -> dict:
        if m.status == "creating":
            raise AdapterError("conflict", "this meeting key is being created right now")
        if m.provider != c.provider:
            raise AdapterError("conflict", "this meeting key belongs to a meeting on another provider")
        return self._output(cfg, m), m.provider_meeting_id

    # Zoom allows 100 create/update calls per host user per day (UTC): spread over a pool, or hold with throttled.
    def _today(self) -> date:
        return self.clock().astimezone(UTC).date()

    def _calls_today(self, db: Session, c: Context, host: str) -> int:
        row = db.scalar(
            scoped(
                db,
                select(HostQuota).where(
                    HostQuota.connection_id == c.connection_id,
                    HostQuota.host_user_id == host,
                    HostQuota.day == self._today(),
                ),
                HostQuota,
            )
        )
        return row.calls if row else 0

    def _pick_zoom_host(self, db: Session, c: Context, cfg: Config, wanted: str) -> str:
        pool = (
            [str(h) for h in (c.settings.get("host_pool") or [])[:50]]
            if c.settings.get("host_resolution") == "pool"
            else []
        )
        limit = cfg.zoom_create_limit_per_host_per_day
        for candidate in dict.fromkeys([wanted, *pool]):
            if self._calls_today(db, c, candidate) < limit:
                return candidate
        raise AdapterError(
            "throttled", "Zoom allows only so many meeting creations and changes per host per day; try after 00:00 UTC",
            provider_code="zoom_daily_limit", retry_after_s=seconds_until_midnight_utc(self.clock()),
        )  # fmt: skip

    def _guard_zoom_quota(self, db: Session, c: Context, cfg: Config, host: str | None) -> None:
        if c.provider == "zoom" and host and self._calls_today(db, c, host) >= cfg.zoom_create_limit_per_host_per_day:
            raise AdapterError(
                "throttled", "Zoom allows only so many meeting creations and changes per host per day; try after 00:00 UTC",
                provider_code="zoom_daily_limit", retry_after_s=seconds_until_midnight_utc(self.clock()),
            )  # fmt: skip

    def _count_call(self, db: Session, c: Context, host: str | None) -> None:
        if not host:
            return
        q = scoped(
            db,
            select(HostQuota).where(
                HostQuota.connection_id == c.connection_id,
                HostQuota.host_user_id == host,
                HostQuota.day == self._today(),
            ),
            HostQuota,
        )
        row = db.scalar(q)
        if row is None:
            db.add(
                HostQuota(
                    organisation_id=c.organisation_id,
                    connection_id=c.connection_id,
                    host_user_id=host,
                    day=self._today(),
                    calls=1,
                )
            )
        else:
            row.calls += 1

    def update_meeting(self, ctx: Any, input: dict) -> Result:
        return self._run(ctx, lambda c: self._update(c, parse(UpdateMeeting, input)))

    def _update(self, c: Context, change: UpdateMeeting):
        provider, _ = self._provider(c)
        cfg = self._cfg_for_store(c)
        with self._db(c.organisation_id) as db:
            m = self._meeting(db, change.meeting_key, c.provider)
            if m.status != "scheduled":
                raise AdapterError("conflict", f"a meeting that is {m.status} cannot be changed")
            self._guard_zoom_quota(db, c, cfg, m.host_user_id)
            ref = self._ref(cfg, m)
            new_host = change.host and (change.host.provider_user_id or change.host.email)
            if new_host and new_host != m.host_user_id and c.provider in ("teams", "webex"):
                raise AdapterError(
                    "unsupported", "this provider cannot move a meeting to another host: cancel it and create it again"
                )
            m_id = m.id
        links = provider.update(c, ref, change, new_host or None)
        with self._db(c.organisation_id) as db:
            m = db.get(Meeting, m_id)
            if m.status != "scheduled":
                raise AdapterError("conflict", f"a meeting that is {m.status} cannot be changed")
            if change.starts_at is not None:
                m.starts_at = change.starts_at
            if change.duration_minutes is not None:
                m.duration_minutes = change.duration_minutes
            if new_host and c.provider == "jitsi":
                m.host_user_id = new_host
            changed = False
            if links is not None and links.join_url != crypto.unseal(cfg, m.join_url):
                changed = True
                m.join_url, m.host_join_url = crypto.seal(cfg, links.join_url), crypto.seal(cfg, links.host_join_url)
            if c.provider == "zoom":
                self._count_call(db, c, m.host_user_id)
            self._audit(db, c, "meeting.updated", "meeting", m.id)
            db.commit()
            return {
                "meeting_id": m.id, "join_url": crypto.unseal(cfg, m.join_url),
                "host_join_url": crypto.unseal(cfg, m.host_join_url), "links_changed": changed,
            }, m.provider_meeting_id  # fmt: skip

    def cancel_meeting(self, ctx: Any, input: dict) -> Result:
        return self._run(ctx, lambda c: self._cancel(c, parse(CancelMeeting, input)))

    def _cancel(self, c: Context, req: CancelMeeting):
        provider, _ = self._provider(c)
        cfg = self._cfg_for_store(c)
        with self._db(c.organisation_id) as db:
            m = self._meeting(db, req.meeting_key, c.provider)
            if m.status == "cancelled":
                return {"meeting_id": m.id, "status": "cancelled"}  # cancelling twice is not an error
            if m.status in ("started", "ended"):
                raise AdapterError("conflict", f"a meeting that is {m.status} cannot be cancelled")
            ref, m_id = self._ref(cfg, m), m.id
        try:
            provider.cancel(c, ref)
        except AdapterError as e:
            if e.code != "not_found":  # already gone at the provider: the meeting is cancelled either way
                raise
        with self._db(c.organisation_id) as db:
            m = db.get(Meeting, m_id)
            m.status = "cancelled"
            self._audit(db, c, "meeting.cancelled", "meeting", m.id)
            db.commit()
            return {"meeting_id": m.id, "status": "cancelled"}, m.provider_meeting_id

    def join_link(self, ctx: Any, input: dict) -> Result:
        def run(c: Context):
            req = parse(JoinLink, input)
            provider, _ = self._provider(c)
            cfg = self._cfg_for_store(c)
            with self._db(c.organisation_id) as db:
                m = self._meeting(db, req.meeting_key, c.provider)
                if m.status in ("cancelled", "ended"):
                    raise AdapterError("conflict", f"a meeting that is {m.status} has no join link")
                ref = self._ref(cfg, m)
            if c.provider == "jitsi":
                url, exp = provider.mint(
                    c, ref, str(req.person_id), req.display_name, req.email, req.role in ("host", "co_host")
                )
                return {"url": url, "expires_at": exp.isoformat()}  # minted for this person, never stored
            url = (ref.host_join_url if req.role in ("host", "co_host") else None) or ref.join_url
            return {"url": url, "expires_at": None}

        return self._run(ctx, run)

    def get_meeting(self, ctx: Any, input: dict) -> Result:
        def run(c: Context):
            req = parse(MeetingRef, input)
            with self._db(c.organisation_id) as db:
                m = self._meeting(db, req.meeting_key, c.provider)
                return {
                    "meeting_id": m.id, "status": m.status, "started_at": iso(m.started_at), "ended_at": iso(m.ended_at),
                    "provider_meeting_id": m.provider_meeting_id,
                }, m.provider_meeting_id  # fmt: skip

        return self._run(ctx, run)

    # ------------------------------------------------------------------ attendance and recordings

    def fetch_attendance(self, ctx: Any, input: dict) -> Result:
        return self._run(ctx, lambda c: self._attendance(c, parse(FetchAttendance, input)))

    def _attendance(self, c: Context, req: FetchAttendance):
        provider, _ = self._provider(c)
        cfg = self._cfg_for_store(c)
        with self._db(c.organisation_id) as db:
            m = self._meeting(db, req.meeting_key, c.provider)
            if m.status == "cancelled":
                raise AdapterError("not_found", "the meeting was cancelled: there is no attendance")
            ref, m_id = self._ref(cfg, m), m.id
        people, ended_at = provider.attendance(c, ref)
        roster = {r.email.lower(): str(r.person_id) for r in req.roster}
        domain = str(c.settings.get("email_domain", "")).lower().lstrip("@")
        now = self.clock()
        with self._db(c.organisation_id) as db:
            m = db.get(Meeting, m_id)
            if ended_at and m.status in ("scheduled", "started"):
                m.status, m.ended_at = "ended", ended_at  # Teams has no event: the report's appearance is the signal
            end = aware(m.ended_at)
            complete = bool(people) and end is not None and now >= end + timedelta(minutes=cfg.attendance_delay_min)
            rows, out = [], []
            for p in people:
                person = _match(p, roster, domain)
                total, intervals = _totals(p, end)
                rows.append(
                    Attendance(
                        organisation_id=c.organisation_id,
                        meeting_id=m.id,
                        person_id=person,
                        display_name=None if person else p.display_name,
                        role=p.role,
                        total_seconds=total,
                        intervals=intervals,
                        complete=complete,
                    )  # fmt: skip
                )
                out.append({"person_id": person, "display_name": p.display_name, "email": p.email, "role": p.role,
                            "total_seconds": total, "intervals": intervals})  # fmt: skip
            for old in db.scalars(scoped(db, select(Attendance).where(Attendance.meeting_id == m.id), Attendance)):
                db.delete(old)
            db.add_all(rows)
            m.attendance_fetched_at = now
            self._audit(db, c, "attendance.stored", "meeting", m.id)
            db.commit()
            return {"meeting_id": m.id, "participants": out, "complete": complete}, m.provider_meeting_id

    def list_recordings(self, ctx: Any, input: dict) -> Result:
        return self._run(ctx, lambda c: self._recordings(c, parse(MeetingRef, input)))

    def _recordings(self, c: Context, req: MeetingRef):
        provider, _ = self._provider(c)
        cfg = self._cfg_for_store(c)
        with self._db(c.organisation_id) as db:
            m = self._meeting(db, req.meeting_key, c.provider)
            ref, m_id = self._ref(cfg, m), m.id
        files = provider.recordings(c, ref)
        with self._db(c.organisation_id) as db:
            known = {
                r.provider_recording_id: r
                for r in db.scalars(scoped(db, select(Recording).where(Recording.meeting_id == m_id), Recording))
            }
            for f in files:
                row = known.get(f.provider_recording_id)
                if row is None:
                    db.add(Recording(organisation_id=c.organisation_id, meeting_id=m_id, provider_recording_id=f.provider_recording_id,
                                     kind=f.kind, started_at=f.started_at, ended_at=f.ended_at, bytes=f.bytes, expires_at=f.expires_at))  # fmt: skip
                else:
                    row.kind, row.bytes = f.kind, f.bytes
            db.commit()
        items = [{"provider_recording_id": f.provider_recording_id, "kind": f.kind, "started_at": iso(f.started_at),
                  "ended_at": iso(f.ended_at), "bytes": f.bytes, "expires_at": iso(f.expires_at)} for f in files]  # fmt: skip
        return {"items": items}

    def import_recording(self, ctx: Any, input: dict) -> Result:
        return self._run(ctx, lambda c: self._import(c, parse(ImportRecording, input)))

    def _import(self, c: Context, req: ImportRecording):
        provider, cfg = self._provider(c)
        with self._db(c.organisation_id) as db:
            m = self._meeting(db, req.meeting_key, c.provider)
            ref, m_id = self._ref(self._cfg_for_store(c), m), m.id
            rec = db.scalar(
                scoped(
                    db,
                    select(Recording).where(
                        Recording.meeting_id == m_id, Recording.provider_recording_id == req.provider_recording_id
                    ),
                    Recording,
                )
            )
            if rec is not None and rec.document_id:
                return {"document_id": rec.document_id, "bytes": rec.bytes or 0, "sha256": rec.sha256 or ""}
        files = {f.provider_recording_id: f for f in provider.recordings(c, ref)}
        file = files.get(req.provider_recording_id)
        if file is None:
            raise AdapterError("not_found", "the provider has no such recording")
        chunks, close = provider.download(c, ref, file)
        digest, size = hashlib.sha256(), 0

        def counted() -> Iterator[bytes]:
            nonlocal size
            for chunk in chunks:
                size += len(chunk)
                if size > cfg.max_recording_bytes:
                    raise AdapterError(
                        "rejected", "the recording is larger than VIDEO_CONFERENCING_MAX_RECORDING_BYTES"
                    )
                digest.update(chunk)
                yield chunk

        try:
            doc_id = self.documents.store(
                organisation_id=c.organisation_id,
                name=f"recording-{m_id}-{file.kind}",
                content_type=_content_type(file.kind),
                chunks=counted(),
            )
        finally:
            close()
        with self._db(c.organisation_id) as db:
            rec = db.scalar(
                scoped(
                    db,
                    select(Recording).where(
                        Recording.meeting_id == m_id, Recording.provider_recording_id == req.provider_recording_id
                    ),
                    Recording,
                )
            )
            if rec is None:
                rec = Recording(
                    organisation_id=c.organisation_id,
                    meeting_id=m_id,
                    provider_recording_id=req.provider_recording_id,
                    kind=file.kind,
                )
                db.add(rec)
            rec.document_id, rec.bytes, rec.sha256 = str(doc_id), size, digest.hexdigest()
            db.flush()
            self._audit(db, c, "recording.imported", "recording", rec.id)
            db.commit()
        return {"document_id": str(doc_id), "bytes": size, "sha256": digest.hexdigest()}, req.provider_recording_id

    # ------------------------------------------------------------------ jobs the hub's scheduler runs

    def due_attendance(self, ctx: Any, input: dict | None = None) -> Result:
        """Meeting keys whose attendance report should now exist and has not been fetched. Providers with no ended event
        (Teams) are polled this way: the scheduler calls this, then fetch_attendance per key."""

        def run(c: Context):
            cfg = self._cfg_for_store(c)
            cutoff = self.clock() - timedelta(minutes=cfg.attendance_delay_min)
            with self._db(c.organisation_id) as db:
                rows = db.scalars(
                    scoped(
                        db,
                        select(Meeting)
                        .where(
                            Meeting.connection_id == c.connection_id,
                            Meeting.status.in_(("scheduled", "started", "ended")),
                            Meeting.attendance_fetched_at.is_(None),
                        )
                        .order_by(Meeting.starts_at)
                        .limit(500),
                        Meeting,
                    )  # fmt: skip
                ).all()
                keys = [
                    m.meeting_key for m in rows if aware(m.starts_at) + timedelta(minutes=m.duration_minutes) <= cutoff
                ]
            return {"meeting_keys": keys}

        return self._run(ctx, run)

    def renew_subscriptions(self, ctx: Any, input: dict | None = None) -> Result:
        """Renew the connection's Graph subscription before it lapses (they live under 3 days), or create it."""

        def run(c: Context):
            provider, cfg = self._provider(c)
            return {"renewed": self._ensure_subscription(c, provider, cfg, strict=True)}

        return self._run(ctx, run)

    def _ensure_subscription(self, c: Context, provider: Provider, cfg: Config, *, strict: bool = False) -> bool:
        try:
            with self._db(c.organisation_id) as db:
                sub = db.scalar(
                    scoped(
                        db,
                        select(GraphSubscription)
                        .where(GraphSubscription.connection_id == c.connection_id)
                        .order_by(GraphSubscription.expires_at.desc()),
                        GraphSubscription,
                    )
                )
                if sub is not None and aware(sub.expires_at) - self.clock() > timedelta(
                    minutes=cfg.teams_renew_lead_min
                ):
                    return False
                existing = (
                    None
                    if sub is None
                    else {
                        "subscription_id": sub.subscription_id,
                        "nonce": sub.client_state_ref,
                        "resource": sub.resource,
                    }
                )
                try:
                    got = provider.ensure_subscription(c, existing)
                except AdapterError as e:
                    if existing is None or e.code != "not_found":
                        raise
                    db.delete(sub)  # Graph forgot it: make a new one
                    got, sub = provider.ensure_subscription(c, None), None
                if sub is None:
                    db.add(GraphSubscription(organisation_id=c.organisation_id, connection_id=c.connection_id, subscription_id=got["subscription_id"],
                                             resource=got["resource"][:300], client_state_ref=got["nonce"], expires_at=got["expires_at"]))  # fmt: skip
                else:
                    sub.expires_at = got["expires_at"]
                self._audit(
                    db,
                    c,
                    "subscription.renewed" if existing else "subscription.created",
                    "graph_subscription",
                    got["subscription_id"][:36],
                )
                db.commit()
                return True
        except AdapterError:
            if strict:
                raise
            log.warning("video-conferencing: could not create or renew the Graph subscription")
            return False

    # ------------------------------------------------------------------ inbound

    def _request(self, request: dict) -> InboundRequest:
        if not isinstance(request, dict):
            raise AdapterError("invalid_request", "the inbound request must be an object")
        raw = request.get("raw_body", b"")
        if isinstance(raw, str):
            raw = raw.encode()
        if not isinstance(raw, (bytes, bytearray)) or len(raw) > MAX_RAW_BODY:
            raise AdapterError("invalid_request", "the inbound body is missing or too large")
        headers = request.get("headers") or {}
        query = request.get("query") or {}
        if not isinstance(headers, dict) or not isinstance(query, dict):
            raise AdapterError("invalid_request", "headers and query must be objects")
        return InboundRequest(str(request.get("method", "POST"))[:10], str(request.get("path_suffix", ""))[:200], query,
                              {str(k)[:100]: str(v)[:4096] for k, v in list(headers.items())[:100]}, bytes(raw), request.get("connection_id"))  # fmt: skip

    def _inbound_provider(self, ctx: Context | None, req: InboundRequest) -> tuple[Provider, Config]:
        cfg = self._config()
        pid = ctx.provider if ctx else ("zoom" if not req.path_suffix else None)
        if pid not in PROVIDERS:
            raise AdapterError("invalid_request", "cannot tell which provider this callback is for")
        return PROVIDERS[pid](cfg, Http(self._client_factory, cfg.http_timeout_s), self.clock), cfg

    def verify_inbound(self, ctx: Any | None, request: dict) -> Result:
        """Reject, handshake or accept. Never raises: whatever cannot be verified is a reject."""
        try:
            c = Context.coerce(ctx) if ctx else None
            req = self._request(request)
            provider, cfg = self._inbound_provider(c, req)
            verdict = provider.verify_inbound(c, req)
            if verdict["verdict"] == "accept" and provider.id == "teams" and not self._graph_state_ok(c, cfg, req):
                verdict = {"verdict": "reject", "reject_status": 401}
            if verdict["verdict"] == "accept" and provider.id == "zoom" and c is None:
                verdict["resolves_to"] = self._resolve_zoom(verdict.get("resolves_to"))
            elif verdict["verdict"] == "accept":
                verdict.setdefault("resolves_to", None)
            if verdict.get("resolves_to") and "provider_meeting_id" in verdict["resolves_to"]:
                verdict["resolves_to"].pop("provider_meeting_id")
            return Result(output=verdict)
        except AdapterError as e:
            if e.code == "invalid_request":
                return Result(output={"verdict": "reject", "reject_status": 400})
            return Result.failure(e)
        except Exception:
            log.exception("video-conferencing: verify_inbound failed")
            return Result(output={"verdict": "reject", "reject_status": 401})

    def _resolve_zoom(self, hint: dict | None) -> dict | None:
        """An app-level Zoom event names an account and a meeting: the meeting we created names the connection."""
        if not hint or not hint.get("provider_meeting_id"):
            return hint
        with platform_scope(), self._db(None) as db:
            m = db.scalar(
                select(Meeting).where(
                    Meeting.provider == "zoom", Meeting.provider_meeting_id == hint["provider_meeting_id"]
                )
            )
            if m is None:
                return {
                    "account_link_subject": hint.get("account_link_subject"),
                    "connection_id": None,
                    "provider_meeting_id": hint["provider_meeting_id"],
                }
            return {
                "connection_id": m.connection_id,
                "account_link_subject": hint.get("account_link_subject"),
                "provider_meeting_id": m.provider_meeting_id,
            }

    def _graph_state_ok(self, ctx: Context | None, cfg: Config, req: InboundRequest) -> bool:
        """Every notification must carry its subscription's clientState (compared in constant time)."""
        if ctx is None:
            return False
        try:
            entries = json.loads(req.raw_body)["value"]
        except (ValueError, KeyError, TypeError):
            return False
        with self._db(ctx.organisation_id) as db:
            subs = {
                s.subscription_id: s
                for s in db.scalars(
                    scoped(
                        db,
                        select(GraphSubscription).where(GraphSubscription.connection_id == ctx.connection_id),
                        GraphSubscription,
                    )
                )
            }
        for n in entries:
            sub = subs.get(n.get("subscriptionId"))
            if sub is None:
                return False
            want = crypto.client_state(cfg, ctx.connection_id, sub.client_state_ref)
            if not hmac.compare_digest(want.encode(), str(n.get("clientState", "")).encode()):
                return False
        return True

    def parse_inbound(self, ctx: Any | None, request: dict) -> Result:
        def run(c: Context | None):
            req = self._request(request)
            provider, cfg = self._inbound_provider(c, req)
            events = provider.parse_inbound(c, req)
            notes: list[dict] = []
            for ev in events:
                notes += self._apply_event(c, provider, cfg, ev)
            return {"notifications": notes}

        try:
            c = Context.coerce(ctx) if ctx else None
        except AdapterError as e:
            return Result.failure(e)
        return self._run_with(c, run)

    def _run_with(self, c, fn) -> Result:
        try:
            out = fn(c)
            return Result(output=out)
        except AdapterError as e:
            return Result.failure(e)
        except Exception:
            log.exception("video-conferencing: unexpected failure")
            return Result.failure(AdapterError("provider_error", "the adapter failed unexpectedly"))

    def _apply_event(self, c: Context | None, provider: Provider, cfg: Config, ev: ProviderEvent) -> list[dict]:
        if ev.kind in ("subscription_renew", "subscription_recreate"):
            if c is not None:
                self._force_subscription(c, provider, cfg, recreate=ev.kind == "subscription_recreate")
            return []
        if not ev.provider_meeting_id:
            return []
        org = c.organisation_id if c else None
        with platform_scope() if org is None else organisation_scope(org), self._db(org) as db:
            q = select(Meeting).where(
                Meeting.provider == provider.id, Meeting.provider_meeting_id == ev.provider_meeting_id
            )
            if c is not None:
                q = q.where(Meeting.connection_id == c.connection_id)
            m = db.scalar(scoped(db, q, Meeting) if org else q)
            if m is None:
                return []  # not a meeting this adapter made (someone's own Zoom meeting): not ours to report
            ctx = c or Context(organisation_id=m.organisation_id, connection_id=m.connection_id, provider=provider.id)
            key, notes = m.meeting_key, []
            if ev.instance_id and ev.kind in ("started", "ended"):
                m.provider_instance_id = ev.instance_id[:256]
            if ev.kind == "started" and m.status == "scheduled":
                m.status, m.started_at = "started", ev.at or self.clock()
                notes.append(_note("meeting_started", {"meeting_key": key, "started_at": iso(m.started_at)}))
                self._audit(db, ctx, "meeting.started", "meeting", m.id, m.organisation_id)
            elif ev.kind == "ended" and m.status in ("scheduled", "started"):
                m.status, m.ended_at = "ended", ev.at or self.clock()
                notes.append(_note("meeting_ended", {"meeting_key": key, "ended_at": iso(m.ended_at)}))
                # The hub runs fetch_attendance itself on this; not_before says when the provider will have the report.
                notes.append(
                    _note(
                        "attendance_ready",
                        {
                            "meeting_key": key,
                            "not_before": iso(aware(m.ended_at) + timedelta(minutes=cfg.attendance_delay_min)),
                        },
                    )
                )
                self._audit(db, ctx, "meeting.ended", "meeting", m.id, m.organisation_id)
            elif ev.kind == "deleted" and m.status == "scheduled":
                m.status = "cancelled"
                self._audit(db, ctx, "meeting.cancelled", "meeting", m.id, m.organisation_id)
            elif ev.kind == "recording_ready" and ev.recording_id:
                if (
                    db.scalar(
                        select(Recording).where(
                            Recording.meeting_id == m.id, Recording.provider_recording_id == ev.recording_id
                        )
                    )
                    is None
                ):
                    db.add(
                        Recording(
                            organisation_id=m.organisation_id,
                            meeting_id=m.id,
                            provider_recording_id=ev.recording_id,
                            kind=ev.recording_kind or "video",
                        )
                    )
                    notes.append(
                        _note(
                            "recording_ready",
                            {
                                "meeting_key": key,
                                "provider_recording_id": ev.recording_id,
                                "kind": ev.recording_kind or "video",
                            },
                        )
                    )
            db.commit()
            return notes

    def _force_subscription(self, c: Context, provider: Provider, cfg: Config, *, recreate: bool) -> None:
        with self._db(c.organisation_id) as db:
            if recreate:
                for s in db.scalars(
                    scoped(
                        db,
                        select(GraphSubscription).where(GraphSubscription.connection_id == c.connection_id),
                        GraphSubscription,
                    )
                ):
                    db.delete(s)
            else:
                for s in db.scalars(
                    scoped(
                        db,
                        select(GraphSubscription).where(GraphSubscription.connection_id == c.connection_id),
                        GraphSubscription,
                    )
                ):
                    s.expires_at = self.clock()  # due now: the next step renews it
            db.commit()
        self._ensure_subscription(c, provider, cfg)


# ---------------------------------------------------------------------- helpers


def _with_mode(cfg: Config, mode: str) -> Config:
    return replace(cfg, mode=mode)


def _note(kind: str, data: dict) -> dict:
    return {"port": "meetings", "kind": kind, "data": data}


def _content_type(kind: str) -> str:
    return {"video": "video/mp4", "audio": "audio/mp4", "transcript": "text/vtt", "chat": "text/plain"}.get(
        kind, "application/octet-stream"
    )


def _match(p: Participant, roster: dict[str, str], domain: str) -> str | None:
    """A participant's person id by email, only for an address in the institution's own domain when it names one."""
    if not p.email:
        return None
    if domain and not p.email.endswith("@" + domain):
        return None
    return roster.get(p.email)


def _totals(p: Participant, ended: datetime | None) -> tuple[int, list[dict]]:
    intervals, summed = [], 0
    for joined, left in p.intervals[:500]:
        end = left or ended
        if end is not None and end > joined:
            summed += int((end - joined).total_seconds())
        intervals.append({"joined_at": iso(joined), "left_at": iso(left)})
    return (p.total_seconds if p.total_seconds is not None else summed), intervals


def _auth_input(input: Any, required: tuple[str, ...]) -> dict:
    if not isinstance(input, dict):
        raise AdapterError("invalid_request", "the input must be an object")
    out: dict[str, Any] = {}
    for key in required:
        v = input.get(key)
        limit = {"redirect_uri": 2000, "code": 4096, "state": 512}.get(key, 256)
        if not isinstance(v, str) or not 1 <= len(v) <= limit or any(ord(ch) < 32 for ch in v):
            raise AdapterError("invalid_request", f"invalid input: {key}")
        out[key] = v
    if "redirect_uri" in out and not out["redirect_uri"].startswith(("https://", "http://")):
        raise AdapterError("invalid_request", "invalid input: redirect_uri")
    hint = input.get("scope_hint") or []
    if not isinstance(hint, list) or len(hint) > 50 or not all(isinstance(s, str) and len(s) <= 200 for s in hint):
        raise AdapterError("invalid_request", "invalid input: scope_hint")
    out["scope_hint"] = hint
    return out


def startup_check(cfg: Config | None = None) -> None:
    """Live mode refuses to start without what it needs: Rooman's platform app credentials for every provider that has
    them, and the data key that protects stored join links. Sandbox needs the data key only."""
    cfg = cfg or Config.load()
    if cfg.mode == "mock":
        return
    missing = ["VIDEO_CONFERENCING_DATA_KEY"] if not cfg.data_key else []
    if cfg.mode == "live":
        wanted = [p.strip() for p in (_providers_env() or ",".join(PROVIDER_IDS)).split(",") if p.strip()]
        for p in wanted:
            if p in PROVIDER_IDS:
                missing += cfg.missing_credentials(p)
        if "teams" in wanted or "zoom" in wanted or "webex" in wanted:
            missing += [] if cfg.public_base_url else ["VIDEO_CONFERENCING_PUBLIC_BASE_URL"]
    if missing:
        raise AdapterError("not_configured", "live/sandbox mode needs: " + ", ".join(sorted(set(missing))))


def _providers_env() -> str:
    return os.environ.get("VIDEO_CONFERENCING_PROVIDERS", "")


def get_adapter(**kwargs) -> VideoConferencingAdapter:
    """The entry-point factory (eos.integration_adapters): refuses to start when the configured mode lacks credentials."""
    startup_check()
    return VideoConferencingAdapter(**kwargs)
