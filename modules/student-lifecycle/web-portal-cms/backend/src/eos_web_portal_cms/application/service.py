"""CMS use cases. Every function works inside the caller's transaction (routes commit), filters every query by the
caller's organisation, and writes an audit row plus, for publish and unpublish, an outbox event in that same
transaction. Event payloads carry ids and title only: never organisation_id (it is on the envelope) or a body."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import sqlalchemy as sa
from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.orm import Session

from ..domain import enums as e
from ..domain import rules
from ..domain.rules import RuleViolationError
from ..infrastructure.models import Announcement, AuditEntry, Page, as_utc, iso

MODULE = "web-portal-cms"
PAGE_MANAGE = "web-portal-cms:page:manage"
ANNOUNCEMENT_MANAGE = "web-portal-cms:announcement:manage"

CODE_STATUS = {
    "not_found": 404,
    "forbidden": 403,
    "duplicate_slug": 409,
    "already_published": 409,
    "not_published": 409,
    "invalid_window": 422,
}


@dataclass
class Actor:
    user_id: str
    organisation_id: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


class CmsError(Exception):
    """A refusal with an HTTP status and the contract's error body {code, message}."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.status = CODE_STATUS.get(code, 422)
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def _check(rule, *args):
    try:
        return rule(*args)
    except RuleViolationError as v:
        raise CmsError(v.code, v.message) from v


def _status_allowed(actor: Actor, status: str, manage_key: str) -> None:
    """Asking to list unpublished content without the manage key is a 403: the filter itself is not allowed."""
    if rules.needs_manage(status) and not actor.can(manage_key):
        raise CmsError("forbidden", f"status={status} needs {manage_key}")


def _audit(db: Session, org: str, actor: Actor, action: str, entity: str, entity_id: str, detail=None) -> None:
    db.add(
        AuditEntry(
            organisation_id=org, actor=actor.user_id, action=action, entity=entity, entity_id=entity_id, detail=detail
        )
    )


def _publish(db: Session, org: str, actor: Actor, name: str, payload: dict) -> None:
    events.publish(db, f"{MODULE}.{name}", org, payload, actor.user_id)


def _paged(query, order_by, page: int, page_size: int, view) -> dict:
    total = query.count()
    rows = query.order_by(*order_by).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [view(r) for r in rows], "total": total, "page": page, "page_size": page_size}


# ---------------------------------------------------------------- pages


def _page_event(db: Session, actor: Actor, page: Page, published: bool) -> None:
    if published:
        payload = {"page_id": page.id, "slug": page.slug, "type": page.type, "title": page.title}
        _publish(db, page.organisation_id, actor, "page.published", payload)
    else:
        _publish(db, page.organisation_id, actor, "page.unpublished", {"page_id": page.id, "slug": page.slug})


def _get_page(db: Session, actor: Actor, slug: str) -> Page:
    """A draft exists only for callers who may manage pages (PRD §6 rule 7)."""
    page = db.query(Page).filter(Page.organisation_id == actor.organisation_id, Page.slug == slug).one_or_none()
    if page is None or (not page.published and not actor.can(PAGE_MANAGE)):
        raise CmsError("not_found", "page not found")
    return page


def list_pages(
    db: Session, actor: Actor, *, type: str | None = None, status: str = e.VISIBLE, page: int = 1, page_size: int = 50
) -> dict:
    _status_allowed(actor, status, PAGE_MANAGE)
    query = db.query(Page).filter(Page.organisation_id == actor.organisation_id)
    if status in (e.VISIBLE, e.PUBLISHED):
        query = query.filter(Page.published.is_(True))
    elif status == e.DRAFT:
        query = query.filter(Page.published.is_(False))
    if type:
        query = query.filter(Page.type == type)
    return _paged(query, (Page.updated_at.desc(), Page.id), page, page_size, Page.to_dict)


