from __future__ import annotations

from datetime import timedelta

import pytest
from conftest import add_announcement, add_page, make_actor
from eos_core.db import utcnow
from eos_web_portal_cms.application import service as svc
from eos_web_portal_cms.application.service import CmsError
from eos_web_portal_cms.infrastructure.models import Page


def refused(fn, *args, **kwargs) -> tuple[int, str]:
    with pytest.raises(CmsError) as exc:
        fn(*args, **kwargs)
    return exc.value.status, exc.value.code


# ---------------------------------------------------------------- pages


def test_page_lifecycle(db, editor):
    page = svc.create_page(db, editor, slug="about", title="  About us ", type="standard", body="Hello\n<b>world</b>")
    assert (page["title"], page["published"], page["published_at"]) == ("About us", False, None)
    assert page["body"] == "Hello\n<b>world</b>"  # stored as given; plain text, never interpreted
    assert refused(svc.create_page, db, editor, slug="about", title="X", type="landing", body="") == (
        409,
        "duplicate_slug",
    )

    updated = svc.update_page(db, editor, "about", {"title": "About", "seo_description": "Who we are"})
    assert (updated["title"], updated["seo_description"], updated["published"]) == ("About", "Who we are", False)
    assert svc.update_page(db, editor, "about", {"seo_description": None})["seo_description"] is None

    published = svc.publish_page(db, editor, "about", True)
    assert published["published"] is True and published["published_at"] is not None
    assert refused(svc.publish_page, db, editor, "about", True) == (409, "already_published")
    assert svc.publish_page(db, editor, "about", False)["published"] is False
    assert refused(svc.publish_page, db, editor, "about", False) == (409, "not_published")

    svc.delete_page(db, editor, "about")
    assert db.query(Page).filter(Page.organisation_id == editor.organisation_id).count() == 0
    assert refused(svc.get_page, db, editor, "about") == (404, "not_found")


def test_page_lists_for_editors(db, editor):
    org = editor.organisation_id
    now = utcnow()
    old = add_page(db, org, slug="old", updated_at=now - timedelta(days=2))
    new = add_page(db, org, slug="new", type="landing", updated_at=now)
    draft = add_page(db, org, slug="draft", published=False, published_at=None)
    assert [p["slug"] for p in svc.list_pages(db, editor)["items"]] == [new.slug, old.slug]
    assert [p["slug"] for p in svc.list_pages(db, editor, status="draft")["items"]] == [draft.slug]
    assert svc.list_pages(db, editor, status="all")["total"] == 3
    assert svc.list_pages(db, editor, status="published")["total"] == 2
    assert [p["slug"] for p in svc.list_pages(db, editor, type="landing")["items"]] == ["new"]
    page = svc.list_pages(db, editor, status="all", page=2, page_size=2)
    assert (page["total"], len(page["items"])) == (3, 1)


# ---------------------------------------------------------------- announcements


def test_announcement_lifecycle(db, editor):
    start = utcnow() - timedelta(hours=1)
    a = svc.create_announcement(db, editor, title=" Exams ", body="Timetable out", starts_at=start)
    assert (a["title"], a["published"], a["visible"]) == ("Exams", False, False)
    published = svc.publish_announcement(db, editor, a["id"], True)
    assert published["published"] is True and published["visible"] is True
    assert refused(svc.publish_announcement, db, editor, a["id"], True) == (409, "already_published")
    assert svc.update_announcement(db, editor, a["id"], {"ends_at": start + timedelta(minutes=30)})["visible"] is False
    svc.delete_announcement(db, editor, a["id"])
    assert refused(svc.get_announcement, db, editor, a["id"]) == (404, "not_found")


def test_window_is_checked_against_stored_values(db, editor):
    now = utcnow()
    assert refused(svc.create_announcement, db, editor, title="T", body="B", starts_at=now, ends_at=now) == (
        422,
        "invalid_window",
    )
    a = svc.create_announcement(db, editor, title="T", body="B", starts_at=now + timedelta(days=2))
    assert refused(svc.update_announcement, db, editor, a["id"], {"ends_at": now + timedelta(days=1)}) == (
        422,
        "invalid_window",
    )
    cleared = svc.update_announcement(db, editor, a["id"], {"starts_at": None, "ends_at": now + timedelta(days=1)})
    assert cleared["starts_at"] is None


def test_announcement_lists(db, editor):
    org, now = editor.organisation_id, utcnow()
    older = add_announcement(db, org, published_at=now - timedelta(days=1))
    newer = add_announcement(db, org, published_at=now)
    scheduled = add_announcement(db, org, starts_at=now + timedelta(days=1))
    expired = add_announcement(db, org, ends_at=now - timedelta(minutes=1))
    draft = add_announcement(db, org, published=False, published_at=None)
    visible = svc.list_announcements(db, editor)
    assert [a["id"] for a in visible["items"]] == [newer.id, older.id]
    assert all(a["visible"] for a in visible["items"])
    assert {a["id"] for a in svc.list_announcements(db, editor, status="published")["items"]} == {
        older.id,
        newer.id,
        scheduled.id,
        expired.id,
    }
    assert [a["id"] for a in svc.list_announcements(db, editor, status="draft")["items"]] == [draft.id]
    assert svc.list_announcements(db, editor, status="all")["total"] == 5


def test_readers_cannot_ask_for_unpublished_lists(db, reader):
    for status in ("draft", "all"):
        assert refused(svc.list_pages, db, reader, status=status) == (403, "forbidden")
    for status in ("draft", "published", "all"):
        assert refused(svc.list_announcements, db, reader, status=status) == (403, "forbidden")
    # For pages, `published` is exactly what a reader sees by default (contract: GET /pages).
    assert svc.list_pages(db, reader, status="published")["items"] == []


def test_another_organisation_gets_not_found(db, editor, other_org):
    page = add_page(db, editor.organisation_id)
    a = add_announcement(db, editor.organisation_id)
    outsider = make_actor(other_org)
    assert refused(svc.get_page, db, outsider, page.slug) == (404, "not_found")
    assert refused(svc.publish_page, db, outsider, page.slug, False) == (404, "not_found")
    assert refused(svc.delete_announcement, db, outsider, a.id) == (404, "not_found")
    assert svc.list_announcements(db, outsider)["total"] == 0
    elsewhere = svc.create_page(db, outsider, slug=page.slug, title="Same slug elsewhere", type="standard", body="")
    assert elsewhere["slug"] == page.slug and elsewhere["organisation_id"] == other_org
