"""Writing and reading audit records. There is no update use case and no delete use case, by design: the only
removal is a retention prune of a whole window, and redaction is not built yet (docs/prd.md, "Later").

`record()` does not commit. A module records a change in the same transaction that makes it, so a record exists
if and only if the change it describes was committed. The HTTP route commits on its own behalf.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta

from eos_core import events
from eos_core.db import scoped, utcnow
from eos_core.tenant import organisation_scope, platform_scope
from eos_identity.application.service import get_user
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from ..domain.models import (
    MAX_ACTION,
    MAX_CLIENT_TOKEN,
    MAX_ENTITY_ID,
    MAX_ENTITY_TYPE,
    MAX_MODULE,
    MAX_SUMMARY,
    AuditRecord,
)
from ..infrastructure import config

# "<entity>.<past-tense-verb>", the contract's vocabulary: application.accepted, leave.overdue.
ACTION_RE = re.compile(r"^[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)+$")
# The contract: before/after are "never secrets, passwords, tokens". A record should say that a password
# changed, never what it changed to, so a payload carrying such a key is refused rather than stored.
SECRET_KEY_RE = re.compile(r"password|secret|(^|_)token$|^api_?key$", re.I)


class AuditError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _scope(organisation_id: str | None):
    """A platform-level record has no organisation, so it is written and read in platform scope."""
    return organisation_scope(organisation_id) if organisation_id else platform_scope()


def _base(db: Session, organisation_id: str | None):
    """Every query starts here. For an organisation, scoped() filters to it (and on PostgreSQL RLS does too).
    For the platform, platform scope bypasses RLS, so the null-organisation filter is what keeps an
    organisation's records out of a platform read."""
    if organisation_id:
        return scoped(db, select(AuditRecord), AuditRecord)
    return select(AuditRecord).where(AuditRecord.organisation_id.is_(None))


def _text(name: str, value, limit: int, *, required: bool) -> None:
    if value is None or value == "":
        if required:
            raise AuditError(422, f"{name} is required")
        return
    if not isinstance(value, str):
        raise AuditError(422, f"{name} must be a string")
    if len(value) > limit:
        raise AuditError(422, f"{name} is longer than {limit} characters")


def _secret_key(value) -> str | None:
    if isinstance(value, dict):
        for key, inner in value.items():
            if SECRET_KEY_RE.search(str(key)):
                return str(key)
            found = _secret_key(inner)
            if found:
                return found
    elif isinstance(value, list):
        for inner in value:
            found = _secret_key(inner)
            if found:
                return found
    return None


def _payload(name: str, value, *, check_secrets: bool) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise AuditError(422, f"{name} must be an object")
    if check_secrets:
        key = _secret_key(value)
        if key:
            raise AuditError(422, f"{name} has a field that looks like a secret ({key}); record that it changed")
    try:
        size = len(json.dumps(value).encode())
    except (TypeError, ValueError):
        raise AuditError(422, f"{name} must be plain JSON") from None
    if size > config.max_payload_bytes():
        # Refused, never truncated: a cut-down payload would be a record that lies about what changed.
        raise AuditError(422, f"{name} is {size} bytes; the limit is {config.max_payload_bytes()}")


def find_by_token(db: Session, organisation_id: str | None, client_token: str | None) -> AuditRecord | None:
    if not client_token:
        return None
    with _scope(organisation_id):
        return db.scalar(_base(db, organisation_id).where(AuditRecord.client_token == client_token))


def record(
    db: Session,
    *,
    organisation_id: str | None,
    actor: str | None,
    module: str,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    context: dict | None = None,
    client_token: str | None = None,
) -> tuple[AuditRecord, bool]:
    """Append one record in the caller's transaction. Returns (record, created). A replayed client_token
    returns the original and appends nothing, so a retried request cannot record twice."""
    _text("module", module, MAX_MODULE, required=True)
    _text("action", action, MAX_ACTION, required=True)
    if not ACTION_RE.match(action):
        raise AuditError(422, "action must be <entity>.<past-tense-verb>, lower case, e.g. application.accepted")
    _text("entity_type", entity_type, MAX_ENTITY_TYPE, required=True)
    _text("entity_id", entity_id, MAX_ENTITY_ID, required=True)
    _text("summary", summary, MAX_SUMMARY, required=False)
    _text("client_token", client_token, MAX_CLIENT_TOKEN, required=False)
    _payload("before", before, check_secrets=True)
    _payload("after", after, check_secrets=True)
    _payload("context", context, check_secrets=False)

    existing = find_by_token(db, organisation_id, client_token)
    if existing is not None:
        return existing, False
    rec = AuditRecord(
        organisation_id=organisation_id,
        actor=actor,
        module=module,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary or None,
        before=before,
        after=after,
        context=context or {},
        client_token=client_token or None,
    )
    with _scope(organisation_id):
        db.add(rec)
        db.flush()
    return rec, True


