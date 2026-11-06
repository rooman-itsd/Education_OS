"""Confidentiality: case content is for the complainant and the committee handling the case, whatever permission a caller
holds (docs/prd.md "Confidentiality and access")."""

from conftest import BASE, audit
from eos_core.db import new_id

TEXT = "A private account that only the committee may read."


def test_only_members_of_the_handling_committee_see_a_case(campus):
    c = campus
    case = c.file(description=TEXT)
    path = f"/grievances/{case['id']}"
    assert c.get(path, c.member("sgrc")).status_code == 200
    for outsider in (c.member("anti_ragging"), c.member("icc"), c.member("ombudsperson")):
        assert c.get(path, outsider).status_code == 404
    # permission without membership, and the people the contract keeps out
    _, stranger = c.org.user("grievance-committee-member")
    for headers in (stranger, c.complainant, c.coordinator, c.viewer):
        r = c.get(path, headers)
        assert r.status_code in (403, 404) and TEXT not in r.text
    assert c.get(f"/grievances/{new_id()}", c.member("sgrc")).status_code == 404
    assert c.get("/grievances/not-a-uuid", c.member("sgrc")).status_code == 404


def test_lists_hold_only_the_callers_committees(campus):
    c = campus
    mine = c.file(description=TEXT)
    c.file("ragging")
    sgrc = c.ok(c.get("/grievances", c.member("sgrc")))
    assert [x["id"] for x in sgrc["items"]] == [mine["id"]]
    assert sgrc["items"][0]["description"] == TEXT and sgrc["items"][0]["complainant_id"] == c.complainant_id
    assert c.ok(c.get("/grievances", c.member("icc")))["items"] == []
    # asking for someone else's committee gives nothing, not an error
    other = c.committees["anti_ragging"]["id"]
    assert c.ok(c.get(f"/grievances?committee_id={other}", c.member("sgrc")))["items"] == []
    _, stranger = c.org.user("grievance-committee-member")
    assert c.ok(c.get("/grievances", stranger)) == {"items": [], "next_cursor": None}


def test_a_member_cannot_change_a_case_of_another_committee(campus):
    c = campus
    case = c.file()
    base = f"/grievances/{case['id']}"
    other = c.member("anti_ragging")
    attempts = [
        ("/status", {"status": "acknowledged"}),
        ("/updates", {"body": "hello"}),
        ("/proceedings", {"kind": "note", "held_on": "2026-11-04", "summary": "note"}),
        ("/decision", {"outcome": "upheld", "findings": "abc"}),
        ("/transfer", {"committee_id": c.committees["icc"]["id"], "reason": "abc"}),
        ("/appeal-decision", {"outcome": "upheld", "outcome_note": "abc"}),
    ]
    for suffix, body in attempts:
        assert c.post(base + suffix, body, other).status_code == 404, suffix
    assert c.ok(c.get(f"/me/grievances/{case['id']}", c.complainant))["status"] == "submitted"


def test_reads_by_members_are_audited(campus):
    c = campus
    case = c.file()
    c.ok(c.get(f"/grievances/{case['id']}", c.member("sgrc")))
    c.ok(c.get("/grievances", c.member("sgrc")))
    actions = [a for a, _ in audit(c.org.id, case["id"])]
    assert actions.count("case.read") == 1 and actions.count("case.listed") == 1
    # a refused read is not a read
    c.get(f"/grievances/{case['id']}", c.member("icc"))
    assert [a for a, _ in audit(c.org.id, case["id"])].count("case.read") == 1


def test_counts_carry_no_case_content(campus):
    c = campus
    c.file(description=TEXT, category="Private category", respondent={"description": "Private name"})
    for path in ("/stats/open-by-committee", "/stats/open"):
        for headers in (c.coordinator, c.viewer):
            r = c.get(path, headers)
            assert r.status_code == 200
            for secret in (TEXT, "Private category", "Private name", c.complainant_id):
                assert secret not in r.text
    assert c.get("/grievances", c.coordinator).status_code == 403
    assert c.get("/grievances", c.viewer).status_code == 403


def test_org_admin_has_no_access_to_case_content(campus):
    c = campus
    case = c.file()
    _, admin = c.org.user("org-admin")
    assert c.get(f"/grievances/{case['id']}", admin).status_code == 403
    assert c.get("/grievances", admin).status_code == 403
    assert c.get("/stats/open", admin).status_code == 403


def test_every_route_needs_a_token_and_its_permission(campus, client):
    """401 without a token, 403 for a caller who lacks the permission the contract names."""
    c = campus
    cid, sgrc = c.committees["sgrc"]["id"], c.committees["sgrc"]["id"]
    case = c.file()["id"]
    routes = [
        ("get", "/committees", None, "viewer"),
        ("post", "/committees", {"name": "N", "kind": "icc"}, "complainant"),
        ("patch", f"/committees/{cid}", {"name": "N"}, "member"),
        ("post", "/me/grievances", {"track": "ragging", "category": "c", "description": "d" * 12}, "viewer"),
        ("get", "/me/grievances", None, "coordinator"),
        ("get", f"/me/grievances/{case}", None, "coordinator"),
        ("post", f"/me/grievances/{case}/updates", {"body": "b"}, "coordinator"),
        ("post", f"/me/grievances/{case}/withdraw", None, "coordinator"),
        ("post", f"/me/grievances/{case}/appeal", {"reason": "r" * 12}, "coordinator"),
        ("get", "/grievances", None, "complainant"),
        ("get", f"/grievances/{case}", None, "complainant"),
        ("post", f"/grievances/{case}/status", {"status": "acknowledged"}, "complainant"),
        ("post", f"/grievances/{case}/updates", {"body": "b"}, "complainant"),
        (
            "post",
            f"/grievances/{case}/proceedings",
            {"kind": "note", "held_on": "2026-11-01", "summary": "sss"},
            "coordinator",
        ),
        ("post", f"/grievances/{case}/decision", {"outcome": "upheld", "findings": "fff"}, "coordinator"),
        ("post", f"/grievances/{case}/transfer", {"committee_id": sgrc, "reason": "rrr"}, "coordinator"),
        ("post", f"/grievances/{case}/appeal-decision", {"outcome": "upheld", "outcome_note": "nnn"}, "coordinator"),
        ("get", "/stats/open-by-committee", None, "complainant"),
        ("get", "/stats/open", None, "member"),
    ]
    callers = {
        "viewer": c.viewer,
        "complainant": c.complainant,
        "coordinator": c.coordinator,
        "member": c.member("sgrc"),
    }
    for method, path, body, lacking in routes:
        kwargs = {"json": body} if body is not None else {}
        anonymous = client.request(method, BASE + path, **kwargs)
        assert anonymous.status_code == 401, (method, path)
        assert anonymous.json()["detail"]["code"] == "unauthenticated"
        refused = client.request(method, BASE + path, headers=callers[lacking], **kwargs)
        assert refused.status_code == 403, (method, path, refused.status_code)
        assert refused.json()["detail"]["code"] == "forbidden"
    bad = client.get(BASE + "/stats/open", headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401


def test_a_token_without_an_organisation_is_refused(client):
    from eos_core.security import create_token

    token = create_token(user_id=new_id(), organisation_id=None, roles=["grievance-viewer"])
    r = client.get(BASE + "/stats/open", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
