"""Payroll runs: computing with loss of pay, adjusting, submitting, deciding by someone else, locking, paying."""

from hp_support import BASE, apply, approved_run, decide, employee, leave_type, outbox, salary, start_run


def _payslips(client, org, run_id):
    return {
        p["employee_id"]: p
        for p in client.get(f"{BASE}/payroll-runs/{run_id}/payslips", headers=org.hr).json()["items"]
    }


def test_a_run_computes_exact_payslips_with_loss_of_pay(client, org):
    """October has 31 days. Three days of unpaid leave pay 28/31 of every line, each rounded to the paisa."""
    full = employee(client, org, who="faculty2")
    lop = employee(client, org)
    joiner = employee(client, org, who=None, joined_on="2026-10-16", bank_account=None)
    for e in (full, lop, joiner):
        salary(client, org, e, e["joined_on"])
    unpaid = leave_type(client, org, code="LWP", days=0, paid=False)
    r = apply(client, org, "faculty", unpaid, "2026-10-29", "2026-10-31")
    assert decide(client, org, r.json()["id"]).status_code == 200
    r = start_run(client, org)
    assert r.status_code == 202, r.text
    run = r.json()
    assert run["status"] == "review" and run["employees"] == 3 and run["prepared_by"] == org.ids["hr"]
    slips = _payslips(client, org, run["id"])
    assert (slips[full["id"]]["gross"], slips[full["id"]]["net"], slips[full["id"]]["paid_days"]) == (
        "42000.00",
        "38400.00",
        31,
    )
    p = slips[lop["id"]]
    assert p["loss_of_pay_days"] == 3 and p["paid_days"] == 28 and p["days_in_month"] == 31
    assert [(x["code"], x["amount"]) for x in p["lines"]] == [
        ("BASIC", "27096.77"),
        ("HRA", "10838.71"),
        ("PF", "3251.61"),
    ]
    assert (p["gross"], p["deductions"], p["net"]) == ("37935.48", "3251.61", "34683.87")
    j = slips[joiner["id"]]  # 16 of 31 days: 30000*16/31 = 15483.870 -> 15483.87; 12000 -> 6193.55; 3600 -> 1858.06
    assert j["paid_days"] == 16 and (j["gross"], j["deductions"], j["net"]) == ("21677.42", "1858.06", "19819.36")
    assert run["gross_total"] == "101612.90" and run["deductions_total"] == "8709.67" and run["net_total"] == "92903.23"
    assert {x["message"] for x in run["exceptions"]} == {"no bank account"} and run["exceptions"][0][
        "employee_id"
    ] == joiner["id"]


def test_missing_salary_and_people_off_the_rolls(client, org):
    no_salary = employee(client, org)
    gone = employee(client, org, who="faculty2")
    salary(client, org, gone)
    client.post(
        f"{BASE}/employees/{gone['id']}/exit",
        json={"kind": "resignation", "last_working_day": "2026-09-30"},
        headers=org.hr,
    )
    later = employee(client, org, who=None, joined_on="2026-11-01")
    salary(client, org, later, "2026-11-01")
    run = start_run(client, org).json()
    assert run["employees"] == 0 and run["exceptions"] == [
        {"employee_id": no_salary["id"], "message": "no salary in effect; no payslip"}
    ]
    r = client.post(f"{BASE}/payroll-runs/{run['id']}/submit", headers=org.hr)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "empty_run"


def test_an_exit_in_the_month_pays_to_the_last_working_day(client, org):
    e = employee(client, org)
    salary(client, org, e)
    client.post(
        f"{BASE}/employees/{e['id']}/exit",
        json={"kind": "resignation", "last_working_day": "2026-10-10"},
        headers=org.hr,
    )
    p = _payslips(client, org, start_run(client, org).json()["id"])[e["id"]]
    assert p["paid_days"] == 10 and p["lines"][0]["amount"] == "9677.42"  # 30000 * 10 / 31


def test_one_run_per_month_and_no_future_months(client, org):
    assert start_run(client, org).status_code == 202
    r = start_run(client, org)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "run_exists"
    r = start_run(client, org, "2026-11")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "period_in_future"
    assert start_run(client, org, "2026-13").status_code == 422
    assert start_run(client, org, "2026-09", who="finance").status_code == 403


