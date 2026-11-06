"""Rebuilds (docs/prd.md, decision 6): backfill when a module opts in, repair after drift, and a new index version
when a mapping changes.

Two cases, one API:

- the type's live mapping is current: every document of the organisation is rewritten into the live alias with a new
  `reindex_run` stamp, then the organisation's documents of the type that lack the stamp and were indexed before the
  run started are deleted (a record removed at the source whose event was lost disappears; a document an event wrote
  during the run survives);
- the live mapping is out of date: a new `-v<n+1>` index is built for every organisation search knows, the alias moves
  to it in one atomic operation, and a failure before that leaves the old index live (search.reindex.failed).
  Events that arrive during the window land in the old index only; the next reindex repairs them.

The provider's `iter_documents` feeds both, in batches, at no more than SEARCH_REINDEX_MAX_DOCS_PER_SECOND."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from eos_audit.application import service as audit
from eos_core import events
from eos_core.db import SessionLocal
from eos_core.tenant import organisation_scope, platform_scope
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import models
from ..domain.declarations import TypeSpec
from ..domain.documents import DocumentRejected, build_document, canonical_record_id, version_of
from ..domain.errors import EngineUnavailable, SearchError
from ..domain.models import ACTIVE, ReindexJob
from ..infrastructure.config import SearchConfig
from ..infrastructure.engine import get_engine
from . import state
from .ports import SearchEngine
from .registry import Registry, get_registry

log = logging.getLogger("eos.search")


def scope_key(module: str, type_key: str | None) -> str:
    return f"{module}|{type_key or ''}"


def job_out(job: ReindexJob) -> dict:
    def iso(v):
        v = state.aware(v)
        return v.isoformat() if v else None

    return {
        "id": job.id,
        "module": job.module,
        "type": job.type,
        "status": job.status,
        "requested_by": job.requested_by,
        "requested_at": iso(job.requested_at),
        "started_at": iso(job.started_at),
        "finished_at": iso(job.finished_at),
        "documents_indexed": job.documents_indexed,
        "documents_failed": job.documents_failed,
        "error": job.error,
    }


# --- requesting --------------------------------------------------------------------------------------------------
def _abandon_stale(db: Session, organisation_id: str, config: SearchConfig) -> None:
    """A job whose worker died would block its scope for ever: after SEARCH_JOB_STALE_SECONDS it is failed."""
    cutoff = datetime.now(UTC) - timedelta(seconds=config.job_stale_seconds)
    db.execute(
        update(ReindexJob)
        .where(
            ReindexJob.organisation_id == organisation_id,
            ReindexJob.status.in_(ACTIVE),
            or_(ReindexJob.started_at < cutoff, (ReindexJob.started_at.is_(None)) & (ReindexJob.requested_at < cutoff)),
        )
        .values(
            status=models.FAILED, finished_at=datetime.now(UTC), error="the rebuild did not finish and was abandoned"
        )
    )


def start_reindex(
    db: Session,
    *,
    organisation_id: str,
    requested_by: str | None,
    module: str,
    type_key: str | None,
    registry: Registry | None = None,
    config: SearchConfig | None = None,
) -> ReindexJob:
    """Create the job and its audit entry in the caller's transaction. The caller commits, then dispatches."""
    registry = registry or get_registry()
    config = config or SearchConfig.from_env()
    types = registry.module_types(module)
    if not types:
        raise SearchError(404, "no such module with searchable types")
    if type_key is not None and not any(s.key == type_key for s in types):
        raise SearchError(404, "no such searchable type in this module")
    _abandon_stale(db, organisation_id, config)
    active = db.scalars(
        select(ReindexJob).where(
            ReindexJob.organisation_id == organisation_id,
            ReindexJob.module == module,
            ReindexJob.status.in_(ACTIVE),
        )
    ).all()
    for other in active:
        if other.type is None or type_key is None or other.type == type_key:
            raise SearchError(409, f"a rebuild for this module and type is already {other.status}: job {other.id}")
    job = ReindexJob(
        organisation_id=organisation_id,
        module=module,
        type=type_key,
        scope_key=scope_key(module, type_key),
        status=models.QUEUED,
        requested_by=requested_by,
    )
    try:
        with db.begin_nested():
            db.add(job)
            db.flush()
    except IntegrityError:
        raise SearchError(409, "a rebuild for this module and type is already queued or running") from None
    audit.record(
        db,
        organisation_id=organisation_id,
        actor=requested_by,
        module="search",
        action="reindex.requested",
        entity_type="reindex_job",
        entity_id=job.id,
        summary=f"Rebuild of {type_key or module} requested",
        context={"module": module, "type": type_key},
    )
    return job


