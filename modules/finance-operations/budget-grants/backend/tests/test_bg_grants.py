"""Grants, funds received, certificates, closing and my grants (R1-R3, R5, M3, I1, I2)."""

from bg_support import BASE, TODAY, grant, head, outbox


def test_grant_sanction_and_investigator_access(client, org):
    g = grant(client, org)
    assert g["status"] == "active" and g["sanctioned_amount"] == "500000.00" and g["organisation_id"] == org.id
    assert len(g["lines"]) == 2 and g["next_uc_due"] == "2027-03-31" and g["balance"] == "0.00"
    [event] = [e for e in outbox("budget-grants.grant.sanctioned", org.id) if e["grant_id"] == g["id"]]
    assert event["principal_investigator_id"] == org.ids["faculty"] and event["funder"] == "DST"
    assert client.get(f"{BASE}/grants/{g['id']}", headers=org.faculty).status_code == 200  # an investigator
    assert client.get(f"{BASE}/grants/{g['id']}", headers=org.scholar).status_code == 200  # co-investigator
    assert client.get(f"{BASE}/grants/{g['id']}", headers=org.dept).status_code == 404  # neither: not revealed
    assert client.get(f"{BASE}/grants", headers=org.faculty).status_code == 403


def test_grant_validation(client, org):
    h = head(client, org)
    base = {
        "code": "G-VAL",
        "title": "t",
        "funder": "f",
        "sanctioned_amount": "100",
        "start_date": "2026-04-01",
        "end_date": "2027-03-31",
        "investigators": [{"user_id": org.ids["faculty"], "role": "principal"}],
        "lines": [{"budget_head_id": h["id"], "sanctioned": "90"}],
    }
    r = client.post(f"{BASE}/grants", json=base, headers=org.research)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "lines_not_sanctioned_total"
    no_pi = {
        **base,
        "lines": [{"budget_head_id": h["id"], "sanctioned": "100"}],
        "investigators": [{"user_id": "x", "role": "co_investigator"}],
    }
    assert client.post(f"{BASE}/grants", json=no_pi, headers=org.research).json()["detail"]["code"] == "no_principal"
    backwards = {**base, "lines": [{"budget_head_id": h["id"], "sanctioned": "100"}], "end_date": "2026-01-01"}
    assert client.post(f"{BASE}/grants", json=backwards, headers=org.research).status_code == 422
    ok = {**base, "lines": [{"budget_head_id": h["id"], "sanctioned": "100"}]}
    assert client.post(f"{BASE}/grants", json=ok, headers=org.research).status_code == 201
    assert client.post(f"{BASE}/grants", json=ok, headers=org.research).status_code == 409


def test_revised_sanction_keeps_lines_with_spend(client, org):
    g = grant(client, org, amount="1000.00")
    line, other = g["lines"][0], g["lines"][1]
    client.post(
        f"{BASE}/expenditures",
        json={"line_id": line["id"], "amount": "100", "date": TODAY, "description": "x"},
        headers=org.staff,
    )
    body = {
        "code": g["code"],
        "title": "Revised",
        "funder": g["funder"],
        "sanctioned_amount": "1200.00",
        "start_date": g["start_date"],
        "end_date": g["end_date"],
        "investigators": [{"user_id": org.ids["faculty"], "role": "principal"}],
        "lines": [
            {"budget_head_id": line["budget_head_id"], "sanctioned": "700"},
            {"budget_head_id": other["budget_head_id"], "sanctioned": "500"},
        ],
    }
    r = client.put(f"{BASE}/grants/{g['id']}", json=body, headers=org.research)
    assert r.status_code == 200 and r.json()["title"] == "Revised" and r.json()["sanctioned_amount"] == "1200.00"
    revised = {x["budget_head_id"]: x for x in r.json()["lines"]}
    assert (
        revised[line["budget_head_id"]]["spent"] == "100.00"
        and revised[line["budget_head_id"]]["allocated"] == "700.00"
    )
    drop = {
        **body,
        "sanctioned_amount": "500.00",
        "lines": [{"budget_head_id": other["budget_head_id"], "sanctioned": "500"}],
    }
    assert (
        client.put(f"{BASE}/grants/{g['id']}", json=drop, headers=org.research).json()["detail"]["code"]
        == "line_in_use"
    )
    assert client.get(f"{BASE}/grants/{g['id']}", headers=org.scholar).status_code == 404  # removed from investigators


