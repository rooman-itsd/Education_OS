"""Port operations and the delivery log (docs/prd.md, "How a module uses a port" and "Delivery log and retries").

`invoke()` is what a module calls, in process, as itself and for its organisation. The hub checks the organisation has
an enabled connection for the port, writes a delivery row, resolves the connection's secrets into memory and calls the
adapter. A sync operation answers within INTEGRATION_HUB_SYNC_TIMEOUT_S and a retryable failure is returned as is; an
async one returns the delivery id at once, its input is kept encrypted only so it can be retried, and the scheduled
sweep (`process_due`, platform/scheduler) runs it, retrying retryable failures with exponential backoff and full
jitter until it succeeds or is dead-lettered. The outcome is integration-hub.delivery.* plus the port's own events.

Never the payload in the log, the API, an event or a log line."""

from __future__ import annotations

import json
import logging
from datetime import timedelta

from eos_core.db import SessionLocal, scoped
from eos_core.tenant import get_current_organisation, organisation_scope, platform_scope
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ..domain import port_events, rules
from ..domain.errors import HubError, not_found
from ..domain.vocabulary import (
    CALLER_MODULE_RE,
    ERROR_CODES,
    MAX_CALLER_REFERENCE,
    MAX_IDEMPOTENCY_KEY,
    NAME_RE,
)
from ..infrastructure.config import HubConfig
from ..infrastructure.models import (
    AccountLink,
    Connection,
    Delivery,
    DeliveryAttempt,
    InboundReceipt,
    OAuthState,
)
from ..infrastructure.ports import load_ports
from ..infrastructure.registry import Outcome, call, get_registry
from ..infrastructure.secrets import SecretStoreError, get_cipher
from .common import (
    Actor,
    aware,
    clock,
    context_for,
    iso,
    link_secrets,
    page,
    publish,
    record,
    resolve_secrets,
)

log = logging.getLogger("eos.integration_hub")

TERMINAL = ("succeeded", "failed", "dead_lettered", "manual_action_required", "rejected_inbound")
MAX_INPUT_BYTES = 1_048_576
SWEEP_BATCH = 200


def async_timeout_s(config: HubConfig) -> int:
    """How long one attempt of an async operation may take inside the sweep (large transfers stream)."""
    return min(max(config.sync_timeout_s * 20, 300), 1800)


# ------------------------------------------------------------------ rendering


def delivery_dict(d: Delivery) -> dict:
    return {
        "id": d.id,
        "direction": d.direction,
        "connection_id": d.connection_id,
        "port": d.port,
        "operation": d.operation,
        "caller_module": d.caller_module,
        "caller_reference": d.caller_reference,
        "idempotency_key": d.idempotency_key,
        "status": d.status,
        "attempts": d.attempts,
        "next_attempt_at": iso(d.next_attempt_at) if d.status in ("queued", "retry_scheduled") else None,
        "last_error_code": d.last_error_code,
        "provider_reference": d.provider_reference,
        "created_at": iso(d.created_at),
        "completed_at": iso(d.completed_at),
    }


def _attempt_dict(a: DeliveryAttempt) -> dict:
    return {
        "attempt": a.attempt,
        "started_at": iso(a.started_at),
        "duration_ms": a.duration_ms,
        "outcome": a.outcome,
        "error_code": a.error_code,
        "provider_code": a.provider_code,
    }


def _get(db: Session, delivery_id: str) -> Delivery:
    row = db.scalar(scoped(db, select(Delivery), Delivery).where(Delivery.id == delivery_id))
    if row is None:
        raise not_found("delivery")
    return row


def get_delivery(db: Session, delivery_id: str) -> dict:
    d = _get(db, delivery_id)
    attempts = db.scalars(
        select(DeliveryAttempt)
        .where(DeliveryAttempt.delivery_id == d.id, DeliveryAttempt.organisation_id == d.organisation_id)
        .order_by(DeliveryAttempt.attempt)
    )
    return {**delivery_dict(d), "attempt_log": [_attempt_dict(a) for a in attempts]}


