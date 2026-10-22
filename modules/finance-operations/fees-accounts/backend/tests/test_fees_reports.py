"""The reports behind the widgets and collection targets (F11, F12, M2)."""

from fees_support import BASE, TODAY, adhoc, head, invoice, pay_cash, published


def test_collections_today_by_mode_and_head(client, org):
    tuition, library = head(client, org, "TUI9"), head(client, org, "LIB9", "library")
    s = published(client, org, [tuition, library])  # instalment 1: 18000 tuition + 6000 library
    inv = invoice(client, org, structure=s)
    pay_cash(client, org, inv["id"], "12000.00")
    cheque = client.post(
        f"{BASE}/invoices/{inv['id']}/payments",
        json={"amount": "2000", "mode": "cheque", "paid_on": TODAY},
        headers=org.staff,
    ).json()
    pay_cash(client, org, adhoc(client, org, "300.00")["id"], "300.00", paid_on="2026-10-21")
    client.post(f"{BASE}/payments/{cheque['id']}/void", json={"reason": "bounced"}, headers=org.staff)
    r = client.get(f"{BASE}/reports/collections", headers=org.staff).json()
    assert r["date"] == TODAY and r["total"] == "12000.00" and r["count"] == 1
    assert r["previous_day_total"] == "300.00"
    assert r["by_mode"] == [{"mode": "cash", "amount": "12000.00", "count": 1}]
    heads = {h["name"]: h["amount"] for h in r["by_fee_head"]}
    assert heads == {"Tui9": "9000.00", "Lib9": "3000.00"}
    yesterday = client.get(f"{BASE}/reports/collections?date=2026-10-21", headers=org.staff).json()
    assert yesterday["total"] == "300.00"


def test_outstanding_with_ageing(client, org):
    adhoc(client, org, "100.00", due="2026-11-30", person="a")  # not due
    adhoc(client, org, "200.00", due="2026-10-10", person="b")  # 12 days late
    adhoc(client, org, "300.00", due="2026-07-01", person="b")  # 113 days late
    part = adhoc(client, org, "400.00", due="2026-09-15", person="c")  # 37 days late
    pay_cash(client, org, part["id"], "150.00")
    done = adhoc(client, org, "999.00", person="d")
    pay_cash(client, org, done["id"], "999.00")
    r = client.get(f"{BASE}/reports/outstanding", headers=org.staff).json()
    assert r["outstanding"] == "850.00" and r["overdue"] == "750.00" and r["people_with_dues"] == 3
    ageing = {a["bucket"]: (a["amount"], a["count"]) for a in r["ageing"]}
    assert ageing == {
        "not_due": ("100.00", 1),
        "0-30": ("200.00", 1),
        "31-60": ("250.00", 1),
        "61-90": ("0.00", 0),
        "90+": ("300.00", 1),
    }
    assert len(r["top_fee_heads"]) <= 5 and r["top_fee_heads"][0]["amount"] == "300.00"


def test_outstanding_by_programme(client, org):
    s = published(client, org, programme_id="prog-1")
    invoice(client, org, "p1", structure=s)
    adhoc(client, org, "50.00", person="p2")
    r = client.get(f"{BASE}/reports/outstanding?programme_id=prog-1", headers=org.staff).json()
    assert r["people_with_dues"] == 1 and r["outstanding"] == "18000.00"


def test_collection_vs_target(client, org):
    t = client.put(
        f"{BASE}/collection-targets",
        json={
            "academic_year": "2026-27",
            "targets": [{"period": "2026-10", "amount": "10000"}, {"period": "2026-11", "amount": "5000"}],
        },
        headers=org.manager,
    )
    assert t.status_code == 200 and len(t.json()) == 2
    pay_cash(client, org, adhoc(client, org, "4000.00")["id"], "4000.00")
    r = client.get(f"{BASE}/reports/collection-vs-target", headers=org.manager).json()
    assert r["academic_year"] == "2026-27" and r["target_total"] == "15000.00" and r["collected_total"] == "4000.00"
    periods = {p["period"]: (p["target"], p["collected"]) for p in r["periods"]}
    assert (
        len(periods) == 12
        and periods["2026-10"] == ("10000.00", "4000.00")
        and periods["2026-11"] == ("5000.00", "0.00")
    )
    # replacing the set for the year
    client.put(
        f"{BASE}/collection-targets",
        json={"academic_year": "2026-27", "targets": [{"period": "2026-12", "amount": "1"}]},
        headers=org.manager,
    )
    assert [
        x["period"] for x in client.get(f"{BASE}/collection-targets?academic_year=2026-27", headers=org.manager).json()
    ] == ["2026-12"]
    bad = client.put(
        f"{BASE}/collection-targets",
        json={"academic_year": "2026-27", "targets": [{"period": "2030-01", "amount": "1"}]},
        headers=org.manager,
    )
    assert bad.status_code == 422
    assert (
        client.put(
            f"{BASE}/collection-targets", json={"academic_year": "2026-27", "targets": []}, headers=org.staff
        ).status_code
        == 403
    )


def test_reports_need_report_read(client, org):
    for path in ("/reports/collections", "/reports/outstanding", "/reports/collection-vs-target"):
        assert client.get(f"{BASE}{path}", headers=org.student).status_code == 403
        assert client.get(f"{BASE}{path}", headers=org.admin).status_code == 200
