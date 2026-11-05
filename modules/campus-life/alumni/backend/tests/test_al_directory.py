"""The directory: add (verified by its creator), list and filter, read, full replace, archive and restore."""

import pytest
from al_support import BASE, NOW, add_alumnus, alumnus_body, assigned, code, iso, mentor, outbox


def test_add_records_the_creator_as_verifier(client, org):
    a = add_alumnus(client, org)
    body = alumnus_body()
    for key, value in body.items():
        assert a[key] == value, key
    assert a["organisation_id"] == org.id and a["status"] == "active" and a["active_mentees"] == 0
    assert a["created_by"] == a["verified_by"] == org.ids["coord"]
    assert a["created_at"] == a["verified_at"] == iso(NOW)
    assert a["archived_at"] is None and a["archive_reason"] is None
    assert client.get(f"{BASE}/directory/{a['id']}", headers=org.coord).json() == a
    assert outbox("alumni.alumnus.added", org.id) == [
        {
            "organisation_id": org.id,
            "alumnus_id": a["id"],
            "graduation_year": 2018,
            "is_mentor": False,
            "verified_by": org.ids["coord"],
        }
    ]


def test_add_needs_only_name_and_year(client, org):
    r = client.post(f"{BASE}/directory", json={"full_name": "Kiran", "graduation_year": 2020}, headers=org.coord)
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["is_mentor"] is False and a["email"] is None and a["programme"] is None


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("full_name", "  ", "invalid_name"),
        ("full_name", "x" * 201, "invalid_name"),
        ("graduation_year", 1899, "invalid_graduation_year"),
        ("graduation_year", 2027, "invalid_graduation_year"),  # after the current year (2026 in Asia/Kolkata)
        ("email", "not-an-email", "invalid_email"),
        ("phone", "call me", "invalid_phone"),
        ("linkedin_url", "linkedin.com/in/x", "invalid_url"),
    ],
)
def test_add_refuses_bad_values_with_their_code(client, org, field, value, error):
    r = client.post(f"{BASE}/directory", json=alumnus_body(**{field: value}), headers=org.coord)
    assert r.status_code == 422 and code(r) == error and r.json()["detail"]["field"] == field
    assert outbox("alumni.alumnus.added", org.id) == []


@pytest.mark.parametrize(
    ("field", "limit"),
    [
        ("programme", 200),
        ("current_company", 200),
        ("current_designation", 200),
        ("industry", 200),
        ("city", 200),
        ("notes", 2000),
    ],
)
def test_free_text_has_the_contract_limits(client, org, field, limit):
    ok = client.post(f"{BASE}/directory", json=alumnus_body(**{field: "x" * limit}), headers=org.coord)
    assert ok.status_code == 201
    r = client.post(f"{BASE}/directory", json=alumnus_body(**{field: "x" * (limit + 1)}), headers=org.coord)
    assert r.status_code == 422


def test_unknown_fields_are_refused(client, org):
    r = client.post(f"{BASE}/directory", json=alumnus_body(verified_by=org.ids["coord"]), headers=org.coord)
    assert r.status_code == 422


def test_list_is_newest_first_active_only_and_filters(client, org, clock):
    old = add_alumnus(client, org, full_name="Old Timer", graduation_year=1995, programme="PGDM", is_mentor=True)
    clock.advance(minutes=1)
    mid = add_alumnus(
        client, org, full_name="Meera", current_company="Tata Steel", current_designation="Manager", programme="PGDM"
    )
    clock.advance(minutes=1)
    new = add_alumnus(client, org, full_name="Rahul", current_designation="Head of Treasury", programme="MBA Finance")
    clock.advance(minutes=1)
    gone = add_alumnus(client, org, full_name="Archived One")
    client.post(f"{BASE}/directory/{gone['id']}/archive", headers=org.coord)

    def names(**params):
        r = client.get(f"{BASE}/directory", params=params, headers=org.coord)
        assert r.status_code == 200, r.text
        return [a["full_name"] for a in r.json()["items"]]

    assert names() == ["Rahul", "Meera", "Old Timer"]
    assert names(status="active") == ["Rahul", "Meera", "Old Timer"]
    assert names(status="archived") == ["Archived One"]
    assert names(is_mentor="true") == ["Old Timer"]
    assert names(is_mentor="false") == ["Rahul", "Meera"]
    assert names(graduation_year=1995) == ["Old Timer"]
    assert names(programme="mba finance") == ["Rahul"]
    assert names(q="tata") == ["Meera"]  # company
    assert names(q="TREASURY") == ["Rahul"]  # designation
    assert names(q="meer") == ["Meera"]  # name
    assert names(q="100%") == []  # wildcards are literal
    assert {old["id"], mid["id"], new["id"]} == {
        a["id"] for a in client.get(f"{BASE}/directory", headers=org.coord).json()["items"]
    }
    assert client.get(f"{BASE}/directory", params={"status": "gone"}, headers=org.coord).status_code == 422
    assert client.get(f"{BASE}/directory", params={"q": "x" * 201}, headers=org.coord).status_code == 422


