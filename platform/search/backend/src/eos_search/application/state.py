"""Search's own small tables: index state, dead letters, the entitlement copy. Every query names the organisation,
so SQLite (which has no row-level security) is as strict as PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime

from eos_core.entitlement import PLATFORM_MODULES
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..domain.models import DeadLetter, Entitlement, IndexState


def now() -> datetime:
    return datetime.now(UTC)


def aware(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; every stored time is UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def touch_state(db: Session, organisation_id: str, type_key: str, *, reindexed: bool = False) -> None:
    row = db.scalar(
        select(IndexState).where(IndexState.organisation_id == organisation_id, IndexState.type_key == type_key)
    )
    if row is None:
        row = IndexState(organisation_id=organisation_id, type_key=type_key)
        db.add(row)
    stamp = now()
    row.last_indexed_at = stamp
    if reindexed:
        row.last_reindex_at = stamp
    db.flush()


def record_dead_letter(
    db: Session, organisation_id: str, module: str, type_key: str, record_id: str, event_id: str | None, reason: str
) -> None:
    row = db.scalar(
        select(DeadLetter).where(
            DeadLetter.organisation_id == organisation_id,
            DeadLetter.type_key == type_key,
            DeadLetter.record_id == record_id,
        )
    )
    if row is None:
        db.add(
            DeadLetter(
                organisation_id=organisation_id,
                module=module,
                type_key=type_key,
                record_id=record_id,
                event_id=event_id,
                reason=reason[:60],
            )
        )
    else:
        row.reason, row.event_id = reason[:60], event_id
    db.flush()


def clear_dead_letters(
    db: Session,
    organisation_id: str,
    *,
    module: str | None = None,
    type_key: str | None = None,
    record_id: str | None = None,
) -> None:
    stmt = delete(DeadLetter).where(DeadLetter.organisation_id == organisation_id)
    if module is not None:
        stmt = stmt.where(DeadLetter.module == module)
    if type_key is not None:
        stmt = stmt.where(DeadLetter.type_key == type_key)
    if record_id is not None:
        stmt = stmt.where(DeadLetter.record_id == record_id)
    db.execute(stmt)


def dead_letter_count(db: Session, organisation_id: str | None) -> int:
    stmt = select(func.count()).select_from(DeadLetter)
    if organisation_id is not None:
        stmt = stmt.where(DeadLetter.organisation_id == organisation_id)
    return int(db.scalar(stmt) or 0)


def module_names(values) -> frozenset[str]:
    """`suite/module` or `module`, as tenancy lists them, reduced to the module name."""
    return frozenset(str(v).rsplit("/", 1)[-1] for v in values or [] if isinstance(v, str) and v)


def set_entitlement(db: Session, organisation_id: str, modules) -> None:
    row = db.scalar(select(Entitlement).where(Entitlement.organisation_id == organisation_id))
    names = sorted(module_names(modules))
    if row is None:
        db.add(Entitlement(organisation_id=organisation_id, modules=names))
    else:
        row.modules = names
    db.flush()


def entitled_modules(db: Session, organisation_id: str) -> frozenset[str] | None:
    """The modules the organisation may use, from search's copy. None when search has not seen an entitlement
    event for it yet. Platform services are always entitled (eos_core.entitlement)."""
    row = db.scalar(select(Entitlement).where(Entitlement.organisation_id == organisation_id))
    if row is None:
        return None
    return frozenset(row.modules or []) | frozenset(PLATFORM_MODULES)


def forget_organisation(db: Session, organisation_id: str) -> None:
    from ..domain.models import ReindexJob

    for model in (ReindexJob, IndexState, Entitlement, DeadLetter):
        db.execute(delete(model).where(model.organisation_id == organisation_id))
