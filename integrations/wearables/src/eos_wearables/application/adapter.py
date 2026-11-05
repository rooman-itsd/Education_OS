"""The wearable-data port and the Adapter contract (contracts/ports/wearable-data.yaml, adapter.yaml) over Garmin, Polar,
Fitbit (Google Health API) and Strava.

Every operation takes the hub's call context and an input object and returns a Result: an output, or an error from the
contract's one vocabulary. Nothing raises to the caller and nothing is a 500: input is validated and bounded first,
provider failures are mapped, and a bug is reported as a generic provider_error and logged without its data.

Health data is the most sensitive personal data Education OS holds. Nothing is collected without the athlete's own link;
every read states a purpose and is logged; Strava records are returned only for the athlete's own view; revoking a link
(or the provider reporting it) deletes every record collected under it at once. The adapter publishes no events of its own
(contracts/events.yaml), so there is no outbox write; every state change writes an audit entry in the same transaction."""

from __future__ import annotations

import base64
import binascii
import logging
import os
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

from eos_core.db import SessionLocal, scoped
from eos_core.tenant import organisation_scope, platform_scope
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import __version__
from ..domain.context import Context, Result
from ..domain.errors import AdapterError
from ..domain.models import DATA_TYPES, LinkAccount, LinkStatus, Read, Sync, UnlinkAccount, parse
from ..infrastructure.config import PROVIDERS as PROVIDER_IDS
from ..infrastructure.config import Config
from ..infrastructure.http import Http
from ..infrastructure.models import AuditEntry, LinkState, ReadLog, Record, aware, iso
from ..infrastructure.providers import PROVIDERS
from ..infrastructure.providers.base import InboundEvent, InboundRequest, Normal, Provider, utcnow
from ..infrastructure.providers.mock import MockProvider

log = logging.getLogger("eos.wearables")
MAX_RAW_BODY = 1024 * 1024
ATHLETE_SELF = "athlete_self"


def _today(clock: Callable[[], datetime]) -> date:
    return clock().astimezone(UTC).date()


