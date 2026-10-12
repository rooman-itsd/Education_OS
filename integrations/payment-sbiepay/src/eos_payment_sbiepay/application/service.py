"""Use cases of the payment adapter. Authenticated calls arrive with the caller's organisation pinned on the
session; public calls (redirect, gateway callback) and scheduled jobs look the payment up by reference and
then act inside that payment's organisation scope."""

from __future__ import annotations

import secrets
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from html import escape
from urllib.parse import urlencode, urlparse

from eos_core import events
from eos_core.db import scoped, utcnow
from eos_core.tenant import organisation_scope, platform_scope
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.models import (
    OPEN_STATUSES,
    PAID_STATUSES,
    MerchantAccount,
    Notification,
    Payment,
    ReconciliationRun,
    Refund,
    iso,
    money,
)
from ..infrastructure import config as config_module
from ..infrastructure import notifier
from ..infrastructure.gateway import (
    GatewayResponseInvalidError,
    GatewayUnavailableError,
    PaymentOrder,
    VerifyResult,
    gateway_for,
)

API_PREFIX = "/api/v1/payment-sbiepay"
MOCK_PLATFORM_MERCHANT_ID = "MOCK-PLATFORM"
PURPOSES = ("subscription", "fee")
MAX_RETRY_DELAY = timedelta(hours=6)


