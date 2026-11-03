"""Leave types, applying, deciding, cancelling, balances and carry-forward."""

from hp_support import BASE, apply, decide, employee, leave_type, outbox


def test_leave_types_are_managed_by_hr_and_listed_to_employees(client, org):
    t = leave_type(client, org, code="cl", days=12, carry_forward_max=5)
    assert (
        t["code"] == "CL"
        and t["days_per_year"] == 12
        and t["applies_to"] == sorted(["permanent", "contract", "visiting", "part_time"])
    )
    r = client.post(f"{BASE}/leave-types", json={"code": "CL", "name": "x", "days_per_year": 1}, headers=org.hr)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "leave_type_code_taken"
    r = client.post(f"{BASE}/leave-types", json={"code": "X", "name": "x", "days_per_year": 1.3}, headers=org.hr)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_days"
    assert (
        client.post(
            f"{BASE}/leave-types", json={"code": "Y", "name": "y", "days_per_year": 1}, headers=org.faculty
        ).status_code
        == 403
    )
    r = client.put(f"{BASE}/leave-types/{t['id']}", json={**t, "days_per_year": 10.5}, headers=org.hr)
    assert r.status_code == 200 and r.json()["days_per_year"] == 10.5
    assert [x["code"] for x in client.get(f"{BASE}/leave-types", headers=org.faculty).json()] == ["CL"]
    assert client.get(f"{BASE}/leave-types", headers=org.nobody).status_code == 403


def test_apply_decide_and_the_events(client, org):
    manager = employee(client, org, who="dept")
    e = employee(client, org, reports_to=manager["id"])
    t = leave_type(client, org)
    r = apply(client, org, "faculty", t, "2026-11-02", "2026-11-04", reason="family")
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["days"] == 3 and req["status"] == "pending" and req["employee_name"] == e["name"]
    assert outbox("hr-payroll.leave-request.submitted", org.id)[-1] == {
        "organisation_id": org.id,
        "leave_request_id": req["id"],
        "employee_id": e["id"],
        "approver_id": org.ids["dept"],
        "from": "2026-11-02",
        "to": "2026-11-04",
        "days": 3,
    }
    pending = client.get(f"{BASE}/leave-requests?status=pending", headers=org.hr).json()
    assert pending["pending_total"] == 1 and [x["id"] for x in pending["items"]] == [req["id"]]
    r = decide(client, org, req["id"], who="dept")
    assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["decided_by"] == org.ids["dept"]
    assert outbox("hr-payroll.leave-request.approved", org.id)[-1] == {
        "organisation_id": org.id,
        "leave_request_id": req["id"],
        "employee_id": e["id"],
        "user_id": org.ids["faculty"],
        "from": "2026-11-02",
        "to": "2026-11-04",
        "half_day": "none",
    }
    r = decide(client, org, req["id"], "rejected")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_pending"
    assert client.get(f"{BASE}/leave-requests?status=pending", headers=org.hr).json()["pending_total"] == 0
    second = apply(client, org, "faculty", t, "2026-11-10", "2026-11-10").json()
    assert decide(client, org, second["id"], "rejected").json()["status"] == "rejected"
    assert outbox("hr-payroll.leave-request.rejected", org.id)[-1] == {
        "organisation_id": org.id,
        "leave_request_id": second["id"],
        "employee_id": e["id"],
    }


def test_nobody_decides_their_own_leave(client, org):
    employee(client, org, who="hr")
    t = leave_type(client, org)
    req = apply(client, org, "hr", t, "2026-11-02", "2026-11-02").json()
    r = decide(client, org, req["id"], who="hr")
    assert r.status_code == 403
    assert decide(client, org, req["id"], who="hr2").status_code == 200
    assert decide(client, org, req["id"], who="faculty").status_code == 403  # no leave:approve


def test_application_rules(client, org):
    e = employee(client, org, employment_type="contract")
    t = leave_type(client, org, days=3, half_day_allowed=False)
    only_permanent = leave_type(client, org, code="SAB", applies_to=["permanent"])
    for (start, end, extra), code in (
        (("2026-10-27", "2026-10-27", {}), "dates_in_past"),
        (("2026-11-05", "2026-11-04", {}), "invalid_dates"),
        (("2026-11-05", "2026-11-06", {"half_day": "first_half"}), "invalid_half_day"),
        (("2026-11-05", "2026-11-05", {"half_day": "first_half"}), "half_day_not_allowed"),
        (("2026-12-31", "2027-01-01", {}), "spans_leave_years"),
        (("2026-11-01", "2026-11-04", {}), "insufficient_balance"),
    ):
        r = apply(client, org, "faculty", t, start, end, **extra)
        assert r.status_code == 422 and r.json()["detail"]["code"] == code, (code, r.text)
    r = apply(client, org, "faculty", only_permanent, "2026-11-05", "2026-11-05")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "leave_type_not_applicable"
    assert apply(client, org, "faculty", t, "2026-11-05", "2026-11-06").status_code == 201
    r = apply(client, org, "faculty", t, "2026-11-06", "2026-11-06")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "overlapping_request"
    r = apply(client, org, "faculty", t, "2026-11-09", "2026-11-10")  # 2 pending + 2 > 3
    assert r.status_code == 422 and r.json()["detail"]["code"] == "insufficient_balance"
    assert apply(client, org, "faculty2", t, "2026-11-09", "2026-11-09").status_code == 404  # not an employee
    assert apply(client, org, "faculty", {"id": "missing"}, "2026-11-20", "2026-11-20").status_code == 404
    assert e["employment_type"] == "contract"


