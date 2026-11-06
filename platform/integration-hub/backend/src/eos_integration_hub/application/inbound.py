"""Provider callbacks (docs/prd.md, "Inbound"). Every callback arrives at the hub, never at an adapter's own route.

1. The body is refused over INTEGRATION_HUB_INBOUND_MAX_BYTES (the API layer) and kept raw: signatures are computed
   over bytes, not re-serialised JSON.
2. The adapter's verify_inbound decides: accept, reject (with the status the provider expects, 401 by default) or
   handshake. A request that cannot be verified is rejected, logged as rejected_inbound, audited and never processed.
3. A redelivery (same dedupe key for the same connection) is acknowledged and ignored. Another connection's event
   with the same id, in another organisation, is its own event.
4. The request is acknowledged before any processing; parse_inbound, follow-up fetches and events run afterwards
   (a background task right after the response, and the scheduled sweep as the safety net).
5. Provider requests (a channel) are answered synchronously by handle_provider_request; the answer is not kept.

The tenant is not known when a request arrives, so this runs in platform scope (the hub's platform role) and sets each
row's organisation_id once the connection is known. Nothing here logs a body, a header value or a secret."""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from datetime import timedelta

from eos_core.db import SessionLocal, new_id
from eos_core.tenant import platform_scope
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import port_events, rules
from ..domain.vocabulary import CHANNEL_RE, CONNECTION_KEY_RE, MAX_DEDUPE_KEY, MAX_SUBJECT
from ..infrastructure.config import HubConfig
from ..infrastructure.models import AccountLink, Connection, Delivery, InboundReceipt
from ..infrastructure.registry import AdapterContext, AdapterInfo, Outcome, call, get_registry
from ..infrastructure.secrets import SecretStoreError, get_cipher
from . import authorisation, deliveries
from .common import aware, clock, context_for, publish, record, resolve_secrets

log = logging.getLogger("eos.integration_hub")

MAX_NOTIFICATIONS = 100
MAX_HEADERS = 100


@dataclass
class Answer:
    status: int
    body: bytes = b""
    content_type: str = "application/json"
    process_delivery_id: str | None = None  # an accepted webhook to process once the response is sent
    headers: dict = field(default_factory=dict)


def _json_answer(status: int, code: str, detail: str) -> Answer:
    return Answer(status, json.dumps({"code": code, "detail": detail}).encode())


NOT_FOUND = ("not_found", "unknown callback address")


def _headers(raw: dict) -> dict[str, str]:
    """Lower-cased header names, bounded. Values are kept for the adapter (signatures live there), never logged."""
    out: dict[str, str] = {}
    for k, v in list(raw.items())[:MAX_HEADERS]:
        if isinstance(k, str) and isinstance(v, str) and len(k) <= 100 and len(v) <= 8192:
            out[k.lower()] = v
    return out


def _handshake(spec) -> Answer:
    spec = spec if isinstance(spec, dict) else {}
    status = spec.get("status")
    status = status if isinstance(status, int) and not isinstance(status, bool) and 200 <= status < 300 else 200
    body = spec.get("body")
    content_type = spec.get("content_type") if isinstance(spec.get("content_type"), str) else None
    if isinstance(body, dict | list):
        data, content_type = json.dumps(body).encode(), content_type or "application/json"
    elif isinstance(body, str):
        data = body.encode()
    elif isinstance(body, bytes):
        data = body
    else:
        data = b""
    return Answer(status, data[:65536], (content_type or "text/plain")[:100])


def _reject_status(value) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and 400 <= value < 500 else 401


def _connection_by_key(db: Session, adapter: str, key: str) -> Connection | None:
    if not CONNECTION_KEY_RE.match(key):
        return None
    return db.scalar(
        select(Connection).where(Connection.connection_key_hash == rules.sha256_hex(key), Connection.adapter == adapter)
    )


