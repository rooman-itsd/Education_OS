from __future__ import annotations

from datetime import datetime

from eos_core.db import get_db
from eos_identity.api.deps import Principal, require
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..application import service
from ..application.service import BillingError

router = APIRouter(tags=["billing"])


def _err(e: BillingError):
    return HTTPException(e.status, str(e))


class Upgrade(BaseModel):
    plan: str
    billing_cycle: str = "monthly"


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
    limits: dict = {}
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


@router.get("/invoices")
def invoices(
    p: Principal = Depends(require("billing:subscription:read", organisation=True)), db: Session = Depends(get_db)
):
    """Invoices of the caller's organisation, newest first (one per paid period)."""
    return service.list_invoices(db, p.organisation_id)


@router.post("/subscription/upgrade", status_code=201)
def upgrade(
    body: Upgrade, p: Principal = Depends(require("billing:subscription:manage")), db: Session = Depends(get_db)
):
    try:
        return service.upgrade(
            db, organisation_id=p.organisation_id, plan_id=body.plan, billing_cycle=body.billing_cycle
        )
    except BillingError as e:
        raise _err(e) from e


@router.post("/subscription/cancel", status_code=204)
def cancel(p: Principal = Depends(require("billing:subscription:manage")), db: Session = Depends(get_db)):
    try:
        service.cancel(db, organisation_id=p.organisation_id)
    except BillingError as e:
        raise _err(e) from e


@router.post("/webhooks/payment", status_code=204)
def payment_webhook(body: dict, db: Session = Depends(get_db)):
    """Payment adapter callback. The adapter verifies the signature before calling this."""
    try:
        service.confirm_payment(db, reference=body.get("reference", ""))
    except BillingError as e:
        raise _err(e) from e


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
