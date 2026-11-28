from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime

from eos_core.db import get_db
from eos_core.settings import settings
from eos_identity.api.deps import Principal, require
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..application import config, service
from ..application.reports import subscription_report
from ..application.service import BillingError
from ..domain.limits import PlanLimits

router = APIRouter(tags=["billing"])


def _err(e: BillingError):
    return HTTPException(e.status, str(e))


def _refusal(e: BillingError) -> JSONResponse:
    """A refusal with its machine-readable code beside the message, for the errors that carry one."""
    return JSONResponse({"detail": str(e), "code": e.code}, status_code=e.status)


SIGNATURE_HEADER = "X-Payment-Signature"


class Upgrade(BaseModel):
    plan: str
    billing_cycle: str = "monthly"


class ProfileBody(BaseModel):
    legal_name: str
    gstin: str | None = None
    address: str = ""
    state_code: str | None = None


class PlanBody(BaseModel):
    id: str
    title: str
    description: str = ""
    price_per_month: float = 0
    currency: str = "INR"
    trial_days: int | None = None
    suites: list[str] = []
    modules: list[str] = []
    specialized_suites: int | str = 0
    integrations: list[str] = []
    limits: PlanLimits = PlanLimits()  # 422 for "unlimited", "50", -1 or an unknown key
    after_trial: str = "read_only"
    published: bool = True


class AdminSet(BaseModel):
    plan: str | None = None
    trial_ends_at: datetime | None = None
    comped_until: datetime | None = None
    reason: str = ""


@router.get("/plans")
def plans(db: Session = Depends(get_db)):
    """Public: the published price list, shown on the sign-up page before anyone has an account."""
    return service.list_plans(db)


@router.get("/subscription")
def subscription(
    p: Principal = Depends(require("billing:subscription:read", organisation=True)), db: Session = Depends(get_db)
):
    sub = service.get_subscription(db, p.organisation_id)
    if not sub:
        raise HTTPException(404, "no subscription")
    return sub.to_dict()


@router.get("/usage")
def usage(
    p: Principal = Depends(require("billing:subscription:read", organisation=True)), db: Session = Depends(get_db)
):
    """Usage against the plan's limits: users counted by identity; students and storage null until a module
    counts them."""
    return service.usage_vs_limits(db, p.organisation_id)


@router.get("/invoices")
def invoices(
    p: Principal = Depends(require("billing:subscription:read", organisation=True)), db: Session = Depends(get_db)
):
    """Invoices of the caller's organisation, newest first (one per paid period)."""
    return service.list_invoices(db, p.organisation_id)


@router.get("/billing-profile")
def billing_profile(
    p: Principal = Depends(require("billing:subscription:read", organisation=True)), db: Session = Depends(get_db)
):
    """Who the caller's invoices are addressed to (the GST recipient)."""
    profile = service.get_profile(db, p.organisation_id)
    if not profile:
        raise HTTPException(404, "no billing profile")
    return profile.to_dict()


@router.put("/billing-profile")
def put_billing_profile(
    body: ProfileBody, p: Principal = Depends(require("billing:subscription:manage")), db: Session = Depends(get_db)
):
    """Set the recipient of future invoices: legal name, optional GSTIN (validated), address and state."""
    try:
        return service.save_profile(db, organisation_id=p.organisation_id, **body.model_dump()).to_dict()
    except BillingError as e:
        raise _err(e) from e


@router.post("/subscription/upgrade", status_code=201)
def upgrade(
    body: Upgrade, p: Principal = Depends(require("billing:subscription:manage")), db: Session = Depends(get_db)
):
    try:
        return service.upgrade(
            db, organisation_id=p.organisation_id, plan_id=body.plan, billing_cycle=body.billing_cycle
        )
    except BillingError as e:
        if e.code:
            return _refusal(e)  # 409 payment_not_configured: no adapter, a paid plan (security review N8)
        raise _err(e) from e


