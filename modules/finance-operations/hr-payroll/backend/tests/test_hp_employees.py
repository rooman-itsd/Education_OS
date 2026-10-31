"""Employees: joining, editing, the masked bank account and PAN, exits, salary structures and the service book."""

from eos_hr_payroll.application import consumers
from hp_support import ACCOUNT, BASE, PAN, approved_run, employee, outbox, salary


def test_joining_publishes_and_records_the_service_book(client, org):
    e = employee(client, org, pan=PAN)
    assert e["status"] == "active" and e["user_id"] == org.ids["faculty"]
    joined = outbox("hr-payroll.employee.joined", org.id)
    assert joined[-1]["employee_id"] == e["id"] and joined[-1]["joined_on"] == "2024-06-01"
    records = client.get(f"{BASE}/employees/{e['id']}/service-records", headers=org.hr).json()
    assert [r["kind"] for r in records] == ["joining"]


def test_bank_account_and_pan_are_kept_masked_and_never_echoed(client, org):
    e = employee(client, org, pan=PAN)
    assert e["bank_account"] == {"account_holder": "Someone", "account_last4": "9012", "ifsc": "SBIN0001234"}
    assert e["pan_masked"] == "XXXXXX234F" and "pan" not in e
    for r in (
        client.get(f"{BASE}/employees/{e['id']}", headers=org.hr),
        client.get(f"{BASE}/employees", headers=org.hr),
        client.get(f"{BASE}/me", headers=org.faculty),
    ):
        assert ACCOUNT not in r.text and PAN not in r.text
    # an invalid body with the full values: the 422 does not repeat them
    bad = {
        "employee_code": "X1",
        "name": "",
        "joined_on": "2024-01-01",
        "employment_type": "permanent",
        "pan": PAN,
        "bank_account": {"account_number": ACCOUNT, "ifsc": "SBIN0001234"},
    }
    r = client.post(f"{BASE}/employees", json=bad, headers=org.hr)
    assert r.status_code == 422 and ACCOUNT not in r.text and PAN not in r.text
    bad = {**bad, "name": "n", "pan": "ABCDE12345"}
    r = client.post(f"{BASE}/employees", json=bad, headers=org.hr)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_pan" and "ABCDE12345" not in r.text
    bad = {**bad, "pan": PAN, "bank_account": {"account_number": "12AB5678", "ifsc": "SBIN0001234"}}
    r = client.post(f"{BASE}/employees", json=bad, headers=org.hr)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_account_number" and "12AB5678" not in r.text
    # nothing anywhere in the outbox holds them
    for name in ("hr-payroll.employee.joined", "hr-payroll.employee.updated"):
        assert all(ACCOUNT not in str(p) and PAN not in str(p) for p in outbox(name, org.id))


def test_editing_keeps_what_is_not_sent_and_records_changes(client, org):
    e = employee(client, org, pan=PAN)
    body = {k: e[k] for k in ("employee_code", "name", "joined_on", "employment_type", "designation")}
    body.update(designation="Associate Professor", department_id="d-2", department_name="Physics")
    r = client.put(f"{BASE}/employees/{e['id']}", json=body, headers=org.hr)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["bank_account"]["account_last4"] == "9012" and out["pan_masked"] == "XXXXXX234F"
    kinds = [x["kind"] for x in client.get(f"{BASE}/employees/{e['id']}/service-records", headers=org.hr).json()]
    assert kinds == ["joining", "transfer", "other"]
    updated = outbox("hr-payroll.employee.updated", org.id)[-1]
    assert updated == {
        "organisation_id": org.id,
        "employee_id": e["id"],
        "name": e["name"],
        "designation": "Associate Professor",
        "department_id": "d-2",
        "reports_to": None,
    }
    # an edit sending the bank account back without its number keeps it; null removes it and the PAN
    r = client.put(f"{BASE}/employees/{e['id']}", json={**body, "bank_account": out["bank_account"]}, headers=org.hr)
    assert r.json()["bank_account"]["account_last4"] == "9012"
    r = client.put(f"{BASE}/employees/{e['id']}", json={**body, "bank_account": None, "pan": None}, headers=org.hr)
    assert r.json()["bank_account"] is None and r.json()["pan_masked"] is None


def test_codes_and_users_are_unique_and_managers_valid(client, org):
    e = employee(client, org)
    body = {"employee_code": e["employee_code"], "name": "B", "joined_on": "2025-01-01", "employment_type": "contract"}
    r = client.post(f"{BASE}/employees", json=body, headers=org.hr)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "employee_code_taken"
    r = client.post(
        f"{BASE}/employees", json={**body, "employee_code": "NEW1", "user_id": org.ids["faculty"]}, headers=org.hr
    )
    assert r.status_code == 409 and r.json()["detail"]["code"] == "user_already_linked"
    r = client.post(f"{BASE}/employees", json={**body, "employee_code": "NEW2", "reports_to": "nope"}, headers=org.hr)
    assert r.status_code == 404
    r = client.post(
        f"{BASE}/employees", json={**body, "employee_code": "NEW3", "date_of_birth": "2026-01-01"}, headers=org.hr
    )
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_date_of_birth"
    r = client.post(
        f"{BASE}/employees", json={**body, "employee_code": "NEW4", "employment_type": "intern"}, headers=org.hr
    )
    assert r.status_code == 422


