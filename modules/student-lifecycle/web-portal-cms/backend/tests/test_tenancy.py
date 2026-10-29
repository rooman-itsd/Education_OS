"""Module standard rule 11: one organisation never reads or changes another's pages or announcements."""

from __future__ import annotations

from conftest import BASE, add_announcement, add_page, headers, mint_token, seed
from eos_core.db import new_id
from eos_testing import assert_no_cross_tenant_leak


def token(org: str) -> str:
    return mint_token(org, ["applicant"])


def test_no_cross_tenant_leak_on_lists(client):
    org_a, org_b = new_id(), new_id()
    for org in (org_a, org_b):
        for _ in range(2):
            seed(add_page, org)
            seed(add_announcement, org)
    assert_no_cross_tenant_leak(client, f"{BASE}/pages", token(org_a), token(org_b))
    assert_no_cross_tenant_leak(client, f"{BASE}/announcements", token(org_a), token(org_b))


def test_another_organisation_cannot_touch_anything_by_id(client):
    org_a, org_b = new_id(), new_id()
    page = seed(add_page, org_a, slug="about")
    a = seed(add_announcement, org_a)
    h = headers(org_b, "org-admin")
    attempts = [
        client.get(f"{BASE}/pages/about", headers=h),
        client.patch(f"{BASE}/pages/about", json={"title": "x"}, headers=h),
        client.post(f"{BASE}/pages/about/publish", json={"published": False}, headers=h),
        client.delete(f"{BASE}/pages/about", headers=h),
        client.get(f"{BASE}/announcements/{a.id}", headers=h),
        client.patch(f"{BASE}/announcements/{a.id}", json={"title": "x"}, headers=h),
        client.post(f"{BASE}/announcements/{a.id}/publish", json={"published": False}, headers=h),
        client.delete(f"{BASE}/announcements/{a.id}", headers=h),
    ]
    assert [r.status_code for r in attempts] == [404] * len(attempts)
    owner = headers(org_a)
    assert client.get(f"{BASE}/pages/{page.slug}", headers=owner).json()["published"] is True
    assert client.get(f"{BASE}/announcements/{a.id}", headers=owner).json()["published"] is True
    assert (
        client.post(
            f"{BASE}/pages", json={"slug": "about", "title": "B", "type": "standard", "body": ""}, headers=h
        ).status_code
        == 201
    )