def list_deliveries(db: Session, filters: dict, cursor: str | None, limit: int) -> dict:
    q = scoped(db, select(Delivery), Delivery)
    for field in ("connection_id", "port", "direction", "caller_module", "caller_reference"):
        if filters.get(field):
            q = q.where(getattr(Delivery, field) == filters[field])
    if filters.get("status"):
        q = q.where(Delivery.status.in_(filters["status"]))
    if filters.get("since"):
        q = q.where(Delivery.created_at >= filters["since"])
    return page(db, q.order_by(Delivery.created_at.desc(), Delivery.id), cursor, limit, delivery_dict)


# ------------------------------------------------------------------ invoke (the modules' calling surface)


def _error(code: str, detail: str, delivery_id: str | None = None, retry_after_s: int | None = None) -> dict:
    return {
        "delivery_id": delivery_id,
        "status": "failed",
        "output": None,
        "error": {
            "code": code,
            "retryable": ERROR_CODES.get(code, False),
            "retry_after_s": retry_after_s,
            "detail": detail,
        },
        "provider_reference": None,
        "replayed": False,
    }


def _summary(d: Delivery, *, output: dict | None = None, replayed: bool = False, out: Outcome | None = None) -> dict:
    error = None
    if d.last_error_code and d.status not in ("succeeded", "queued", "in_progress", "retry_scheduled"):
        error = {
            "code": d.last_error_code,
            "retryable": ERROR_CODES.get(d.last_error_code, False),
            "retry_after_s": out.retry_after_s if out else None,
            "detail": (out.detail if out else None) or d.last_error_code,
        }
    return {
        "delivery_id": d.id,
        "status": d.status,
        "output": output,
        "error": error,
        "provider_reference": d.provider_reference,
        "replayed": replayed,
    }


def prior_delivery(db: Session, org: str, port: str, subject: str | None, object_id: str | None) -> Delivery | None:
    """The earliest successful outbound delivery for the same port object, to inherit its caller and keys."""
    if not subject and not object_id:
        return None
    q = select(Delivery).where(
        Delivery.organisation_id == org,
        Delivery.port == port,
        Delivery.direction == "outbound",
        Delivery.status == "succeeded",
    )
    q = q.where(Delivery.object_id == object_id) if object_id else q.where(Delivery.subject_key == subject)
    return db.scalar(q.order_by(Delivery.created_at).limit(1))


def enqueue(
    db: Session,
    c: Connection,
    *,
    operation: str,
    payload: dict,
    sync: bool,
    caller_module: str,
    caller_reference: str | None,
    idempotency_key: str | None,
    link: AccountLink | None = None,
) -> Delivery:
    """Write the delivery row (and, for an async operation, its encrypted input) in the caller's transaction."""
    subject = port_events.subject_of(c.port, payload)
    object_id = port_events.object_of(c.port, payload)
    prior = prior_delivery(db, c.organisation_id, c.port, subject, object_id)
    refs = {**(prior.refs if prior else {}), **port_events.refs_of(payload)}
    d = Delivery(
        organisation_id=c.organisation_id,
        direction="outbound",
        connection_id=c.id,
        account_link_id=link.id if link else None,
        port=c.port,
        operation=operation,
        sync=sync,
        mode=c.mode,
        provider=c.provider,
        caller_module=caller_module,
        caller_reference=caller_reference,
        idempotency_key=idempotency_key,
        subject_key=subject or (prior.subject_key if prior else None),
        object_id=object_id or (prior.object_id if prior else None),
        person_id=port_events.person_of(payload)
        or (link.person_id if link else None)
        or (prior.person_id if prior else None),
        refs=refs,
        status="queued",
        attempts=0,
        next_attempt_at=clock(),
        created_at=clock(),
    )
    db.add(d)
    db.flush()
    if not sync:
        d.payload_encrypted = get_cipher().encrypt(json.dumps(payload).encode(), d.id)
    return d


