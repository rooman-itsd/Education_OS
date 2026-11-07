"""Indexing from events (docs/prd.md, decision 1).

An event only says that a record changed. For an `upsert` trigger the module's provider is asked for the record's
current document, in the event's organisation, and that is written with an external version taken from the event's
time, so repeated or out-of-order delivery is harmless. A `delete` trigger removes the document without a call.

`organisation_id` comes from the event envelope and nowhere else. A provider that returns a document naming another
organisation is refused. A failing provider or engine call is retried with backoff; after the last attempt the
document is counted as dead-lettered (visible in GET /platform/health) and a reindex repairs it. The handler does
not raise for those, because raising would make the relay redeliver the event for ever to the same failure."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..domain.declarations import TypeSpec
from ..domain.documents import DocumentRejected, build_document, canonical_record_id, version_of
from ..domain.errors import EngineUnavailable
from ..infrastructure.config import SearchConfig
from ..infrastructure.engine import get_engine
from . import state
from .ports import SearchEngine
from .registry import Registry, get_registry

log = logging.getLogger("eos.search")


def sleep(seconds: float) -> None:  # replaceable in tests
    time.sleep(seconds)


def _upsert(spec: TypeSpec, provider, engine: SearchEngine, organisation_id: str, record_id: str, version: int) -> str:
    """One attempt. Returns 'indexed', 'deleted' (record gone) or 'stale'. Raises on a failing provider or engine,
    and DocumentRejected on a document that must not be stored."""
    raw = provider.get_document(organisation_id, spec.name, record_id)
    if raw is None:
        return "deleted" if engine.delete(organisation_id, spec, record_id, version) else "stale"
    doc = build_document(
        spec,
        organisation_id=organisation_id,
        record_id=record_id,
        raw=raw,
        version=version,
        now=datetime.now(UTC),
    )
    written, _ = engine.index_many(organisation_id, spec, [doc])
    return "indexed" if written else "stale"


def process_trigger(
    db: Session,
    spec: TypeSpec,
    action: str,
    record_id: str,
    *,
    organisation_id: str,
    version: int,
    event_id: str | None,
    registry: Registry,
    engine: SearchEngine,
    config: SearchConfig,
    pause: Callable[[float], None] | None = None,
) -> str:
    pause = pause or sleep
    if action == "delete":
        engine.ensure_index(spec)
        engine.delete(organisation_id, spec, record_id, version)
        state.clear_dead_letters(db, organisation_id, type_key=spec.key, record_id=record_id)
        return "deleted"
    provider = registry.providers[spec.module]
    reason = "provider_failed"
    for attempt in range(1, config.index_attempts + 1):
        try:
            outcome = _upsert(spec, provider, engine, organisation_id, record_id, version)
        except DocumentRejected as e:
            # Fail closed: an earlier, possibly more permissive document must not outlive a refused one.
            log.error("search: refused a %s document: %s", spec.key, e.reason)
            try:
                engine.delete(organisation_id, spec, record_id, version)
            except Exception:  # noqa: BLE001
                log.warning("search: could not remove the earlier %s document", spec.key)
            state.record_dead_letter(db, organisation_id, spec.module, spec.key, record_id, event_id, e.reason)
            return "rejected"
        except Exception as e:  # noqa: BLE001  the type only is logged: messages can carry record content
            reason = "engine_unavailable" if isinstance(e, EngineUnavailable) else "provider_failed"
            log.warning(
                "search: %s attempt %d of %d failed: %s", spec.key, attempt, config.index_attempts, type(e).__name__
            )
            if attempt < config.index_attempts:
                pause(config.index_retry_backoff_seconds * 2 ** (attempt - 1))
            continue
        state.clear_dead_letters(db, organisation_id, type_key=spec.key, record_id=record_id)
        if outcome != "stale":
            state.touch_state(db, organisation_id, spec.key)
        return outcome
    state.record_dead_letter(db, organisation_id, spec.module, spec.key, record_id, event_id, reason)
    return "dead_lettered"


def index_event(
    db: Session,
    event,
    *,
    registry: Registry | None = None,
    engine: SearchEngine | None = None,
    config: SearchConfig | None = None,
    pause: Callable[[float], None] | None = None,
) -> list[str]:
    """Handle one trigger event for every type that names it. Returns one outcome per type (for tests and logs)."""
    registry = registry or get_registry()
    organisation_id = event.organisation_id
    triggered = list(registry.triggered_by(event.name))
    if not triggered:
        return []
    if not organisation_id:
        log.warning("search: %s has no organisation in its envelope; nothing indexed", event.name)
        return []
    engine = engine or get_engine()
    config = config or SearchConfig.from_env().validate()
    payload = event.payload or {}
    version = version_of(event.occurred_at)
    outcomes = []
    for spec, action, id_field in triggered:
        try:
            record_id = canonical_record_id(payload.get(id_field))
        except DocumentRejected:
            log.warning("search: %s has no usable %s in its payload", event.name, id_field)
            outcomes.append("skipped")
            continue
        outcomes.append(
            process_trigger(
                db,
                spec,
                action,
                record_id,
                organisation_id=str(organisation_id),
                version=version,
                event_id=getattr(event, "id", None),
                registry=registry,
                engine=engine,
                config=config,
                pause=pause,
            )
        )
    return outcomes