def test_list_pages_with_a_cursor(client, org, clock):
    for i in range(5):
        add_alumnus(client, org, full_name=f"A{i}")
        clock.advance(seconds=1)
    first = client.get(f"{BASE}/directory", params={"limit": 2}, headers=org.coord).json()
    assert [a["full_name"] for a in first["items"]] == ["A4", "A3"] and first["next_cursor"]
    second = client.get(
        f"{BASE}/directory", params={"limit": 2, "cursor": first["next_cursor"]}, headers=org.coord
    ).json()
    third = client.get(
        f"{BASE}/directory", params={"limit": 2, "cursor": second["next_cursor"]}, headers=org.coord
    ).json()
    assert [a["full_name"] for a in second["items"] + third["items"]] == ["A2", "A1", "A0"]
    assert third["next_cursor"] is None
    for bad in ("abc", "-1", ""):
        r = client.get(f"{BASE}/directory", params={"cursor": bad}, headers=org.coord)
        assert r.status_code == 400 and code(r) == "invalid_cursor"
    for bad in (0, 201):
        assert client.get(f"{BASE}/directory", params={"limit": bad}, headers=org.coord).status_code == 422


def test_missing_ids_are_404(client, org):
    for method, path, body in (
        ("get", "/directory/nope", None),
        ("put", "/directory/nope", alumnus_body()),
        ("post", "/directory/nope/archive", None),
        ("post", "/directory/nope/restore", None),
    ):
        r = client.request(method.upper(), f"{BASE}{path}", json=body, headers=org.coord)
        assert r.status_code == 404 and code(r) == "not_found", path


def test_put_is_a_full_replace(client, org):
    a = add_alumnus(client, org, is_mentor=True)
    body = {"full_name": "Ananya R. Rao", "graduation_year": 2019, "is_mentor": True}
    r = client.put(f"{BASE}/directory/{a['id']}", json=body, headers=org.coord)
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["full_name"] == "Ananya R. Rao" and got["graduation_year"] == 2019 and got["is_mentor"] is True
    for cleared in (
        "programme",
        "current_company",
        "current_designation",
        "industry",
        "city",
        "email",
        "phone",
        "linkedin_url",
        "notes",
    ):
        assert got[cleared] is None, cleared
    assert got["created_by"] == a["created_by"] and got["verified_at"] == a["verified_at"]
    assert client.get(f"{BASE}/directory/{a['id']}", headers=org.coord).json() == got
    full = alumnus_body(full_name="Ananya Rao", is_mentor=False)
    again = client.put(f"{BASE}/directory/{a['id']}", json=full, headers=org.coord).json()
    assert again["email"] == full["email"] and again["is_mentor"] is False


def test_put_requires_is_mentor(client, org):
    a = add_alumnus(client, org, is_mentor=True)
    body = alumnus_body()
    del body["is_mentor"]
    r = client.put(f"{BASE}/directory/{a['id']}", json=body, headers=org.coord)
    assert r.status_code == 422
    assert client.get(f"{BASE}/directory/{a['id']}", headers=org.coord).json()["is_mentor"] is True
    for missing in ("full_name", "graduation_year"):
        body = alumnus_body()
        del body[missing]
        assert client.put(f"{BASE}/directory/{a['id']}", json=body, headers=org.coord).status_code == 422


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("full_name", "", "invalid_name"),
        ("graduation_year", 3000, "invalid_graduation_year"),
        ("email", "x@", "invalid_email"),
        ("phone", "12", "invalid_phone"),
        ("linkedin_url", "javascript:alert(1)", "invalid_url"),
    ],
)
def test_put_refuses_bad_values(client, org, field, value, error):
    a = add_alumnus(client, org)
    r = client.put(f"{BASE}/directory/{a['id']}", json=alumnus_body(**{field: value}), headers=org.coord)
    assert r.status_code == 422 and code(r) == error
    assert client.get(f"{BASE}/directory/{a['id']}", headers=org.coord).json() == a