def _context(db: Session, info: AdapterInfo, c: Connection | None, timeout_s: int) -> AdapterContext:
    if c is None:  # an app-level callback: the adapter verifies with its platform credentials
        return AdapterContext(
            organisation_id=None, connection_id=None, provider=None, mode=None, operation="verify_inbound"
        )
    try:
        secrets = resolve_secrets(db, c)
    except SecretStoreError:
        secrets = {}
    return context_for(c, secrets=secrets, timeout_s=timeout_s, operation="verify_inbound")


def _reject(db: Session, adapter: str, c: Connection | None, status: int, channel: str | None, note: str) -> Answer:
    """Log and audit a request that could not be verified. It is never processed."""
    org = c.organisation_id if c else None
    receipt = InboundReceipt(
        organisation_id=org,
        adapter=adapter,
        connection_id=c.id if c else None,
        channel=channel,
        verdict="rejected",
        received_at=clock(),
        note=note[:200],
    )
    db.add(receipt)
    db.flush()
    if c is not None:
        db.add(
            Delivery(
                organisation_id=org,
                direction="inbound",
                connection_id=c.id,
                port=c.port,
                operation=f"provider_request:{channel}" if channel else "webhook",
                mode=c.mode,
                provider=c.provider,
                status="rejected_inbound",
                attempts=0,
                last_error_code="signature_invalid",
                inbound_receipt_id=receipt.id,
                created_at=clock(),
                completed_at=clock(),
            )
        )
    record(
        db, org, None, "inbound.rejected", "inbound_receipt", receipt.id, after={"adapter": adapter, "note": note[:200]}
    )
    db.commit()
    return _json_answer(status, "signature_invalid", "the request could not be verified")


def receive(
    db: Session,
    *,
    adapter: str,
    connection_key: str | None,
    channel: str | None,
    method: str,
    query: dict,
    headers: dict,
    raw_body: bytes,
) -> Answer:
    config = HubConfig.from_env()
    info = get_registry().get(adapter)
    if info is None:
        return _json_answer(404, *NOT_FOUND)
    if channel is not None and not CHANNEL_RE.match(channel):
        return _json_answer(404, *NOT_FOUND)
    with platform_scope():
        try:
            return _receive(db, config, info, connection_key, channel, method, query, _headers(headers), raw_body)
        except Exception:
            db.rollback()
            raise


