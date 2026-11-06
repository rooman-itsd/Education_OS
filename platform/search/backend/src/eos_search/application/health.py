"""Index health for an organisation and engine health for the platform (contracts: GET /health, /platform/health).

Both are totals about the index, never content. The organisation's counts use the same query builder as search, with
the organisation filter and no document fields."""

from __future__ import annotations

from datetime import UTC, datetime

from eos_core.events import OutboxEvent
from eos_core.tenant import platform_scope
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..domain.errors import EngineUnavailable
from ..domain.models import IndexState
from . import state
from .ports import SearchEngine
from .query import build_count_query
from .registry import Registry, get_registry


def lag_seconds(db: Session, registry: Registry, organisation_id: str | None) -> int | None:
    """Age of the oldest event search still has to receive (an outbox row not yet delivered, among the events search
    subscribes to). None when nothing is waiting."""
    names = registry.trigger_events()
    if not names:
        return None
    stmt = select(func.min(OutboxEvent.occurred_at)).where(
        OutboxEvent.published.is_(False), OutboxEvent.name.in_(names)
    )
    if organisation_id is not None:
        stmt = stmt.where(OutboxEvent.organisation_id == organisation_id)
    oldest = state.aware(db.scalar(stmt))
    if oldest is None:
        return None
    return max(0, int((datetime.now(UTC) - oldest).total_seconds()))


def index_health(
    db: Session,
    organisation_id: str,
    engine: SearchEngine,
    entitled: frozenset[str] | None,
    registry: Registry | None = None,
) -> dict:
    registry = registry or get_registry()
    states = {
        s.type_key: s for s in db.scalars(select(IndexState).where(IndexState.organisation_id == organisation_id))
    }
    unavailable = False
    types = []
    for spec in sorted(registry.types.values(), key=lambda s: s.key):
        if entitled is not None and spec.module not in entitled:
            continue
        documents = 0
        try:
            documents = engine.count_documents(build_count_query(organisation_id, spec))
        except EngineUnavailable:
            unavailable = True
        row = states.get(spec.key)
        iso = lambda v: v.isoformat() if v else None  # noqa: E731
        types.append(
            {
                "type": spec.key,
                "documents": documents,
                "last_indexed_at": iso(state.aware(row.last_indexed_at)) if row else None,
                "last_reindex_at": iso(state.aware(row.last_reindex_at)) if row else None,
            }
        )
    degraded = state.dead_letter_count(db, organisation_id) > 0
    status = "unavailable" if unavailable else "degraded" if degraded else "ok"
    return {"status": status, "lag_seconds": lag_seconds(db, registry, organisation_id), "types": types}


def platform_health(db: Session, engine: SearchEngine, registry: Registry | None = None) -> dict:
    """Totals across every organisation. Reads in platform scope on a session that has not begun a transaction yet."""
    registry = registry or get_registry()
    with platform_scope():
        dead = state.dead_letter_count(db, None)
        lag = lag_seconds(db, registry, None)
    try:
        h = engine.health()
    except EngineUnavailable:
        return {
            "status": "unavailable",
            "cluster_status": "unknown",
            "indices": 0,
            "shards": 0,
            "lag_seconds": lag,
            "dead_lettered": dead,
        }
    status = "degraded" if h.cluster_status == "red" or dead > 0 else "ok"
    return {
        "status": status,
        "cluster_status": h.cluster_status,
        "indices": h.indices,
        "shards": h.shards,
        "lag_seconds": lag,
        "dead_lettered": dead,
    }
