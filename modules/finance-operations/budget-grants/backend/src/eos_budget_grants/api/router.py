"""HTTP surface of contracts/openapi.yaml. The host app mounts `router` under /api/v1/budget-grants. Handlers only map
HTTP to the application layer; errors render as {"detail": {"code", "message", "field"?}}."""

from __future__ import annotations

from datetime import date

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..application import access as p
from ..application import reports, service
from ..application.access import Actor
from ..application.errors import BudgetError
from . import schemas as s
from .deps import current_actor, require

router = APIRouter(tags=["budget-grants"])


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except BudgetError as e:
        raise HTTPException(e.status, e.body()) from e


def _head(body: s.BudgetHeadInput) -> dict:
    return {k: v for k, v in s.dump(body).items() if k not in ("id", "organisation_id")}


# ---------------------------------------------------------------- budget heads and budgets


@router.get("/budget-heads")
def list_heads(a: Actor = Depends(require(p.BUDGET_READ)), db: Session = Depends(get_db)):
    return _run(service.list_heads, db)


@router.post("/budget-heads", status_code=201)
def create_head(body: s.BudgetHeadInput, a: Actor = Depends(require(p.BUDGET_MANAGE)), db: Session = Depends(get_db)):
    return _run(service.create_head, db, a, _head(body))


