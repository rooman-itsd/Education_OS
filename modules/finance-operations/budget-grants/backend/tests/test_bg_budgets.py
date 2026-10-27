"""Budget heads, budgets, approval, reappropriation, availability, lines and manual spend (F1-F5, F7, M1, M2, X1)."""

from bg_support import BASE, TODAY, YEAR, approved_budget, head, outbox


def test_budget_heads(client, org):
    h = head(client, org, "EQUIP", "Equipment")
    assert h["kind"] == "recurring" and h["organisation_id"] == org.id
    dup = client.post(f"{BASE}/budget-heads", json={"code": "EQUIP", "name": "x"}, headers=org.staff)
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "code_taken"
    r = client.put(
        f"{BASE}/budget-heads/{h['id']}",
        json={"code": "EQUIP", "name": "Equipment", "kind": "non_recurring", "active": False},
        headers=org.staff,
    )
    assert r.json()["kind"] == "non_recurring" and not r.json()["active"]
    assert client.post(f"{BASE}/budget-heads", json={"code": "E", "name": "x"}, headers=org.staff).status_code == 422
    assert client.get(f"{BASE}/budget-heads", headers=org.scholar).status_code == 403


def test_budget_lifecycle_and_separation_of_duties(client, org):
    h = head(client, org)
    body = {"financial_year": YEAR, "title": "Institution", "lines": [{"budget_head_id": h["id"], "allocated": "1000"}]}
    b = client.post(f"{BASE}/budgets", json=body, headers=org.staff).json()
    assert b["status"] == "draft" and b["allocated_total"] == "1000.00" and b["lines"][0]["available"] == "1000.00"
    assert client.post(f"{BASE}/budgets", json=body, headers=org.staff).status_code == 409
    edited = client.put(
        f"{BASE}/budgets/{b['id']}",
        json={**body, "lines": [{"budget_head_id": h["id"], "allocated": "1500"}]},
        headers=org.staff,
    )
    assert edited.json()["allocated_total"] == "1500.00"
    client.post(f"{BASE}/budgets/{b['id']}/submit", headers=org.staff)
    assert client.put(f"{BASE}/budgets/{b['id']}", json=body, headers=org.staff).status_code == 409
    returned = client.post(
        f"{BASE}/budgets/{b['id']}/decision", json={"decision": "returned", "note": "split it"}, headers=org.manager
    )
    assert returned.json()["status"] == "returned"
    client.post(f"{BASE}/budgets/{b['id']}/submit", headers=org.staff)
    assert (
        client.post(
            f"{BASE}/budgets/{b['id']}/decision", json={"decision": "rejected"}, headers=org.manager
        ).status_code
        == 422
    )
    ok = client.post(f"{BASE}/budgets/{b['id']}/decision", json={"decision": "approved"}, headers=org.manager)
    assert ok.json()["status"] == "approved" and ok.json()["approved_by"] == org.ids["manager"]
    assert [
        e["allocated_total"] for e in outbox("budget-grants.budget.approved", org.id) if e["budget_id"] == b["id"]
    ] == ["1500.00"]
    assert (
        client.post(
            f"{BASE}/budgets/{b['id']}/decision", json={"decision": "approved"}, headers=org.manager
        ).status_code
        == 409
    )


def test_preparer_cannot_approve(client, org):
    from bg_support import auth
    from eos_core.security import create_token

    both = auth(create_token(user_id=org.ids["staff"], organisation_id=org.id, roles=["finance-staff", "management"]))
    h = head(client, org)
    b = client.post(
        f"{BASE}/budgets",
        json={"financial_year": "2027-28", "lines": [{"budget_head_id": h["id"], "allocated": "1"}]},
        headers=org.staff,
    ).json()
    client.post(f"{BASE}/budgets/{b['id']}/submit", headers=org.staff)
    assert (
        client.post(f"{BASE}/budgets/{b['id']}/decision", json={"decision": "approved"}, headers=both).status_code
        == 403
    )


def test_budget_validation(client, org):
    h = head(client, org)
    twice = {
        "financial_year": "2028-29",
        "lines": [{"budget_head_id": h["id"], "allocated": "1"}, {"budget_head_id": h["id"], "allocated": "2"}],
    }
    assert (
        client.post(f"{BASE}/budgets", json=twice, headers=org.staff).json()["detail"]["code"]
        == "duplicate_budget_head"
    )
    unknown = {"financial_year": "2028-29", "lines": [{"budget_head_id": "nope", "allocated": "1"}]}
    assert client.post(f"{BASE}/budgets", json=unknown, headers=org.staff).status_code == 422


def test_availability_and_lines_for_procurement(client, org):
    h = head(client, org, name="Consumables")
    b = approved_budget(client, org, {h["id"]: "50000"})
    line = b["lines"][0]["id"]
    ok = client.get(f"{BASE}/availability?line_id={line}&amount=50000", headers=org.faculty).json()
    assert ok == {"line_id": line, "available": "50000.00", "sufficient": True}
    assert (
        client.get(f"{BASE}/availability?line_id={line}&amount=50000.01", headers=org.faculty).json()["sufficient"]
        is False
    )
    assert client.get(f"{BASE}/availability?line_id=nope&amount=1", headers=org.faculty).status_code == 404
    lines = client.get(f"{BASE}/lines?financial_year={YEAR}&q=consum", headers=org.faculty).json()
    assert [x["line_id"] for x in lines] == [line] and lines[0]["kind"] == "budget"
    assert client.get(f"{BASE}/lines", headers=org.scholar).status_code == 403