def create_page(
    db: Session, actor: Actor, *, slug: str, title: str, type: str, body: str, seo_description: str | None = None
) -> dict:
    org = actor.organisation_id
    if db.query(Page.id).filter(Page.organisation_id == org, Page.slug == slug).first() is not None:
        raise CmsError("duplicate_slug", f"The slug {slug!r} is already used in this organisation")
    now = utcnow()
    page = Page(
        organisation_id=org,
        slug=slug,
        title=title.strip(),
        type=type,
        body=body,
        seo_description=seo_description,
        published=False,
        created_by=actor.user_id,
        updated_by=actor.user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(page)
    db.flush()
    _audit(db, org, actor, "created", "page", page.id, {"slug": slug})
    db.flush()
    return page.to_dict()


def get_page(db: Session, actor: Actor, slug: str) -> dict:
    return _get_page(db, actor, slug).to_dict()


def update_page(db: Session, actor: Actor, slug: str, changes: dict) -> dict:
    page = _get_page(db, actor, slug)
    for name in ("title", "type", "body", "seo_description"):
        if name in changes:
            value = changes[name]
            setattr(page, name, value.strip() if name == "title" else value)
    page.updated_by = actor.user_id
    page.updated_at = utcnow()
    _audit(db, page.organisation_id, actor, "updated", "page", page.id, {"fields": sorted(changes)})
    db.flush()
    return page.to_dict()


def delete_page(db: Session, actor: Actor, slug: str) -> None:
    """A published page publishes page.unpublished first, so consumers holding a copy drop it (PRD D7)."""
    page = _get_page(db, actor, slug)
    if page.published:
        _page_event(db, actor, page, published=False)
    _audit(db, page.organisation_id, actor, "deleted", "page", page.id, {"slug": page.slug})
    db.delete(page)
    db.flush()


def publish_page(db: Session, actor: Actor, slug: str, published: bool) -> dict:
    page = _get_page(db, actor, slug)
    _check(rules.check_publish_change, page.published, published)
    page.published = published
    if published:
        page.published_at = utcnow()
    page.updated_by = actor.user_id
    page.updated_at = utcnow()
    _audit(db, page.organisation_id, actor, "published" if published else "unpublished", "page", page.id)
    _page_event(db, actor, page, published)
    db.flush()
    return page.to_dict()


# ---------------------------------------------------------------- announcements


def _announcement_view(announcement: Announcement, now: datetime | None = None) -> dict:
    visible = rules.is_visible(
        announcement.published, as_utc(announcement.starts_at), as_utc(announcement.ends_at), now or utcnow()
    )
    return announcement.to_dict() | {"visible": visible}


def _announcement_event(db: Session, actor: Actor, a: Announcement, published: bool) -> None:
    if published:
        payload = {"announcement_id": a.id, "title": a.title, "starts_at": iso(a.starts_at), "ends_at": iso(a.ends_at)}
        _publish(db, a.organisation_id, actor, "announcement.published", payload)
    else:
        _publish(db, a.organisation_id, actor, "announcement.unpublished", {"announcement_id": a.id})


def _get_announcement(db: Session, actor: Actor, announcement_id: str) -> Announcement:
    """Without the manage key, a draft or an announcement outside its window does not exist (PRD §6 rule 7)."""
    a = (
        db.query(Announcement)
        .filter(Announcement.organisation_id == actor.organisation_id, Announcement.id == announcement_id)
        .one_or_none()
    )
    if a is None:
        raise CmsError("not_found", "announcement not found")
    if not actor.can(ANNOUNCEMENT_MANAGE) and not rules.is_visible(
        a.published, as_utc(a.starts_at), as_utc(a.ends_at), utcnow()
    ):
        raise CmsError("not_found", "announcement not found")
    return a


def list_announcements(
    db: Session, actor: Actor, *, status: str = e.VISIBLE, page: int = 1, page_size: int = 50
) -> dict:
    _status_allowed(actor, status, ANNOUNCEMENT_MANAGE)
    now = utcnow()
    query = db.query(Announcement).filter(Announcement.organisation_id == actor.organisation_id)
    if status == e.VISIBLE:
        query = query.filter(
            Announcement.published.is_(True),
            sa.or_(Announcement.starts_at.is_(None), Announcement.starts_at <= now),
            sa.or_(Announcement.ends_at.is_(None), Announcement.ends_at > now),
        )
    elif status == e.PUBLISHED:
        query = query.filter(Announcement.published.is_(True))
    elif status == e.DRAFT:
        query = query.filter(Announcement.published.is_(False))
    order = (Announcement.published_at.desc(), Announcement.updated_at.desc(), Announcement.id)
    return _paged(query, order, page, page_size, lambda a: _announcement_view(a, now))


def create_announcement(
    db: Session,
    actor: Actor,
    *,
    title: str,
    body: str,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
) -> dict:
    _check(rules.check_window, starts_at, ends_at)
    now = utcnow()
    a = Announcement(
        organisation_id=actor.organisation_id,
        title=title.strip(),
        body=body,
        starts_at=starts_at,
        ends_at=ends_at,
        published=False,
        created_by=actor.user_id,
        updated_by=actor.user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(a)
    db.flush()
    _audit(db, a.organisation_id, actor, "created", "announcement", a.id, {"title": a.title})
    db.flush()
    return _announcement_view(a, now)


def get_announcement(db: Session, actor: Actor, announcement_id: str) -> dict:
    return _announcement_view(_get_announcement(db, actor, announcement_id))


def update_announcement(db: Session, actor: Actor, announcement_id: str, changes: dict) -> dict:
    """The window is checked from the stored values with the changes applied, so moving one bound is checked too."""
    a = _get_announcement(db, actor, announcement_id)
    starts_at = changes["starts_at"] if "starts_at" in changes else as_utc(a.starts_at)
    ends_at = changes["ends_at"] if "ends_at" in changes else as_utc(a.ends_at)
    _check(rules.check_window, starts_at, ends_at)
    for name in ("title", "body", "starts_at", "ends_at"):
        if name in changes:
            value = changes[name]
            setattr(a, name, value.strip() if name == "title" else value)
    a.updated_by = actor.user_id
    a.updated_at = utcnow()
    _audit(db, a.organisation_id, actor, "updated", "announcement", a.id, {"fields": sorted(changes)})
    db.flush()
    return _announcement_view(a)


def delete_announcement(db: Session, actor: Actor, announcement_id: str) -> None:
    a = _get_announcement(db, actor, announcement_id)
    if a.published:
        _announcement_event(db, actor, a, published=False)
    _audit(db, a.organisation_id, actor, "deleted", "announcement", a.id, {"title": a.title})
    db.delete(a)
    db.flush()


def publish_announcement(db: Session, actor: Actor, announcement_id: str, published: bool) -> dict:
    a = _get_announcement(db, actor, announcement_id)
    _check(rules.check_publish_change, a.published, published)
    now = utcnow()
    a.published = published
    if published:
        a.published_at = now
    a.updated_by = actor.user_id
    a.updated_at = now
    _audit(db, a.organisation_id, actor, "published" if published else "unpublished", "announcement", a.id)
    _announcement_event(db, actor, a, published)
    db.flush()
    return _announcement_view(a, now)