def test_permissions_on_employees(client, org):
    e = employee(client, org)
    other = employee(client, org, who="faculty2")
    body = {"employee_code": "P1", "name": "x", "joined_on": "2025-01-01", "employment_type": "permanent"}
    assert client.post(f"{BASE}/employees", json=body, headers=org.faculty).status_code == 403
    assert client.post(f"{BASE}/employees", json=body, headers=org.manager).status_code == 403
    assert client.get(f"{BASE}/employees", headers=org.faculty).status_code == 403
    assert client.get(f"{BASE}/employees", headers=org.manager).status_code == 200
    assert client.get(f"{BASE}/employees/{e['id']}", headers=org.faculty).status_code == 200  # their own
    assert client.get(f"{BASE}/employees/{other['id']}", headers=org.faculty).status_code == 403
    assert client.get(f"{BASE}/employees", headers=org.nobody).status_code == 403
    assert client.get(f"{BASE}/employees").status_code == 401
    assert client.get(f"{BASE}/me", headers=org.dept).status_code == 404  # not an employee


def test_salary_is_visible_to_the_employee_and_payroll_readers_only(client, org):
    e = employee(client, org)
    other = employee(client, org, who="faculty2")
    s = salary(client, org, e)
    assert (s["gross"], s["deductions"], s["net"]) == ("42000.00", "3600.00", "38400.00")
    assert client.get(f"{BASE}/employees/{e['id']}/salary", headers=org.faculty).json()["net"] == "38400.00"
    assert client.get(f"{BASE}/employees/{e['id']}/salary", headers=org.finance).status_code == 200
    assert client.get(f"{BASE}/employees/{e['id']}/salary", headers=org.faculty2).status_code == 403
    assert client.get(f"{BASE}/employees/{e['id']}/salary", headers=org.dept).status_code == 403
    r = client.get(f"{BASE}/employees/{other['id']}/salary", headers=org.hr)
    assert r.status_code == 404 and r.json()["detail"]["code"] == "no_salary"
    body = {"effective_from": "2026-01-01", "lines": [{"code": "BASIC", "kind": "earning", "amount": "1.00"}]}
    assert client.put(f"{BASE}/employees/{e['id']}/salary", json=body, headers=org.finance).status_code == 403


def test_salary_history_and_validation(client, org):
    e = employee(client, org)
    salary(client, org, e)
    raise_ = salary(client, org, e, "2026-11-01", [{"code": "BASIC", "kind": "earning", "amount": "35000.00"}])
    assert raise_["effective_from"] == "2026-11-01"
    current = client.get(f"{BASE}/employees/{e['id']}/salary", headers=org.hr).json()
    assert current["effective_from"] == "2024-06-01"  # the November structure is not in effect yet
    url = f"{BASE}/employees/{e['id']}/salary"
    for lines, code in (
        ([{"code": "PF", "kind": "deduction", "amount": "10.00"}], "no_earnings"),
        (
            [{"code": "B", "kind": "earning", "amount": "1.00"}, {"code": "P", "kind": "deduction", "amount": "2.00"}],
            "deductions_exceed_earnings",
        ),
    ):
        r = client.put(url, json={"effective_from": "2026-12-01", "lines": lines}, headers=org.hr)
        assert r.status_code == 422 and r.json()["detail"]["code"] == code
    r = client.put(
        url,
        json={"effective_from": "2026-12-01", "lines": [{"code": "B", "kind": "earning", "amount": "1.5"}]},
        headers=org.hr,
    )
    assert r.status_code == 200
    r = client.put(
        url,
        json={"effective_from": "2026-12-01", "lines": [{"code": "B", "kind": "earning", "amount": "1.555"}]},
        headers=org.hr,
    )
    assert r.status_code == 422
    r = client.put(
        url,
        json={"effective_from": "2020-01-01", "lines": [{"code": "B", "kind": "earning", "amount": "1"}]},
        headers=org.hr,
    )
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_date"


def test_nobody_sets_their_own_salary(client, org):
    hr_self = employee(client, org, who="hr")
    body = {"effective_from": "2026-01-01", "lines": [{"code": "BASIC", "kind": "earning", "amount": "99999.00"}]}
    r = client.put(f"{BASE}/employees/{hr_self['id']}/salary", json=body, headers=org.hr)
    assert r.status_code == 403
    assert client.put(f"{BASE}/employees/{hr_self['id']}/salary", json=body, headers=org.hr2).status_code == 200


def test_a_locked_month_keeps_its_salary(client, org):
    e = employee(client, org)
    salary(client, org, e)
    approved_run(client, org)
    body = {"effective_from": "2026-10-15", "lines": [{"code": "BASIC", "kind": "earning", "amount": "50000.00"}]}
    r = client.put(f"{BASE}/employees/{e['id']}/salary", json=body, headers=org.hr)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "period_locked"
    body["effective_from"] = "2026-11-01"
    assert client.put(f"{BASE}/employees/{e['id']}/salary", json=body, headers=org.hr).status_code == 200