@router.post("/subscription/cancel", status_code=204)
def cancel(p: Principal = Depends(require("billing:subscription:manage")), db: Session = Depends(get_db)):
    try:
        service.cancel(db, organisation_id=p.organisation_id)
    except BillingError as e:
        raise _err(e) from e


@router.post("/webhooks/payment", status_code=204)
async def payment_webhook(request: Request, db: Session = Depends(get_db)):
    """The payment adapter's server-to-server notification (payment-sbiepay's PaymentNotification). Security
    review N7: it takes no token, so it is trusted only when signed: HMAC-SHA256 of the raw body with
    BILLING_PAYMENT_WEBHOOK_SECRET, hex, in X-Payment-Signature, compared in constant time. With no adapter
    configured there is nothing to notify and the route answers 404; with no secret it refuses everything (503).
    Only a succeeded payment for billing activates the pending upgrade, and only for the plan's amount."""
    if settings.payment_adapter == "none":
        raise HTTPException(404, "Not Found")
    secret = config.payment_webhook_secret()
    if not secret:
        raise HTTPException(503, "BILLING_PAYMENT_WEBHOOK_SECRET is not set: payment notifications cannot be verified")
    raw = await request.body()
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, request.headers.get(SIGNATURE_HEADER, "")):
        raise HTTPException(401, "invalid payment notification signature")
    try:
        body = json.loads(raw)
    except ValueError as e:
        raise HTTPException(400, "the notification is not JSON") from e
    if not isinstance(body, dict):
        raise HTTPException(400, "the notification is not a JSON object")
    source = body.get("source_module")
    if source not in (None, "billing") or body.get("status", "succeeded") != "succeeded":
        return Response(status_code=204)  # another module's payment, or not a success: nothing to activate
    reference = body.get("source_reference") if source == "billing" else body.get("reference")
    try:
        await run_in_threadpool(_confirm, db, str(reference or ""), body.get("amount"), body.get("organisation_id"))
    except BillingError as e:
        if e.code:
            return _refusal(e)
        raise _err(e) from e
    return Response(status_code=204)


def _confirm(db: Session, reference: str, amount, organisation_id) -> None:
    service.confirm_payment(db, reference=reference, amount=amount, organisation_id=organisation_id)


@router.get("/admin/reports/subscriptions")
def admin_subscription_report(p: Principal = Depends(require("platform:revenue:read")), db: Session = Depends(get_db)):
    """Super admin: subscriptions per plan and status, monthly recurring revenue, paid in the last 30 days, and
    trials ending in the next 14 days (application/reports.py)."""
    return subscription_report(db)


@router.get("/admin/plans")
def admin_plans(p: Principal = Depends(require("platform:plans:manage")), db: Session = Depends(get_db)):
    return service.list_plans(db, include_unpublished=True)


@router.put("/admin/plans/{plan_id}")
def admin_put_plan(
    plan_id: str,
    body: PlanBody,
    p: Principal = Depends(require("platform:plans:manage")),
    db: Session = Depends(get_db),
):
    from ..domain.models import Plan

    plan = db.get(Plan, plan_id) or Plan(id=plan_id)
    for k, v in body.model_dump().items():
        if k == "id":
            continue
        setattr(plan, k, str(v) if k == "specialized_suites" else v)
    plan.limits = body.limits.stored()
    db.add(plan)
    db.commit()
    return plan.to_dict()


@router.put("/admin/subscriptions/{org_id}")
def admin_subscription(
    org_id: str,
    body: AdminSet,
    p: Principal = Depends(require("platform:subscriptions:manage")),
    db: Session = Depends(get_db),
):
    try:
        return service.admin_set(
            db,
            organisation_id=org_id,
            plan_id=body.plan,
            trial_ends_at=body.trial_ends_at,
            comped_until=body.comped_until,
            reason=body.reason,
        ).to_dict()
    except BillingError as e:
        raise _err(e) from e
