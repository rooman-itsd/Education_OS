"""Business dates follow Asia/Kolkata (IST), as in procurement (decided on #129). 18:30 UTC is midnight in India."""

from datetime import UTC, datetime

from bg_support import BASE, approved_budget, head
from eos_budget_grants.application import consumers, service
from eos_core.db import SessionLocal


def _at(monkeypatch, moment):
    monkeypatch.setattr(service, "clock", lambda: moment)


def test_today_is_the_date_in_india(monkeypatch):
    _at(monkeypatch, datetime(2026, 10, 28, 18, 29, tzinfo=UTC))
    assert service.today().isoformat() == "2026-10-28"  # 23:59 IST
    _at(monkeypatch, datetime(2026, 10, 28, 18, 30, tzinfo=UTC))
    assert service.today().isoformat() == "2026-10-29"  # 00:00 IST, still the 28th in UTC


def test_the_default_financial_year_turns_at_ist_midnight(client, org, monkeypatch):
    _at(monkeypatch, datetime(2027, 3, 31, 18, 29, tzinfo=UTC))  # 23:59 IST on 31 March
    assert client.get(f"{BASE}/reports/budget-vs-spend", headers=org.staff).json()["financial_year"] == "2026-27"
    _at(monkeypatch, datetime(2027, 3, 31, 18, 30, tzinfo=UTC))  # 00:00 IST on 1 April, still 31 March in UTC
    assert client.get(f"{BASE}/reports/budget-vs-spend", headers=org.staff).json()["financial_year"] == "2027-28"


def test_a_commitment_from_an_event_is_dated_in_india(client, org, monkeypatch):
    b = approved_budget(client, org, {head(client, org)["id"]: "10000"}, year="2026-27")
    line = b["lines"][0]["id"]
    _at(monkeypatch, datetime(2026, 10, 28, 18, 30, tzinfo=UTC))
    issued = {"organisation_id": org.id, "purchase_order_id": "PO-IST", "line_id": line, "total": "100.00"}
    with SessionLocal() as db:
        assert consumers.handle(db, consumers.PO_ISSUED, issued)["result"] == "committed"
    entries = client.get(f"{BASE}/expenditures?line_id={line}", headers=org.staff).json()["items"]
    assert [e["date"] for e in entries] == ["2026-10-29"]
