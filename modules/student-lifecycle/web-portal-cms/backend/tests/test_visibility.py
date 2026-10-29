"""Readers (any signed-in member) never see a draft or an announcement outside its window, not even by id; editors
do (PRD §6 rule 7, decision D5)."""

from __future__ import annotations

from datetime import timedelta

from conftest import APPLICANT, BASE, add_announcement, add_page, headers, seed
from eos_core.db import utcnow


def test_readers_see_only_published_pages(client, org):
    live = seed(add_page, org, slug="live")
    seed(add_page, org, slug="secret", published=False, published_at=None)
    reader, editor = headers(org, APPLICANT), headers(org)
    assert [p["slug"] for p in client.get(f"{BASE}/pages", headers=reader).json()["items"]] == [live.slug]
    assert client.get(f"{BASE}/pages/live", headers=reader).status_code == 200
    assert client.get(f"{BASE}/pages/secret", headers=reader).status_code == 404
    assert client.get(f"{BASE}/pages/secret", headers=editor).status_code == 200


def test_readers_see_only_announcements_in_their_window(client, org):
    now = utcnow()
    live = seed(add_announcement, org)
    hidden = [
        seed(add_announcement, org, published=False, published_at=None),
        seed(add_announcement, org, starts_at=now + timedelta(days=1)),
        seed(add_announcement, org, ends_at=now - timedelta(minutes=1)),
    ]
    reader, editor = headers(org, APPLICANT), headers(org)
    listed = client.get(f"{BASE}/announcements", headers=reader).json()
    assert [a["id"] for a in listed["items"]] == [live.id]
    for a in hidden:
        assert client.get(f"{BASE}/announcements/{a.id}", headers=reader).status_code == 404
        seen = client.get(f"{BASE}/announcements/{a.id}", headers=editor)
        assert seen.status_code == 200 and seen.json()["visible"] is False


def test_readers_may_ask_for_published_pages_but_not_published_announcements(client, org):
    """For pages `published` is what readers see anyway (contract: only draft and all need the manage key); for
    announcements it also shows scheduled and expired ones, so it needs the key."""
    reader = headers(org, APPLICANT)
    assert client.get(f"{BASE}/pages", params={"status": "published"}, headers=reader).status_code == 200
    assert client.get(f"{BASE}/announcements", params={"status": "published"}, headers=reader).status_code == 403


def test_readers_cannot_ask_for_drafts(client, org):
    reader = headers(org, APPLICANT)
    for path in ("/pages", "/announcements"):
        response = client.get(f"{BASE}{path}", params={"status": "draft"}, headers=reader)
        assert response.status_code == 403 and response.json()["detail"]["code"] == "forbidden"
        assert client.get(f"{BASE}{path}", params={"status": "draft"}, headers=headers(org)).status_code == 200
