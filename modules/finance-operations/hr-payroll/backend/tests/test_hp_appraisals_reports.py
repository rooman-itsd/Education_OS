"""Appraisals from the cycle to completion, and the joinings-and-exits report."""

from hp_support import BASE, employee, outbox


def _cycle(client, org, *employees, cycle="2026-27"):
    r = client.post(
        f"{BASE}/appraisals", json={"cycle": cycle, "employee_ids": [e["id"] for e in employees]}, headers=org.hr
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_self_review_then_rating_then_completed(client, org):
    e = employee(client, org)
    (a,) = _cycle(client, org, e)
    assert a["status"] == "self_review" and a["employee_name"] == e["name"]
    url = f"{BASE}/appraisals/{a['id']}"
    r = client.put(url, json={"rating": 5}, headers=org.faculty)
    assert r.status_code == 403  # nobody rates themselves
    r = client.put(url, json={"rating": 4}, headers=org.dept)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_in_manager_review"
    r = client.put(url, json={"submit": True}, headers=org.faculty)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "self_review_required"
    assert (
        client.put(url, json={"self_review": "Taught four courses"}, headers=org.faculty).json()["status"]
        == "self_review"
    )
    assert client.put(url, json={"submit": True}, headers=org.faculty).json()["status"] == "manager_review"
    r = client.put(url, json={"self_review": "changed"}, headers=org.faculty)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_in_self_review"
    r = client.put(url, json={"self_review": "rewritten by the reviewer"}, headers=org.dept)
    assert r.status_code == 403
    r = client.put(url, json={"reviewer_comments": "Good year", "submit": True}, headers=org.dept)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "rating_required"
    r = client.put(url, json={"rating": 6}, headers=org.dept)
    assert r.status_code == 422
    r = client.put(url, json={"rating": 4, "reviewer_comments": "Good year", "submit": True}, headers=org.dept)
    assert r.status_code == 200 and r.json()["status"] == "completed" and r.json()["reviewer_id"] == org.ids["dept"]
    assert outbox("hr-payroll.appraisal.completed", org.id) == [
        {"organisation_id": org.id, "appraisal_id": a["id"], "employee_id": e["id"], "cycle": "2026-27"}
    ]
    r = client.put(url, json={"rating": 5}, headers=org.dept)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "appraisal_completed"
    assert [x["id"] for x in client.get(f"{BASE}/me/appraisals", headers=org.faculty).json()] == [a["id"]]


def test_appraisal_cycles_and_visibility(client, org):
    a, b = employee(client, org), employee(client, org, who="faculty2")
    _cycle(client, org, a, b)
    r = client.post(f"{BASE}/appraisals", json={"cycle": "2026-27", "employee_ids": [a["id"]]}, headers=org.hr)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "appraisal_exists"
    assert (
        client.post(f"{BASE}/appraisals", json={"cycle": "x", "employee_ids": [a["id"]]}, headers=org.dept).status_code
        == 403
    )
    listed = client.get(f"{BASE}/appraisals?cycle=2026-27&status=self_review", headers=org.manager).json()
    assert {x["employee_id"] for x in listed} == {a["id"], b["id"]}
    assert client.get(f"{BASE}/appraisals", headers=org.faculty).status_code == 403
    theirs = next(x for x in listed if x["employee_id"] == b["id"])
    assert client.get(f"{BASE}/appraisals/{theirs['id']}", headers=org.faculty).status_code == 403
    assert client.get(f"{BASE}/appraisals/{theirs['id']}", headers=org.faculty2).status_code == 200


def test_joinings_and_exits(client, org):
    old = employee(client, org, who=None, joined_on="2020-01-01", department_name="Physics")
    new = employee(client, org, who=None, joined_on="2026-10-05", designation="Lab assistant")
    leaving = employee(client, org, who=None, joined_on="2021-01-01")
    left = employee(client, org, who=None, joined_on="2021-01-01")
    client.post(
        f"{BASE}/employees/{leaving['id']}/exit",
        json={"kind": "retirement", "last_working_day": "2026-11-30"},
        headers=org.hr,
    )
    client.post(
        f"{BASE}/employees/{left['id']}/exit",
        json={"kind": "resignation", "last_working_day": "2026-10-20"},
        headers=org.hr,
    )
    r = client.get(f"{BASE}/reports/joinings-and-exits", headers=org.hr)
    assert r.status_code == 200, r.text
    report = r.json()
    assert (report["from"], report["to"]) == ("2026-10-01", "2026-10-28")
    assert (report["joined"], report["exited"], report["headcount"]) == (1, 1, 3)
    assert report["recent_joinings"] == [
        {
            "employee_id": new["id"],
            "name": new["name"],
            "designation": "Lab assistant",
            "department_name": None,
            "date": "2026-10-05",
        }
    ]
    assert [x["employee_id"] for x in report["recent_exits"]] == [left["id"]]
    assert [(x["employee_id"], x["date"]) for x in report["upcoming_exits"]] == [(leaving["id"], "2026-11-30")]
    r = client.get(f"{BASE}/reports/joinings-and-exits?from=2019-01-01&to=2020-12-31", headers=org.admin)
    assert (
        r.json()["joined"] == 1
        and r.json()["headcount"] == 1
        and r.json()["recent_joinings"][0]["employee_id"] == old["id"]
    )
    r = client.get(f"{BASE}/reports/joinings-and-exits?from=2026-10-10&to=2026-10-01", headers=org.hr)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_range"
    assert client.get(f"{BASE}/reports/joinings-and-exits", headers=org.faculty).status_code == 403