def test_cancel_returns_the_days_before_the_leave_starts(client, org):
    employee(client, org)
    t = leave_type(client, org, days=2)
    req = apply(client, org, "faculty", t, "2026-11-02", "2026-11-03").json()
    decide(client, org, req["id"])
    assert client.get(f"{BASE}/me/leave-balances", headers=org.faculty).json()[0]["available"] == 0
    assert client.post(f"{BASE}/leave-requests/{req['id']}/cancel", headers=org.hr).status_code == 403
    r = client.post(f"{BASE}/leave-requests/{req['id']}/cancel", headers=org.faculty)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert outbox("hr-payroll.leave-request.cancelled", org.id)[-1] == {
        "organisation_id": org.id,
        "leave_request_id": req["id"],
        "employee_id": req["employee_id"],
        "from": "2026-11-02",
        "to": "2026-11-03",
    }
    assert client.get(f"{BASE}/me/leave-balances", headers=org.faculty).json()[0]["available"] == 2
    r = client.post(f"{BASE}/leave-requests/{req['id']}/cancel", headers=org.faculty)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_cancellable"


def test_leave_that_has_started_cannot_be_withdrawn(client, org, monkeypatch):
    from datetime import UTC, datetime

    from eos_hr_payroll.application import common

    employee(client, org)
    t = leave_type(client, org)
    req = apply(client, org, "faculty", t, "2026-10-29", "2026-10-30").json()
    monkeypatch.setattr(common, "clock", lambda: datetime(2026, 10, 28, 19, 0, tzinfo=UTC))  # 00:30 on the 29th, IST
    r = client.post(f"{BASE}/leave-requests/{req['id']}/cancel", headers=org.faculty)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "already_started"


def test_balances_carry_forward_and_pro_rata(client, org):
    """Joined 1 June 2024; 12 days a year, up to 5 carried. 2024 gives 7 (June to December), 2025 gives 12."""
    from eos_core.db import SessionLocal
    from eos_core.tenant import organisation_scope
    from eos_hr_payroll.infrastructure.models import LeaveRequest

    e = employee(client, org, joined_on="2024-06-01")
    t = leave_type(client, org, days=12, carry_forward_max=5)
    unpaid = leave_type(client, org, code="LWP", days=0, paid=False)
    with organisation_scope(org.id), SessionLocal() as db:  # history: 2 days used in 2024, 10 in 2025
        for start, end, days in (("2024-07-01", "2024-07-02", 2), ("2025-03-02", "2025-03-11", 10)):
            from datetime import date

            db.add(
                LeaveRequest(
                    organisation_id=org.id,
                    employee_id=e["id"],
                    leave_type_id=t["id"],
                    from_date=date.fromisoformat(start),
                    to_date=date.fromisoformat(end),
                    half_day="none",
                    days=days,
                    paid=True,
                    reason="",
                    status="approved",
                )
            )
        db.commit()
    # 2024: 7 - 2 = 5 left -> 5 carried; 2025: 12 + 5 - 10 = 7 left -> 5 carried (the limit)
    apply(client, org, "faculty", t, "2026-11-02", "2026-11-02", half_day="second_half")
    balances = {b["code"]: b for b in client.get(f"{BASE}/me/leave-balances", headers=org.faculty).json()}
    assert balances["CL"] == {
        "leave_type_id": t["id"],
        "name": "CL leave",
        "code": "CL",
        "paid": True,
        "leave_year": 2026,
        "entitled": 12,
        "carried_forward": 5,
        "taken": 0,
        "pending": 0.5,
        "available": 16.5,
    }
    assert balances["LWP"]["carried_forward"] == 0
    assert apply(client, org, "faculty", unpaid, "2026-11-09", "2026-11-20").status_code == 201  # no balance needed


def test_the_leave_year_start_month_is_configurable(client, org, monkeypatch):
    monkeypatch.setenv("HR_PAYROLL_LEAVE_YEAR_START_MONTH", "4")
    employee(client, org, joined_on="2026-10-01")
    t = leave_type(client, org, days=12)
    b = client.get(f"{BASE}/me/leave-balances", headers=org.faculty).json()[0]
    assert b["leave_year"] == 2026 and b["entitled"] == 6  # October to March
    assert apply(client, org, "faculty", t, "2026-12-31", "2027-01-01").status_code == 201  # one leave year now
    r = apply(client, org, "faculty", t, "2027-03-31", "2027-04-01")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "spans_leave_years"


def test_leave_list_filters_and_permissions(client, org):
    a = employee(client, org, department_id="d-1")
    employee(client, org, who="faculty2", department_id="d-2")
    t = leave_type(client, org)
    apply(client, org, "faculty", t, "2026-11-02", "2026-11-02")
    apply(client, org, "faculty2", t, "2026-12-02", "2026-12-02")
    items = client.get(f"{BASE}/leave-requests?department_id=d-1", headers=org.manager).json()["items"]
    assert [x["employee_id"] for x in items] == [a["id"]]
    items = client.get(f"{BASE}/leave-requests?from=2026-12-01&to=2026-12-31", headers=org.dept).json()["items"]
    assert len(items) == 1 and items[0]["from"] == "2026-12-02"
    page = client.get(f"{BASE}/leave-requests?status=pending&limit=1", headers=org.hr).json()
    assert page["pending_total"] == 2 and page["next_cursor"] == "1" and page["items"][0]["from"] == "2026-11-02"
    assert client.get(f"{BASE}/leave-requests", headers=org.faculty).status_code == 403
    assert client.get(f"{BASE}/leave-requests?status=maybe", headers=org.hr).status_code == 422
    assert client.get(f"{BASE}/leave-requests?cursor=x", headers=org.hr).status_code == 400
    mine = client.get(f"{BASE}/me/leave-requests", headers=org.faculty).json()
    assert [x["from"] for x in mine] == ["2026-11-02"]