def test_adjust_submit_return_approve_and_pay(client, org):
    e = employee(client, org)
    salary(client, org, e)
    run = start_run(client, org).json()
    slip = _payslips(client, org, run["id"])[e["id"]]
    lines = [*slip["lines"], {"code": "ARREARS", "name": "September arrears", "kind": "earning", "amount": "1500.50"}]
    url = f"{BASE}/payroll-runs/{run['id']}/payslips/{slip['id']}"
    r = client.put(url, json={"lines": lines, "reason": "  "}, headers=org.hr2)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "reason_required"
    r = client.put(url, json={"lines": lines, "reason": "arrears for September"}, headers=org.hr2)
    assert r.status_code == 200 and r.json()["net"] == "39900.50"
    assert r.json()["adjustments"][0]["reason"] == "arrears for September"
    assert client.put(url, json={"lines": lines, "reason": "x"}, headers=org.faculty).status_code == 403
    assert client.put(url, json={"lines": lines, "reason": "x"}, headers=org.finance).status_code == 403
    assert client.get(f"{BASE}/payroll-runs/{run['id']}", headers=org.hr).json()["net_total"] == "39900.50"

    r = client.post(f"{BASE}/payroll-runs/{run['id']}/decision", json={"decision": "approved"}, headers=org.finance)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "run_not_submitted"
    r = client.post(f"{BASE}/payroll-runs/{run['id']}/submit", headers=org.hr)
    assert r.status_code == 200 and r.json()["status"] == "submitted"
    assert outbox("hr-payroll.payroll-run.submitted", org.id)[-1] == {
        "organisation_id": org.id,
        "run_id": run["id"],
        "period": "2026-10",
        "employees": 1,
    }
    r = client.post(f"{BASE}/payroll-runs/{run['id']}/decision", json={"decision": "returned"}, headers=org.finance)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "note_required"
    r = client.post(
        f"{BASE}/payroll-runs/{run['id']}/decision",
        json={"decision": "returned", "note": "check arrears"},
        headers=org.manager,
    )
    assert r.status_code == 200 and r.json()["status"] == "review" and r.json()["note"] == "check arrears"
    client.post(f"{BASE}/payroll-runs/{run['id']}/submit", headers=org.hr)
    assert client.get(f"{BASE}/me/payslips", headers=org.faculty).json() == []  # not visible before approval
    r = client.post(f"{BASE}/payroll-runs/{run['id']}/decision", json={"decision": "approved"}, headers=org.finance)
    assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["approved_by"] == org.ids["finance"]
    assert outbox("hr-payroll.payroll-run.approved", org.id)[-1] == {
        "organisation_id": org.id,
        "run_id": run["id"],
        "period": "2026-10",
        "employees": 1,
        "net_total": "39900.50",
    }
    mine = client.get(f"{BASE}/me/payslips", headers=org.faculty).json()
    assert [p["net"] for p in mine] == ["39900.50"]

    # locked: no adjustment, no second decision
    r = client.put(url, json={"lines": lines, "reason": "late change"}, headers=org.hr)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "run_not_in_review"
    r = client.post(f"{BASE}/payroll-runs/{run['id']}/submit", headers=org.hr)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "run_not_in_review"

    pay = f"{BASE}/payroll-runs/{run['id']}/mark-paid"
    r = client.post(pay, json={"paid_on": "2026-10-29"}, headers=org.finance)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_date"
    assert client.post(pay, json={"paid_on": "2026-10-28"}, headers=org.hr).status_code == 403
    r = client.post(pay, json={"paid_on": "2026-10-28", "bank_reference": "NEFT-1"}, headers=org.finance)
    assert r.status_code == 200 and r.json()["status"] == "paid" and r.json()["paid_on"] == "2026-10-28"
    assert outbox("hr-payroll.payroll-run.paid", org.id)[-1] == {
        "organisation_id": org.id,
        "run_id": run["id"],
        "period": "2026-10",
        "net_total": "39900.50",
        "paid_on": "2026-10-28",
    }
    r = client.post(pay, json={"paid_on": "2026-10-28"}, headers=org.finance)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "run_not_approved"