def invoke(
    *,
    port: str,
    operation: str,
    input: dict,
    idempotency_key: str,
    caller_module: str,
    caller_reference: str | None = None,
    organisation_id: str | None = None,
    provider: str | None = None,
    account_link_id: str | None = None,
) -> dict:
    """Run one port operation for the calling module and organisation (the current tenant unless given).

    Returns {delivery_id, status, output, error, provider_reference, replayed}. `error` is
    {code, retryable, retry_after_s, detail} with a code from contracts/ports/adapter.yaml. Never raises for a business
    failure: a module handles not_configured the same way whoever the provider is. The same idempotency key within
    INTEGRATION_HUB_IDEMPOTENCY_WINDOW_DAYS returns the first delivery (replayed: true, output null) and never calls the
    provider again."""
    org = organisation_id or get_current_organisation()
    if not org:
        return _error("invalid_request", "no organisation: call within the request's tenant or pass organisation_id")
    spec = load_ports().get(port) if isinstance(port, str) else None
    if spec is None or not isinstance(operation, str) or operation not in spec.operations:
        return _error("unsupported", f"port {port!r} has no operation {operation!r}")
    if not isinstance(caller_module, str) or not CALLER_MODULE_RE.match(caller_module):
        return _error("invalid_request", "caller_module must be the calling module's name")
    if not isinstance(idempotency_key, str) or not 0 < len(idempotency_key) <= MAX_IDEMPOTENCY_KEY:
        return _error("invalid_request", f"idempotency_key must be 1 to {MAX_IDEMPOTENCY_KEY} characters")
    if caller_reference is not None and (
        not isinstance(caller_reference, str) or len(caller_reference) > MAX_CALLER_REFERENCE
    ):
        return _error("invalid_request", f"caller_reference must be at most {MAX_CALLER_REFERENCE} characters")
    if provider is not None and (not isinstance(provider, str) or not NAME_RE.match(provider)):
        return _error("invalid_request", "provider is not a provider id")
    if not isinstance(input, dict):
        return _error("invalid_request", "input must be an object")
    try:
        rules.check_json(input, what="input", code="invalid_request", max_bytes=MAX_INPUT_BYTES)
    except rules.RuleError as e:
        return _error("invalid_request", e.message)
    sync = spec.operations[operation] == "sync"
    config = HubConfig.from_env()
    with organisation_scope(org), SessionLocal() as db:
        window = clock() - timedelta(days=config.idempotency_window_days)
        first = db.scalar(
            scoped(db, select(Delivery), Delivery)
            .where(
                Delivery.direction == "outbound",
                Delivery.caller_module == caller_module,
                Delivery.idempotency_key == idempotency_key,
                Delivery.created_at >= window,
            )
            .order_by(Delivery.created_at)
            .limit(1)
        )
        if first is not None:
            return _summary(first, replayed=True)
        q = scoped(db, select(Connection), Connection).where(Connection.port == port, Connection.enabled.is_(True))
        if provider:
            q = q.where(Connection.provider == provider)
        candidates = list(db.scalars(q))
        if not candidates:
            return _error("not_configured", f"no enabled connection for {port}")
        if len(candidates) > 1:
            return _error("invalid_request", f"several providers serve {port}: name one in `provider`")
        c = candidates[0]
        if c.mode == "mock" and not config.allow_mock:
            return _error("not_configured", "the connection is in mock mode, which this deployment refuses")
        link = None
        link_id = account_link_id or (
            input.get("account_link_id") if isinstance(input.get("account_link_id"), str) else None
        )
        if link_id:
            link = db.scalar(scoped(db, select(AccountLink), AccountLink).where(AccountLink.id == link_id))
            if link is None or link.status != "active" or link.connection_id != c.id:
                return _error("consent_required", "the person has not linked an account at this provider")
        try:
            d = enqueue(
                db,
                c,
                operation=operation,
                payload=input,
                sync=sync,
                caller_module=caller_module,
                caller_reference=caller_reference,
                idempotency_key=idempotency_key,
                link=link,
            )
        except SecretStoreError:
            db.rollback()
            return _error("not_configured", "the secret store is not available")
        db.commit()
        if not sync:
            return _summary(d)
        out = _attempt(db, d, c, input, link, config)
        db.commit()
        return _summary(d, output=out.output if out.ok else None, out=out)


