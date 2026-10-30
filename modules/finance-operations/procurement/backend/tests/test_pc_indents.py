"""Indents: raise, edit, submit; approval checks budget-grants GET /availability with the approver's token and sets the
purchase method; the requester never decides (R1, R2, M1, D1)."""

from decimal import Decimal

from pc_support import BASE, BUDGET_URL, indent, outbox


def submitted(client, org, cost="1000.00", who="faculty", **fields):
    i = indent(client, org, cost, who, **fields)
    assert client.post(f"{BASE}/indents/{i['id']}/submit", headers=org.headers[who]).status_code == 200
    return i


def decide(client, org, i, decision="approved", who="manager", **extra):
    return client.post(
        f"{BASE}/indents/{i['id']}/decision", json={"decision": decision, **extra}, headers=org.headers[who]
    )


def test_raise_edit_and_submit_an_indent(client, org):
    i = indent(client, org, "1200.50", needed_by="2026-11-30", justification="Practical classes")
    assert i["status"] == "draft" and i["number"].startswith("IND-") and i["requested_by"] == org.ids["faculty"]
    assert i["estimated_cost"] == "1200.50" and i["items"][0]["quantity"] == 10 and "unit_price" not in i["items"][0]
    body = {"title": "Glassware, revised", "line_id": org.line, "items": i["items"], "estimated_cost": "900"}
    r = client.put(f"{BASE}/indents/{i['id']}", json=body, headers=org.faculty)
    assert r.status_code == 200 and r.json()["estimated_cost"] == "900.00" and r.json()["title"] == "Glassware, revised"
    assert client.put(f"{BASE}/indents/{i['id']}", json=body, headers=org.research).status_code == 403
    r = client.post(f"{BASE}/indents/{i['id']}/submit", headers=org.faculty)
    assert r.status_code == 200 and r.json()["status"] == "submitted"
    assert client.put(f"{BASE}/indents/{i['id']}", json=body, headers=org.faculty).status_code == 409
    event = [e for e in outbox("procurement.indent.submitted", org.id) if e["indent_id"] == i["id"]]
    assert event == [
        {
            "organisation_id": org.id,
            "indent_id": i["id"],
            "number": i["number"],
            "requested_by": org.ids["faculty"],
            "department_id": None,
            "estimated_cost": "900.00",
        }
    ]
    mine = client.get(f"{BASE}/me/indents", headers=org.faculty).json()
    assert [x["id"] for x in mine] == [i["id"]]
    assert client.get(f"{BASE}/me/indents", headers=org.research).json() == []


def test_approval_checks_the_budget_with_the_approvers_token(client, org, budget):
    i = submitted(client, org, "60000.00")
    r = decide(client, org, i)
    assert r.status_code == 200, r.text
    approved = r.json()
    assert approved["status"] == "approved" and approved["purchase_method"] == "quotation"
    assert approved["decided_by"] == org.ids["manager"]
    req = budget.requests[-1]
    assert str(req.url).startswith(f"{BUDGET_URL}/availability")
    assert req.url.params["line_id"] == org.line and req.url.params["amount"] == "60000.00"
    assert req.headers["authorization"] == f"Bearer {org.token('manager')}"
    event = [e for e in outbox("procurement.indent.approved", org.id) if e["indent_id"] == i["id"]]
    assert event[0]["line_id"] == org.line and event[0]["purchase_method"] == "quotation"
    assert event[0]["estimated_cost"] == "60000.00"
    # a department admin may decide too; the method follows the value
    j = submitted(client, org, "40000.00")
    assert decide(client, org, j, who="dept").json()["purchase_method"] == "direct"
    k = submitted(client, org, "600000.00")
    assert decide(client, org, k).json()["purchase_method"] == "tender"


def test_a_line_that_cannot_cover_the_cost_is_refused(client, org, budget):
    i = submitted(client, org, "5000.00")
    budget.available[org.line] = Decimal("4999.99")
    r = decide(client, org, i)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "insufficient_budget"
    assert "4999.99" in r.json()["detail"]["message"]
    budget.missing.add(org.line)
    r = decide(client, org, i)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "insufficient_budget"
    assert client.get(f"{BASE}/indents/{i['id']}", headers=org.manager).json()["status"] == "submitted"
    # returning or rejecting needs no budget check
    calls = len(budget.requests)
    assert decide(client, org, i, "returned", note="split it").json()["status"] == "returned"
    assert len(budget.requests) == calls