def _receive(db, config, info, connection_key, channel, method, query, headers, raw_body) -> Answer:
    adapter = info.adapter
    c = None
    if connection_key is not None:
        c = _connection_by_key(db, adapter, connection_key)
        if c is None:
            return _json_answer(404, *NOT_FOUND)
    timeout = config.provider_request_timeout_s
    ctx = _context(db, info, c, timeout)
    suffix = channel or ""  # what follows the connection key; the key itself is never handed to the adapter
    verify = call(
        info,
        "verify_inbound",
        ctx,
        {
            "method": method,
            "path_suffix": suffix,
            "query": dict(query),
            "headers": headers,
            "raw_body": raw_body,
            "connection_id": c.id if c else None,
        },
        timeout_s=timeout,
    )
    v = verify.output if verify.ok else {}
    verdict = v.get("verdict")
    if verdict == "handshake":
        db.add(
            InboundReceipt(
                organisation_id=c.organisation_id if c else None,
                adapter=adapter,
                connection_id=c.id if c else None,
                channel=channel,
                verdict="handshake",
                received_at=clock(),
                processed_at=clock(),
            )
        )
        db.commit()
        return _handshake(v.get("handshake_response"))
    if verdict != "accept":
        return _reject(
            db,
            adapter,
            c,
            _reject_status(v.get("reject_status")),
            channel,
            "verification failed" if verify.ok else f"verify_inbound: {verify.error_code}",
        )
    link = None
    if c is None:
        c, link = _resolve(db, adapter, v.get("resolves_to"))
        if c is None:
            return _reject(db, adapter, None, 401, channel, "the callback names no connection")
    dedupe = v.get("dedupe_key")
    dedupe = dedupe[:MAX_DEDUPE_KEY] if isinstance(dedupe, str) and dedupe else None
    if dedupe and db.scalar(
        select(InboundReceipt.id).where(InboundReceipt.connection_id == c.id, InboundReceipt.dedupe_key == dedupe)
    ):
        return Answer(_ack_status(v))  # a redelivery to this connection: acknowledged and ignored
    receipt_id = new_id()
    try:
        raw = get_cipher(config).encrypt(_pack(headers, raw_body), f"inbound:{receipt_id}")
    except SecretStoreError:
        raw = None
    receipt = InboundReceipt(
        id=receipt_id,
        organisation_id=c.organisation_id,
        adapter=adapter,
        connection_id=c.id,
        channel=channel,
        dedupe_key=dedupe,
        verdict="accepted",
        raw_encrypted=raw,
        received_at=clock(),
    )
    db.add(receipt)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()  # the same event arrived twice at once; the other request keeps it
        return Answer(_ack_status(v))
    d = Delivery(
        organisation_id=c.organisation_id,
        direction="inbound",
        connection_id=c.id,
        account_link_id=link.id if link else None,
        port=c.port,
        operation=f"provider_request:{channel}" if channel else "webhook",
        mode=c.mode,
        provider=c.provider,
        status="queued",
        attempts=0,
        inbound_receipt_id=receipt.id,
        created_at=clock(),
        next_attempt_at=clock(),
    )
    db.add(d)
    if channel is not None:
        return _provider_request(db, info, c, d, receipt, channel, headers, raw_body, timeout)
    if not c.enabled:
        # Verified and logged, not processed (contracts/openapi.yaml, POST /connections/{id}/disable).
        d.status, d.last_error_code, d.completed_at, d.next_attempt_at = "failed", "not_configured", clock(), None
        receipt.processed_at = clock()
        db.commit()
        return Answer(_ack_status(v))
    db.commit()
    return Answer(_ack_status(v), process_delivery_id=d.id)


def _ack_status(v: dict) -> int:
    status = v.get("ack_status")
    return status if status in (200, 202, 204) else 200


def _pack(headers: dict, raw_body: bytes) -> bytes:
    return json.dumps({"headers": headers, "body": base64.b64encode(raw_body).decode()}).encode()


def _unpack(blob: bytes) -> tuple[dict, bytes]:
    data = json.loads(blob)
    return data.get("headers") or {}, base64.b64decode(data.get("body") or "")


def _resolve(db: Session, adapter: str, resolves_to) -> tuple[Connection | None, AccountLink | None]:
    r = resolves_to if isinstance(resolves_to, dict) else {}
    cid, subject = r.get("connection_id"), r.get("account_link_subject")
    if isinstance(cid, str) and len(cid) <= 36:
        c = db.scalar(select(Connection).where(Connection.id == cid, Connection.adapter == adapter))
        return c, None
    if isinstance(subject, str) and 0 < len(subject) <= MAX_SUBJECT:
        link = db.scalar(
            select(AccountLink)
            .join(Connection, Connection.id == AccountLink.connection_id)
            .where(AccountLink.provider_subject == subject, Connection.adapter == adapter)
            .order_by(AccountLink.created_at.desc())
            .limit(1)
        )
        if link is not None:
            return db.get(Connection, link.connection_id), link
    return None, None