def test_mentor_flag_is_not_cleared_while_mentoring(client, org):
    m = mentor(client, org)
    x = assigned(client, org, m)
    assert client.get(f"{BASE}/directory/{m['id']}", headers=org.coord).json()["active_mentees"] == 1
    r = client.put(f"{BASE}/directory/{m['id']}", json=alumnus_body(is_mentor=False), headers=org.coord)
    assert r.status_code == 409 and code(r) == "mentor_has_active_assignments"
    assert client.get(f"{BASE}/directory/{m['id']}", headers=org.coord).json()["is_mentor"] is True
    # other edits keep the flag and are fine
    assert (
        client.put(f"{BASE}/directory/{m['id']}", json=alumnus_body(is_mentor=True), headers=org.coord).status_code
        == 200
    )
    client.post(f"{BASE}/mentoring/assignments/{x['id']}/end", headers=org.coord)
    r = client.put(f"{BASE}/directory/{m['id']}", json=alumnus_body(is_mentor=False), headers=org.coord)
    assert r.status_code == 200 and r.json()["is_mentor"] is False and r.json()["active_mentees"] == 0


def test_archive_and_restore(client, org, clock):
    a = add_alumnus(client, org)
    clock.advance(hours=1)
    r = client.post(f"{BASE}/directory/{a['id']}/archive", json={"reason": "Asked to be removed"}, headers=org.coord)
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["status"] == "archived" and got["archived_at"] == iso(clock.now)
    assert got["archive_reason"] == "Asked to be removed"
    again = client.post(f"{BASE}/directory/{a['id']}/archive", headers=org.coord)
    assert again.status_code == 409 and code(again) == "alumnus_archived"
    edit = client.put(f"{BASE}/directory/{a['id']}", json=alumnus_body(), headers=org.coord)
    assert edit.status_code == 409 and code(edit) == "alumnus_archived"
    restored = client.post(f"{BASE}/directory/{a['id']}/restore", headers=org.coord)
    assert restored.status_code == 200
    assert restored.json()["status"] == "active" and restored.json()["archived_at"] is None
    assert restored.json()["archive_reason"] is None
    twice = client.post(f"{BASE}/directory/{a['id']}/restore", headers=org.coord)
    assert twice.status_code == 409 and code(twice) == "not_archived"
    assert outbox("alumni.alumnus.archived", org.id) == [{"organisation_id": org.id, "alumnus_id": a["id"]}]
    assert outbox("alumni.alumnus.restored", org.id) == [{"organisation_id": org.id, "alumnus_id": a["id"]}]


def test_archive_without_a_body_and_with_a_long_reason(client, org):
    a = add_alumnus(client, org)
    long = client.post(f"{BASE}/directory/{a['id']}/archive", json={"reason": "x" * 2001}, headers=org.coord)
    assert long.status_code == 422
    r = client.post(f"{BASE}/directory/{a['id']}/archive", headers=org.coord)
    assert r.status_code == 200 and r.json()["archive_reason"] is None


def test_a_mentor_with_an_active_assignment_is_not_archived(client, org):
    m = mentor(client, org)
    x = assigned(client, org, m)
    r = client.post(f"{BASE}/directory/{m['id']}/archive", headers=org.coord)
    assert r.status_code == 409 and code(r) == "mentor_has_active_assignments"
    client.post(f"{BASE}/mentoring/assignments/{x['id']}/end", headers=org.coord)
    assert client.post(f"{BASE}/directory/{m['id']}/archive", headers=org.coord).status_code == 200


@pytest.mark.parametrize("who", ["student", "faculty", "nobody"])
def test_only_staff_use_the_directory(client, org, who):
    a = add_alumnus(client, org)
    h = org.headers[who]
    for method, path, body in (
        ("get", "/directory", None),
        ("get", f"/directory/{a['id']}", None),
        ("post", "/directory", alumnus_body()),
        ("put", f"/directory/{a['id']}", alumnus_body()),
        ("post", f"/directory/{a['id']}/archive", None),
        ("post", f"/directory/{a['id']}/restore", None),
    ):
        r = client.request(method.upper(), f"{BASE}{path}", json=body, headers=h)
        assert r.status_code == 403 and code(r) == "forbidden", (who, path)


def test_no_token_is_401(client):
    assert client.get(f"{BASE}/directory").status_code == 401
    assert client.get(f"{BASE}/directory", headers={"Authorization": "Bearer junk"}).status_code == 401