# ------------------------------------------------------------------ running an attempt


def _attempt(
    db: Session, d: Delivery, c: Connection, payload: dict, link: AccountLink | None, config: HubConfig
) -> Outcome:
    info = get_registry().get(c.adapter)
    d.attempts += 1
    d.status = "in_progress"
    started = clock()
    d.started_at = d.started_at or started
    timeout = config.sync_timeout_s if d.sync else async_timeout_s(config)
    d.next_attempt_at = started + timedelta(seconds=timeout + 60)  # the lease: the sweep re-drives it after this
    db.commit()
    if info is None:
        out = Outcome.failure("not_configured", f"adapter {c.adapter} is not installed")
    else:
        try:
            secrets = resolve_secrets(db, c)
            if link is not None:
                secrets.update(link_secrets(link))
        except SecretStoreError:
            out = Outcome.failure("not_configured", "the secret store is not available")
        else:
            ctx = context_for(
                c,
                secrets=secrets,
                link=link,
                delivery_id=d.id,
                attempt=d.attempts,
                idempotency_key=d.idempotency_key,
                timeout_s=timeout,
                port=d.port,
                operation=d.operation,
            )
            out = call(info, d.operation, ctx, payload, timeout_s=timeout, port_operation=True)
    db.add(
        DeliveryAttempt(
            organisation_id=d.organisation_id,
            delivery_id=d.id,
            attempt=d.attempts,
            started_at=started,
            duration_ms=out.duration_ms,
            outcome="succeeded" if out.ok else "failed",
            error_code=out.error_code,
            provider_code=out.provider_code,
        )
    )
    _settle(db, d, c, out, payload, link, config)
    return out


def _event_context(d: Delivery) -> dict:
    return {
        "caller_module": d.caller_module,
        "caller_reference": d.caller_reference,
        "provider": d.provider or "",
        "subject_key": d.subject_key,
        "object_id": d.object_id,
        "person_id": d.person_id,
        "account_link_id": d.account_link_id,
        "refs": d.refs or {},
    }


def _delivery_event(db: Session, d: Delivery, name: str, **extra) -> None:
    if d.sync or d.direction != "outbound":
        return  # a sync caller has the answer already; events are for async outcomes
    publish(
        db,
        d.organisation_id,
        name,
        {
            "delivery_id": d.id,
            "port": d.port,
            "operation": d.operation,
            "caller_module": d.caller_module or "",
            "caller_reference": d.caller_reference or "",
            **extra,
        },
    )


