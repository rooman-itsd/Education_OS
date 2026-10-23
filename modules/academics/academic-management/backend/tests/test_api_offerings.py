"""API tests of offerings and sections (FR-8, FR-9, FR-10) and faculty assignment (FR-11, FR-12), including that
each event is published in the same transaction as its state change."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see test_api_deps.py)")

from conftest import BASE, assign, make_course, make_offering, make_term, ok, open_offering, outbox  # noqa: E402
from eos_core.db import new_id  # noqa: E402

HOD = "department-admin"
PROGRAMME = {
    "name": "P",
    "level": "undergraduate",
    "department_id": "11111111-1111-4111-8111-111111111111",
    "duration_terms": 2,
    "credits_required": 8,
}


def setup(client, org, sections=(("A", 2),)):
    _, h = org.user(HOD)
    _, admin = org.user("org-admin")
    term = make_term(client, admin)
    course = make_course(client, admin)
    offering = make_offering(client, h, course["id"], term["id"], sections)
    return h, offering, course, term


def test_create_offering_with_sections_publishes_offering_and_section_events(client, org):
    h, o, course, term = setup(client, org, (("A", 30), ("B", 25)))
    assert (o["status"], o["course"]["code"], o["enrolled_count"]) == ("planned", "CS101", 0)
    assert [(s["code"], s["capacity"], s["status"], s["enrolled_count"]) for s in o["sections"]] == [
        ("A", 30, "open", 0),
        ("B", 25, "open", 0),
    ]
    names = [n.split(".", 1)[1] for n, _, _ in outbox(org.id) if "offering" in n or "section" in n]
    assert names == ["offering.created", "section.created", "section.created"]
    created = [p for n, p, _ in outbox(org.id) if n.endswith("offering.created")][0]
    assert created["course_code"] == "CS101" and created["course_offering_id"] == o["id"]


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        ({"sections": []}, 400, "sections_required"),
        ({"sections": [{"code": "A", "capacity": 0}]}, 400, "below_minimum"),
        ({"sections": [{"code": "A", "capacity": 2}, {"code": "A", "capacity": 3}]}, 409, "duplicate_code"),
        ({"course_id": "99999999-9999-4999-8999-999999999999"}, 400, "unknown_course"),
    ],
)
def test_invalid_offerings(client, org, body, status, code):
    _, admin = org.user("org-admin")
    term, course = make_term(client, admin), make_course(client, admin)
    full = {
        "course_id": course["id"],
        "academic_period_id": term["id"],
        "sections": [{"code": "A", "capacity": 2}],
        **body,
    }
    r = client.post(f"{BASE}/offerings", json=full, headers=admin)
    assert (r.status_code, r.json()["detail"]["code"]) == (status, code)


def test_an_archived_course_cannot_be_offered(client, org):
    _, admin = org.user("org-admin")
    term, course = make_term(client, admin), make_course(client, admin)
    ok(client.post(f"{BASE}/courses/{course['id']}/archive", headers=admin))
    r = client.post(
        f"{BASE}/offerings",
        json={"course_id": course["id"], "academic_period_id": term["id"], "sections": [{"code": "A", "capacity": 2}]},
        headers=admin,
    )
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "course_archived")


def test_status_transitions_follow_the_contract(client, org):
    h, o, _, _ = setup(client, org)
    no_primary = client.post(f"{BASE}/offerings/{o['id']}/status", json={"status": "open"}, headers=h)
    assert (no_primary.status_code, no_primary.json()["detail"]["code"]) == (409, "primary_required")
    opened = open_offering(client, h, o["id"], new_id())
    assert opened["status"] == "open"
    skip = client.post(f"{BASE}/offerings/{o['id']}/status", json={"status": "completed"}, headers=h)
    assert (skip.status_code, skip.json()["detail"]["code"]) == (409, "invalid_status_transition")
    assert (
        ok(client.post(f"{BASE}/offerings/{o['id']}/status", json={"status": "in_progress"}, headers=h))["status"]
        == "in_progress"
    )
    late = client.post(f"{BASE}/offerings/{o['id']}/sections", json={"code": "Z", "capacity": 5}, headers=h)
    assert (late.status_code, late.json()["detail"]["code"]) == (409, "offering_not_editable")
    changes = [p for n, p, _ in outbox(org.id) if n.endswith("offering.status-changed")]
    assert [(c["from_status"], c["to_status"]) for c in changes] == [("planned", "open"), ("open", "in_progress")]


def test_sections_can_be_added_and_closed_never_deleted(client, org):
    h, o, _, _ = setup(client, org)
    b = ok(client.post(f"{BASE}/offerings/{o['id']}/sections", json={"code": "B", "capacity": 10}, headers=h), 201)
    dup = client.post(f"{BASE}/offerings/{o['id']}/sections", json={"code": "B", "capacity": 10}, headers=h)
    assert dup.status_code == 409
    closed = ok(client.patch(f"{BASE}/sections/{b['id']}", json={"status": "closed", "capacity": 12}, headers=h))
    assert (closed["status"], closed["capacity"]) == ("closed", 12)
    listed = ok(client.get(f"{BASE}/offerings/{o['id']}/sections", headers=h))
    assert [s["code"] for s in listed["items"]] == ["A", "B"]  # the closed section stays
    assert client.delete(f"{BASE}/sections/{b['id']}", headers=h).status_code == 405  # no delete operation exists
    bad = client.patch(f"{BASE}/sections/{b['id']}", json={"capacity": 0}, headers=h)
    assert (bad.status_code, bad.json()["detail"]["code"]) == (400, "below_minimum")


def test_faculty_assignment_rules(client, org):
    h, o, _, _ = setup(client, org)
    lead, ta = new_id(), new_id()
    section_a = o["sections"][0]["id"]
    open_offering(client, h, o["id"], lead)
    second = client.post(
        f"{BASE}/offerings/{o['id']}/faculty-assignments",
        json={"faculty_id": new_id(), "role": "primary", "contact_hours": 2},
        headers=h,
    )
    assert (second.status_code, second.json()["detail"]["code"]) == (409, "primary_already_assigned")
    helper = assign(client, h, o["id"], ta, role="teaching_assistant", hours=2, section_id=section_a)
    assert (helper["section_id"], helper["contact_hours"], helper["status"]) == (section_a, 2, "active")
    wrong = client.post(
        f"{BASE}/offerings/{o['id']}/faculty-assignments",
        json={"faculty_id": ta, "role": "co_instructor", "contact_hours": 1, "section_id": new_id()},
        headers=h,
    )
    assert (wrong.status_code, wrong.json()["detail"]["code"]) == (400, "section_not_in_offering")
    primary_id = ok(client.get(f"{BASE}/offerings/{o['id']}/faculty-assignments", headers=h))["items"][0]["id"]
    keep = client.post(f"{BASE}/faculty-assignments/{primary_id}/end", headers=h)
    assert (keep.status_code, keep.json()["detail"]["code"]) == (409, "primary_required")
    ended = ok(client.post(f"{BASE}/faculty-assignments/{helper['id']}/end", headers=h))
    assert ended["status"] == "ended"
    twice = client.post(f"{BASE}/faculty-assignments/{helper['id']}/end", headers=h)
    assert (twice.status_code, twice.json()["detail"]["code"]) == (409, "assignment_ended")
    assert ok(client.get(f"{BASE}/offerings/{o['id']}/faculty-assignments", headers=h))["total"] == 1
    assert ok(client.get(f"{BASE}/offerings/{o['id']}/faculty-assignments?include_ended=true", headers=h))["total"] == 2
    created = [p for n, p, _ in outbox(org.id) if n.endswith("faculty-assignment.created")]
    assert created[0]["faculty_id"] == lead and "organisation_id" not in created[0]


def test_listing_offerings_by_filter(client, org):
    h, o, course, term = setup(client, org)
    lead = new_id()
    assign(client, h, o["id"], lead)
    assert ok(client.get(f"{BASE}/offerings?academic_period_id={term['id']}", headers=h))["total"] == 1
    assert ok(client.get(f"{BASE}/offerings?faculty_id={lead}", headers=h))["total"] == 1
    assert ok(client.get(f"{BASE}/offerings?faculty_id={new_id()}", headers=h))["total"] == 0
    assert ok(client.get(f"{BASE}/offerings?department_id={course['department_id']}", headers=h))["total"] == 1


# ---------------------------------------------------------------- events share the transaction


def test_a_refused_change_writes_no_event(client, org):
    h, o, _, _ = setup(client, org)
    before = outbox(org.id)
    r = client.post(f"{BASE}/offerings/{o['id']}/status", json={"status": "open"}, headers=h)  # no primary
    assert r.status_code == 409
    assert outbox(org.id) == before


def test_an_event_is_written_only_if_its_change_commits(client, org, monkeypatch):
    """The event is added to the same session as the change; if the commit fails, neither survives."""
    from eos_academic_management.application import service

    h, o, _, _ = setup(client, org)
    before = outbox(org.id)

    def failing_commit(self):
        raise RuntimeError("database went away")

    monkeypatch.setattr("sqlalchemy.orm.Session.commit", failing_commit)
    with pytest.raises(RuntimeError):
        client.post(f"{BASE}/offerings/{o['id']}/sections", json={"code": "C", "capacity": 5}, headers=h)
    monkeypatch.undo()
    assert outbox(org.id) == before
    assert [s["code"] for s in ok(client.get(f"{BASE}/offerings/{o['id']}/sections", headers=h))["items"]] == ["A"]
    assert service.MODULE == "academic-management"


def test_programme_ids_must_be_programmes_of_the_organisation(client, org, other_org):
    """An unknown programme, including another organisation's, is 422 unknown_programme naming the item; on create
    and on update. A known one is stored."""
    h, o, course, term = setup(client, org)
    _, admin = org.user("org-admin")
    _, other_admin = other_org.user("org-admin")
    mine = ok(client.post(f"{BASE}/programmes", json={**PROGRAMME, "code": "MINE"}, headers=admin), 201)
    theirs = ok(client.post(f"{BASE}/programmes", json={**PROGRAMME, "code": "THEIRS"}, headers=other_admin), 201)
    body = {"course_id": course["id"], "academic_period_id": term["id"], "sections": [{"code": "Z", "capacity": 1}]}
    for bad in (theirs["id"], new_id()):
        r = client.post(f"{BASE}/offerings", json={**body, "programme_ids": [mine["id"], bad]}, headers=h)
        detail = r.json()["detail"]
        assert (r.status_code, detail["code"], detail["details"]["field"]) == (
            422,
            "unknown_programme",
            "programme_ids[1]",
        )
        r = client.patch(f"{BASE}/offerings/{o['id']}", json={"programme_ids": [bad]}, headers=h)
        assert (r.status_code, r.json()["detail"]["code"]) == (422, "unknown_programme")
    assert ok(client.get(f"{BASE}/offerings?programme_id={theirs['id']}", headers=h))["total"] == 0
    created = ok(client.post(f"{BASE}/offerings", json={**body, "programme_ids": [mine["id"]]}, headers=h), 201)
    assert created["programme_ids"] == [mine["id"]]
    assert ok(client.patch(f"{BASE}/offerings/{o['id']}", json={"programme_ids": [mine["id"]]}, headers=h))[
        "programme_ids"
    ] == [mine["id"]]
