"""API tests of the catalogue: terms (FR-1, FR-2), programmes (FR-3), curricula (FR-4, FR-5) and courses (FR-6, FR-7),
through the real router, use cases and a throwaway SQLite database."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see test_api_deps.py)")

from conftest import BASE, make_course, make_programme, make_term, ok, outbox  # noqa: E402

ADMIN = "org-admin"


# ---------------------------------------------------------------- terms


def test_create_list_get_and_update_a_term(client, org):
    _, h = org.user(ADMIN)
    term = make_term(client, h)
    assert (term["code"], term["status"], term["organisation_id"]) == ("2026-ODD", "upcoming", org.id)
    listed = ok(client.get(f"{BASE}/terms", headers=h))
    assert (listed["total"], listed["items"][0]["id"]) == (1, term["id"])
    renamed = ok(client.patch(f"{BASE}/terms/{term['id']}", json={"name": "Odd 2026"}, headers=h))
    assert (renamed["name"], renamed["starts_on"]) == ("Odd 2026", "2026-07-01")
    assert ok(client.get(f"{BASE}/terms/{term['id']}", headers=h))["name"] == "Odd 2026"


def test_overlapping_terms_and_duplicate_codes_are_conflicts(client, org):
    _, h = org.user(ADMIN)
    make_term(client, h)
    clash = client.post(
        f"{BASE}/terms", json={"code": "X", "name": "X", "starts_on": "2026-11-30", "ends_on": "2026-12-31"}, headers=h
    )
    assert (clash.status_code, clash.json()["detail"]["code"]) == (409, "term_dates_overlap")
    dup = client.post(
        f"{BASE}/terms",
        json={"code": "2026-ODD", "name": "X", "starts_on": "2027-01-01", "ends_on": "2027-02-01"},
        headers=h,
    )
    assert (dup.status_code, dup.json()["detail"]["code"]) == (409, "duplicate_code")


def test_end_before_start_is_400(client, org):
    _, h = org.user(ADMIN)
    r = client.post(
        f"{BASE}/terms", json={"code": "B", "name": "B", "starts_on": "2026-07-02", "ends_on": "2026-07-01"}, headers=h
    )
    assert (r.status_code, r.json()["detail"]["code"], r.json()["detail"]["details"]["field"]) == (
        400,
        "invalid_term_dates",
        "ends_on",
    )


def test_activating_a_term_closes_the_active_one_and_publishes(client, org):
    _, h = org.user(ADMIN)
    odd = make_term(client, h)
    even = make_term(client, h, code="2027-EVEN", start="2026-12-01", end="2027-04-30")
    assert ok(client.post(f"{BASE}/terms/{odd['id']}/activate", headers=h))["status"] == "active"
    assert ok(client.post(f"{BASE}/terms/{even['id']}/activate", headers=h))["status"] == "active"
    assert ok(client.get(f"{BASE}/terms/{odd['id']}", headers=h))["status"] == "closed"
    activated = [p for n, p, _ in outbox(org.id) if n == "academic-management.term.activated"]
    assert activated[-1]["previous_academic_period_id"] == odd["id"]
    assert ok(client.post(f"{BASE}/terms/{even['id']}/activate", headers=h))["status"] == "active"  # no change
    assert len([n for n, _, _ in outbox(org.id) if n.endswith("term.activated")]) == 2


def test_unknown_term_is_404(client, org):
    _, h = org.user(ADMIN)
    assert client.get(f"{BASE}/terms/no-such-term", headers=h).status_code == 404
    assert client.post(f"{BASE}/terms/no-such-term/activate", headers=h).status_code == 404


# ---------------------------------------------------------------- programmes


def test_programme_lifecycle_and_events(client, org):
    uid, h = org.user(ADMIN)
    p = make_programme(client, h)
    assert (p["status"], p["credits_required"], p["published_curriculum_id"]) == ("active", 8, None)
    updated = ok(client.patch(f"{BASE}/programmes/{p['id']}", json={"credits_required": 10.5}, headers=h))
    assert updated["credits_required"] == 10.5
    archived = ok(client.post(f"{BASE}/programmes/{p['id']}/archive", headers=h))
    assert archived["status"] == "archived"
    assert ok(client.post(f"{BASE}/programmes/{p['id']}/archive", headers=h))["status"] == "archived"  # idempotent
    names = [n.rsplit(".", 2)[-2] + "." + n.rsplit(".", 1)[-1] for n, _, _ in outbox(org.id)]
    assert names == ["programme.created", "programme.updated", "programme.archived"]
    created = outbox(org.id)[0]
    assert created[2] == uid and "organisation_id" not in created[1]


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"level": "bachelor"}, "invalid_choice"),
        ({"duration_terms": 0}, "below_minimum"),
        ({"credits_required": -1}, "below_minimum"),
    ],
)
def test_invalid_programmes_are_400(client, org, change, code):
    _, h = org.user(ADMIN)
    body = {
        "code": "P",
        "name": "P",
        "level": "diploma",
        "department_id": "11111111-1111-4111-8111-111111111111",
        "duration_terms": 2,
        "credits_required": 8,
        **change,
    }
    r = client.post(f"{BASE}/programmes", json=body, headers=h)
    assert (r.status_code, r.json()["detail"]["code"]) == (400, code)


# ---------------------------------------------------------------- courses


def test_course_lifecycle(client, org):
    _, h = org.user(ADMIN)
    c = make_course(client, h)
    assert (c["code"], c["credits"], c["status"]) == ("CS101", 4, "active")
    dup = client.post(
        f"{BASE}/courses",
        json={**{k: c[k] for k in ("code", "title", "credits", "course_type", "department_id")}},
        headers=h,
    )
    assert (dup.status_code, dup.json()["detail"]["code"]) == (409, "duplicate_code")
    assert ok(client.patch(f"{BASE}/courses/{c['id']}", json={"lecture_hours": 3}, headers=h))["lecture_hours"] == 3
    found = ok(client.get(f"{BASE}/courses?q=cs1", headers=h))
    assert found["total"] == 1
    assert ok(client.post(f"{BASE}/courses/{c['id']}/archive", headers=h))["status"] == "archived"
    assert ok(client.get(f"{BASE}/courses?status=archived", headers=h))["total"] == 1


# ---------------------------------------------------------------- curricula


def test_curriculum_versions_items_and_publication(client, org):
    _, h = org.user(ADMIN)
    p = make_programme(client, h, duration_terms=2, credits_required=8)
    c1, c2 = make_course(client, h, "C1", 4), make_course(client, h, "C2", 4)
    items = [
        {"course_id": c1["id"], "programme_term": 1, "category": "core", "credits": 4},
        {"course_id": c2["id"], "programme_term": 2, "category": "elective", "credits": 4},
    ]
    cur = ok(client.post(f"{BASE}/programmes/{p['id']}/curricula", json={"items": items[:1]}, headers=h), 201)
    assert (cur["version"], cur["status"], cur["total_credits"]) == (1, "draft", 4)
    short = client.post(f"{BASE}/curricula/{cur['id']}/publish", headers=h)
    assert (short.status_code, short.json()["detail"]["code"]) == (422, "credits_mismatch")
    replaced = ok(client.put(f"{BASE}/curricula/{cur['id']}", json={"items": items}, headers=h))
    assert [i["course_code"] for i in replaced["items"]] == ["C1", "C2"]
    published = ok(client.post(f"{BASE}/curricula/{cur['id']}/publish", headers=h))
    assert (published["status"], published["total_credits"]) == ("published", 8)
    assert ok(client.get(f"{BASE}/programmes/{p['id']}", headers=h))["published_curriculum_id"] == cur["id"]
    frozen = client.put(f"{BASE}/curricula/{cur['id']}", json={"items": items}, headers=h)
    assert (frozen.status_code, frozen.json()["detail"]["code"]) == (409, "curriculum_published")
    again = client.post(f"{BASE}/curricula/{cur['id']}/publish", headers=h)
    assert again.status_code == 409
    copy = ok(
        client.post(f"{BASE}/programmes/{p['id']}/curricula", json={"copy_from_curriculum_id": cur["id"]}, headers=h),
        201,
    )
    assert (copy["version"], len(copy["items"])) == (2, 2)
    event = [x for n, x, _ in outbox(org.id) if n.endswith("curriculum.published")][0]
    assert event["curriculum_version"] == 1 and "version" not in event and "organisation_id" not in event


@pytest.mark.parametrize(
    ("item", "code", "field"),
    [
        ({"programme_term": 3}, "programme_term_out_of_range", "items[0].programme_term"),
        ({"category": "optional"}, "invalid_choice", "items[0].category"),
        ({"course_id": "99999999-9999-4999-8999-999999999999"}, "unknown_course", "items[0].course_id"),
    ],
)
def test_invalid_curriculum_items_are_400(client, org, item, code, field):
    _, h = org.user(ADMIN)
    p = make_programme(client, h)
    c = make_course(client, h)
    body = {"items": [{"course_id": c["id"], "programme_term": 1, "category": "core", "credits": 4, **item}]}
    r = client.post(f"{BASE}/programmes/{p['id']}/curricula", json=body, headers=h)
    assert (r.status_code, r.json()["detail"]["code"], r.json()["detail"]["details"]["field"]) == (400, code, field)


# ---------------------------------------------------------------- permissions


@pytest.mark.parametrize(
    ("role", "method", "path", "status"),
    [
        ("student", "post", "/terms", 403),  # read-only role cannot write
        ("faculty", "post", "/courses", 403),
        ("examination-staff", "get", "/courses", 200),  # reads the catalogue
        ("department-admin", "post", "/terms", 403),  # terms are the org-admin's
    ],
)
def test_platform_roles_get_exactly_their_grants(client, org, role, method, path, status):
    _, h = org.user(role)
    body = (
        {"code": "Z", "name": "Z", "starts_on": "2030-01-01", "ends_on": "2030-02-01"}
        if path == "/terms"
        else {
            "code": "Z",
            "title": "Z",
            "credits": 1,
            "course_type": "theory",
            "department_id": "11111111-1111-4111-8111-111111111111",
        }
    )
    r = client.request(method.upper(), f"{BASE}{path}", json=body if method == "post" else None, headers=h)
    assert r.status_code == status