def test_the_preparer_never_approves(client, org):
    """A user who holds both prepare and approve (hr-staff plus management) cannot approve a run they started,
    adjusted or submitted."""
    from eos_core.security import create_token
    from hp_support import auth

    both = auth(create_token(user_id=org.ids["hr2"], organisation_id=org.id, roles=["hr-staff", "management"]))
    e = employee(client, org)
    salary(client, org, e)
    run = start_run(client, org, who="hr2").json()  # hr2 started it
    client.post(f"{BASE}/payroll-runs/{run['id']}/submit", headers=org.hr)
    r = client.post(f"{BASE}/payroll-runs/{run['id']}/decision", json={"decision": "approved"}, headers=both)
    assert r.status_code == 403
    r = client.post(f"{BASE}/payroll-runs/{run['id']}/decision", json={"decision": "approved"}, headers=org.faculty)
    assert r.status_code == 403  # no payroll:approve
    assert client.get(f"{BASE}/payroll-runs/{run['id']}", headers=org.hr).json()["status"] == "submitted"
    assert (
        client.post(
            f"{BASE}/payroll-runs/{run['id']}/decision", json={"decision": "approved"}, headers=org.manager
        ).status_code
        == 200
    )


def test_nobody_adjusts_their_own_payslip(client, org):
    me_ = employee(client, org, who="hr")
    salary(client, org, me_, who="hr2")
    run = start_run(client, org, who="hr2").json()
    slip = _payslips(client, org, run["id"])[me_["id"]]
    body = {"lines": [{"code": "BONUS", "kind": "earning", "amount": "99999.00"}], "reason": "me"}
    assert (
        client.put(f"{BASE}/payroll-runs/{run['id']}/payslips/{slip['id']}", json=body, headers=org.hr).status_code
        == 403
    )


def test_unpaid_leave_cannot_reach_a_locked_month(client, org, monkeypatch):
    from datetime import UTC, datetime

    from eos_hr_payroll.application import common

    e = employee(client, org)
    salary(client, org, e)
    unpaid = leave_type(client, org, code="LWP", days=0, paid=False)
    pending = apply(client, org, "faculty", unpaid, "2026-10-30", "2026-10-30").json()
    approved_run(client, org)
    r = apply(client, org, "faculty", unpaid, "2026-10-31", "2026-10-31")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "period_locked"
    r = decide(client, org, pending["id"])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "period_locked"
    monkeypatch.setattr(common, "clock", lambda: datetime(2026, 11, 2, 6, 0, tzinfo=UTC))
    r = client.post(
        f"{BASE}/employees/{e['id']}/exit",
        json={"kind": "resignation", "last_working_day": "2026-09-30"},
        headers=org.hr,
    )
    assert r.status_code == 409 and r.json()["detail"]["code"] == "period_locked"


def test_current_run_and_lateness(client, org, monkeypatch):
    from datetime import UTC, datetime

    from eos_hr_payroll.application import common

    r = client.get(f"{BASE}/payroll-runs/current", headers=org.finance)
    assert r.status_code == 404
    e = employee(client, org)
    salary(client, org, e)
    september = start_run(client, org, "2026-09").json()
    assert september["due_on"] == "2026-09-28" and september["late"] is True
    current = client.get(f"{BASE}/payroll-runs/current", headers=org.finance).json()
    assert current["id"] == september["id"]  # no October run yet: the latest
    october = start_run(client, org).json()
    assert october["late"] is False and october["due_on"] == "2026-10-28"
    assert client.get(f"{BASE}/payroll-runs/current", headers=org.hr).json()["id"] == october["id"]
    monkeypatch.setenv("HR_PAYROLL_PAYROLL_DUE_DAY", "25")
    assert client.get(f"{BASE}/payroll-runs/current", headers=org.hr).json()["late"] is True
    runs = client.get(f"{BASE}/payroll-runs?year=2026", headers=org.manager).json()
    assert [x["period"] for x in runs] == ["2026-10", "2026-09"]
    assert client.get(f"{BASE}/payroll-runs?year=2025", headers=org.manager).json() == []
    assert client.get(f"{BASE}/payroll-runs/current", headers=org.dept).status_code == 403
    assert client.get(f"{BASE}/payroll-runs/{october['id']}/payslips", headers=org.faculty).status_code == 403
    monkeypatch.setattr(common, "clock", lambda: datetime(2026, 11, 3, 6, 0, tzinfo=UTC))
    assert client.get(f"{BASE}/payroll-runs/current", headers=org.hr).json()["id"] == october["id"]