def test_draft_lines_are_not_open(client, org):
    h = head(client, org)
    b = client.post(
        f"{BASE}/budgets",
        json={"financial_year": "2029-30", "lines": [{"budget_head_id": h["id"], "allocated": "10"}]},
        headers=org.staff,
    ).json()
    assert (
        client.get(f"{BASE}/availability?line_id={b['lines'][0]['id']}&amount=1", headers=org.staff).status_code == 404
    )


def test_manual_spend_never_exceeds_available_and_is_reversed_not_deleted(client, org):
    b = approved_budget(client, org, {head(client, org)["id"]: "1000"})
    line = b["lines"][0]["id"]
    too_much = client.post(
        f"{BASE}/expenditures",
        json={"line_id": line, "amount": "1000.01", "date": TODAY, "description": "Travel"},
        headers=org.staff,
    )
    assert too_much.status_code == 422 and too_much.json()["detail"]["code"] == "exceeds_available"
    e = client.post(
        f"{BASE}/expenditures",
        json={"line_id": line, "amount": "850", "date": TODAY, "description": "Travel"},
        headers=org.staff,
    ).json()
    assert e["kind"] == "actual" and e["source"] == {"module": "manual", "reference": ""}
    assert [x["percent"] for x in outbox("budget-grants.line.threshold-reached", org.id) if x["line_id"] == line] == [
        80
    ]
    assert client.get(f"{BASE}/budgets/{b['id']}", headers=org.staff).json()["lines"][0]["available"] == "150.00"
    r = client.post(f"{BASE}/expenditures/{e['id']}/reverse", json={"reason": "wrong line"}, headers=org.staff)
    assert r.json()["reversed"]
    assert (
        client.post(f"{BASE}/expenditures/{e['id']}/reverse", json={"reason": "again"}, headers=org.staff).status_code
        == 409
    )
    assert client.get(f"{BASE}/budgets/{b['id']}", headers=org.staff).json()["lines"][0]["available"] == "1000.00"
    listed = client.get(f"{BASE}/expenditures?line_id={line}&kind=actual", headers=org.staff).json()["items"]
    assert [x["id"] for x in listed] == [e["id"]]  # still there, marked reversed


def test_threshold_is_published_once(client, org):
    b = approved_budget(client, org, {head(client, org)["id"]: "100"})
    line = b["lines"][0]["id"]
    for amount in ("80", "5", "15"):
        client.post(
            f"{BASE}/expenditures",
            json={"line_id": line, "amount": amount, "date": TODAY, "description": "x"},
            headers=org.staff,
        )
    assert [x["percent"] for x in outbox("budget-grants.line.threshold-reached", org.id) if x["line_id"] == line] == [
        80,
        100,
    ]


def test_reappropriation(client, org):
    h1, h2 = head(client, org), head(client, org)
    b = approved_budget(client, org, {h1["id"]: "1000", h2["id"]: "500"}, year="2030-31")
    by_head = {x["budget_head_id"]: x["id"] for x in b["lines"]}
    src, dst = by_head[h1["id"]], by_head[h2["id"]]
    too_much = client.post(
        f"{BASE}/reappropriations",
        json={"from_line_id": src, "to_line_id": dst, "amount": "1000.01", "reason": "x"},
        headers=org.staff,
    )
    assert too_much.status_code == 422
    r = client.post(
        f"{BASE}/reappropriations",
        json={"from_line_id": src, "to_line_id": dst, "amount": "300", "reason": "more lab work"},
        headers=org.staff,
    ).json()
    assert r["status"] == "requested" and r["organisation_id"] == org.id
    assert (
        client.post(
            f"{BASE}/reappropriations/{r['id']}/decision", json={"decision": "returned"}, headers=org.manager
        ).status_code
        == 422
    )
    ok = client.post(f"{BASE}/reappropriations/{r['id']}/decision", json={"decision": "approved"}, headers=org.manager)
    assert ok.json()["status"] == "approved"
    lines = {
        x["id"]: x["allocated"] for x in client.get(f"{BASE}/budgets/{b['id']}", headers=org.staff).json()["lines"]
    }
    assert lines == {src: "700.00", dst: "800.00"}
    assert [
        e["amount"]
        for e in outbox("budget-grants.reappropriation.approved", org.id)
        if e["reappropriation_id"] == r["id"]
    ] == ["300.00"]
    other = approved_budget(client, org, {head(client, org)["id"]: "10"}, year="2031-32")
    cross = client.post(
        f"{BASE}/reappropriations",
        json={"from_line_id": src, "to_line_id": other["lines"][0]["id"], "amount": "1", "reason": "x"},
        headers=org.staff,
    )
    assert cross.status_code == 422 and cross.json()["detail"]["code"] == "different_budgets"
    assert client.get(f"{BASE}/reappropriations?status=approved", headers=org.staff).json()[0]["id"] == r["id"]