def record_cross_organisation_read(db: Session, *, actor: str, organisation_id: str, what: str) -> None:
    """ADR-0005: a super admin reading another organisation's records leaves a trail. It is a platform-level
    record, so it appears among the super admin's own actions."""
    record(
        db,
        organisation_id=None,
        actor=actor,
        module="audit",
        action="audit_trail.read",
        entity_type="organisation",
        entity_id=organisation_id,
        summary="A super admin read this organisation's audit records",
        context={"read": what},
    )


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _actor_names(db: Session, rows) -> dict[str, str]:
    """Resolved at read time, as the contract says, so a renamed user shows their current name."""
    names: dict[str, str] = {}
    for actor in {r.actor for r in rows if r.actor}:
        user = get_user(db, actor)
        if user is not None:
            names[actor] = user.name
    return names


def _page(db: Session, rows) -> list[dict]:
    names = _actor_names(db, rows)
    return [r.to_dict(names.get(r.actor)) for r in rows]


def search(
    db: Session,
    *,
    organisation_id: str | None,
    module: str | None = None,
    action: str | None = None,
    actor: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Newest first. `action` is exact, or a prefix when it ends in '*'."""
    limit = max(1, min(limit, config.max_page_size()))
    with _scope(organisation_id):
        q = _base(db, organisation_id)
        if module:
            q = q.where(AuditRecord.module == module)
        if action:
            if action.endswith("*"):
                q = q.where(AuditRecord.action.startswith(action[:-1], autoescape=True))
            else:
                q = q.where(AuditRecord.action == action)
        if actor:
            q = q.where(AuditRecord.actor == actor)
        if entity_type:
            q = q.where(AuditRecord.entity_type == entity_type)
        if entity_id:
            q = q.where(AuditRecord.entity_id == entity_id)
        if occurred_from:
            q = q.where(AuditRecord.occurred_at >= _utc(occurred_from))
        if occurred_to:
            q = q.where(AuditRecord.occurred_at <= _utc(occurred_to))
        total = db.scalar(select(func.count()).select_from(q.subquery()))
        rows = db.scalars(
            q.order_by(AuditRecord.occurred_at.desc(), AuditRecord.id.desc()).limit(limit).offset(max(0, offset))
        ).all()
        return {"items": _page(db, rows), "total": total}


def get_record(db: Session, *, organisation_id: str | None, record_id: str, any_organisation: bool) -> AuditRecord:
    """An organisation caller sees only its own records; a record elsewhere is a 404, never a 403, so its
    existence is not disclosed. `any_organisation` is the super admin's cross-organisation read."""
    if any_organisation:
        with platform_scope():
            rec = db.get(AuditRecord, record_id)
    else:
        with _scope(organisation_id):
            rec = db.scalar(_base(db, organisation_id).where(AuditRecord.id == record_id))
    if rec is None:
        raise AuditError(404, "no such record")
    return rec


def view(db: Session, rec: AuditRecord) -> dict:
    """One record as the API returns it, with the actor's current name."""
    return _page(db, [rec])[0]


def history(
    db: Session,
    *,
    organisation_id: str | None,
    entity_type: str,
    entity_id: str,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """Every recorded change to one entity, oldest first: the "who changed this" view."""
    with _scope(organisation_id):
        q = _base(db, organisation_id).where(AuditRecord.entity_type == entity_type, AuditRecord.entity_id == entity_id)
        total = db.scalar(select(func.count()).select_from(q.subquery()))
        rows = db.scalars(
            q.order_by(AuditRecord.occurred_at.asc(), AuditRecord.id.asc()).offset(offset).limit(limit)
        ).all()
        return {"items": _page(db, rows), "total": total}


def prune(db: Session, *, now: datetime | None = None) -> int:
    """Delete the whole window older than the retention period, never a single record. Meant to be run by
    platform/scheduler (#82) in a fresh session. Publishes audit.retention.pruned once per run, even when
    nothing was old enough, so every run is accounted for."""
    if not config.retention_enabled():
        return 0
    cutoff = (now or utcnow()) - timedelta(days=config.retention_days())
    with platform_scope():
        if db.get_bind().dialect.name == "postgresql":
            # The immutability trigger allows a DELETE only inside a transaction that declares itself a prune.
            db.execute(text("SELECT set_config('audit.pruning', 'on', true)"))
        removed = db.execute(delete(AuditRecord).where(AuditRecord.occurred_at < cutoff)).rowcount or 0
        events.publish(db, "audit.retention.pruned", None, {"removed_count": removed, "older_than": cutoff.isoformat()})
        db.commit()
    return removed