def test_budget_check_unavailable_decides_nothing(client, org, budget, monkeypatch):
    i = submitted(client, org)
    budget.status = 403  # e.g. the approver's role lacks budget-grants:availability:read
    r = decide(client, org, i)
    assert r.status_code == 503 and r.json()["detail"]["code"] == "budget_check_unavailable"
    budget.status, budget.down = None, True
    assert decide(client, org, i).status_code == 503
    budget.down = False
    monkeypatch.delenv("PROCUREMENT_BUDGET_GRANTS_URL")
    r = decide(client, org, i)
    assert r.status_code == 503 and "PROCUREMENT_BUDGET_GRANTS_URL" in r.json()["detail"]["message"]
    assert client.get(f"{BASE}/indents/{i['id']}", headers=org.manager).json()["status"] == "submitted"


def test_no_method_is_guessed_without_purchase_limits(client, org, budget, monkeypatch):
    i = submitted(client, org)
    monkeypatch.delenv("PROCUREMENT_QUOTATION_LIMIT")
    calls = len(budget.requests)
    r = decide(client, org, i)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "purchase_limits_not_configured"
    assert len(budget.requests) == calls  # refused before budget-grants is asked


def test_the_requester_never_decides_and_states_are_enforced(client, org):
    i = submitted(client, org, who="dept")  # a department admin raising their own indent
    r = decide(client, org, i, who="dept")
    assert r.status_code == 403
    assert decide(client, org, i, who="faculty").status_code == 403  # no indent:approve
    draft = indent(client, org)
    assert decide(client, org, draft).status_code == 409
    r = decide(client, org, i, "rejected", note="not needed this term")
    assert r.json()["status"] == "rejected" and r.json()["note"] == "not needed this term"
    assert decide(client, org, i).status_code == 409
    event = [e for e in outbox("procurement.indent.rejected", org.id) if e["indent_id"] == i["id"]]
    assert event[0]["note"] == "not needed this term" and event[0]["requested_by"] == org.ids["dept"]


def test_returned_indents_are_edited_and_resubmitted(client, org):
    i = submitted(client, org)
    decide(client, org, i, "returned", note="add specifications")
    body = {
        "title": "Glassware",
        "line_id": org.line,
        "items": [{"description": "Beaker", "specification": "Borosilicate", "quantity": 5, "unit": "nos"}],
        "estimated_cost": "500",
    }
    assert client.put(f"{BASE}/indents/{i['id']}", json=body, headers=org.faculty).status_code == 200
    r = client.post(f"{BASE}/indents/{i['id']}/submit", headers=org.faculty)
    assert r.json()["status"] == "submitted" and r.json()["note"] is None
    assert decide(client, org, i).json()["status"] == "approved"


def test_who_can_see_indents(client, org):
    i = indent(client, org)
    assert client.get(f"{BASE}/indents/{i['id']}", headers=org.faculty).status_code == 200
    assert client.get(f"{BASE}/indents/{i['id']}", headers=org.research).status_code == 403
    assert client.get(f"{BASE}/indents/{i['id']}", headers=org.manager).status_code == 200
    assert client.get(f"{BASE}/indents", headers=org.faculty).status_code == 403
    listed = client.get(f"{BASE}/indents?status=draft", headers=org.dept).json()["items"]
    assert i["id"] in {x["id"] for x in listed}
    assert client.get(f"{BASE}/indents/nope", headers=org.manager).status_code == 404


def test_indent_input_is_validated(client, org):
    base = {"title": "x", "line_id": org.line, "items": [{"description": "a", "quantity": 1, "unit": "nos"}]}
    for body in (
        {**base, "estimated_cost": "0"},
        {**base, "estimated_cost": "1.234"},
        {**base, "estimated_cost": "10", "items": []},
        {**base, "estimated_cost": "10", "items": [{"description": "a", "quantity": 0, "unit": "nos"}]},
        {**base, "estimated_cost": "10", "items": [{"description": "a", "quantity": 1.0001, "unit": "nos"}]},
    ):
        assert client.post(f"{BASE}/indents", json=body, headers=org.faculty).status_code == 422, body
    assert client.post(f"{BASE}/indents", json={**base, "estimated_cost": "10"}, headers=org.admin).status_code == 403
