"""Committees: set-up, members, deactivation (docs/prd.md "Main flows" 1)."""

from conftest import audit
from eos_core.db import new_id


def test_create_and_list_committees(campus):
    c = campus
    person = new_id()
    body = {
        "name": "Second SGRC",
        "kind": "sgrc",
        "members": [{"person_id": person, "role": "external_member"}],
        "active": False,
    }
    made = c.ok(c.post("/committees", body))
    assert made["active"] is False and made["organisation_id"] == c.org.id
    assert made["members"] == [{"person_id": person, "role": "external_member"}]
    assert ("committee.created", None) in audit(c.org.id, made["id"])
    names = [x["name"] for x in c.ok(c.get("/committees"))]
    assert names == sorted(names) and "Second SGRC" in names
    assert [x["kind"] for x in c.ok(c.get("/committees?kind=icc"))] == ["icc"]
    assert "Second SGRC" not in [x["name"] for x in c.ok(c.get("/committees?active=true"))]
    assert [x["name"] for x in c.ok(c.get("/committees?active=false"))] == ["Second SGRC"]


def test_name_is_unique_per_organisation_ignoring_case(campus, other_org):
    c = campus
    r = c.post("/committees", {"name": "SGRC COMMITTEE", "kind": "sgrc"})
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "name_used")
    # another organisation may use the same name
    _, headers = other_org.user("grievance-coordinator")
    assert c.post("/committees", {"name": "sgrc committee", "kind": "sgrc"}, headers).status_code == 201
    r = c.patch(f"/committees/{c.committees['icc']['id']}", {"name": "Sgrc Committee"})
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "name_used")


def test_members_are_shown_to_coordinators_and_their_own_members_only(campus):
    c = campus
    by_name = {x["kind"]: x for x in c.ok(c.get("/committees"))}
    assert all("members" in x for x in by_name.values())
    mine = {x["kind"]: x for x in c.ok(c.get("/committees", c.member("sgrc")))}
    assert "members" in mine["sgrc"] and "members" not in mine["icc"]
    seen = {x["kind"]: x for x in c.ok(c.get("/committees", c.complainant))}
    assert set(seen) == {"sgrc", "anti_ragging", "icc", "ombudsperson"}
    assert all("members" not in x for x in seen.values())


def test_patch_renames_replaces_members_and_keeps_what_is_not_sent(campus):
    c = campus
    sgrc = c.committees["sgrc"]
    new_member = new_id()
    r = c.ok(c.patch(f"/committees/{sgrc['id']}", {"members": [{"person_id": new_member, "role": "member"}]}))
    assert r["members"] == [{"person_id": new_member, "role": "member"}] and r["name"] == sgrc["name"]
    r = c.ok(c.patch(f"/committees/{sgrc['id']}", {"name": "Student Grievance Committee"}))
    assert r["name"] == "Student Grievance Committee" and len(r["members"]) == 1
    actions = [a for a, _ in audit(c.org.id, sgrc["id"])]
    assert "committee.members_changed" in actions and "committee.renamed" in actions
    # the old member lost access
    assert c.get("/grievances", c.member("sgrc")).json() == {"items": [], "next_cursor": None}
    assert c.patch(f"/committees/{new_id()}", {"name": "x"}).status_code == 404
    assert c.patch("/committees/not-a-uuid", {"name": "x"}).status_code == 404


def test_a_committee_with_open_cases_cannot_be_deactivated(campus):
    c = campus
    case = c.file()
    sgrc = c.committees["sgrc"]["id"]
    r = c.patch(f"/committees/{sgrc}", {"active": False})
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "committee_has_open_cases")
    c.ok(c.post(f"/me/grievances/{case['id']}/withdraw", {"reason": "sorted out"}, c.complainant))
    r = c.ok(c.patch(f"/committees/{sgrc}", {"active": False}))
    assert r["active"] is False and ("committee.deactivated", None) in audit(c.org.id, sgrc)
    assert c.ok(c.patch(f"/committees/{sgrc}", {"active": True}))["active"] is True


def test_an_ombudsperson_committee_with_an_appeal_waiting_is_busy(campus, monkeypatch):
    c = campus
    monkeypatch.setenv("GRIEVANCE_APPEAL_WINDOW_DAYS", "10")
    case = c.file()
    c.decide(case["id"])
    c.ok(c.post(f"/me/grievances/{case['id']}/appeal", {"reason": "The findings ignore my evidence."}, c.complainant))
    r = c.patch(f"/committees/{c.committees['ombudsperson']['id']}", {"active": False})
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "committee_has_open_cases")


def test_committee_validation(campus):
    c = campus
    person = new_id()
    dup = [{"person_id": person, "role": "chair"}, {"person_id": person.upper(), "role": "member"}]
    r = c.post("/committees", {"name": "Dup", "kind": "icc", "members": dup})
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "duplicate_member")
    bad = [
        {"name": "", "kind": "icc"},
        {"name": "   ", "kind": "icc"},
        {"name": "x" * 121, "kind": "icc"},
        {"name": "x", "kind": "board"},
        {"name": "x"},
        {"name": "x", "kind": "icc", "extra": 1},
        {"name": "x", "kind": "icc", "members": [{"person_id": "me", "role": "chair"}]},
        {"name": "x", "kind": "icc", "members": [{"person_id": person, "role": "boss"}]},
        {"name": "x", "kind": "icc", "members": "oops"},
        {"name": "x", "kind": "icc", "active": "maybe"},
    ]
    for body in bad:
        assert c.post("/committees", body).status_code == 422, body
    assert c.patch(f"/committees/{c.committees['icc']['id']}", {"name": "x" * 121}).status_code == 422
    assert c.patch(f"/committees/{c.committees['icc']['id']}", {"kind": "sgrc"}).status_code == 422
    assert c.get("/committees?kind=board").status_code == 422
    assert c.get("/committees?active=maybe").status_code == 422
