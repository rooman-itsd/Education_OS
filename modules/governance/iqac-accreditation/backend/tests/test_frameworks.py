"""Frameworks and metrics (PRD flow 1): create, correct, deactivate, list and filter."""

from conftest import audit, days


def test_framework_create_list_and_filter(desk):
    d = desk
    f = d.framework(code="NAAC", name="NAAC 2025", description="Cycle 4")
    assert f == {
        "id": f["id"],
        "organisation_id": d.org.id,
        "code": "NAAC",
        "name": "NAAC 2025",
        "description": "Cycle 4",
        "active": True,
    }
    nba = d.framework(code="NBA", active=False)
    assert "description" not in nba and nba["active"] is False
    assert [x["code"] for x in d.ok(d.get("/frameworks"))] == ["NAAC", "NBA"]
    assert [x["code"] for x in d.ok(d.get("/frameworks?active=true"))] == ["NAAC"]
    assert [x["code"] for x in d.ok(d.get("/frameworks?active=false"))] == ["NBA"]
    assert audit(d.org.id, f["id"]) == [("framework.created", None)]


def test_framework_code_is_unique_in_the_organisation(desk, other_org):
    d = desk
    d.framework(code="NAAC")
    r = d.post("/frameworks", {"code": "NAAC", "name": "Again"})
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "code_taken")
    # Another organisation may use the same code.
    other = type(d)(d.client, other_org)
    assert other.framework(code="NAAC")["organisation_id"] == other_org.id
    # Renaming onto an existing code is refused the same way.
    nba = d.framework(code="NBA")
    r = d.patch(f"/frameworks/{nba['id']}", {"code": "NAAC"})
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "code_taken")
    assert d.patch(f"/frameworks/{nba['id']}", {"code": "NBA"}).status_code == 200  # its own code is not a clash


def test_framework_patch_changes_only_what_is_sent_and_audits(desk):
    d = desk
    f = d.framework(code="NAAC", name="Old", description="Keep me")
    r = d.ok(d.patch(f"/frameworks/{f['id']}", {"name": "New"}))
    assert (r["name"], r["description"], r["code"]) == ("New", "Keep me", "NAAC")
    assert d.ok(d.patch(f"/frameworks/{f['id']}", {})) == r  # nothing sent, nothing changed
    assert audit(d.org.id, f["id"]) == [("framework.created", None), ("framework.updated", None)]


def test_a_framework_used_by_an_open_cycle_cannot_be_deactivated(desk):
    d = desk
    f = d.framework()
    c = d.cycle(f["id"])
    r = d.patch(f"/frameworks/{f['id']}", {"active": False})
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "framework_in_open_cycle")
    for status, extra in (
        ("collecting", {}),
        ("under_review", {}),
        ("submitted", {"submitted_on": "2026-06-01"}),
    ):
        d.move(c["id"], status, **extra)
        assert d.patch(f"/frameworks/{f['id']}", {"active": False}).status_code == 409, status
    d.move(c["id"], "closed")
    off = d.ok(d.patch(f"/frameworks/{f['id']}", {"active": False}))
    assert off["active"] is False
    assert audit(d.org.id, f["id"])[-1] == ("framework.deactivated", None)
    assert d.ok(d.patch(f"/frameworks/{f['id']}", {"active": True}))["active"] is True


def test_metrics_create_list_filter_and_correct(desk):
    d = desk
    f = d.framework()
    m1 = d.metric(f["id"], code="1.1.1", title="Curriculum design", criterion="Criterion 1", kind="qualitative")
    d.metric(f["id"], code="2.1.1", title="Enrolment", criterion="Criterion 2", unit="students")
    assert m1["framework_id"] == f["id"] and m1["organisation_id"] == d.org.id
    assert "unit" not in m1 and "guidance" not in m1
    assert [m["code"] for m in d.ok(d.get(f"/frameworks/{f['id']}/metrics"))] == ["1.1.1", "2.1.1"]
    assert [m["code"] for m in d.ok(d.get(f"/frameworks/{f['id']}/metrics?criterion=criterion%202"))] == ["2.1.1"]
    dup = d.post(f"/frameworks/{f['id']}/metrics", {"code": "1.1.1", "title": "x", "kind": "qualitative"})
    assert (dup.status_code, dup.json()["detail"]["code"]) == (409, "code_taken")
    r = d.ok(d.patch(f"/metrics/{m1['id']}", {"title": "Curriculum planning", "active": False, "guidance": "See SSR"}))
    assert (r["title"], r["active"], r["guidance"], r["kind"], r["code"]) == (
        "Curriculum planning",
        False,
        "See SSR",
        "qualitative",
        "1.1.1",
    )
    assert [m["code"] for m in d.ok(d.get(f"/frameworks/{f['id']}/metrics?active=false"))] == ["1.1.1"]
    assert audit(d.org.id, m1["id"]) == [("metric.created", None), ("metric.deactivated", None)]
    # The same metric code may be used in another framework.
    assert d.metric(d.framework()["id"], code="1.1.1")["code"] == "1.1.1"


def test_deactivating_a_metric_keeps_existing_responses(desk):
    d = desk
    c = d.collecting()
    q = c["metrics"][0]
    d.ok(d.patch(f"/metrics/{q['id']}", {"active": False}))
    kept = d.ok(d.get(f"/responses/{c['q']['id']}"))
    assert kept["status"] == "pending" and kept["metric_code"] == "Q1"
    # ...but it cannot be assigned again in another cycle.
    other = d.cycle(c["framework"]["id"])
    r = d.post(
        f"/cycles/{other['id']}/assignments",
        {"assignments": [{"metric_id": q["id"], "owner_id": d.alice_id, "due_on": days(5)}]},
    )
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "metric_inactive")


def test_unknown_framework_or_metric_is_not_found(desk):
    from eos_core.db import new_id

    d = desk
    assert d.patch(f"/frameworks/{new_id()}", {"name": "x"}).status_code == 404
    assert d.get(f"/frameworks/{new_id()}/metrics").status_code == 404
    assert (
        d.post(f"/frameworks/{new_id()}/metrics", {"code": "x", "title": "x", "kind": "qualitative"}).status_code == 404
    )
    assert d.patch(f"/metrics/{new_id()}", {"title": "x"}).status_code == 404
