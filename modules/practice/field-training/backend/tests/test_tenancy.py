"""Cross-tenant leak test (module standard rule 11): one organisation never sees or changes another's rows."""

from conftest import BASE, PERIOD, TODAY, Programme
from eos_field_training.infrastructure.models import new_id
from eos_testing import assert_no_cross_tenant_leak


def seed(client, org) -> tuple[Programme, dict]:
    c = Programme(client, org)
    _, me, p = c.active()
    log = c.ok(c.log(p, me), 201)
    final = c.post(f"/placements/{p['id']}/assessments", {"stage": "final", "outcome": "Pass"}, c.supervisor)
    return c, {"me": me, "placement": p["id"], "log": log["id"], "assessment": final.json()["id"]}


def token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def test_no_cross_tenant_leak(client, org, other_org):
    a, a_ids = seed(client, org)
    b, b_ids = seed(client, other_org)
    lists = [
        ("/sites", a.viewer, b.viewer),
        ("/openings", a.viewer, b.viewer),
        ("/openings", a.supervisor, b.supervisor),
        ("/placements", a.viewer, b.viewer),
        ("/placements", a.supervisor, b.supervisor),
        ("/me/placements", a_ids["me"], b_ids["me"]),
    ]
    for path, ha, hb in lists:
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(ha), token(hb))
    trainees_a = client.get(f"{BASE}/me/trainees", headers=a.supervisor).json()
    trainees_b = client.get(f"{BASE}/me/trainees", headers=b.supervisor).json()
    assert {r["placement"]["organisation_id"] for r in trainees_a} == {org.id}
    assert {r["placement"]["organisation_id"] for r in trainees_b} == {other_org.id}
    hours_b = client.get(f"{BASE}/me/hours", headers=b_ids["me"]).json()
    assert hours_b["placement_id"] == b_ids["placement"]


def test_another_organisations_records_are_not_found(client, org, other_org):
    a, ids = seed(client, org)
    b = Programme(client, other_org)
    _, b_trainee = other_org.user("field-training-trainee")
    pid, oid, sid, lid = ids["placement"], a.opening["id"], a.site["id"], ids["log"]
    gets = [
        (f"/sites/{sid}", b.viewer),
        (f"/openings/{oid}", b.viewer),
        (f"/placements/{pid}", b.viewer),
        (f"/placements/{pid}/logs", b.viewer),
        (f"/placements/{pid}/assessments", b.viewer),
        (f"/me/hours?placement_id={pid}", b_trainee),
    ]
    for path, headers in gets:
        assert client.get(f"{BASE}{path}", headers=headers).status_code == 404, path
    reason = {"reason": "Not yours"}
    posts = [
        (f"/openings/{oid}/publish", None, b.coordinator),
        (f"/openings/{oid}/close", None, b.coordinator),
        (f"/openings/{oid}/cancel", reason, b.coordinator),
        (f"/openings/{oid}/apply", None, b_trainee),
        ("/placements", {"opening_id": oid, "trainee_id": new_id()}, b.coordinator),
        ("/openings", {"site_id": sid, "title": "x", **PERIOD, "seats": 1}, b.coordinator),
        (f"/placements/{pid}/decision", {"decision": "rejected", "reason": "Not yours"}, b.coordinator),
        (f"/placements/{pid}/start", None, b.coordinator),
        (f"/placements/{pid}/complete", None, b.coordinator),
        (f"/placements/{pid}/withdraw", reason, b.coordinator),
        (f"/placements/{pid}/logs", {"date": TODAY, "hours": 1, "activities": "x"}, b_trainee),
        (f"/logs/{lid}/verify", None, b.supervisor),
        (f"/logs/{lid}/return", reason, b.supervisor),
        (f"/placements/{pid}/assessments", {"stage": "mid", "outcome": "x"}, b.supervisor),
    ]
    for path, body, headers in posts:
        assert client.post(f"{BASE}{path}", json=body, headers=headers).status_code == 404, path
    patches = [
        (f"/sites/{sid}", {"name": "x"}, b.coordinator),
        (f"/openings/{oid}", {"site_id": sid, "title": "x", **PERIOD, "seats": 1}, b.coordinator),
        (f"/placements/{pid}", {"ends_on": "2026-11-30"}, b.coordinator),
        (f"/logs/{lid}", {"date": TODAY, "hours": 1, "activities": "x"}, b_trainee),
    ]
    for path, body, headers in patches:
        assert client.patch(f"{BASE}{path}", json=body, headers=headers).status_code == 404, path
    # A's records are unchanged.
    assert a.ok(a.get(f"/placements/{pid}", a.coordinator))["status"] == "active"
    assert a.ok(a.get(f"/openings/{oid}", a.coordinator))["status"] == "open"
    assert a.ok(a.get(f"/sites/{sid}", a.coordinator))["name"] == "North Ward"