def _settle(
    db: Session, d: Delivery, c: Connection, out: Outcome, payload: dict, link: AccountLink | None, config: HubConfig
) -> None:
    now = clock()
    if out.provider_reference:
        d.provider_reference = out.provider_reference
    manual = out.error_code == "manual_action_required" or (
        out.ok and out.output.get("status") == "manual_action_required"
    )
    if out.ok and not manual:
        d.status = "succeeded"
        d.completed_at = now
        d.next_attempt_at = None
        d.last_error_code = None
        d.object_id = port_events.object_of(d.port, out.output) or d.object_id
        if link is not None and d.operation == "sync":
            link.last_synced_at = now
        _delivery_event(db, d, "delivery.succeeded", provider_reference=d.provider_reference)
        for name, body in port_events.outbound_events(
            d.port, d.operation, payload, out.output, _event_context(d), now.date()
        ):
            publish(db, d.organisation_id, name, body)
        return
    if manual:
        d.status = "manual_action_required"
        d.completed_at = now
        d.next_attempt_at = None
        d.last_error_code = "manual_action_required"
        if out.ok:
            d.object_id = port_events.object_of(d.port, out.output) or d.object_id
        _delivery_event(db, d, "delivery.manual-action-required")
        return
    d.last_error_code = out.error_code
    if out.retryable and not d.sync and d.attempts < config.retry_max_attempts:
        delay = rules.backoff_s(
            d.attempts, base_s=config.retry_base_s, max_s=config.retry_max_s, retry_after_s=out.retry_after_s
        )
        d.status = "retry_scheduled"
        d.next_attempt_at = now + timedelta(seconds=delay)
        if out.error_code == "throttled":
            c.throttled_until = d.next_attempt_at  # hold the connection's queue, not each item's attempts
        return
    dead = out.retryable and not d.sync
    d.status = "dead_lettered" if dead else "failed"
    d.completed_at = now
    d.next_attempt_at = None
    _delivery_event(db, d, "delivery.failed", error_code=out.error_code, dead_lettered=dead)


def _fail(db: Session, d: Delivery, code: str) -> None:
    d.status = "failed"
    d.last_error_code = code
    d.completed_at = clock()
    d.next_attempt_at = None
    _delivery_event(db, d, "delivery.failed", error_code=code, dead_lettered=False)


# ------------------------------------------------------------------ the sweep (scheduled)


def process_due(db: Session, *, limit: int = SWEEP_BATCH) -> int:
    """Run every outbound delivery that is due and every inbound callback not yet processed. Each runs in its own
    organisation's scope and transaction; one failing never stops the others. Returns how many were attempted."""
    from . import inbound  # the inbound side shares this sweep

    now = clock()
    with platform_scope():
        rows = db.execute(
            select(Delivery.id, Delivery.organisation_id, Delivery.direction)
            .where(
                Delivery.status.in_(("queued", "retry_scheduled", "in_progress")),
                Delivery.next_attempt_at.is_not(None),
                Delivery.next_attempt_at <= now,
            )
            .order_by(Delivery.next_attempt_at)
            .limit(limit)
        ).all()
        db.rollback()
    done = 0
    for delivery_id, org, direction in rows:
        try:
            if direction == "inbound":
                done += inbound.process(db, delivery_id)
            else:
                with organisation_scope(org):
                    done += _process_outbound(db, delivery_id)
        except Exception as e:  # noqa: BLE001 - one bad row must not stop the sweep
            db.rollback()
            log.warning("delivery %s could not be processed: %s", delivery_id, type(e).__name__)
    return done


def _process_outbound(db: Session, delivery_id: str) -> int:
    config = HubConfig.from_env()
    now = clock()
    d = db.scalar(scoped(db, select(Delivery), Delivery).where(Delivery.id == delivery_id).with_for_update())
    if d is None or d.status in TERMINAL or (d.next_attempt_at and aware(d.next_attempt_at) > now):
        db.rollback()
        return 0
    c = db.get(Connection, d.connection_id) if d.connection_id else None
    if c is None:
        _fail(db, d, "not_configured")
        db.commit()
        return 0
    if not c.enabled:
        if now - aware(d.created_at) > timedelta(hours=config.queue_expiry_hours):
            _fail(db, d, "not_configured")
        else:
            d.next_attempt_at = now + timedelta(minutes=5)  # kept queued until enabled or expired
            if d.status == "in_progress":
                d.status = "retry_scheduled"
        db.commit()
        return 0
    if d.mode != c.mode or (c.mode == "mock" and not config.allow_mock):
        _fail(db, d, "not_configured")  # never replayed in another mode (docs/prd.md)
        db.commit()
        return 0
    if c.throttled_until and aware(c.throttled_until) > now:
        d.next_attempt_at = c.throttled_until
        db.commit()
        return 0
    if d.payload_encrypted is None:
        _fail(db, d, "invalid_request")  # the input is no longer kept
        db.commit()
        return 0
    try:
        payload = json.loads(get_cipher(config).decrypt(d.payload_encrypted, d.id))
    except (SecretStoreError, ValueError):
        _fail(db, d, "not_configured")
        db.commit()
        return 0
    link = db.get(AccountLink, d.account_link_id) if d.account_link_id else None
    if link is not None and link.status != "active":
        _fail(db, d, "consent_required")
        db.commit()
        return 0
    _attempt(db, d, c, payload, link, config)
    db.commit()
    return 1


