"""Course spaces, content units and materials (FR-1 to FR-5): who may do what, lifecycles, visibility, events and
audit entries."""

from conftest import BASE, FACULTY, HEAD, STUDENT, Course, audit_actions, deliver, offering_created, outbox
from eos_lms.application import consumers as cons
from eos_lms.infrastructure.models import new_id


def test_create_course_space_publishes_and_audits(client, org):
    c = Course(client, org)
    created = outbox("lms.course-space.created", org.id)
    assert created == [
        {
            "organisation_id": org.id,
            "course_space_id": c.space["id"],
            "course_offering_id": c.offering,
            "title": "Programming",
            "visible_section_ids": [],
        }
    ]
    assert audit_actions(org.id, c.space["id"]) == ["course-space.activated", "course-space.created"]
    assert c.space["course_code"] == "CS101" and c.space["department_id"] == c.department
    assert c.space["status"] == "active" and c.space["caller_is_instructor"] is False


def test_only_one_space_per_offering_and_only_known_offerings(course):
    c = course
    r = c.call("POST", "/course-spaces", {"course_offering_id": c.offering, "title": "Again"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "course_space_exists"
    r = c.call("POST", "/course-spaces", {"course_offering_id": new_id(), "title": "Unknown"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "unknown_course_offering"
    # Only an LMS administrator creates (owner decision C17).
    other = new_id()
    deliver(c.org.id, cons.OFFERING_CREATED, offering_created(other))
    assert c.call("POST", "/course-spaces", {"course_offering_id": other, "title": "x"}, c.teacher).status_code == 403
    assert c.call("POST", "/course-spaces", {"course_offering_id": other, "title": "x"}).status_code == 201


def test_listing_course_spaces_by_scope(client, org, course):
    c = course
    second = Course(client, org)
    assert {s["id"] for s in c.get("/course-spaces", c.admin)["items"]} == {c.space["id"], second.space["id"]}
    assert {s["id"] for s in c.get("/course-spaces", c.viewer)["items"]} == {c.space["id"], second.space["id"]}
    mine = c.get("/course-spaces", c.teacher)
    assert [s["id"] for s in mine["items"]] == [c.space["id"]] and mine["total"] == 1
    assert mine["items"][0]["caller_is_instructor"] is True
    assert [s["id"] for s in c.get("/course-spaces", c.student)["items"]] == [c.space["id"]]
    assert c.get(f"/course-spaces?department_id={second.department}", c.admin)["items"][0]["id"] == second.space["id"]
    assert c.get("/course-spaces?status=draft", c.admin)["items"] == []
    assert c.get("/course-spaces?limit=1&offset=1", c.admin)["total"] == 2
    assert len(c.get("/course-spaces?limit=1&offset=1", c.admin)["items"]) == 1
    _, head = org.user(HEAD)
    assert c.get("/course-spaces", head)["items"] == []  # department scope waits for LQ13


def test_students_do_not_see_a_draft_space(client, org):
    c = Course(client, org)
    offering = new_id()
    deliver(org.id, cons.OFFERING_CREATED, offering_created(offering))
    draft = c.post("/course-spaces", {"course_offering_id": offering, "title": "Draft"}, 201)
    person, student = org.user(STUDENT)
    from conftest import registration_confirmed

    deliver(org.id, cons.REGISTRATION_CONFIRMED, registration_confirmed(offering, person, new_id()))
    assert c.call("GET", f"/course-spaces/{draft['id']}", headers=student).status_code == 404
    assert c.get("/course-spaces", student)["items"] == []
    c.post(f"/course-spaces/{draft['id']}/status", {"status": "active"})
    assert c.get(f"/course-spaces/{draft['id']}", student)["status"] == "active"


def test_reading_a_space_needs_membership_or_read_all(course, org):
    c = course
    _, outsider = org.user(STUDENT)
    r = c.call("GET", f"/course-spaces/{c.space['id']}", headers=outsider)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "not_in_scope"
    assert c.get(f"/course-spaces/{c.space['id']}", c.viewer)["id"] == c.space["id"]
    assert c.call("GET", f"/course-spaces/{new_id()}", headers=c.viewer).status_code == 404
    assert c.call("GET", "/course-spaces/not-a-uuid", headers=c.viewer).status_code == 404


def test_space_settings_and_lifecycle(course, org):
    c = course
    body = {"title": "Programming I", "description": "Intro", "visible_section_ids": [c.section_a]}
    updated = c.patch(f"/course-spaces/{c.space['id']}", body, c.teacher)
    assert updated["title"] == "Programming I" and updated["visible_section_ids"] == [c.section_a]
    # Section B no longer sees the space.
    assert c.call("GET", f"/course-spaces/{c.space['id']}", headers=c.student_b).status_code == 403
    _, stranger = org.user(FACULTY)
    assert c.call("PATCH", f"/course-spaces/{c.space['id']}", {"title": "x"}, stranger).status_code == 403
    assert c.call("PATCH", f"/course-spaces/{c.space['id']}", {"title": "x"}, c.student).status_code == 403
    r = c.call("POST", f"/course-spaces/{c.space['id']}/status", {"status": "active"}, c.teacher)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "invalid_status"
    c.post(f"/course-spaces/{c.space['id']}/status", {"status": "archived"}, headers=c.teacher)
    for method, path, payload in (
        ("PATCH", f"/course-spaces/{c.space['id']}", {"title": "x"}),
        ("POST", f"/course-spaces/{c.space['id']}/units", {"title": "x"}),
        ("POST", f"/course-spaces/{c.space['id']}/materials", {"material_type": "page", "title": "x", "body": "b"}),
    ):
        r = c.call(method, path, payload, c.teacher)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "course_space_archived", path
    assert c.call("POST", f"/course-spaces/{c.space['id']}/status", {"status": "draft"}).status_code == 400


def test_units_order_publish_and_hide_from_students(course):
    c = course
    base = f"/course-spaces/{c.space['id']}/units"
    w1 = c.post(base, {"title": "Week 1", "published": True}, 201, c.teacher)
    w2 = c.post(base, {"title": "Week 2"}, 201, c.teacher)
    assert (w1["position"], w2["position"]) == (0, 1)
    assert [u["title"] for u in c.get(base, c.teacher)["items"]] == ["Week 1", "Week 2"]
    assert [u["title"] for u in c.get(base, c.student)["items"]] == ["Week 1"]
    c.patch(f"/units/{w2['id']}", {"position": 0, "published": True, "title": "Week 0"}, c.teacher)
    assert [u["title"] for u in c.get(base, c.student)["items"]] == ["Week 0", "Week 1"]
    assert c.call("PATCH", f"/units/{w2['id']}", {"title": "x"}, c.student).status_code == 403
    assert c.call("PATCH", f"/units/{new_id()}", {"title": "x"}, c.teacher).status_code == 404
    assert c.call("PATCH", f"/units/{w2['id']}", {"position": -1}, c.teacher).status_code == 400
    assert [u["position"] for u in c.get(base, c.teacher)["items"]] == [0, 1]
    assert audit_actions(c.org.id, w2["id"]) == ["content-unit.created", "content-unit.published"]


def test_materials_kinds_lifecycle_and_events(course):
    c = course
    base = f"/course-spaces/{c.space['id']}/materials"
    for body in (
        {"material_type": "document", "title": "x"},
        {"material_type": "link", "title": "x", "url": "ftp://example.org"},
        {"material_type": "page", "title": "x", "body": "   "},
        {"material_type": "video", "title": "x"},
    ):
        assert c.call("POST", base, body, c.teacher).status_code == 400, body
    link = c.post(base, {"material_type": "link", "title": "Docs", "url": "https://docs.python.org"}, 201, c.teacher)
    assert link["status"] == "draft" and link["published_at"] is None and "unit_id" not in link
    assert c.call("GET", f"/materials/{link['id']}", headers=c.student).status_code == 404
    published = c.post(f"/materials/{link['id']}/status", {"status": "published"}, headers=c.teacher)
    assert published["status"] == "published" and published["published_at"]
    assert outbox("lms.material.published", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "material_id": link["id"],
        "course_space_id": c.space["id"],
        "course_offering_id": c.offering,
        "unit_id": None,
        "material_type": "link",
        "title": "Docs",
        "visible_section_ids": [],
        "published_at": published["published_at"],
    }
    assert c.get(f"/materials/{link['id']}", c.student)["url"] == "https://docs.python.org"
    r = c.call("POST", f"/materials/{link['id']}/status", {"status": "published"}, c.teacher)
    assert r.status_code == 409
    c.post(f"/materials/{link['id']}/status", {"status": "unpublished"}, headers=c.teacher)
    assert c.call("GET", f"/materials/{link['id']}", headers=c.student).status_code == 404
    assert c.get(f"{base}?material_type=link", c.teacher)["total"] == 1
    assert c.get(base, c.student)["items"] == []
    # Editing keeps the kind's content rule.
    assert c.call("PATCH", f"/materials/{link['id']}", {"url": None}, c.teacher).status_code == 400
    page = c.material("A page")
    r = c.call("PATCH", f"/materials/{page['id']}", {"body": "  "}, c.teacher)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "invalid_material"
    assert c.patch(f"/materials/{link['id']}", {"title": "Python docs"}, c.teacher)["title"] == "Python docs"
    assert audit_actions(c.org.id, link["id"]) == [
        "material.created",
        "material.published",
        "material.unpublished",
        "material.updated",
    ]  # sorted


def test_material_units_must_belong_to_the_space(client, org, course):
    c = course
    other = Course(client, org)
    foreign = other.post(f"/course-spaces/{other.space['id']}/units", {"title": "Theirs"}, 201, other.teacher)
    body = {"material_type": "page", "title": "x", "body": "b", "unit_id": foreign["id"]}
    r = c.call("POST", f"/course-spaces/{c.space['id']}/materials", body, c.teacher)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "unknown_unit"
    m = c.material()
    assert c.call("PATCH", f"/materials/{m['id']}", {"unit_id": foreign["id"]}, c.teacher).status_code == 422
    # Another space's instructor cannot touch this space's material.
    assert c.call("PATCH", f"/materials/{m['id']}", {"title": "x"}, other.teacher).status_code == 403


def test_section_limited_materials(course):
    c = course
    only_b = c.material("B only", visible_section_ids=[c.section_b])
    assert c.call("GET", f"/materials/{only_b['id']}", headers=c.student).status_code == 404
    assert c.get(f"/materials/{only_b['id']}", c.student_b)["id"] == only_b["id"]
    assert c.get(f"/materials/{only_b['id']}", c.viewer)["id"] == only_b["id"]


def test_unauthenticated_is_refused(client, course):
    for path in ("/course-spaces", f"/course-spaces/{course.space['id']}/materials"):
        assert client.get(f"{BASE}{path}").status_code == 401
    r = client.post(f"{BASE}/course-spaces", json={}, headers={"Authorization": "Basic x"})
    assert r.status_code == 401 and r.json()["detail"]["code"] == "unauthenticated"