class PaymentError(Exception):
    def __init__(self, message: str, status: int = 400, body: dict | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


def _aware(value: datetime | None) -> datetime | None:
    """SQLite hands datetimes back without a zone; everything here is UTC."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _config() -> config_module.Config:
    try:
        return config_module.load()
    except config_module.ConfigError as e:
        raise PaymentError(str(e), 503) from e


def _amount(value: str) -> Decimal:
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError) as e:
        raise PaymentError("amount must be a decimal string in rupees", 422) from e
    if not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal("0.01")):
        raise PaymentError("amount must be positive with at most two decimal places", 422)
    return amount.quantize(Decimal("0.01"))


def _check_url(url: str | None, cfg: config_module.Config, field: str) -> None:
    if url is None:
        return
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise PaymentError(f"{field} must be an absolute http(s) URL", 422)
    if not cfg.allowed_return_hosts:
        if cfg.mode == "mock":
            return
        raise PaymentError("PAYMENT_SBIEPAY_ALLOWED_RETURN_HOSTS is not set", 503)
    if parsed.hostname.lower() not in cfg.allowed_return_hosts:
        raise PaymentError(f"{field} host is not allowed", 422)


def _order(p: Payment) -> PaymentOrder:
    return PaymentOrder(
        reference=p.reference,
        merchant_id=p.merchant_id,
        amount=Decimal(p.amount),
        currency=p.currency,
        description=p.description,
        payer=dict(p.payer or {}),
    )


def _session(p: Payment, cfg: config_module.Config) -> dict:
    return {
        "reference": p.reference,
        "payment_url": f"{cfg.callback_base_url}{API_PREFIX}/payments/{p.reference}/redirect",
        "expires_at": iso(_aware(p.expires_at)),
    }


def _org_merchant(db: Session) -> MerchantAccount | None:
    return db.scalar(scoped(db, select(MerchantAccount), MerchantAccount))


def _merchant_id_for(db: Session, purpose: str, cfg: config_module.Config) -> str:
    if purpose == "subscription":
        if cfg.merchant_id:
            return cfg.merchant_id
        if cfg.mode == "mock":
            return MOCK_PLATFORM_MERCHANT_ID
        raise PaymentError("no active merchant account for subscription payments", 503)
    account = _org_merchant(db)
    if account is None or not account.active:
        raise PaymentError("no active merchant account for fee payments", 503)
    if cfg.mode != "mock" and account.encryption_key_ciphertext is None:
        raise PaymentError("the organisation's merchant account has no encryption key", 503)
    return account.merchant_id


# ---------------------------------------------------------------- events and notifications


def _publish(db: Session, p: Payment, name: str, payload: dict, actor: str | None = None) -> None:
    """Publish the event in the same transaction and, when the caller gave notify_url, queue the signed
    PaymentNotification with the same id so receivers can de-duplicate on event_id."""
    ev = events.publish(db, name, p.organisation_id, {"organisation_id": p.organisation_id, **payload}, actor=actor)
    db.flush()
    if not p.notify_url:
        return
    body = {
        "event_id": ev.id,
        "event": name,
        "organisation_id": p.organisation_id,
        "reference": p.reference,
        "purpose": p.purpose,
        "source_module": p.source_module,
        "source_reference": p.source_reference,
        "status": p.status,
        "amount": money(p.amount),
        "currency": p.currency,
        "gateway_transaction_id": p.gateway_transaction_id,
        "occurred_at": iso(_aware(ev.occurred_at)),
    }
    db.add(
        Notification(organisation_id=p.organisation_id, event_id=ev.id, payment_id=p.id, url=p.notify_url, body=body)
    )


def _base_payload(p: Payment) -> dict:
    return {
        "reference": p.reference,
        "purpose": p.purpose,
        "source_module": p.source_module,
        "source_reference": p.source_reference,
    }


def _expire(db: Session, p: Payment) -> None:
    p.status, p.completed_at = "expired", utcnow()
    _publish(db, p, "payment-sbiepay.payment.expired", _base_payload(p))


def _apply(db: Session, p: Payment, result: VerifyResult) -> None:
    """Record the outcome of double verification. Final payments never change again (idempotent)."""
    if p.status not in OPEN_STATUSES:
        return
    if result.status == "succeeded" and result.amount is not None and Decimal(result.amount) != Decimal(p.amount):
        result = VerifyResult(
            "failed",
            gateway_transaction_id=result.gateway_transaction_id,
            failure_reason=f"gateway amount {money(result.amount)} differs from requested {money(p.amount)}",
        )
    if result.status == "succeeded":
        p.status, p.completed_at = "succeeded", utcnow()
        p.gateway_transaction_id, p.payment_mode = result.gateway_transaction_id, result.payment_mode
        _publish(
            db,
            p,
            "payment-sbiepay.payment.succeeded",
            {
                **_base_payload(p),
                "amount": money(p.amount),
                "currency": p.currency,
                "gateway_transaction_id": p.gateway_transaction_id,
                "payment_mode": p.payment_mode,
                "completed_at": iso(_aware(p.completed_at)),
            },
        )
    elif result.status == "failed":
        p.status, p.completed_at = "failed", utcnow()
        p.gateway_transaction_id = result.gateway_transaction_id
        p.failure_reason = (result.failure_reason or "failed at gateway")[:300]
        _publish(
            db,
            p,
            "payment-sbiepay.payment.failed",
            {**_base_payload(p), "amount": money(p.amount), "currency": p.currency, "failure_reason": p.failure_reason},
        )
    else:  # pending or not_found: the gateway has no final answer yet
        p.status = "pending"


def deliver_notifications(db: Session, organisation_id: str | None = None) -> int:
    """Post due notifications. Scheduled job (all organisations) and called right after a request (one).
    Failures back off exponentially up to MAX_RETRY_DELAY and keep retrying until a 2xx answer."""
    cfg = _config()
    scope = organisation_scope(organisation_id) if organisation_id else platform_scope()
    delivered = 0
    with scope:
        now = utcnow()
        due = list(
            db.scalars(
                select(Notification)
                .where(Notification.delivered_at.is_(None), Notification.next_attempt_at <= now)
                .where(*([Notification.organisation_id == organisation_id] if organisation_id else []))
                .order_by(Notification.next_attempt_at)
            )
        )
        for n in due:
            n.attempts += 1
            try:
                notifier.post(n.url, n.body, cfg.notify_secret)
            except Exception as e:  # any failure is retried; the reason is kept for operators
                n.last_error = str(e)[:300]
                n.next_attempt_at = utcnow() + min(timedelta(minutes=2 ** min(n.attempts, 10)), MAX_RETRY_DELAY)
            else:
                n.delivered_at, n.last_error = utcnow(), None
                delivered += 1
        db.commit()
    return delivered


# ---------------------------------------------------------------- payments


def initiate(db: Session, *, organisation_id: str, user_id: str, body: dict) -> tuple[dict, bool]:
    """Returns (session, created). created is False when an open payment for the same source exists."""
    cfg = _config()
    purpose = body["purpose"]
    if purpose not in PURPOSES:
        raise PaymentError("purpose must be subscription or fee", 422)
    if body["currency"] != "INR":
        raise PaymentError("currency must be INR", 422)
    amount = _amount(body["amount"])
    _check_url(body["return_url"], cfg, "return_url")
    _check_url(body.get("notify_url"), cfg, "notify_url")

    for open_payment in _open_payments(db, body["source_module"], body["source_reference"]):
        if open_payment.status == "pending" or _aware(open_payment.expires_at) > utcnow():
            raise PaymentError("an open payment already exists", 409, _session(open_payment, cfg))
        _expire(db, open_payment)  # created but never opened before its session ran out
    db.flush()  # the expiry must reach the database before the new payment takes the open slot

    p = Payment(
        organisation_id=organisation_id,
        reference=f"EOS{secrets.token_hex(8).upper()}",
        purpose=purpose,
        source_module=body["source_module"],
        source_reference=body["source_reference"],
        merchant_id=_merchant_id_for(db, purpose, cfg),
        amount=amount,
        currency="INR",
        description=body.get("description") or "",
        payer=body.get("payer") or {},
        return_url=body["return_url"],
        notify_url=body.get("notify_url"),
        status="created",
        initiated_by=user_id,
        expires_at=utcnow() + timedelta(minutes=cfg.session_ttl_minutes),
    )
    db.add(p)
    try:
        db.commit()
    except IntegrityError as e:
        # A simultaneous request won the open slot (uq_payment_sbiepay_open_source): answer like the check above.
        db.rollback()
        winner = next(iter(_open_payments(db, body["source_module"], body["source_reference"])), None)
        if winner is None:
            raise
        raise PaymentError("an open payment already exists", 409, _session(winner, cfg)) from e
    return _session(p, cfg), True


def _open_payments(db: Session, source_module: str, source_reference: str) -> list[Payment]:
    q = select(Payment).where(
        Payment.source_module == source_module,
        Payment.source_reference == source_reference,
        Payment.status.in_(OPEN_STATUSES),
    )
    return list(db.scalars(scoped(db, q, Payment)))


def list_payments(db: Session, *, filters: dict, cursor: str | None, limit: int) -> dict:
    q = select(Payment)
    for key in ("status", "purpose", "source_module"):
        if filters.get(key):
            q = q.where(getattr(Payment, key) == filters[key])
    if filters.get("from"):
        q = q.where(Payment.created_at >= datetime.combine(filters["from"], time.min, UTC))
    if filters.get("to"):
        q = q.where(Payment.created_at < datetime.combine(filters["to"] + timedelta(days=1), time.min, UTC))
    try:
        offset = int(cursor) if cursor else 0
    except ValueError as e:
        raise PaymentError("invalid cursor", 400) from e
    q = scoped(db, q, Payment).order_by(Payment.created_at.desc(), Payment.id).offset(offset).limit(limit + 1)
    rows = list(db.scalars(q))
    more = len(rows) > limit
    return {"items": [p.to_dict() for p in rows[:limit]], "next_cursor": str(offset + limit) if more else None}


def get_payment(db: Session, reference: str) -> Payment:
    p = db.scalar(scoped(db, select(Payment).where(Payment.reference == reference), Payment))
    if p is None:
        raise PaymentError("payment not found", 404)
    return p


def _by_reference(db: Session, reference: str) -> Payment | None:
    """Public and scheduled paths: find a payment in any organisation, then end the bypass transaction."""
    with platform_scope():
        p = db.scalar(select(Payment).where(Payment.reference == reference))
        db.commit()
    return p


def redirect_page(db: Session, reference: str) -> str:
    cfg = _config()
    p = _by_reference(db, reference)
    if p is None or p.status not in OPEN_STATUSES or _aware(p.expires_at) <= utcnow():
        raise PaymentError("payment session expired or already finished", 410)
    callback_url = f"{cfg.callback_base_url}{API_PREFIX}/callbacks/sbiepay"
    try:
        form = gateway_for(cfg).redirect_form(_order(p), callback_url)
    except GatewayUnavailableError as e:
        raise PaymentError(str(e), 503) from e
    with organisation_scope(p.organisation_id):
        p.status = "pending"
        db.add(p)
        db.commit()
    inputs = "".join(
        f'<input type="hidden" name="{escape(k)}" value="{escape(v)}">' for k, v in sorted(form.fields.items())
    )
    return (
        '<!doctype html><html><head><meta charset="utf-8"><title>Redirecting to payment</title></head>'
        '<body onload="document.forms[0].submit()">'
        f'<form method="post" action="{escape(form.action_url)}">{inputs}'
        '<noscript><button type="submit">Continue to payment</button></noscript></form></body></html>'
    )


def handle_callback(db: Session, form: dict[str, str]) -> str:
    """Gateway return through the browser. Returns the caller's return_url with reference and status."""
    cfg = _config()
    gateway = gateway_for(cfg)
    try:
        reference = gateway.parse_response(form)
    except GatewayUnavailableError as e:
        raise PaymentError(str(e), 503) from e
    except GatewayResponseInvalidError as e:
        raise PaymentError("gateway response could not be read", 400) from e
    p = _by_reference(db, reference)
    if p is None:
        raise PaymentError("gateway response does not match a payment", 400)
    with organisation_scope(p.organisation_id):
        if p.status in OPEN_STATUSES:
            try:
                result = gateway.verify(_order(p))  # double verification: the browser response alone is never trusted
            except GatewayUnavailableError as e:
                raise PaymentError(str(e), 503) from e
            _apply(db, p, result)
            db.add(p)
            db.commit()
    deliver_notifications(db, p.organisation_id)
    joiner = "&" if urlparse(p.return_url).query else "?"
    return f"{p.return_url}{joiner}{urlencode({'reference': p.reference, 'status': p.status})}"


def _reverify(db: Session, p: Payment, cfg: config_module.Config) -> None:
    try:
        result = gateway_for(cfg).verify(_order(p))
    except GatewayUnavailableError as e:
        raise PaymentError(str(e), 503) from e
    if result.status == "not_found" and _aware(p.expires_at) <= utcnow():
        _expire(db, p)
    else:
        _apply(db, p, result)


def verify(db: Session, reference: str) -> dict:
    cfg = _config()
    p = get_payment(db, reference)
    if p.status in OPEN_STATUSES:
        _reverify(db, p, cfg)
        db.commit()
        deliver_notifications(db, p.organisation_id)
    return p.to_dict()


def sweep_open_payments(db: Session) -> int:
    """Scheduled job (platform/scheduler). Sessions never opened expire; payments left pending longer than
    PAYMENT_SBIEPAY_PENDING_VERIFY_AFTER_MINUTES are re-verified and expired if the gateway never saw them."""
    cfg = _config()
    now = utcnow()
    pending_cutoff = now - timedelta(minutes=cfg.pending_verify_after_minutes)
    with platform_scope():
        candidates = list(db.scalars(select(Payment).where(Payment.status.in_(OPEN_STATUSES))))
        db.commit()
    changed = 0
    for p in candidates:
        with organisation_scope(p.organisation_id):
            before = p.status
            if p.status == "created" and _aware(p.expires_at) <= now:
                _expire(db, p)
            elif p.status == "pending" and _aware(p.created_at) <= pending_cutoff:
                _reverify(db, p, cfg)
            db.add(p)
            db.commit()
            changed += p.status != before
    deliver_notifications(db)
    return changed


# ---------------------------------------------------------------- refunds


def refund(db: Session, *, reference: str, user_id: str, amount: str, reason: str) -> dict:
    cfg = _config()
    p = get_payment(db, reference)
    if p.status not in ("succeeded", "partially_refunded"):
        raise PaymentError("payment is not in status succeeded or partially_refunded", 409)
    value = _amount(amount)
    refundable = Decimal(p.amount) - Decimal(p.refunded_amount or 0)
    if value > refundable:
        raise PaymentError(f"amount exceeds the refundable balance of {money(refundable)}", 422)
    r = Refund(
        organisation_id=p.organisation_id,
        payment_id=p.id,
        reference=p.reference,
        amount=value,
        reason=reason,
        requested_by=user_id,
    )
    db.add(r)
    db.flush()
    try:
        result = gateway_for(cfg).refund(_order(p), r.id, value)
    except GatewayUnavailableError as e:
        db.rollback()
        raise PaymentError(str(e), 503) from e
    r.status, r.gateway_refund_id, r.failure_reason = result.status, result.gateway_refund_id, result.failure_reason
    if result.status == "succeeded":
        p.refunded_amount = Decimal(p.refunded_amount or 0) + value
        p.status = "refunded" if p.refunded_amount >= Decimal(p.amount) else "partially_refunded"
        _publish(
            db,
            p,
            "payment-sbiepay.payment.refunded",
            {
                **_base_payload(p),
                "refund_id": r.id,
                "amount": money(value),
                "refunded_total": money(p.refunded_amount),
                "currency": p.currency,
                "gateway_refund_id": r.gateway_refund_id,
            },
            actor=user_id,
        )
    db.commit()
    deliver_notifications(db, p.organisation_id)
    return r.to_dict()


# ---------------------------------------------------------------- reconciliation


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, UTC)
    return start, start + timedelta(days=1)