def get_job(db: Session, organisation_id: str, job_id: str) -> ReindexJob:
    job = None
    try:
        key = str(uuid.UUID(job_id))
    except ValueError:
        key = None
    if key:
        job = db.scalar(select(ReindexJob).where(ReindexJob.id == key, ReindexJob.organisation_id == organisation_id))
    if job is None:
        raise SearchError(404, "no such reindex job")
    return job


def list_jobs(
    db: Session,
    organisation_id: str,
    *,
    module: str | None,
    status: str | None,
    limit: int,
    after: tuple[datetime, str] | None,
) -> list[ReindexJob]:
    stmt = select(ReindexJob).where(ReindexJob.organisation_id == organisation_id)
    if module:
        stmt = stmt.where(ReindexJob.module == module)
    if status:
        stmt = stmt.where(ReindexJob.status == status)
    if after:
        t, i = after
        stmt = stmt.where(or_(ReindexJob.requested_at < t, (ReindexJob.requested_at == t) & (ReindexJob.id < i)))
    return list(db.scalars(stmt.order_by(ReindexJob.requested_at.desc(), ReindexJob.id.desc()).limit(limit + 1)).all())


# --- running -----------------------------------------------------------------------------------------------------
class _Counts:
    def __init__(self) -> None:
        self.indexed = 0
        self.failed = 0


def _batches(provider, organisation_id: str, spec: TypeSpec, size: int):
    after: str | None = None
    while True:
        page = list(provider.iter_documents(organisation_id, spec.name, after, size))
        if not page:
            return
        yield page
        last = canonical_record_id(page[-1].get("record_id") if hasattr(page[-1], "get") else None)
        if last == after:
            raise RuntimeError("the provider did not advance")
        after = last
        if len(page) < size:
            return


def _build_page(
    db: Session | None,
    spec: TypeSpec,
    organisation_id: str,
    page,
    *,
    version: int,
    run: str | None,
    counts: _Counts,
    job_id: str,
) -> list[dict]:
    docs: list[dict] = []
    for raw in page:
        try:
            rid = canonical_record_id(raw.get("record_id") if hasattr(raw, "get") else None)
            docs.append(
                build_document(
                    spec,
                    organisation_id=organisation_id,
                    record_id=rid,
                    raw=raw,
                    version=version,
                    now=datetime.now(UTC),
                    reindex_run=run,
                )
            )
        except DocumentRejected as e:
            counts.failed += 1
            rid = str(raw.get("record_id", ""))[:128] if hasattr(raw, "get") else ""
            if rid and db is not None:  # another organisation's refusals are counted by its own next reindex
                state.record_dead_letter(db, organisation_id, spec.module, spec.key, rid, job_id, e.reason)
    return docs


def _throttle(config: SearchConfig, written: int, started: float, pause: Callable[[float], None]) -> None:
    due = written / config.reindex_max_docs_per_second
    elapsed = time.monotonic() - started
    if elapsed < due:
        pause(due - elapsed)


def _reindex_in_place(
    db: Session,
    spec: TypeSpec,
    provider,
    engine: SearchEngine,
    organisation_id: str,
    job: ReindexJob,
    config: SearchConfig,
    counts: _Counts,
    pause: Callable[[float], None],
) -> None:
    run = job.id
    started_iso = datetime.now(UTC).isoformat()
    for page in _batches(provider, organisation_id, spec, config.reindex_batch_size):
        t0 = time.monotonic()
        version = version_of(datetime.now(UTC))
        docs = _build_page(db, spec, organisation_id, page, version=version, run=run, counts=counts, job_id=job.id)
        written, _stale = engine.index_many(organisation_id, spec, docs, version=version)
        counts.indexed += written
        _throttle(config, len(page), t0, pause)
    engine.delete_stale(organisation_id, spec, run, started_iso)