def test_an_exit_dated_today_is_published_at_once(client, org):
    e = employee(client, org)
    r = client.post(
        f"{BASE}/employees/{e['id']}/exit",
        json={"kind": "resignation", "last_working_day": "2026-10-28"},
        headers=org.hr,
    )
    assert r.status_code == 200 and r.json()["status"] == "exited"
    assert r.json()["exit"] == {"kind": "resignation", "last_working_day": "2026-10-28", "reason": ""}
    exited = outbox("hr-payroll.employee.exited", org.id)
    assert exited == [
        {
            "organisation_id": org.id,
            "employee_id": e["id"],
            "user_id": org.ids["faculty"],
            "kind": "resignation",
            "last_working_day": "2026-10-28",
        }
    ]
    r = client.post(
        f"{BASE}/employees/{e['id']}/exit",
        json={"kind": "resignation", "last_working_day": "2026-10-28"},
        headers=org.hr,
    )
    assert r.status_code == 409 and r.json()["detail"]["code"] == "employee_exited"


def test_a_future_exit_waits_for_the_scheduler_job(client, org, monkeypatch):
    from datetime import UTC, datetime

    from eos_core.db import SessionLocal
    from eos_core.events import OutboxEvent
    from eos_core.tenant import platform_scope
    from eos_hr_payroll.application import common
    from sqlalchemy import select

    e = employee(client, org)
    r = client.post(
        f"{BASE}/employees/{e['id']}/exit",
        json={"kind": "retirement", "last_working_day": "2026-11-30"},
        headers=org.hr,
    )
    assert r.json()["status"] == "on_notice"
    assert outbox("hr-payroll.employee.exited", org.id) == []

    class Due:
        organisation_id = None
        payload = {"job": consumers.JOB, "run_id": "run-1"}

    def run_job():
        with platform_scope(), SessionLocal() as db:
            consumers.on_job_due(db, Due())
            db.commit()

    run_job()  # 28 October: not yet
    assert outbox("hr-payroll.employee.exited", org.id) == []
    monkeypatch.setattr(common, "clock", lambda: datetime(2026, 11, 30, 13, 30, tzinfo=UTC))
    run_job()
    run_job()  # at-least-once delivery: published once
    exited = outbox("hr-payroll.employee.exited", org.id)
    assert [x["employee_id"] for x in exited] == [e["id"]]
    assert client.get(f"{BASE}/employees/{e['id']}", headers=org.hr).json()["status"] == "exited"
    with platform_scope(), SessionLocal() as db:
        q = select(OutboxEvent).where(OutboxEvent.name == "hr-payroll.job.finished")
        finished = [e.payload for e in db.scalars(q) if e.payload.get("run_id") == "run-1"]
    # one platform run covers every organisation (other tests' exits may be due too)
    assert finished and all(f["outcome"] == "succeeded" and f["detail"].endswith("exit(s) published") for f in finished)
    assert set(finished[0]) == {"run_id", "outcome", "detail"}
    other = type("Other", (), {"organisation_id": None, "payload": {"job": "billing.expire-trials"}})()
    with platform_scope(), SessionLocal() as db:
        consumers.on_job_due(db, other)  # another module's job: nothing happens


def test_exit_cancels_leave_after_the_last_day_and_validates_dates(client, org):
    from hp_support import apply, leave_type

    e = employee(client, org)
    t = leave_type(client, org, code="EL")
    later = apply(client, org, "faculty", t, "2026-12-07", "2026-12-08").json()
    r = client.post(
        f"{BASE}/employees/{e['id']}/exit",
        json={"kind": "resignation", "last_working_day": "2020-01-01"},
        headers=org.hr,
    )
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_date"
    client.post(
        f"{BASE}/employees/{e['id']}/exit",
        json={"kind": "resignation", "last_working_day": "2026-11-30"},
        headers=org.hr,
    )
    mine = client.get(f"{BASE}/me/leave-requests", headers=org.faculty).json()
    assert [x["status"] for x in mine if x["id"] == later["id"]] == ["cancelled"]
    assert outbox("hr-payroll.leave-request.cancelled", org.id)[-1]["leave_request_id"] == later["id"]


def test_service_records(client, org):
    e = employee(client, org)
    body = {"kind": "award", "effective_on": "2026-09-05", "title": "Best teacher", "document_id": None}
    r = client.post(f"{BASE}/employees/{e['id']}/service-records", json=body, headers=org.hr)
    assert r.status_code == 201 and r.json()["recorded_by"] == org.ids["hr"] and r.json()["document_id"] is None
    assert client.post(f"{BASE}/employees/{e['id']}/service-records", json=body, headers=org.manager).status_code == 403
    r = client.post(f"{BASE}/employees/{e['id']}/service-records", json={**body, "kind": "medal"}, headers=org.hr)
    assert r.status_code == 422
    kinds = [x["kind"] for x in client.get(f"{BASE}/employees/{e['id']}/service-records", headers=org.faculty).json()]
    assert kinds == ["joining", "award"]