def run_reconciliation(
    db: Session, *, organisation_id: str, user_id: str, settlement_date: date, report_document_id: str | None
) -> dict:
    """Compare the gateway's settlement report for the organisation's merchant account with the fee
    payments completed that day. Runs inline; the scheduler calls the same function daily."""
    cfg = _config()
    if report_document_id:
        raise PaymentError("settlement reports from platform/documents are not supported yet", 501)
    run = ReconciliationRun(
        organisation_id=organisation_id, settlement_date=settlement_date, status="running", requested_by=user_id
    )
    db.add(run)
    db.flush()
    account = _org_merchant(db)
    if account is None:
        run.status, run.failure_reason, run.finished_at = "failed", "no merchant account", utcnow()
        db.commit()
        return run.to_dict()
    try:
        report = gateway_for(cfg).settlement(account.merchant_id, settlement_date)
    except GatewayUnavailableError as e:
        run.status, run.failure_reason, run.finished_at = "failed", str(e)[:300], utcnow()
        db.commit()
        return run.to_dict()

    start, end = _day_bounds(settlement_date)
    recorded = {
        p.reference: p
        for p in db.scalars(
            scoped(
                db,
                select(Payment).where(
                    Payment.purpose == "fee",
                    Payment.merchant_id == account.merchant_id,
                    Payment.status.in_(PAID_STATUSES),
                    Payment.completed_at >= start,
                    Payment.completed_at < end,
                ),
                Payment,
            )
        )
    }
    mismatches: list[dict] = []
    matched = 0
    seen: set[str] = set()
    for row in report:
        p = recorded.get(row.reference or "")
        if p is None and row.reference:
            p = db.scalar(scoped(db, select(Payment).where(Payment.reference == row.reference), Payment))
        if p is None:
            kind = "missing_in_records"
        elif p.status not in PAID_STATUSES:
            kind = "status_differs"
        elif Decimal(row.amount) != Decimal(p.amount):
            kind = "amount_differs"
        else:
            kind = None
        if p is not None:
            seen.add(p.reference)
        if kind is None:
            matched += 1
            p.settled_at = p.settled_at or utcnow()
            continue
        mismatches.append(
            {
                "reference": p.reference if p else row.reference,
                "gateway_transaction_id": row.gateway_transaction_id or (p.gateway_transaction_id if p else None),
                "kind": kind,
                "recorded_amount": money(p.amount) if p else None,
                "settled_amount": money(row.amount),
            }
        )
    for reference, p in recorded.items():
        if reference not in seen:
            mismatches.append(
                {
                    "reference": reference,
                    "gateway_transaction_id": p.gateway_transaction_id,
                    "kind": "missing_in_gateway",
                    "recorded_amount": money(p.amount),
                    "settled_amount": None,
                }
            )
    run.matched, run.mismatches = matched, mismatches
    run.status, run.finished_at = "completed", utcnow()
    for m in mismatches:
        events.publish(
            db,
            "payment-sbiepay.reconciliation.mismatch-found",
            organisation_id,
            {
                "organisation_id": organisation_id,
                "run_id": run.id,
                "settlement_date": settlement_date.isoformat(),
                "reference": m["reference"],
                "gateway_transaction_id": m["gateway_transaction_id"],
                "kind": m["kind"],
            },
            actor=user_id,
        )
    db.commit()
    return run.to_dict()


