"""Routes over HTTP: authentication, the permission each route needs, validation, and the contract's status codes
and {code, message} error bodies."""

from __future__ import annotations

import pytest
from conftest import APPLICANT, BASE, ORG_ADMIN, add_announcement, add_page, headers, mint_token, seed
from eos_core.db import new_id

PAGE = {"slug": "about", "title": "About", "type": "standard", "body": "Hello"}
READS = [
    ("get", "/pages", None),
    ("get", "/pages/about", None),
    ("get", "/announcements", None),
    ("get", "/announcements/{id}", None),
]
MANAGES = [
    ("post", "/pages", PAGE),
    ("patch", "/pages/about", {"title": "New"}),
    ("delete", "/pages/about", None),
    ("post", "/pages/about/publish", {"published": True}),
    ("post", "/announcements", {"title": "T", "body": "B"}),
    ("patch", "/announcements/{id}", {"title": "New"}),
    ("delete", "/announcements/{id}", None),
    ("post", "/announcements/{id}/publish", {"published": True}),
]


def call(client, method, path, body, h=None):
    kwargs = {"headers": h or {}}
    if body is not None:
        kwargs["json"] = body
    return client.request(method.upper(), BASE + path.format(id=new_id()), **kwargs)


@pytest.mark.parametrize(("method", "path", "body"), READS + MANAGES)
def test_every_route_needs_a_valid_token_and_an_organisation(client, method, path, body):
    assert call(client, method, path, body).status_code == 401
    forged = {"Authorization": f"Bearer {mint_token(new_id(), ['org-admin'], secret='x' * 40)}"}
    assert call(client, method, path, body, forged).status_code == 401
    assert call(client, method, path, body, headers(None)).status_code == 403


@pytest.mark.parametrize(("method", "path", "body"), MANAGES)
def test_a_member_without_the_editor_role_cannot_change_anything(client, method, path, body):
    for role in (APPLICANT, "student", "no-such-role"):
        assert call(client, method, path, body, headers(new_id(), role)).status_code == 403


@pytest.mark.parametrize("role", [APPLICANT, "student", "faculty", "no-such-role"])
def test_every_organisation_user_can_read_through_the_member_role(client, org, role):
    seed(add_announcement, org)
    response = client.get(f"{BASE}/announcements", headers=headers(org, role))
    assert response.status_code == 200 and response.json()["total"] == 1
    assert client.get(f"{BASE}/pages", headers=headers(org, role)).status_code == 200


def test_page_journey(client, org):
    h = headers(org)
    made = client.post(f"{BASE}/pages", json={**PAGE, "slug": "admissions-2026"}, headers=h)
    assert made.status_code == 201 and made.json()["published"] is False
    again = client.post(f"{BASE}/pages", json={**PAGE, "slug": "admissions-2026"}, headers=h)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "duplicate_slug"
    url = f"{BASE}/pages/admissions-2026"
    assert client.patch(url, json={"body": "Updated"}, headers=h).json()["body"] == "Updated"
    assert client.post(f"{url}/publish", json={"published": True}, headers=h).json()["published"] is True
    twice = client.post(f"{url}/publish", json={"published": True}, headers=h)
    assert twice.status_code == 409 and twice.json()["detail"]["code"] == "already_published"
    assert client.delete(url, headers=h).status_code == 204
    assert client.get(url, headers=h).status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {**PAGE, "slug": "Has Spaces"},
        {**PAGE, "slug": "x" * 121},
        {**PAGE, "type": "signup_marketing"},
        {**PAGE, "title": "   "},
        {**PAGE, "body": "x" * 20001},
        {**PAGE, "seo_description": "x" * 301},
        {"slug": "a", "title": "T", "type": "standard"},
    ],
)
def test_page_validation(client, org, body):
    assert client.post(f"{BASE}/pages", json=body, headers=headers(org)).status_code == 422


def test_update_validation(client, org):
    page = seed(add_page, org)
    url = f"{BASE}/pages/{page.slug}"
    assert client.patch(url, json={}, headers=headers(org)).status_code == 422
    assert client.patch(url, json={"title": None}, headers=headers(org)).status_code == 422
    assert client.get(f"{BASE}/pages/Not_A_Slug", headers=headers(org)).status_code == 422


def test_announcement_journey(client, org):
    h = headers(org, ORG_ADMIN)
    naive = client.post(
        f"{BASE}/announcements", json={"title": "T", "body": "B", "starts_at": "2026-11-01T09:00:00"}, headers=h
    )
    assert naive.status_code == 422
    window = {"title": "T", "body": "B", "starts_at": "2026-11-02T09:00:00Z", "ends_at": "2026-11-01T09:00:00Z"}
    bad = client.post(f"{BASE}/announcements", json=window, headers=h)
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "invalid_window"
    assert client.post(f"{BASE}/announcements", json={"title": "T", "body": "x" * 5001}, headers=h).status_code == 422
    made = client.post(f"{BASE}/announcements", json={"title": "Fees due", "body": "Pay by Friday"}, headers=h)
    assert made.status_code == 201 and made.json()["visible"] is False
    url = f"{BASE}/announcements/{made.json()['id']}"
    assert client.post(f"{url}/publish", json={"published": True}, headers=h).json()["visible"] is True
    assert client.patch(url, json={"title": "Fees due soon"}, headers=h).json()["title"] == "Fees due soon"
    assert client.post(f"{url}/publish", json={"published": False}, headers=h).json()["published"] is False
    assert client.delete(url, headers=h).status_code == 204


def test_list_query_validation(client, org):
    h = headers(org)
    assert client.get(f"{BASE}/announcements", params={"status": "secret"}, headers=h).status_code == 422
    assert client.get(f"{BASE}/pages", params={"type": "signup_marketing"}, headers=h).status_code == 422
    assert client.get(f"{BASE}/pages", params={"page_size": 201}, headers=h).status_code == 422
