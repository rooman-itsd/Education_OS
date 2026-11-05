"""Company records (story O1): create, find, edit, deactivate; every error code of /companies; who may do what."""

import pytest
from pc_support import BASE, code, company, drive, ok, opening


def test_record_find_and_edit_a_company(client, org):
    co = company(
        client,
        org,
        name="  Infosys   Limited ",
        contact_name="Priya",
        contact_email="campus@infosys.example",
        contact_phone="+91 80 1234 5678",
        notes="Prefers January drives",
    )
    assert co["name"] == "Infosys   Limited" and co["active"] is True and co["organisation_id"] == org.id
    assert co["contact_email"] == "campus@infosys.example" and co["drives_count"] == 0 and co["openings_count"] == 0
    got = ok(client.get(f"{BASE}/companies/{co['id']}", headers=org.viewer))
    assert got == co
    found = ok(client.get(f"{BASE}/companies", params={"q": "infosys limited"}, headers=org.officer))
    assert [c["id"] for c in found["items"]] == [co["id"]] and found["next_cursor"] is None
    body = {**co, "name": "Infosys", "website": "http://infosys.example", "industry": " "}
    edited = ok(client.put(f"{BASE}/companies/{co['id']}", json=body, headers=org.officer))
    assert edited["name"] == "Infosys" and edited["website"] == "http://infosys.example" and edited["industry"] is None


def test_deactivate_and_filter_by_active(client, org):
    a, b = company(client, org), company(client, org)
    off = ok(client.put(f"{BASE}/companies/{b['id']}", json={"name": b["name"], "active": False}, headers=org.officer))
    assert off["active"] is False
    active = ok(client.get(f"{BASE}/companies", params={"active": True}, headers=org.officer))["items"]
    inactive = ok(client.get(f"{BASE}/companies", params={"active": False}, headers=org.officer))["items"]
    assert [c["id"] for c in active] == [a["id"]] and [c["id"] for c in inactive] == [b["id"]]
    on = ok(client.put(f"{BASE}/companies/{b['id']}", json={"name": b["name"]}, headers=org.officer))
    assert on["active"] is True  # `active` defaults to true, as the contract says


def test_counts_are_what_the_caller_may_see(client, org):
    co = company(client, org)
    drive(client, org, co)
    drive(client, org, co, schedule=False)
    opening(client, org, co=co)
    opening(client, org, co=co, publish=False)
    officer = ok(client.get(f"{BASE}/companies/{co['id']}", headers=org.officer))
    viewer = ok(client.get(f"{BASE}/companies/{co['id']}", headers=org.viewer))
    assert (officer["drives_count"], officer["openings_count"]) == (2, 2)
    assert (viewer["drives_count"], viewer["openings_count"]) == (1, 1)


def test_company_names_are_unique_per_organisation(client, org, other_org):
    co = company(client, org, name="Wipro")
    assert (
        code(client.post(f"{BASE}/companies", json={"name": " wipro "}, headers=org.officer), 409) == "company_exists"
    )
    other = company(client, org, name="TCS")
    r = client.put(f"{BASE}/companies/{other['id']}", json={"name": "WIPRO"}, headers=org.officer)
    assert code(r, 409) == "company_exists"
    assert (
        ok(client.put(f"{BASE}/companies/{co['id']}", json={"name": "Wipro"}, headers=org.officer))["name"] == "Wipro"
    )
    company(client, other_org, name="Wipro")  # another organisation may use the name


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"name": ""}, "invalid_name"),
        ({"name": "   "}, "invalid_name"),
        ({"name": "x" * 201}, "invalid_name"),
        ({"name": "Acme", "website": "ftp://acme.example"}, "invalid_url"),
        ({"name": "Acme", "website": "acme.example"}, "invalid_url"),
        ({"name": "Acme", "website": "https://acme example"}, "invalid_url"),
        ({"name": "Acme", "contact_email": "not-an-email"}, "invalid_email"),
    ],
)
def test_invalid_company_values(client, org, fields, expected):
    r = client.post(f"{BASE}/companies", json=fields, headers=org.officer)
    assert code(r, 422) == expected
    co = company(client, org)
    assert code(client.put(f"{BASE}/companies/{co['id']}", json=fields, headers=org.officer), 422) == expected


def test_missing_company_is_404(client, org):
    assert code(client.get(f"{BASE}/companies/nope", headers=org.officer), 404) == "not_found"
    assert code(client.put(f"{BASE}/companies/nope", json={"name": "x"}, headers=org.officer), 404) == "not_found"


def test_company_permissions(client, org):
    co = company(client, org)
    for who in ("student", "nobody"):
        assert code(client.get(f"{BASE}/companies", headers=org.headers[who]), 403) == "forbidden"
        assert code(client.get(f"{BASE}/companies/{co['id']}", headers=org.headers[who]), 403) == "forbidden"
    for who in ("viewer", "student", "nobody"):
        assert code(client.post(f"{BASE}/companies", json={"name": "x"}, headers=org.headers[who]), 403) == "forbidden"
        r = client.put(f"{BASE}/companies/{co['id']}", json={"name": "x"}, headers=org.headers[who])
        assert code(r, 403) == "forbidden"
    company(client, org) and ok(client.get(f"{BASE}/companies", headers=org.coordinator))


def test_no_token_is_401(client):
    assert code(client.get(f"{BASE}/companies"), 401) == "unauthenticated"
    assert code(client.get(f"{BASE}/companies", headers={"Authorization": "Bearer junk"}), 401) == "unauthenticated"


def test_company_pages_follow_the_cursor(client, org):
    ids = {company(client, org)["id"] for _ in range(5)}
    seen, cursor, pages = [], None, 0
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        page = ok(client.get(f"{BASE}/companies", params=params, headers=org.officer))
        seen += [c["id"] for c in page["items"]]
        pages += 1
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert pages == 3 and len(seen) == 5 and set(seen) == ids
    for bad in ("abc", "-1", "1.5", "²", "９", "٣", "1234567890"):
        assert (
            code(client.get(f"{BASE}/companies", params={"cursor": bad}, headers=org.officer), 400) == "invalid_cursor"
        )