def _provider_request(db, info, c, d, receipt, channel, headers, raw_body, timeout) -> Answer:
    d.attempts = 1
    if not c.enabled:
        out = Outcome.failure("not_configured", "connection disabled")
    else:
        ctx = _context(db, info, c, timeout)
        ctx.operation = "handle_provider_request"
        out = call(
            info,
            "handle_provider_request",
            ctx,
            {"channel": channel, "headers": headers, "raw_body": raw_body},
            timeout_s=timeout,
        )
    d.status = "succeeded" if out.ok else "failed"
    d.last_error_code = out.error_code
    d.completed_at = receipt.processed_at = clock()
    d.next_attempt_at = None
    db.commit()
    if not out.ok:
        return _json_answer(503, out.error_code, "the request could not be answered now")
    status = out.output.get("status")
    status = status if isinstance(status, int) and not isinstance(status, bool) and 100 <= status < 600 else 200
    body = out.output.get("body")
    body = body.encode() if isinstance(body, str) else body if isinstance(body, bytes) else b""
    ctype = out.output.get("content_type") if isinstance(out.output.get("content_type"), str) else "application/xml"
    return Answer(status, body, ctype[:100])


# ------------------------------------------------------------------ processing (after the acknowledgement)


def process_now(delivery_id: str) -> None:
    """The background task the route schedules after answering. Its own session; the sweep retries anything left."""
    db = SessionLocal()
    try:
        process(db, delivery_id)
    except Exception as e:  # noqa: BLE001 - after the response nothing may raise; the sweep picks it up again
        db.rollback()
        log.warning("inbound delivery %s could not be processed now: %s", delivery_id, type(e).__name__)
    finally:
        db.close()


def process(db: Session, delivery_id: str) -> int:
    config = HubConfig.from_env()
    with platform_scope():
        d = db.scalar(select(Delivery).where(Delivery.id == delivery_id).with_for_update())
        if d is None or d.direction != "inbound" or d.status not in ("queued", "retry_scheduled", "in_progress"):
            db.rollback()
            return 0
        if d.next_attempt_at is not None and aware(d.next_attempt_at) > clock():
            db.rollback()  # claimed by another worker (its lease runs), or a retry not yet due
            return 0
        c = db.get(Connection, d.connection_id) if d.connection_id else None
        receipt = db.get(InboundReceipt, d.inbound_receipt_id) if d.inbound_receipt_id else None
        info = get_registry().get(c.adapter) if c else None
        if c is None or receipt is None or info is None or receipt.raw_encrypted is None:
            d.status, d.last_error_code, d.completed_at, d.next_attempt_at = "failed", "not_configured", clock(), None
            db.commit()
            return 0
        d.attempts += 1
        d.status = "in_progress"
        d.started_at = d.started_at or clock()
        d.next_attempt_at = clock() + timedelta(seconds=deliveries.async_timeout_s(config) + 60)
        db.commit()
        try:
            headers, raw_body = _unpack(get_cipher(config).decrypt(receipt.raw_encrypted, f"inbound:{receipt.id}"))
            secrets = resolve_secrets(db, c)
        except (SecretStoreError, ValueError):
            out = Outcome.failure("not_configured", "the stored callback cannot be read")
        else:
            ctx = context_for(
                c,
                secrets=secrets,
                delivery_id=d.id,
                attempt=d.attempts,
                operation="parse_inbound",
                timeout_s=deliveries.async_timeout_s(config),
            )
            out = call(
                info,
                "parse_inbound",
                ctx,
                {"headers": headers, "raw_body": raw_body},
                timeout_s=deliveries.async_timeout_s(config),
            )
        if out.ok:
            kinds = _apply(db, c, d, out.output.get("notifications"))
            d.operation = (",".join(dict.fromkeys(kinds)) or d.operation)[:80]
            d.status, d.last_error_code, d.completed_at, d.next_attempt_at = "succeeded", None, clock(), None
            receipt.processed_at = clock()
        elif out.retryable and d.attempts < config.retry_max_attempts:
            d.status, d.last_error_code = "retry_scheduled", out.error_code
            delay = rules.backoff_s(
                d.attempts, base_s=config.retry_base_s, max_s=config.retry_max_s, retry_after_s=out.retry_after_s
            )
            d.next_attempt_at = clock() + timedelta(seconds=delay)
        else:
            dead = out.retryable
            d.status = "dead_lettered" if dead else "failed"
            d.last_error_code, d.completed_at, d.next_attempt_at = out.error_code, clock(), None
            receipt.processed_at = clock()
        db.commit()
    return 1