def list_runs(db: Session) -> list[dict]:
    q = scoped(db, select(ReconciliationRun), ReconciliationRun).order_by(ReconciliationRun.started_at.desc())
    return [r.to_dict() for r in db.scalars(q)]


def get_run(db: Session, run_id: str) -> dict:
    r = db.scalar(scoped(db, select(ReconciliationRun).where(ReconciliationRun.id == run_id), ReconciliationRun))
    if r is None:
        raise PaymentError("reconciliation run not found", 404)
    return r.to_dict()


def summary(db: Session, day: date) -> dict:
    """Counts and amounts for the Finance Staff widget payment-sbiepay.reconciliation. Days are UTC."""
    start, end = _day_bounds(day)
    payments = list(
        db.scalars(
            scoped(
                db,
                select(Payment).where(
                    ((Payment.created_at >= start) & (Payment.created_at < end))
                    | ((Payment.completed_at >= start) & (Payment.completed_at < end))
                ),
                Payment,
            )
        )
    )

    def on_day(value: datetime | None) -> bool:
        value = _aware(value)
        return value is not None and start <= value < end

    succeeded = [p for p in payments if p.status in PAID_STATUSES and on_day(p.completed_at)]
    pending = [p for p in payments if p.status in OPEN_STATUSES and on_day(p.created_at)]
    failed = [p for p in payments if p.status == "failed" and on_day(p.completed_at)]
    settled = [p for p in succeeded if p.settled_at is not None]
    last_run = db.scalar(
        scoped(
            db,
            select(ReconciliationRun).where(ReconciliationRun.settlement_date == day),
            ReconciliationRun,
        ).order_by(ReconciliationRun.started_at.desc())
    )

    def total(rows: list[Payment]) -> str:
        return money(sum((Decimal(p.amount) for p in rows), Decimal("0"))) or "0.00"

    return {
        "date": day.isoformat(),
        "succeeded": {"count": len(succeeded), "amount": total(succeeded)},
        "pending": {"count": len(pending), "amount": total(pending)},
        "failed": {"count": len(failed)},
        "settled": {"count": len(settled), "amount": total(settled)},
        "mismatches": len(last_run.mismatches or []) if last_run else 0,
        "last_run_at": iso(_aware(last_run.started_at)) if last_run else None,
    }


# ---------------------------------------------------------------- merchant account


def get_merchant_account(db: Session) -> dict:
    account = _org_merchant(db)
    if account is None:
        raise PaymentError("merchant account not configured", 404)
    return account.to_dict()


def put_merchant_account(db: Session, *, organisation_id: str, body: dict) -> dict:
    if body.get("encryption_key"):
        # PRD: keys are stored encrypted. Until an AES library is on the approved stack, none is stored.
        raise PaymentError("storing the encryption key is not available yet; it needs an approved AES library", 501)
    if body["mode"] not in ("sandbox", "live"):
        raise PaymentError("mode must be sandbox or live", 422)
    account = _org_merchant(db) or MerchantAccount(organisation_id=organisation_id)
    account.merchant_id, account.mode = body["merchant_id"], body["mode"]
    account.active = body.get("active", True)
    account.updated_at = utcnow()
    db.add(account)
    db.commit()
    return account.to_dict()