def test_funds_spend_certificate_and_close(client, org):
    g = grant(client, org, amount="1000.00")
    line = g["lines"][0]["id"]
    client.post(
        f"{BASE}/grants/{g['id']}/funds-received",
        json={"amount": "600", "received_on": "2026-05-01", "reference": "T1"},
        headers=org.research,
    )
    client.post(
        f"{BASE}/expenditures",
        json={"line_id": line, "amount": "150", "date": "2026-06-15", "description": "Reagents"},
        headers=org.staff,
    )
    client.post(
        f"{BASE}/grants/{g['id']}/funds-received",
        json={"amount": "200", "received_on": "2026-11-01"},
        headers=org.research,
    )
    client.post(
        f"{BASE}/expenditures",
        json={"line_id": line, "amount": "50", "date": "2026-10-20", "description": "Travel"},
        headers=org.staff,
    )
    after = client.get(f"{BASE}/grants/{g['id']}", headers=org.research).json()
    assert after["received_total"] == "800.00" and after["spent_total"] == "200.00" and after["balance"] == "600.00"
    assert [e["amount"] for e in outbox("budget-grants.grant.funds-received", org.id) if e["grant_id"] == g["id"]] == [
        "600.00",
        "200.00",
    ]

    uc = client.post(
        f"{BASE}/grants/{g['id']}/utilisation-certificates",
        json={"period_from": "2026-06-01", "period_to": "2027-03-31"},
        headers=org.research,
    ).json()
    assert (uc["opening_balance"], uc["received"], uc["spent"], uc["closing_balance"]) == (
        "600.00",
        "200.00",
        "200.00",
        "600.00",
    )
    assert uc["status"] == "draft" and {h["spent"] for h in uc["by_head"]} == {"200.00", "0.00"}
    assert (
        client.post(f"{BASE}/utilisation-certificates/{uc['id']}/mark-submitted", headers=org.research).status_code
        == 409
    )
    certified = client.post(
        f"{BASE}/utilisation-certificates/{uc['id']}/decision", json={"decision": "approved"}, headers=org.manager
    ).json()
    assert certified["status"] == "approved" and certified["approved_by"] == org.ids["manager"]
    sent = client.post(
        f"{BASE}/utilisation-certificates/{uc['id']}/mark-submitted",
        json={"submitted_on": "2027-04-05", "reference": "DST/UC/1"},
        headers=org.research,
    ).json()
    assert sent["status"] == "submitted" and sent["submitted_on"] == "2027-04-05"
    assert [
        e["spent"]
        for e in outbox("budget-grants.utilisation-certificate.submitted", org.id)
        if e["grant_id"] == g["id"]
    ] == ["200.00"]
    assert client.get(f"{BASE}/grants/{g['id']}", headers=org.research).json()["next_uc_due"] == "2028-03-31"  # covered
    listed = client.get(f"{BASE}/grants/{g['id']}/utilisation-certificates", headers=org.faculty).json()
    assert [c["id"] for c in listed] == [uc["id"]]

    closed = client.post(
        f"{BASE}/grants/{g['id']}/close", json={"unspent_action": "returned"}, headers=org.research
    ).json()
    assert closed["status"] == "closed" and closed["unspent_action"] == "returned" and closed["next_uc_due"] is None
    assert [e["unspent"] for e in outbox("budget-grants.grant.closed", org.id) if e["grant_id"] == g["id"]] == [
        "600.00"
    ]
    assert client.get(f"{BASE}/availability?line_id={line}&amount=1", headers=org.staff).status_code == 404
    assert (
        client.post(f"{BASE}/grants/{g['id']}/close", json={"unspent_action": "none"}, headers=org.research).status_code
        == 409
    )


def test_a_certificate_needs_someone_else_to_certify(client, org):
    from bg_support import auth
    from eos_core.security import create_token

    g = grant(client, org)
    both = auth(
        create_token(user_id=org.ids["research"], organisation_id=org.id, roles=["research-office", "management"])
    )
    uc = client.post(
        f"{BASE}/grants/{g['id']}/utilisation-certificates",
        json={"period_from": "2026-04-01", "period_to": "2027-03-31"},
        headers=org.research,
    ).json()
    assert (
        client.post(
            f"{BASE}/utilisation-certificates/{uc['id']}/decision", json={"decision": "approved"}, headers=both
        ).status_code
        == 403
    )
    back = client.post(
        f"{BASE}/utilisation-certificates/{uc['id']}/decision", json={"decision": "returned"}, headers=org.manager
    )
    assert back.json()["status"] == "returned"


def test_my_grants(client, org):
    g = grant(client, org)
    mine = client.get(f"{BASE}/me/grants", headers=org.scholar).json()
    assert [x["id"] for x in mine] == [g["id"]] and mine[0]["my_role"] == "co_investigator"
    assert mine[0]["next_uc_due"] == "2027-03-31" and mine[0]["balance"] == "0.00"
    assert client.get(f"{BASE}/me/grants", headers=org.faculty).json()[0]["my_role"] == "principal"
    assert client.get(f"{BASE}/me/grants", headers=org.dept).json() == []
    assert client.get(f"{BASE}/me/grants", headers=org.research).status_code == 403