def _apply(db: Session, c: Connection, d: Delivery, notifications) -> list[str]:
    """Publish the port events and start the follow-up work each notification calls for."""
    kinds: list[str] = []
    if not isinstance(notifications, list):
        return kinds
    for i, n in enumerate(notifications[:MAX_NOTIFICATIONS]):
        if not isinstance(n, dict) or not isinstance(n.get("kind"), str):
            continue
        port = n.get("port") if isinstance(n.get("port"), str) else c.port
        if port != c.port:
            continue  # a connection serves one port; anything else is the adapter's mistake
        kind, data = n["kind"][:40], n.get("data") if isinstance(n.get("data"), dict) else {}
        kinds.append(kind)
        ctx = _known(db, c, port, kind, data)
        for name, body in port_events.inbound_events(port, kind, data, ctx):
            publish(db, c.organisation_id, name, body)
        _follow_up(db, c, d, port, kind, data, ctx, i)
    return kinds


def _known(db: Session, c: Connection, port: str, kind: str, data: dict) -> dict:
    """What the delivery log knows about the object a notification is about: the module that asked, the person."""
    subject = port_events.subject_of(port, data) if port != "wearable-data" else None
    object_id = port_events.object_of(port, data)
    prior = deliveries.prior_delivery(db, c.organisation_id, port, subject, object_id)
    return {
        "provider": c.provider,
        "caller_module": prior.caller_module if prior else None,
        "caller_reference": prior.caller_reference if prior else None,
        "person_id": prior.person_id if prior else None,
        "subject_key": prior.subject_key if prior else subject,
        "refs": prior.refs if prior else {},
    }


def _link_by_subject(db: Session, c: Connection, data: dict) -> AccountLink | None:
    subject = data.get("account_link_subject")
    if not isinstance(subject, str) or not subject:
        return None
    return db.scalar(
        select(AccountLink).where(
            AccountLink.connection_id == c.id,
            AccountLink.provider_subject == subject[:MAX_SUBJECT],
            AccountLink.status == "active",
        )
    )


def _follow_up(db: Session, c: Connection, d: Delivery, port: str, kind: str, data: dict, known: dict, i: int) -> None:
    if port == "meetings" and kind == "attendance_ready" and known.get("subject_key"):
        key = known["subject_key"]
        if not db.scalar(
            select(Delivery.id).where(
                Delivery.organisation_id == c.organisation_id,
                Delivery.idempotency_key == f"integration-hub:attendance:{key}",
            )
        ):
            deliveries.enqueue(
                db,
                c,
                operation="fetch_attendance",
                payload={"meeting_key": key},
                sync=False,
                caller_module=known.get("caller_module") or "integration-hub",
                caller_reference=known.get("caller_reference"),
                idempotency_key=f"integration-hub:attendance:{key}",
            )
    elif port == "wearable-data" and kind == "data_available":
        link = _link_by_subject(db, c, data)
        if link is not None:
            payload = {
                "account_link_id": link.id,
                "data_types": data.get("data_types") or [],
                "from": data.get("from"),
                "to": data.get("to"),
            }
            deliveries.enqueue(
                db,
                c,
                operation="sync",
                payload=payload,
                sync=False,
                caller_module="integration-hub",
                caller_reference=link.id,
                idempotency_key=f"integration-hub:sync:{d.id}:{i}",
                link=link,
            )
    elif port == "wearable-data" and kind == "link_revoked_by_provider":
        link = _link_by_subject(db, c, data)
        if link is not None:
            authorisation.end_link(db, link, cause="revoked_at_provider", actor=None)
