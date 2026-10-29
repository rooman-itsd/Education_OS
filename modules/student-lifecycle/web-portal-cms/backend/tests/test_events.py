"""Publish and unpublish go to the outbox with exactly the payload fields in contracts/events.yaml: no organisation_id
(it is on the envelope), no body. Every change is audited."""

from __future__ import annotations

import yaml
from conftest import CONTRACTS, add_announcement, add_page
from eos_core.events import OutboxEvent
from eos_web_portal_cms.application import service as svc
from eos_web_portal_cms.application.service import CmsError
from eos_web_portal_cms.infrastructure.models import AuditEntry

PAYLOADS = {
    ev["name"]: set(ev["payload"])
    for ev in yaml.safe_load((CONTRACTS / "events.yaml").read_text(encoding="utf-8"))["events"]
}


def outbox(db, org) -> list[OutboxEvent]:
    return db.query(OutboxEvent).filter(OutboxEvent.organisation_id == org).order_by(OutboxEvent.occurred_at).all()


def check(event: OutboxEvent, org: str, actor) -> None:
    assert set(event.payload) == PAYLOADS[event.name], event.name
    assert "organisation_id" not in event.payload and "body" not in event.payload
    assert (event.organisation_id, event.actor) == (org, actor.user_id)


def test_page_events(db, editor, org):
    svc.create_page(db, editor, slug="about", title="About", type="standard", body="secret body")
    svc.update_page(db, editor, "about", {"title": "About us"})
    assert outbox(db, org) == []
    svc.publish_page(db, editor, "about", True)
    svc.publish_page(db, editor, "about", False)
    names = [ev.name for ev in outbox(db, org)]
    assert names == ["web-portal-cms.page.published", "web-portal-cms.page.unpublished"]
    for ev in outbox(db, org):
        check(ev, org, editor)
    assert outbox(db, org)[0].payload["title"] == "About us"


def test_announcement_events(db, editor, org):
    a = svc.create_announcement(db, editor, title="Exams", body="secret body")
    svc.publish_announcement(db, editor, a["id"], True)
    svc.publish_announcement(db, editor, a["id"], False)
    assert [ev.name for ev in outbox(db, org)] == [
        "web-portal-cms.announcement.published",
        "web-portal-cms.announcement.unpublished",
    ]
    for ev in outbox(db, org):
        check(ev, org, editor)


def test_deleting_a_published_item_unpublishes_it_first_and_a_draft_emits_nothing(db, editor, org):
    page = add_page(db, org)
    published = add_announcement(db, org)
    draft = add_announcement(db, org, published=False, published_at=None)
    svc.delete_page(db, editor, page.slug)
    svc.delete_announcement(db, editor, published.id)
    svc.delete_announcement(db, editor, draft.id)
    assert [ev.name for ev in outbox(db, org)] == [
        "web-portal-cms.page.unpublished",
        "web-portal-cms.announcement.unpublished",
    ]
    actions = [a.action for a in db.query(AuditEntry).filter(AuditEntry.organisation_id == org)]
    assert actions == ["deleted", "deleted", "deleted"]


def test_every_change_is_audited_and_a_refusal_writes_nothing(db, editor, org):
    svc.create_page(db, editor, slug="about", title="About", type="standard", body="")
    svc.update_page(db, editor, "about", {"body": "x"})
    svc.publish_page(db, editor, "about", True)
    actions = [a.action for a in db.query(AuditEntry).filter(AuditEntry.organisation_id == org)]
    assert actions == ["created", "updated", "published"]
    before = (len(outbox(db, org)), db.query(AuditEntry).filter(AuditEntry.organisation_id == org).count())
    try:
        svc.publish_page(db, editor, "about", True)
    except CmsError as exc:
        assert exc.code == "already_published"
    after = (len(outbox(db, org)), db.query(AuditEntry).filter(AuditEntry.organisation_id == org).count())
    assert before == after
