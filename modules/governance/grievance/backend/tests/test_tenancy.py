"""Cross-tenant leak test (module standard rule 11): one organisation never sees or changes another's rows."""

from conftest import BASE, Campus
from eos_core.db import new_id
from eos_testing import assert_no_cross_tenant_leak


def token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def seed(client, org) -> tuple[Campus, dict]:
    c = Campus(client, org)
    case = c.file()
    c.decide(case["id"])
    return c, {"case": case["id"], "committee": c.committees["sgrc"]["id"]}


def test_no_cross_tenant_leak(client, org, other_org, clock):
    a, _ = seed(client, org)
    b, _ = seed(client, other_org)
    lists = [
        ("/committees", a.coordinator, b.coordinator),
        ("/grievances", a.member(), b.member()),
    ]
    for path, ha, hb in lists:
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(ha), token(hb))
    # the counts are per organisation: each sees its own single open case
    assert a.ok(a.get("/stats/open", a.viewer))["total_open"] == 1
    assert b.ok(b.get("/stats/open-by-committee", b.coordinator))["total_open"] == 1
    assert {x["committee_id"] for x in b.ok(b.get("/stats/open-by-committee", b.coordinator))["committees"]} == {
        x["id"] for x in b.committees.values()
    }
    # MyGrievance has no organisation_id in the contract, so the helper cannot compare organisations: compare the rows
    mine_a = a.ok(a.get("/me/grievances", a.complainant))["items"]
    mine_b = b.ok(b.get("/me/grievances", b.complainant))["items"]
    assert mine_a and mine_b and not {x["id"] for x in mine_a} & {x["id"] for x in mine_b}


def test_another_organisations_records_are_not_found(client, org, other_org, clock):
    a, ids = seed(client, org)
    b = Campus(client, other_org)
    case, committee = ids["case"], ids["committee"]
    assert b.get(f"/grievances/{case}", b.member()).status_code == 404
    assert b.get(f"/me/grievances/{case}", b.complainant).status_code == 404
    posts = [
        (f"/me/grievances/{case}/updates", {"body": "steal"}, b.complainant),
        (f"/me/grievances/{case}/withdraw", None, b.complainant),
        (f"/grievances/{case}/status", {"status": "closed"}, b.member()),
        (f"/grievances/{case}/updates", {"body": "steal"}, b.member()),
        (f"/grievances/{case}/transfer", {"committee_id": b.committees["icc"]["id"], "reason": "steal"}, b.member()),
    ]
    for path, body, headers in posts:
        assert b.post(path, body, headers).status_code == 404, path
    # B cannot rename A's committee or use it to file
    assert b.patch(f"/committees/{committee}", {"name": "stolen"}).status_code == 404
    mine = {"track": "student_grievance", "committee_id": committee, "category": "x", "description": "d" * 12}
    r = b.post("/me/grievances", mine, b.complainant)
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "committee_not_found")
    # B cannot transfer its own case into A's committee
    own = b.file()
    r = b.post(f"/grievances/{own['id']}/transfer", {"committee_id": committee, "reason": "steal"}, b.member())
    assert r.status_code == 404
    # A's case is intact
    assert a.ok(a.get(f"/grievances/{case}", a.member()))["status"] == "decided"
    assert a.ok(a.get("/committees", a.coordinator))[0]["name"].endswith("committee")


def test_numbers_and_committee_names_are_per_organisation(client, org, other_org, clock):
    a, _ = seed(client, org)
    b, _ = seed(client, other_org)
    assert a.ok(a.get("/me/grievances", a.complainant))["items"][0]["number"] == "GRV-000001"
    assert b.ok(b.get("/me/grievances", b.complainant))["items"][0]["number"] == "GRV-000001"
    assert new_id() not in (a.org.id, b.org.id)