def _rebuild_mapping(
    db: Session,
    spec: TypeSpec,
    provider,
    engine: SearchEngine,
    job: ReindexJob,
    config: SearchConfig,
    counts: _Counts,
    pause: Callable[[float], None],
    session_factory: Callable[[], Session],
) -> None:
    organisations = {job.organisation_id}
    with platform_scope(), session_factory() as every:  # its own session: row-level security is set per transaction
        organisations |= set(
            every.scalars(select(models.IndexState.organisation_id).where(models.IndexState.type_key == spec.key))
        )
    version_n = engine.build_next_index(spec)
    for org in sorted(organisations):
        with organisation_scope(org):
            for page in _batches(provider, org, spec, config.reindex_batch_size):
                t0 = time.monotonic()
                version = version_of(datetime.now(UTC))
                own = _Counts() if org != job.organisation_id else counts
                docs = _build_page(
                    db if org == job.organisation_id else None,
                    spec,
                    org,
                    page,
                    version=version,
                    run=None,
                    counts=own,
                    job_id=job.id,
                )
                written, _ = engine.index_many(org, spec, docs, version=version, target_version=version_n)
                own.indexed += written
                _throttle(config, len(page), t0, pause)
    engine.swap_alias(spec, version_n)  # atomic; nothing above was visible to queries


def _error_sentence(error: Exception) -> str:
    if isinstance(error, EngineUnavailable):
        return "the search engine was unavailable; the previous index is still live"
    return "the module's provider failed; the previous index is still live"


def run_reindex_job(
    job_id: str,
    *,
    registry: Registry | None = None,
    engine: SearchEngine | None = None,
    config: SearchConfig | None = None,
    session_factory: Callable[[], Session] = SessionLocal,
    pause: Callable[[float], None] = time.sleep,
) -> None:
    """Run one job to its end in sessions of its own. Never raises: the outcome is the job's status and an event."""
    registry = registry or get_registry()
    engine = engine or get_engine()
    config = config or SearchConfig.from_env().validate()
    with platform_scope(), session_factory() as db:
        job = db.get(ReindexJob, job_id)
        if job is None or job.status != models.QUEUED:
            return
        organisation_id, module, type_key = job.organisation_id, job.module, job.type
    with organisation_scope(organisation_id), session_factory() as db:
        job = db.get(ReindexJob, job_id)
        if job is None or job.status != models.QUEUED:
            return
        job.status, job.started_at = models.RUNNING, datetime.now(UTC)
        db.commit()
        started = time.monotonic()
        counts = _Counts()
        specs = [s for s in registry.module_types(module) if type_key in (None, s.key)]
        try:
            state.clear_dead_letters(db, organisation_id, module=module, type_key=type_key)
            db.commit()
            provider = registry.providers[module]
            for spec in specs:
                engine.ensure_index(spec)
                if engine.mapping_current(spec):
                    _reindex_in_place(db, spec, provider, engine, organisation_id, job, config, counts, pause)
                else:
                    _rebuild_mapping(db, spec, provider, engine, job, config, counts, pause, session_factory)
                state.touch_state(db, organisation_id, spec.key, reindexed=True)
                db.commit()
        except Exception as e:  # noqa: BLE001  the type only is logged: messages can carry document content
            log.warning("search: reindex job %s failed: %s", job_id, type(e).__name__)
            db.rollback()
            job = db.get(ReindexJob, job_id)
            job.status, job.finished_at = models.FAILED, datetime.now(UTC)
            job.documents_indexed, job.documents_failed = counts.indexed, counts.failed
            job.error = _error_sentence(e)
            events.publish(
                db,
                "search.reindex.failed",
                organisation_id,
                {"job_id": job_id, "module": module, "type": type_key, "error": job.error},
            )
            db.commit()
            return
        job = db.get(ReindexJob, job_id)
        job.status, job.finished_at = models.SUCCEEDED, datetime.now(UTC)
        job.documents_indexed, job.documents_failed = counts.indexed, counts.failed
        events.publish(
            db,
            "search.reindex.completed",
            organisation_id,
            {
                "job_id": job_id,
                "module": module,
                "type": type_key,
                "documents_indexed": counts.indexed,
                "documents_failed": counts.failed,
                "duration_seconds": int(time.monotonic() - started),
            },
        )
        db.commit()


# --- dispatch ----------------------------------------------------------------------------------------------------
def enqueue_arq(job_id: str, config: SearchConfig) -> None:  # pragma: no cover - needs Redis
    import asyncio

    from arq import create_pool
    from arq.connections import RedisSettings

    async def _go() -> None:
        pool = await create_pool(RedisSettings.from_dsn(config.redis_url))
        try:
            await pool.enqueue_job("run_reindex", job_id)
        finally:
            await pool.close()

    asyncio.run(_go())