class WearablesAdapter:
    name = "wearables"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] = SessionLocal,
        client_factory=None,
        clock: Callable[[], datetime] = utcnow,
        config: Callable[[], Config] = Config.load,
    ) -> None:
        self._session_factory = session_factory
        self._client_factory = client_factory
        self.clock = clock
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
                    "ports": ["wearable-data"],
                    "modes": ["mock", "sandbox", "live"],
                    "auth": p.auth,
                    "link_scope": p.link_scope,
                    "inbound": list(p.inbound),
                    "settings_schema": p.settings_schema,
                    "credential_names": list(p.credential_names),
                    "platform_credential_names": [f"WEARABLES_{n}" for n in p.platform_credential_names],
                }
            )
        return {
            "adapter": self.name,
            "version": __version__,
            "ports": [{"port": "wearable-data", "version": 1}],
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
            log.exception("wearables: unexpected failure")
            return Result.failure(AdapterError("provider_error", "the adapter failed unexpectedly"))

    def _audit(self, db: Session, ctx: Context | None, org: str, action: str, entity: str, entity_id: str) -> None:
        actor = str(ctx.delivery_id)[:36] if ctx and ctx.delivery_id else None
        db.add(
            AuditEntry(
                organisation_id=org,
                actor=actor,
                action=action,
                entity=entity,
                entity_id=entity_id,
                occurred_at=self.clock(),
            )
        )

    @staticmethod
    def _types_for(provider: Provider, ctx: Context, requested: list[str]) -> list[str]:
        """Data types for a link: what was asked (or all), what the provider offers, what the connection collects."""
        enabled = ctx.settings.get("data_types")
        allowed = [
            t for t in DATA_TYPES if t in provider.data_types and (not isinstance(enabled, list) or t in enabled)
        ]
        return [t for t in allowed if not requested or t in requested]

    # ------------------------------------------------------------------ Adapter contract

    def capabilities(self, ctx: Any, input: dict | None = None) -> Result:
        def run(c: Context):
            provider, _ = self._provider(c)
            return {"port": "wearable-data", "capabilities": provider.capabilities(c)}

        return self._run(ctx, run)

    def healthcheck(self, ctx: Any, input: dict | None = None) -> Result:
        def run(c: Context):
            provider, cfg = self._provider(c)
            missing = cfg.missing_credentials(c.provider) if (c.mode or cfg.mode) != "mock" else []
            if missing:
                return {
                    "status": "auth_failed",
                    "detail": "platform credentials missing: " + ", ".join(missing),
                    "expires_at": None,
                }
            return provider.healthcheck(c)

        return self._run(ctx, run)

    def begin_authorisation(self, ctx: Any, input: dict) -> Result:
        def run(c: Context):
            a = _auth_input(input, ("state", "code_challenge", "redirect_uri"))
            provider, _ = self._provider(c)
            return {
                "authorize_url": provider.begin_authorisation(
                    c, a["state"], a["code_challenge"], a["redirect_uri"], a["scope_hint"]
                )
            }

        return self._run(ctx, run)

    def complete_authorisation(self, ctx: Any, input: dict) -> Result:
        return self._run(ctx, lambda c: self._complete(c, input))

    def _complete(self, c: Context, input: dict):
        a = _auth_input(input, ("code", "code_verifier", "redirect_uri"))
        provider, cfg = self._provider(c)
        out = provider.complete_authorisation(c, a["code"], a["code_verifier"], a["redirect_uri"])
        link = c.account_link or {}
        link_id, person_id = str(link.get("id") or ""), str(link.get("person_id") or "")
        if link_id and person_id:
            with_tokens = replace(c, secrets=out["secrets"])
            provider.register_user(
                with_tokens, person_id, out["provider_subject"]
            )  # Polar: POST /v3/users, 409 is success
            with self._db(c.organisation_id) as db:
                row = db.scalar(scoped(db, select(LinkState).where(LinkState.account_link_id == link_id), LinkState))
                if row is None:
                    row = LinkState(organisation_id=c.organisation_id, connection_id=c.connection_id, account_link_id=link_id, person_id=person_id,
                                    provider=c.provider, data_types=self._types_for(provider, c, []))  # fmt: skip
                    db.add(row)
                self._activate(row, out["provider_subject"])
                db.flush()
                self._audit(db, c, c.organisation_id, "link.connected", "link", row.account_link_id)
                db.commit()
            if provider.backfill_mode == "request" and cfg.default_backfill_days:
                try:  # asking Garmin for history is best effort: Starter has none, and a refusal must not undo the link
                    end = _today(self.clock)
                    provider.backfill(
                        with_tokens,
                        self._types_for(provider, c, []),
                        end - timedelta(days=cfg.default_backfill_days),
                        end,
                    )
                except AdapterError:
                    log.info("wearables: no backfill requested for a new link")
        return out, out.get("provider_subject")

    def _activate(self, row: LinkState, subject: str | None) -> None:
        row.status, row.status_since = "active", self.clock()
        row.provider_subject = subject or row.provider_subject
        row.consecutive_failures, row.failing_since, row.last_error_code = 0, None, None

    def refresh_authorisation(self, ctx: Any, input: dict | None = None) -> Result:
        def run(c: Context):
            provider, _ = self._provider(c)
            try:
                return provider.refresh_authorisation(c)
            except AdapterError as e:
                if e.code == "consent_required" and c.account_link and c.account_link.get("id"):
                    self._set_status(c, str(c.account_link["id"]), "expired", e.code)  # the link can no longer fetch
                raise

        return self._run(ctx, run)

    def revoke_authorisation(self, ctx: Any, input: dict | None = None) -> Result:
        return self._run(ctx, lambda c: {"revoked": self._provider(c)[0].revoke_authorisation(c)})

    def _set_status(self, c: Context, account_link_id: str, status: str, error_code: str | None) -> None:
        with self._db(c.organisation_id) as db:
            row = db.scalar(
                scoped(db, select(LinkState).where(LinkState.account_link_id == account_link_id), LinkState)
            )
            if row is not None and row.status != status:
                row.status, row.status_since, row.last_error_code = status, self.clock(), error_code
                self._audit(db, c, c.organisation_id, f"link.{status}", "link", account_link_id)
                db.commit()

    # ------------------------------------------------------------------ the port: linking

    def link_account(self, ctx: Any, input: dict) -> Result:
        return self._run(ctx, lambda c: self._link_new(c, parse(LinkAccount, input)))

    def _link_new(self, c: Context, req: LinkAccount):
        if req.provider != c.provider:
            raise AdapterError("invalid_request", "the provider of the call and of the input differ")
        if req.minor and not req.guardian_consent_recorded:
            raise AdapterError(
                "invalid_request",
                "guardian_consent_required: an athlete under 18 cannot link a device until a guardian's consent is recorded",
            )
        provider, _ = self._provider(c)
        types = self._types_for(provider, c, list(req.data_types))
        if not types:
            raise AdapterError(
                "invalid_request",
                "this provider offers none of the requested data types, or the organisation collects none of them",
            )
        with self._db(c.organisation_id) as db:
            mine = db.scalars(
                scoped(
                    db,
                    select(LinkState).where(
                        LinkState.person_id == str(req.person_id), LinkState.provider == c.provider
                    ),
                    LinkState,
                )
            ).all()
            hub_id = str(req.account_link_id) if req.account_link_id else None
            if any(m.status == "active" and m.account_link_id != hub_id for m in mine):
                raise AdapterError("conflict", "this athlete already has an active link to this provider")
            row = next((m for m in mine if hub_id and m.account_link_id == hub_id), None) or next(
                (m for m in mine if m.status in ("pending", "expired", "error", "revoked")), None
            )
            if row is None:
                row = LinkState(
                    organisation_id=c.organisation_id,
                    connection_id=c.connection_id,
                    account_link_id=hub_id or str(uuid.uuid4()),
                    person_id=str(req.person_id),
                    provider=c.provider,
                )
                db.add(row)
            row.account_link_id, row.connection_id, row.data_types = (
                hub_id or row.account_link_id,
                c.connection_id,
                types,
            )
            row.status, row.status_since, row.provider_subject = "pending", self.clock(), None
            row.consecutive_failures, row.failing_since, row.last_error_code = 0, None, None
            link_id = row.account_link_id
            url = provider.begin_authorisation(c, req.state, req.code_challenge, req.redirect_uri, [])
            db.flush()
            self._audit(db, c, c.organisation_id, "link.started", "link", link_id)
            db.commit()
        return {"account_link_id": link_id, "authorize_url": url, "data_types": types}

    def unlink_account(self, ctx: Any, input: dict) -> Result:
        return self._run(ctx, lambda c: self._unlink(c, parse(UnlinkAccount, input)))

    def _unlink(self, c: Context, req: UnlinkAccount):
        provider, _ = self._provider(c)
        with self._db(c.organisation_id) as db:
            row = self._link_lookup(db, str(req.account_link_id))
            deleted = self._revoke_row(db, c, row, "link.revoked")
        try:
            provider.revoke_authorisation(
                c
            )  # after the deletion, so a provider that is down cannot keep health data here
        except AdapterError as e:
            if e.retryable:
                raise
        return {"account_link_id": str(req.account_link_id), "status": "revoked", "records_deleted": deleted}

    def _link_lookup(self, db: Session, account_link_id: str) -> LinkState:
        row = db.scalar(scoped(db, select(LinkState).where(LinkState.account_link_id == account_link_id), LinkState))
        if row is None:
            raise AdapterError("not_found", "no account link with this id")
        return row

    def _revoke_row(self, db: Session, c: Context | None, row: LinkState, action: str) -> int:
        """Mark the link revoked and delete every record collected under it, in one transaction. Idempotent."""
        res = db.execute(
            delete(Record).where(
                Record.account_link_id == row.account_link_id, Record.organisation_id == row.organisation_id
            )
        )
        deleted = res.rowcount or 0
        if row.status != "revoked":
            row.status, row.status_since = "revoked", self.clock()
        row.last_data_at = row.last_synced_at = None
        self._audit(db, c, row.organisation_id, action, "link", row.account_link_id)
        db.commit()
        return deleted

    def revoke_by_link_id(self, organisation_id: str, account_link_id: str, db: Session | None = None) -> int:
        """integration-hub.account-link.revoked: delete what was collected under the link (see consumers.py)."""
        own = db is None
        session = self._session_factory() if own else db
        try:
            session.info["organisation_id"] = organisation_id
            with organisation_scope(organisation_id):
                row = session.scalar(
                    scoped(session, select(LinkState).where(LinkState.account_link_id == account_link_id), LinkState)
                )
                if row is None:
                    return 0
                return self._revoke_row(session, None, row, "link.revoked")
        finally:
            if own:
                session.close()

    # ------------------------------------------------------------------ the port: data

    def sync(self, ctx: Any, input: dict) -> Result:
        return self._run(ctx, lambda c: self._sync(c, parse(Sync, input)))

    def _window(self, cfg: Config, row: LinkState, req_from: date | None, req_to: date | None) -> tuple[date, date]:
        end = req_to or _today(self.clock)
        if req_from:
            return req_from, max(end, req_from)
        last = aware(row.last_synced_at)
        start = last.date() - timedelta(days=1) if last else end - timedelta(days=cfg.default_backfill_days)
        return min(start, end), end

    def _sync(self, c: Context, req: Sync):
        provider, cfg = self._provider(c)
        with self._db(c.organisation_id) as db:
            row = self._link_lookup(db, str(req.account_link_id))
            if row.provider != c.provider:
                raise AdapterError("not_found", "no account link with this id")
            if row.status in ("revoked", "expired", "pending"):
                raise AdapterError("consent_required", f"the athlete's link is {row.status}")
            start, end = self._window(cfg, row, req.from_, req.to)
            enabled = c.settings.get("data_types")  # only what the organisation collects is fetched
            granted = [t for t in (row.data_types or []) if not isinstance(enabled, list) or t in enabled]
            asked = list(req.data_types)
            if asked:
                unsupported = [t for t in asked if t not in provider.data_types]
                if unsupported:
                    raise AdapterError("unsupported", f"this provider does not offer: {', '.join(unsupported)}")
                not_granted = [t for t in asked if t not in granted]
                if not_granted:
                    raise AdapterError(
                        "consent_required", f"the athlete's link does not cover: {', '.join(not_granted)}"
                    )
            types = asked or granted
            link = {
                "id": row.account_link_id,
                "org": row.organisation_id,
                "person": row.person_id,
                "provider_subject": row.provider_subject,
            }
        ctx = replace(
            c,
            account_link={"id": link["id"], "person_id": link["person"], "provider_subject": link["provider_subject"]},
        )
        found: list[Normal] = []
        denied: list[str] = []
        try:
            for t in types:
                try:
                    found += provider.pull(ctx, t, start, end)
                except AdapterError as e:
                    if e.code == "consent_required" and e.provider_code == "403":
                        denied.append(t)
                        continue
                    raise
        except AdapterError as e:
            self._failed(c, link["id"], e)
            raise
        if denied and len(denied) == len(types):
            self._failed(c, link["id"], AdapterError("consent_required", "denied", provider_code="403"), count=False)
            raise AdapterError(
                "consent_required", f"the athlete did not grant: {', '.join(denied)}", provider_code="403"
            )
        stored, updated = self._store(c, link["id"], found, ctx.settings, narrow=denied)
        return {"stored": stored, "updated": updated, "from": start.isoformat(), "to": end.isoformat()}, link[
            "provider_subject"
        ]

    def _failed(self, c: Context, link_id: str, e: AdapterError, *, count: bool = True) -> None:
        with self._db(c.organisation_id) as db:
            row = db.scalar(scoped(db, select(LinkState).where(LinkState.account_link_id == link_id), LinkState))
            if row is None:
                return
            row.last_error_code = e.code
            if e.code == "consent_required" and e.provider_code != "403":
                if row.status != "expired":
                    row.status, row.status_since = "expired", self.clock()
                    self._audit(db, c, row.organisation_id, "link.expired", "link", link_id)
            elif count:
                row.consecutive_failures += 1
                row.failing_since = row.failing_since or self.clock()
            db.commit()

    def _display_scope(self, provider: str, settings: dict) -> str:
        return (
            "athlete_only"
            if provider == "strava" and settings.get("strava_shared_display_approved") is not True
            else "all"
        )

    def _store(
        self,
        c: Context | None,
        link_id: str,
        records: list[Normal],
        settings: dict,
        *,
        narrow: list[str] | None = None,
        org: str | None = None,
    ) -> tuple[int, int]:
        """Upsert the records of one link, update its freshness, audit once: (stored, updated). One transaction."""
        organisation = org or (c.organisation_id if c else None)
        with self._db(organisation) as db:
            row = db.scalar(scoped(db, select(LinkState).where(LinkState.account_link_id == link_id), LinkState))
            if row is None or row.status == "revoked":
                return 0, 0
            scope = self._display_scope(row.provider, settings)
            keys = (
                {
                    (r.data_type, r.provider_record_id): r
                    for r in db.scalars(scoped(db, select(Record).where(Record.account_link_id == link_id), Record))
                }
                if records
                else {}
            )
            stored = updated = 0
            now = self.clock()
            for n in records:
                have = keys.get((n.data_type, n.provider_record_id[:200]))
                if have is None:
                    new = Record(organisation_id=row.organisation_id, account_link_id=link_id, person_id=row.person_id, provider=row.provider, data_type=n.data_type,
                                 provider_record_id=n.provider_record_id[:200], record_date=n.record_date, fields=n.fields, display_scope=scope, received_at=now)  # fmt: skip
                    db.add(new)
                    keys[(n.data_type, new.provider_record_id)] = new
                    stored += 1
                elif have.fields != n.fields or have.record_date != n.record_date:
                    have.fields, have.record_date, have.received_at = n.fields, n.record_date, now
                    updated += 1
            row.last_synced_at = now
            row.consecutive_failures, row.failing_since, row.last_error_code = 0, None, None
            if stored or updated:
                row.last_data_at = now
            if narrow:
                row.data_types = [t for t in (row.data_types or []) if t not in narrow]
            if stored or updated or narrow:
                self._audit(
                    db,
                    c,
                    row.organisation_id,
                    "records.stored" if stored or updated else "link.narrowed",
                    "link",
                    link_id,
                )
            db.commit()
        return stored, updated

    def request_backfill(self, ctx: Any, input: dict) -> Result:
        return self._run(ctx, lambda c: self._backfill(c, parse(Sync, input)))

    def _backfill(self, c: Context, req: Sync):
        provider, cfg = self._provider(c)
        caps = provider.capabilities(c)
        if not caps["backfill_days"] or provider.backfill_mode is None:
            raise AdapterError("unsupported", "this provider offers no history before the link was made")
        end = req.to or _today(self.clock)
        available = max(
            req.from_ or end - timedelta(days=cfg.default_backfill_days),
            end - timedelta(days=int(caps["backfill_days"])),
        )
        with self._db(c.organisation_id) as db:
            row = self._link_lookup(db, str(req.account_link_id))
            if row.status != "active":
                raise AdapterError("consent_required", f"the athlete's link is {row.status}")
            types = [
                t
                for t in (req.data_types or row.data_types or [])
                if t in provider.data_types and t in (row.data_types or [])
            ]
            link = {"id": row.account_link_id, "person": row.person_id, "sub": row.provider_subject}
        ctx = replace(c, account_link={"id": link["id"], "person_id": link["person"], "provider_subject": link["sub"]})
        if provider.backfill_mode == "request":
            provider.backfill(ctx, types, available, end)
        else:  # the history is read like any other window
            self._sync(c, Sync(account_link_id=req.account_link_id, data_types=types, **{"from": available, "to": end}))
        return {"requested": True, "available_from": available.isoformat()}

    # ------------------------------------------------------------------ the port: reads

    def read(self, ctx: Any, input: dict) -> Result:
        return self._run(ctx, lambda c: self._read(c, parse(Read, input)))

    def _read(self, c: Context, req: Read):
        person = str(req.person_id)
        self_view = req.purpose == ATHLETE_SELF
        if self_view:
            asker = str(req.requester_person_id or (c.account_link or {}).get("person_id") or "")
            if asker != person:
                raise AdapterError(
                    "consent_required", "athlete_self is the athlete's own view: the requester must be the athlete"
                )
        elif c.settings.get("share_with_coaches") is False:
            raise AdapterError("consent_required", "the organisation does not share device data with coaches")
        cursor = _decode_cursor(req.cursor) if req.cursor else None
        approved = c.settings.get("strava_shared_display_approved") is True
        with self._db(c.organisation_id) as db:
            links = db.scalars(
                scoped(
                    db, select(LinkState).where(LinkState.person_id == person, LinkState.status != "revoked"), LinkState
                )
            ).all()
            if not links:
                raise AdapterError("consent_required", "the athlete has no device link")
            q = scoped(
                db,
                select(Record).where(
                    Record.person_id == person,
                    Record.data_type == req.data_type,
                    Record.record_date >= req.from_,
                    Record.record_date <= req.to,
                ),
                Record,
            )
            if not self_view:
                # Strava's terms: its data may be shown only to its athlete, unless Strava approved wider display in writing.
                q = q.where(Record.display_scope == "all")
                if not approved:
                    q = q.where(Record.provider != "strava")
            if cursor:
                q = q.where(
                    (Record.record_date > cursor[0]) | ((Record.record_date == cursor[0]) & (Record.id > cursor[1]))
                )
            rows = db.scalars(q.order_by(Record.record_date, Record.id).limit(req.limit + 1)).all()
            page = rows[: req.limit]
            visible = [lk for lk in links if self_view or lk.provider != "strava" or approved]
            synced = [aware(lk.last_synced_at) for lk in visible if lk.last_synced_at]
            db.add(ReadLog(organisation_id=c.organisation_id, person_id=person, caller_module=req.caller_module, purpose=req.purpose, data_type=req.data_type,
                           date_from=req.from_, date_to=req.to, read_at=self.clock()))  # fmt: skip
            db.commit()
            items = [{**r.fields, "provider": r.provider} for r in page]
            nxt = _encode_cursor(page[-1]) if len(rows) > req.limit else None
            return {"items": items, "next_cursor": nxt, "last_synced_at": iso(max(synced)) if synced else None}

    def link_status(self, ctx: Any, input: dict) -> Result:
        def run(c: Context):
            req = parse(LinkStatus, input)
            with self._db(c.organisation_id) as db:
                rows = (
                    db.scalars(
                        scoped(
                            db,
                            select(LinkState)
                            .where(LinkState.person_id.in_([str(p) for p in req.person_ids]))
                            .order_by(LinkState.created_at),
                            LinkState,
                        )
                    ).all()
                    if req.person_ids
                    else []
                )
                return {
                    "items": [
                        {
                            "person_id": r.person_id,
                            "account_link_id": r.account_link_id,
                            "provider": r.provider,
                            "status": r.status,
                            "last_synced_at": None if r.provider == "strava" else iso(r.last_synced_at),
                            "data_types": list(r.data_types or []),
                        }  # fmt: skip
                        for r in rows
                    ]
                }

        return self._run(ctx, run)

    def purge_expired(self, ctx: Any, input: dict | None = None) -> Result:
        """Retention: delete the organisation's records older than WEARABLES_RETENTION_DAYS (the hub's scheduler runs it daily)."""

        def run(c: Context):
            cfg = self._config()
            cutoff = _today(self.clock) - timedelta(days=cfg.retention_days)
            with self._db(c.organisation_id) as db:
                n = (
                    db.execute(
                        delete(Record).where(Record.organisation_id == c.organisation_id, Record.record_date < cutoff)
                    ).rowcount
                    or 0
                )
                if n:
                    self._audit(db, c, c.organisation_id, "records.expired", "organisation", c.organisation_id)
                db.commit()
            return {"records_deleted": n, "older_than": cutoff.isoformat()}

        return self._run(ctx, run)

    # ------------------------------------------------------------------ inbound

    def _request(self, request: dict) -> InboundRequest:
        if not isinstance(request, dict):
            raise AdapterError("invalid_request", "the inbound request must be an object")
        raw = request.get("raw_body", b"")
        if isinstance(raw, str):
            raw = raw.encode()
        if not isinstance(raw, (bytes, bytearray)) or len(raw) > MAX_RAW_BODY:
            raise AdapterError("invalid_request", "the inbound body is missing or too large")
        headers, query = request.get("headers") or {}, request.get("query") or {}
        if not isinstance(headers, dict) or not isinstance(query, dict):
            raise AdapterError("invalid_request", "headers and query must be objects")
        return InboundRequest(str(request.get("method", "POST"))[:10], str(request.get("path_suffix", ""))[:200], {str(k)[:100]: v for k, v in list(query.items())[:50]},
                              {str(k)[:100]: str(v)[:4096] for k, v in list(headers.items())[:100]}, bytes(raw), request.get("connection_id"))  # fmt: skip

    def _inbound_provider(self, ctx: Context | None, req: InboundRequest) -> tuple[Provider, Config]:
        cfg = self._config()
        pid = ctx.provider if ctx else req.q("provider")
        if pid not in PROVIDERS:
            raise AdapterError("invalid_request", "cannot tell which provider this callback is for")
        return PROVIDERS[pid](cfg, Http(self._client_factory, cfg.http_timeout_s), self.clock), cfg

    def _link_of(self, provider: str) -> Callable[[str], dict | None]:
        def find(subject: str) -> dict | None:
            with platform_scope(), self._db(None) as db:
                row = db.scalar(
                    select(LinkState)
                    .where(
                        LinkState.provider == provider,
                        LinkState.provider_subject == subject[:128],
                        LinkState.status == "active",
                    )
                    .order_by(LinkState.created_at)
                )
                if row is None:
                    return None
                return {
                    "connection_id": row.connection_id,
                    "organisation_id": row.organisation_id,
                    "account_link_id": row.account_link_id,
                    "person_id": row.person_id,
                }

        return find

    def verify_inbound(self, ctx: Any | None, request: dict) -> Result:
        """Reject, handshake or accept. Never raises: whatever cannot be verified is a reject."""
        try:
            c = Context.coerce(ctx) if ctx else None
            req = self._request(request)
            provider, _ = self._inbound_provider(c, req)
            return Result(output=provider.verify_inbound(req, self._link_of(provider.id)))
        except AdapterError as e:
            if e.code == "invalid_request":
                return Result(output={"verdict": "reject", "reject_status": 400})
            return Result.failure(e)
        except Exception:
            log.exception("wearables: verify_inbound failed")
            return Result(output={"verdict": "reject", "reject_status": 401})

    def parse_inbound(self, ctx: Any | None, request: dict) -> Result:
        try:
            c = Context.coerce(ctx) if ctx else None
            req = self._request(request)
            provider, cfg = self._inbound_provider(c, req)
            notes: list[dict] = []
            for ev in provider.parse_inbound(req):
                notes += self._apply(c, provider, cfg, ev)
            return Result(output={"notifications": notes})
        except AdapterError as e:
            return Result.failure(e)
        except Exception:
            log.exception("wearables: parse_inbound failed")
            return Result.failure(AdapterError("provider_error", "the adapter failed unexpectedly"))

    def _apply(self, c: Context | None, provider: Provider, cfg: Config, ev: InboundEvent) -> list[dict]:
        found = self._link_of(provider.id)(ev.subject)
        if found is None:
            return []  # not an athlete with an active link: nothing is stored, nothing is announced
        org, link_id = found["organisation_id"], found["account_link_id"]
        settings = c.settings if c and c.organisation_id == org else {}
        if ev.kind == "data":
            self._store(c, link_id, ev.records, settings, org=org)
            return [
                _note(
                    "data_available",
                    {
                        "account_link_subject": ev.subject,
                        "data_types": ev.data_types,
                        "from": _d(ev.start),
                        "to": _d(ev.end),
                    },
                )
            ]
        if ev.kind == "changed":
            return [
                _note(
                    "data_available",
                    {
                        "account_link_subject": ev.subject,
                        "data_types": ev.data_types,
                        "from": _d(ev.start),
                        "to": _d(ev.end),
                    },
                )
            ]
        with self._db(org) as db:
            row = db.scalar(scoped(db, select(LinkState).where(LinkState.account_link_id == link_id), LinkState))
            if row is None:
                return []
            if ev.kind == "revoked":
                self._revoke_row(db, c, row, "link.revoked_by_provider")
                return [_note("link_revoked_by_provider", {"account_link_subject": ev.subject})]
            if ev.kind == "narrowed":
                row.data_types = [t for t in (row.data_types or []) if t in ev.data_types]
                self._audit(db, c, org, "link.narrowed", "link", link_id)
                db.commit()
            elif ev.kind == "deleted":
                db.execute(
                    delete(Record).where(
                        Record.account_link_id == link_id,
                        Record.organisation_id == org,
                        Record.provider_record_id.in_([i[:200] for i in ev.record_ids]),
                    )
                )
                self._audit(db, c, org, "records.deleted", "link", link_id)
                db.commit()
        return []


# ---------------------------------------------------------------------- helpers


def _note(kind: str, data: dict) -> dict:
    return {"port": "wearable-data", "kind": kind, "data": data}


def _d(v: date | None) -> str | None:
    return v.isoformat() if v else None


def _encode_cursor(r: Record) -> str:
    return base64.urlsafe_b64encode(f"{r.record_date.isoformat()}|{r.id}".encode()).decode()


def _decode_cursor(cursor: str) -> tuple[date, str]:
    try:
        d, rid = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 1)
        if len(rid) != 36:
            raise ValueError
        return date.fromisoformat(d), rid
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise AdapterError("invalid_request", "invalid input: cursor") from None


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
    """Live mode refuses to start without Rooman's developer app credentials for every provider it serves; sandbox and
    mock start regardless (each call then names what it lacks)."""
    cfg = cfg or Config.load()
    if cfg.mode != "live":
        return
    wanted = [
        p.strip() for p in (os.environ.get("WEARABLES_PROVIDERS", "") or ",".join(PROVIDER_IDS)).split(",") if p.strip()
    ]
    missing: list[str] = []
    for p in wanted:
        if p in PROVIDER_IDS:
            missing += cfg.missing_credentials(p)
    if missing:
        raise AdapterError("not_configured", "live mode needs: " + ", ".join(sorted(set(missing))))


def get_adapter(**kwargs) -> WearablesAdapter:
    """The entry-point factory (eos.integration_adapters): refuses to start when live mode lacks credentials."""
    startup_check()
    return WearablesAdapter(**kwargs)