@router.put("/budget-heads/{head_id}")
def update_head(
    head_id: str, body: s.BudgetHeadInput, a: Actor = Depends(require(p.BUDGET_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.update_head, db, a, head_id, _head(body))


@router.get("/budgets")
def list_budgets(
    financial_year: str | None = None,
    department_id: str | None = None,
    status: str | None = Query(default=None, pattern="^(draft|submitted|returned|approved|closed)$"),
    a: Actor = Depends(require(p.BUDGET_READ)),
    db: Session = Depends(get_db),
):
    return _run(service.list_budgets, db, financial_year, department_id, status)


@router.post("/budgets", status_code=201)
def create_budget(body: s.BudgetInput, a: Actor = Depends(require(p.BUDGET_MANAGE)), db: Session = Depends(get_db)):
    return _run(service.create_budget, db, a, s.dump(body))


@router.get("/budgets/{budget_id}")
def get_budget(budget_id: str, a: Actor = Depends(require(p.BUDGET_READ)), db: Session = Depends(get_db)):
    return _run(service.get_budget, db, budget_id)


@router.put("/budgets/{budget_id}")
def update_budget(
    budget_id: str, body: s.BudgetInput, a: Actor = Depends(require(p.BUDGET_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.update_budget, db, a, budget_id, s.dump(body))


@router.post("/budgets/{budget_id}/submit")
def submit_budget(budget_id: str, a: Actor = Depends(require(p.BUDGET_MANAGE)), db: Session = Depends(get_db)):
    return _run(service.submit_budget, db, a, budget_id)


@router.post("/budgets/{budget_id}/decision")
def decide_budget(
    budget_id: str, body: s.Decision, a: Actor = Depends(require(p.BUDGET_APPROVE)), db: Session = Depends(get_db)
):
    return _run(service.decide_budget, db, a, budget_id, body.decision, body.note)


# ---------------------------------------------------------------- reappropriations, availability, lines, spend


@router.get("/reappropriations")
def list_reappropriations(
    status: str | None = Query(default=None, pattern="^(requested|approved|rejected)$"),
    a: Actor = Depends(require(p.BUDGET_READ)),
    db: Session = Depends(get_db),
):
    return _run(service.list_reappropriations, db, status)


@router.post("/reappropriations", status_code=201)
def request_reappropriation(
    body: s.ReappropriationInput, a: Actor = Depends(require(p.BUDGET_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.request_reappropriation, db, a, s.dump(body))


@router.post("/reappropriations/{reappropriation_id}/decision")
def decide_reappropriation(
    reappropriation_id: str,
    body: s.Decision,
    a: Actor = Depends(require(p.BUDGET_APPROVE)),
    db: Session = Depends(get_db),
):
    return _run(service.decide_reappropriation, db, a, reappropriation_id, body.decision, body.note)


@router.get("/availability")
def availability(
    line_id: str,
    amount: str = Query(pattern=s.MONEY),
    a: Actor = Depends(require(p.AVAILABILITY_READ)),
    db: Session = Depends(get_db),
):
    return _run(service.availability, db, line_id, amount)


@router.get("/lines")
def list_lines(
    financial_year: str | None = None,
    department_id: str | None = None,
    q: str | None = None,
    a: Actor = Depends(require(p.AVAILABILITY_READ)),
    db: Session = Depends(get_db),
):
    return _run(service.list_lines, db, financial_year, department_id, q)


@router.get("/expenditures")
def list_expenditures(
    line_id: str | None = None,
    kind: str | None = Query(default=None, pattern="^(commitment|actual)$"),
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    a: Actor = Depends(require(p.BUDGET_READ)),
    db: Session = Depends(get_db),
):
    filters = {"line_id": line_id, "kind": kind, "from": from_, "to": to}
    return _run(service.list_expenditures, db, filters, cursor, limit)


@router.post("/expenditures", status_code=201)
def record_expenditure(
    body: s.ExpenditureInput, a: Actor = Depends(require(p.EXPENDITURE_RECORD)), db: Session = Depends(get_db)
):
    return _run(service.record_manual_expenditure, db, a, s.dump(body))


@router.post("/expenditures/{expenditure_id}/reverse")
def reverse_expenditure(
    expenditure_id: str,
    body: s.Reason,
    a: Actor = Depends(require(p.EXPENDITURE_RECORD)),
    db: Session = Depends(get_db),
):
    return _run(service.reverse_expenditure, db, a, expenditure_id, body.reason)


# ---------------------------------------------------------------- grants and certificates


@router.get("/grants")
def list_grants(
    status: str | None = Query(default=None, pattern="^(active|closed)$"),
    funder: str | None = None,
    principal_investigator_id: str | None = None,
    a: Actor = Depends(require(p.GRANT_READ)),
    db: Session = Depends(get_db),
):
    return _run(service.list_grants, db, status, funder, principal_investigator_id)


@router.post("/grants", status_code=201)
def create_grant(body: s.GrantInput, a: Actor = Depends(require(p.GRANT_MANAGE)), db: Session = Depends(get_db)):
    return _run(service.create_grant, db, a, s.dump(body))


@router.get("/grants/{grant_id}")
def get_grant(grant_id: str, a: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    return _run(service.get_grant, db, a, grant_id)


@router.put("/grants/{grant_id}")
def update_grant(
    grant_id: str, body: s.GrantInput, a: Actor = Depends(require(p.GRANT_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.update_grant, db, a, grant_id, s.dump(body))


@router.post("/grants/{grant_id}/funds-received", status_code=201)
def funds_received(
    grant_id: str,
    body: s.FundsReceivedInput,
    a: Actor = Depends(require(p.GRANT_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.funds_received, db, a, grant_id, s.dump(body))


@router.post("/grants/{grant_id}/close")
def close_grant(
    grant_id: str, body: s.CloseInput, a: Actor = Depends(require(p.GRANT_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.close_grant, db, a, grant_id, body.unspent_action, body.note)


@router.get("/grants/{grant_id}/utilisation-certificates")
def list_certificates(grant_id: str, a: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    return _run(service.list_certificates, db, a, grant_id)


@router.post("/grants/{grant_id}/utilisation-certificates", status_code=201)
def draft_certificate(
    grant_id: str, body: s.CertificateInput, a: Actor = Depends(require(p.GRANT_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.draft_certificate, db, a, grant_id, body.period_from, body.period_to)


@router.post("/utilisation-certificates/{certificate_id}/decision")
def decide_certificate(
    certificate_id: str,
    body: s.Decision,
    a: Actor = Depends(require(p.UTILISATION_APPROVE)),
    db: Session = Depends(get_db),
):
    return _run(service.decide_certificate, db, a, certificate_id, body.decision, body.note)


@router.post("/utilisation-certificates/{certificate_id}/mark-submitted")
def mark_submitted(
    certificate_id: str,
    body: s.SubmittedInput | None = None,
    a: Actor = Depends(require(p.GRANT_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.mark_certificate_submitted, db, a, certificate_id, s.dump(body) if body else {})


@router.get("/me/grants")
def my_grants(a: Actor = Depends(require(p.SELF_READ)), db: Session = Depends(get_db)):
    return _run(service.my_grants, db, a)


@router.get("/reports/budget-vs-spend")
def budget_vs_spend(
    financial_year: str | None = None,
    department_id: str | None = None,
    scope: str = Query(default="all", pattern="^(all|budgets|grants)$"),
    a: Actor = Depends(require(p.REPORT_READ)),
    db: Session = Depends(get_db),
):
    return _run(reports.budget_vs_spend, db, financial_year, department_id, scope)
