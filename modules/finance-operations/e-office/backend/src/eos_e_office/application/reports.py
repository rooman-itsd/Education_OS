"""The pendency report: open files by age, holder and department. It counts every open file of the organisation,
confidential ones included, and shows no subject, so nothing confidential is revealed by it."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from ..domain import rules
from ..infrastructure.config import load_settings
from ..infrastructure.models import File
from . import service
from .service import _iso, _q, user_ref


def pendency(db: Session, department_id: str | None) -> dict:
    """Age is whole days since the holder received the file, by Indian business dates. Holders are listed with the
    most overdue first, then the most open; departments with the most open first (no department last)."""
    q = _q(db, File).where(File.status == "open")
    if department_id:
        q = q.where(File.department_id == department_id)
    rows = list(db.scalars(q.order_by(File.held_since, File.number)))
    today, days = service.business_today(), load_settings().default_due_days
    by_age = {name: 0 for name, _, _ in rules.AGE_BUCKETS}
    holders: dict[str, dict] = {}
    departments: dict[str | None, dict] = defaultdict(lambda: {"open": 0, "overdue": 0})
    overdue_total = 0
    for f in rows:
        overdue = service._overdue(f, today, days)
        overdue_total += overdue
        by_age[rules.age_bucket((today - service.business_date(f.held_since)).days)] += 1
        h = holders.setdefault(f.holder_id, {"open": 0, "overdue": 0, "oldest": f.held_since})
        h["open"] += 1
        h["overdue"] += overdue
        dep = departments[f.department_id]
        dep["open"] += 1
        dep["overdue"] += overdue
    return {
        "open_files": len(rows),
        "overdue": overdue_total,
        "by_age": [{"bucket": name, "count": count} for name, count in by_age.items()],
        "by_holder": [
            {
                "holder": user_ref(holder_id),
                "open": h["open"],
                "overdue": h["overdue"],
                "oldest_held_since": _iso(h["oldest"]),
            }
            for holder_id, h in sorted(holders.items(), key=lambda kv: (-kv[1]["overdue"], -kv[1]["open"], kv[0]))
        ],
        "by_department": [
            {"department_id": dep_id, **counts}
            for dep_id, counts in sorted(
                departments.items(), key=lambda kv: (kv[0] is None, -kv[1]["open"], kv[0] or "")
            )
        ],
    }