# ------------------------------------------------------------------ manual retry


def retry(db: Session, actor: Actor, delivery_id: str) -> dict:
    d = _get(db, delivery_id)
    if d.direction != "outbound" or d.status not in ("failed", "dead_lettered"):
        raise HubError(409, "not_retryable", "only a failed or dead-lettered outbound delivery can be retried")
    if d.payload_encrypted is None:
        raise HubError(409, "not_retryable", "the delivery's input is no longer kept (sync, or past retention)")
    c = db.get(Connection, d.connection_id) if d.connection_id else None
    if not ERROR_CODES.get(d.last_error_code or "", False):
        changed = c is not None and d.completed_at is not None and aware(c.changed_at) > aware(d.completed_at)
        if not changed:
            raise HubError(409, "not_retryable", "the error is not retryable and the connection has not changed since")
    if c is None or d.mode != c.mode:
        raise HubError(409, "not_retryable", "the delivery was made in another mode; deliveries are never replayed")
    d.status = "queued"
    d.next_attempt_at = clock()
    d.completed_at = None
    record(
        db,
        d.organisation_id,
        actor.user_id,
        "delivery.retried",
        "delivery",
        d.id,
        after={"attempts": d.attempts, "last_error_code": d.last_error_code},
    )
    db.commit()
    return delivery_dict(d)


# ------------------------------------------------------------------ retention (scheduled)


def purge(db: Session) -> int:
    """Encrypted inputs after INTEGRATION_HUB_DELIVERY_PAYLOAD_RETENTION_DAYS from the delivery's end, raw callbacks
    after INTEGRATION_HUB_INBOUND_RAW_RETENTION_DAYS, log rows after INTEGRATION_HUB_DELIVERY_LOG_RETENTION_DAYS, and
    spent OAuth states. Returns how many rows changed."""
    config = HubConfig.from_env()
    now = clock()
    changed = 0
    with platform_scope():
        changed += db.execute(
            update(Delivery)
            .where(
                Delivery.payload_encrypted.is_not(None),
                Delivery.completed_at.is_not(None),
                Delivery.completed_at < now - timedelta(days=config.delivery_payload_retention_days),
            )
            .values(payload_encrypted=None)
        ).rowcount
        changed += db.execute(
            update(InboundReceipt)
            .where(
                InboundReceipt.raw_encrypted.is_not(None),
                InboundReceipt.received_at < now - timedelta(days=config.inbound_raw_retention_days),
            )
            .values(raw_encrypted=None)
        ).rowcount
        cutoff = now - timedelta(days=config.delivery_log_retention_days)
        old = select(Delivery.id).where(Delivery.created_at < cutoff)
        db.execute(delete(DeliveryAttempt).where(DeliveryAttempt.delivery_id.in_(old)))
        changed += db.execute(delete(Delivery).where(Delivery.created_at < cutoff)).rowcount
        changed += db.execute(delete(InboundReceipt).where(InboundReceipt.received_at < cutoff)).rowcount
        changed += db.execute(delete(OAuthState).where(OAuthState.expires_at < now - timedelta(days=1))).rowcount
        db.commit()
    return changed
