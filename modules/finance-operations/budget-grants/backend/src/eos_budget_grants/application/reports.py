"""The budget-vs-spend report behind the Finance Staff and Research Office widget."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import ZERO, money
from ..infrastructure.config import load_settings
from ..infrastructure.models import Budget, Grant, Line
from . import service
from .service import _q


def budget_vs_spend(db: Session, financial_year: str | None, department_id: str | None, scope: str) -> dict:
    """Allocated, committed and spent per budget head: approved budgets of the year (scope budgets), lines of active
    grants (scope grants), or both (all). Grant totals are always the active grants."""
    start_month = load_settings().financial_year_start_month
    year = financial_year or rules.financial_year_of(service.today(), start_month)
    service._rule(rules.financial_year_bounds, year, start_month)
    lines: list[Line] = []
    if scope in ("all", "budgets"):
        bq = _q(db, Budget).where(Budget.financial_year == year, Budget.status.in_(("approved", "closed")))
        if department_id:
            bq = bq.where(Budget.department_id == department_id)
        for b in db.scalars(bq):
            lines += service._lines_of(db, budget_id=b.id)
    gq = _q(db, Grant).where(Grant.status == "active")
    if department_id:
        gq = gq.where(Grant.department_id == department_id)
    grants = list(db.scalars(gq))
    grant_lines = [x for g in grants for x in service._lines_of(db, grant_id=g.id)]
    if scope in ("all", "grants"):
        lines += grant_lines
    totals = service.line_totals(db, [x.id for x in lines + grant_lines])
    heads = service._heads(db)
    by_head: dict[str, list[Decimal]] = defaultdict(lambda: [ZERO, ZERO, ZERO])
    for x in lines:
        committed, spent = totals[x.id]
        row = by_head[x.budget_head_id]
        row[0] += Decimal(x.allocated)
        row[1] += committed
        row[2] += spent
    ranked = sorted(by_head.items(), key=lambda kv: (-kv[1][0], heads[kv[0]].name if kv[0] in heads else ""))
    soon = service.today() + timedelta(days=30)
    return {
        "financial_year": year,
        "allocated": money(sum((r[0] for r in by_head.values()), ZERO)),
        "committed": money(sum((r[1] for r in by_head.values()), ZERO)),
        "spent": money(sum((r[2] for r in by_head.values()), ZERO)),
        "by_head": [
            {
                "budget_head_id": head_id,
                "name": heads[head_id].name if head_id in heads else "",
                "allocated": money(r[0]),
                "committed": money(r[1]),
                "spent": money(r[2]),
            }
            for head_id, r in ranked
        ],
        "grants": {
            "active": len(grants),
            "sanctioned": money(sum((Decimal(g.sanctioned_amount) for g in grants), ZERO)),
            "spent": money(sum((totals[x.id][1] for x in grant_lines), ZERO)),
            "ucs_due_30_days": sum(
                1 for g in grants if (d := service.grant_next_uc_due(db, g)) is not None and d <= soon
            ),
        },
    }
