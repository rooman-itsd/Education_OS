"""Use cases of knowledge-base (docs/prd.md, contracts/openapi.yaml). Each one checks the caller's permission and the
domain rules, changes state, writes an audit entry, and publishes the matching event from contracts/events.yaml to the
outbox in the same transaction. Event payloads carry ids, slug, revision number, type, category and audience only;
titles, bodies, feedback and reader ids are never published (PRD rule).

Writes to one article lock its row first (repository.article_for_update), so revision numbers, the open revision and
the vote counts change one request at a time.

Where the contract leaves a detail open, the choice made here is noted at the function. Choices that apply throughout:
- Audience is enforced in every read: an article whose content the caller may not read is "not found" (404), never
  403, so its existence is not revealed.
- Submit and return notify editors and authors through notification in the PRD; there is no notification SDK yet
  (packages/sdk is empty), so v1 records both steps in the audit table only.
- Writing a staff article needs knowledge-base:article:read-internal as well, so an author never writes content they
  could not read back."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime, timedelta

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import articles as rules
from ..domain import categories as tree
from ..domain import search
from ..domain.errors import DomainRuleError
from ..domain.stats import PERIOD_DAYS, Candidate, top_articles
from ..infrastructure import repository as repo
from ..infrastructure.config import load_settings
from ..infrastructure.models import Article, AuditEntry, Category, Feedback, Revision
from .access import (
    ARTICLE_PUBLISH,
    ARTICLE_READ,
    ARTICLE_WRITE,
    CATEGORY_MANAGE,
    MODULE,
    READ_INTERNAL,
    STATS_READ,
    Actor,
    require,
)
from .errors import KnowledgeBaseError, forbidden, from_domain

CATEGORY, ARTICLE, REVISION = "category", "article", "revision"  # audit entities
SORTS = ("relevance", "newest", "popular", "helpful", "title")
# Every id this module hands out is a uuid; anything else names no row, and is answered without a query (a NUL byte
# in a path would otherwise reach Postgres, which cannot compare it).
ID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


def today() -> date:
    return clock().astimezone(UTC).date()


# ---------------------------------------------------------------- helpers


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; everything stored is UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | None) -> str | None:
    return None if value is None else as_utc(value).isoformat()


def _day(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _not_found(what: str) -> KnowledgeBaseError:
    return KnowledgeBaseError(404, "not_found", f"{what} not found")


def _invalid(code: str, message: str, field: str | None = None) -> KnowledgeBaseError:
    return KnowledgeBaseError(422, code, message, field=field)


def _conflict(code: str, message: str, field: str | None = None) -> KnowledgeBaseError:
    return KnowledgeBaseError(409, code, message, field=field)


def _domain(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except DomainRuleError as err:
        raise from_domain(err) from err


def _audit(db: Session, actor: Actor, action: str, entity: str, entity_id: str, reason: str | None = None) -> None:
    db.add(
        AuditEntry(
            organisation_id=actor.organisation_id,
            actor=actor.user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            reason=reason,
            occurred_at=clock(),
        )
    )


def _publish(db: Session, actor: Actor, name: str, payload: dict) -> None:
    events.publish(
        db,
        f"{MODULE}.article.{name}",
        actor.organisation_id,
        {"organisation_id": actor.organisation_id, **payload},
        actor=actor.user_id,
    )


def _article(db: Session, article_id: str, *, lock: bool = False) -> Article:
    if not ID.match(article_id):
        raise _not_found("article")
    article = repo.article_for_update(db, article_id) if lock else repo.get(db, Article, article_id)
    if article is None:
        raise _not_found("article")
    return article


def _rev(db: Session, article: Article, number: int | None) -> Revision | None:
    return None if number is None else repo.revision(db, article.id, number)


def _display_no(article: Article) -> int | None:
    """The revision that stands for the article in lists and audience checks: the published one, otherwise the open
    one, otherwise the latest."""
    return article.published_revision_no or article.open_revision_no or article.last_revision_no or None


def _visible(db: Session, actor: Actor, article: Article) -> Revision:
    """The article's display revision, or 404 when the caller may not read its audience."""
    rev = _rev(db, article, _display_no(article))
    if rev is None or not actor.may_read(rev.audience):
        raise _not_found("article")
    return rev


def _check_may_write_audience(actor: Actor, audience: str) -> None:
    if not actor.may_read(audience):
        raise forbidden(f"writing a staff article needs {READ_INTERNAL}")


def _check_category(db: Session, category_id: str) -> None:
    """422 "Inactive category" (and an unknown one)."""
    category = repo.get(db, Category, category_id)
    if category is None:
        raise _invalid("unknown_category", "no such category", "category_id")
    if not category.active:
        raise _invalid("inactive_category", "the category is inactive", "category_id")


def _check_related(db: Session, article_id: str | None, related: list[str]) -> list[str]:
    """422 "unknown related article": every id must be an article of the organisation, other than this one.
    Duplicates are kept once."""
    ids = list(dict.fromkeys(related))
    known = repo.articles_by_id(db, ids)
    unknown = [i for i in ids if i not in known or i == article_id]
    if unknown:
        raise _invalid("unknown_related_article", f"unknown related article {unknown[0]}", "related_article_ids")
    return ids


def _commit(db: Session, on_conflict: KnowledgeBaseError | None = None) -> None:
    """Commits; a unique-constraint violation from a concurrent request becomes `on_conflict` (409), never a 500."""
    try:
        db.commit()
    except IntegrityError as err:
        db.rollback()
        if on_conflict is None:
            raise
        raise on_conflict from err


def _flush(db: Session, on_conflict: KnowledgeBaseError) -> None:
    """Flushes; a unique-constraint violation becomes `on_conflict` (409), as in _commit, for writes whose ids the rest
    of the use case needs before the commit."""
    try:
        db.flush()
    except IntegrityError as err:
        db.rollback()
        raise on_conflict from err


# ---------------------------------------------------------------- serialisation (contract schemas)


def category_dict(c: Category, published_article_count: int) -> dict:
    return {
        "id": c.id,
        "organisation_id": c.organisation_id,
        "parent_id": c.parent_id,
        "name": c.name,
        "description": c.description,
        "position": c.position,
        "active": c.active,
        "published_article_count": published_article_count,
    }


def article_dict(a: Article, open_rev: Revision | None, on: date) -> dict:
    return {
        "id": a.id,
        "organisation_id": a.organisation_id,
        "slug": a.slug,
        "status": a.status,
        "owner_id": a.owner_id,
        "review_by": _day(a.review_by),
        "stale": rules.is_stale(a.status, a.review_by, on),
        "published_revision_no": a.published_revision_no,
        "open_revision_no": a.open_revision_no,
        "open_revision_state": open_rev.state if open_rev is not None else None,
        "view_count": a.view_count,
        "helpful_count": a.helpful_count,
        "not_helpful_count": a.not_helpful_count,
        "created_at": iso(a.created_at),
        "first_published_at": iso(a.first_published_at),
        "published_at": iso(a.published_at),
        "archived_at": iso(a.archived_at),
    }


def summary_dict(r: Revision) -> dict:
    """Contract RevisionSummary."""
    return {
        "revision_no": r.revision_no,
        "state": r.state,
        "title": r.title,
        "author_id": r.author_id,
        "change_note": r.change_note,
        "created_at": iso(r.created_at),
        "submitted_at": iso(r.submitted_at),
        "reviewed_by": r.reviewed_by,
        "review_comment": r.review_comment,
        "published_at": iso(r.published_at),
    }


def revision_dict(r: Revision) -> dict:
    """Contract Revision: the content with its summary."""
    return {
        "article_id": r.article_id,
        **summary_dict(r),
        "type": r.type,
        "summary": r.summary,
        "body": r.body,
        "category_id": r.category_id,
        "tags": list(r.tags or []),
        "audience": r.audience,
        "related_article_ids": list(r.related_article_ids or []),
        "references": list(r.references or []),
    }


def list_item(a: Article, r: Revision, on: date, *, writer: bool, open_state: str | None, snippet: str | None) -> dict:
    """Contract ArticleListItem. open_revision_state is returned to callers with knowledge-base:article:write only."""
    item = {
        "id": a.id,
        "slug": a.slug,
        "status": a.status,
        "type": r.type,
        "title": r.title,
        "summary": r.summary,
        "category_id": r.category_id,
        "tags": list(r.tags or []),
        "audience": r.audience,
        "snippet": snippet,
        "helpful_share": rules.helpful_share(a.helpful_count, a.not_helpful_count),
        "view_count": a.view_count,
        "published_at": iso(a.published_at),
        "stale": rules.is_stale(a.status, a.review_by, on),
    }
    if writer:
        item["open_revision_state"] = open_state
    return item


def _related(db: Session, actor: Actor, rev: Revision) -> list[dict]:
    """Related articles the caller may read: published, with an audience they may read."""
    found = repo.articles_by_id(db, list(rev.related_article_ids or []))
    keys = [
        (a.id, a.published_revision_no) for a in found.values() if a.status == "published" and a.published_revision_no
    ]
    revs = repo.revisions_by_key(db, keys)
    on = today()
    out = []
    for article_id in rev.related_article_ids or []:
        a = found.get(article_id)
        r = revs.get((article_id, a.published_revision_no)) if a else None
        if a is not None and r is not None and a.status == "published" and actor.may_read(r.audience):
            out.append(list_item(a, r, on, writer=False, open_state=None, snippet=None))
    return out


def _detail(db: Session, actor: Actor, a: Article, rev: Revision) -> dict:
    """Contract ArticleDetail."""
    open_rev = rev if a.open_revision_no == rev.revision_no else _rev(db, a, a.open_revision_no)
    return {**article_dict(a, open_rev, today()), "revision": revision_dict(rev), "related": _related(db, actor, rev)}


# ---------------------------------------------------------------- categories


def _nodes(rows: list[Category]) -> list[tree.Node]:
    return [tree.Node(c.id, c.parent_id, c.name, c.position) for c in rows]


def _published_in(db: Session, actor: Actor | None) -> dict[str, int]:
    """Published articles per category; with an actor, only those whose audience they may read. A top-level category
    counts its sub-categories' articles too, as the category_id filter on GET /articles does."""
    counts = repo.published_count_by_category(db)
    per = {cid: e + (s if actor is None or actor.can(READ_INTERNAL) else 0) for cid, (e, s) in counts.items()}
    rows = repo.categories(db)
    total = dict(per)
    for c in rows:
        if c.parent_id is not None and per.get(c.id):
            total[c.parent_id] = total.get(c.parent_id, 0) + per[c.id]
    return total


def list_categories(db: Session, actor: Actor, active: bool | None = None) -> list[dict]:
    """GET /categories. Without knowledge-base:category:manage only active categories are listed (active=false then
    returns none)."""
    require(actor, ARTICLE_READ)
    rows = repo.categories(db)
    if not actor.can(CATEGORY_MANAGE):
        rows = [c for c in rows if c.active]
    if active is not None:
        rows = [c for c in rows if c.active is active]
    by_id = {c.id: c for c in rows}
    counts = _published_in(db, actor)
    return [category_dict(by_id[n.id], counts.get(n.id, 0)) for n in tree.tree_order(_nodes(rows))]


def _parent(db: Session, parent_id: str | None) -> Category | None:
    if parent_id is None:
        return None
    parent = repo.get(db, Category, parent_id)
    if parent is None:
        raise _invalid("unknown_parent", "no such parent category", "parent_id")
    return parent


def _node(c: Category | None) -> tree.Node | None:
    return None if c is None else tree.Node(c.id, c.parent_id, c.name, c.position)


def create_category(db: Session, actor: Actor, body: dict) -> dict:
    """POST /categories. position defaults to after the last sibling."""
    require(actor, CATEGORY_MANAGE)
    parent = _parent(db, body.get("parent_id"))
    _domain(tree.check_parent, None, _node(parent), False)
    siblings = [c for c in repo.categories(db) if c.parent_id == body.get("parent_id")]
    _domain(tree.check_unique_name, body["name"], _nodes(siblings))
    position = body.get("position")
    if position is None:
        position = max((c.position for c in siblings), default=-1) + 1
    category = Category(
        organisation_id=actor.organisation_id,
        parent_id=body.get("parent_id"),
        name=body["name"].strip(),
        description=body.get("description"),
        position=position,
        active=body.get("active", True),
    )
    db.add(category)
    db.flush()
    _audit(db, actor, "category.created", CATEGORY, category.id)
    _commit(db)
    return category_dict(category, 0)


def update_category(db: Session, actor: Actor, category_id: str, body: dict) -> dict:
    """PATCH /categories/{id}: rename, move (parent_id null moves to the top level), reorder or (de)activate. The
    contract's CategoryInput lists name as required; on PATCH only the fields sent change."""
    require(actor, CATEGORY_MANAGE)
    category = repo.get(db, Category, category_id) if ID.match(category_id) else None
    if category is None:
        raise _not_found("category")
    rows = repo.categories(db)
    parent_id = body["parent_id"] if "parent_id" in body else category.parent_id
    if "parent_id" in body:
        parent = _parent(db, parent_id)
        has_children = any(c.parent_id == category.id for c in rows)
        _domain(tree.check_parent, category.id, _node(parent), has_children)
    name = body.get("name", category.name)
    if "name" in body or "parent_id" in body:
        siblings = [c for c in rows if c.parent_id == parent_id]
        _domain(tree.check_unique_name, name, _nodes(siblings), category.id)
    if body.get("active") is False and category.active:
        _domain(tree.check_deactivatable, _published_in(db, None).get(category.id, 0))
    category.parent_id = parent_id
    category.name = name.strip()
    for key in ("description", "position", "active"):
        if key in body:
            setattr(category, key, body[key])
    _audit(db, actor, "category.updated", CATEGORY, category.id)
    _commit(db)
    return category_dict(category, _published_in(db, actor).get(category.id, 0))


# ---------------------------------------------------------------- articles


def _unique_slug(db: Session, title: str) -> str:
    """The title's slug, or the first of slug-2, slug-3, ... not taken. Each candidate is checked itself: a long slug
    is trimmed to make room for its suffix, so a candidate does not always start with the untrimmed slug."""
    candidate = base = rules.slugify(title)
    n = 1
    while repo.slug_taken(db, candidate):
        n += 1
        candidate = rules.with_suffix(base, n)
    return candidate


def _content(body: dict) -> dict:
    """The revision content of a request, tags cleaned."""
    content = {f: body.get(f) for f in rules.CONTENT_FIELDS}
    content["tags"] = rules.clean_tags(content["tags"])
    content["related_article_ids"] = content["related_article_ids"] or []
    content["references"] = content["references"] or []
    return content


def _apply(rev: Revision, content: dict) -> None:
    for key, value in content.items():
        setattr(rev, key, value)


def create_article(db: Session, actor: Actor, body: dict) -> dict:
    """POST /articles: the article as a draft with revision 1. A slug derived from the title gets -2, -3, ... when
    taken; a slug the caller sends that is taken is 409."""
    require(actor, ARTICLE_WRITE)
    _domain(rules.check_complete, body)
    content = _content(body)
    _check_may_write_audience(actor, content["audience"])
    _check_category(db, content["category_id"])
    content["related_article_ids"] = _check_related(db, None, content["related_article_ids"])
    if body.get("slug"):
        slug = body["slug"]
        if repo.slug_taken(db, slug):
            raise _conflict("slug_taken", "the slug is already used in the organisation", "slug")
    else:
        slug = _unique_slug(db, content["title"])
    article = Article(
        organisation_id=actor.organisation_id,
        slug=slug,
        status=rules.DRAFT,
        owner_id=body.get("owner_id") or actor.user_id,
        review_by=body.get("review_by"),
        open_revision_no=1,
        last_revision_no=1,
        view_count=0,
        helpful_count=0,
        not_helpful_count=0,
        created_at=clock(),
    )
    db.add(article)
    taken = _conflict("slug_taken", "the slug is already used in the organisation", "slug")
    _flush(db, taken)  # a concurrent create with the same slug hits the unique constraint here
    rev = Revision(
        organisation_id=actor.organisation_id,
        article_id=article.id,
        revision_no=1,
        state=rules.DRAFT,
        author_id=actor.user_id,
        change_note=body.get("change_note"),
        created_at=clock(),
    )
    _apply(rev, content)
    db.add(rev)
    _audit(db, actor, "article.created", ARTICLE, article.id)
    _commit(db, taken)
    return _detail(db, actor, article, rev)


def get_article(db: Session, actor: Actor, article_id: str, view: str = "published") -> dict:
    """GET /articles/{id}. view=published counts a view of a published article, at most once per reader per day."""
    require(actor, ARTICLE_READ)
    article = _article(db, article_id)
    if view == "open":
        require(actor, ARTICLE_WRITE)
        rev = _rev(db, article, article.open_revision_no)
    else:
        rev = _rev(db, article, article.published_revision_no)
    if rev is None or not actor.may_read(rev.audience):
        raise _not_found("article or revision")
    if view != "open" and article.status == rules.PUBLISHED:
        on = today()
        key = hashlib.sha256(f"{actor.organisation_id}|{article.id}|{actor.user_id}|{on}".encode()).hexdigest()
        if repo.count_view(db, actor.organisation_id, article.id, on, key):
            db.commit()
            db.refresh(article)
    return _detail(db, actor, article, rev)


def update_settings(db: Session, actor: Actor, article_id: str, body: dict) -> dict:
    """PATCH /articles/{id}: owner_id and review_by. knowledge-base:article:publish, or write for the article's owner."""
    require(actor, ARTICLE_WRITE, ARTICLE_PUBLISH)
    article = _article(db, article_id, lock=True)
    _visible(db, actor, article)
    if not actor.can(ARTICLE_PUBLISH) and article.owner_id != actor.user_id:
        raise forbidden(f"only the article's owner, or {ARTICLE_PUBLISH}, may change its settings")
    if "owner_id" in body:
        article.owner_id = body["owner_id"]
    if "review_by" in body:
        article.review_by = body["review_by"]
    _audit(db, actor, "article.settings_changed", ARTICLE, article.id)
    _commit(db)
    return article_dict(article, _rev(db, article, article.open_revision_no), today())


def save_draft(db: Session, actor: Actor, article_id: str, body: dict, from_revision: int | None = None) -> dict:
    """PUT /articles/{id}/draft. With an open draft its content is replaced (every content field required; optional
    fields left out are cleared). Without one, a new draft starts from from_revision, else the published revision,
    else the latest; fields left out (or null) are copied from that source, except summary, which a null clears."""
    require(actor, ARTICLE_WRITE, ARTICLE_PUBLISH)
    article = _article(db, article_id, lock=True)
    _visible(db, actor, article)
    open_rev = _rev(db, article, article.open_revision_no)
    if open_rev is not None:
        _domain(rules.check_draft_editable, open_rev.state, from_revision)
        if open_rev.author_id != actor.user_id and not actor.can(ARTICLE_PUBLISH):
            raise forbidden(f"editing another author's draft needs {ARTICLE_PUBLISH}")
        _domain(rules.check_complete, body)
        content = _content(body)
        rev, action = open_rev, "revision.saved"
    else:
        if from_revision is not None:
            source = _rev(db, article, from_revision)
            if source is None:
                raise _not_found("revision")
        else:
            source = _rev(db, article, article.published_revision_no or article.last_revision_no)
        if source is None:
            raise _not_found("revision")
        content = {f: getattr(source, f) for f in rules.CONTENT_FIELDS}
        content.update(
            {f: body[f] for f in rules.CONTENT_FIELDS if f in body and (body[f] is not None or f == "summary")}
        )
        content = _content(content)
        number = article.last_revision_no + 1
        rev = Revision(
            organisation_id=actor.organisation_id,
            article_id=article.id,
            revision_no=number,
            state=rules.DRAFT,
            author_id=actor.user_id,
            created_at=clock(),
        )
        db.add(rev)
        article.last_revision_no = number
        article.open_revision_no = number
        action = "revision.created"
    _check_may_write_audience(actor, content["audience"])
    _check_category(db, content["category_id"])
    content["related_article_ids"] = _check_related(db, article.id, content["related_article_ids"])
    _apply(rev, content)
    rev.change_note = body.get("change_note")
    db.flush()
    _audit(db, actor, action, REVISION, rev.id)
    _commit(db)
    return revision_dict(rev)


def _open(db: Session, actor: Actor, article_id: str) -> tuple[Article, Revision | None]:
    article = _article(db, article_id, lock=True)
    _visible(db, actor, article)
    return article, _rev(db, article, article.open_revision_no)


def submit_draft(db: Session, actor: Actor, article_id: str) -> dict:
    """POST /draft/submit: draft → in_review, the caller's own draft only."""
    require(actor, ARTICLE_WRITE)
    article, rev = _open(db, actor, article_id)
    state = _domain(rules.submit, rev.state if rev else None)
    if rev.author_id != actor.user_id:
        raise forbidden("only the draft's author may submit it")
    rev.state, rev.submitted_at = state, clock()
    _audit(db, actor, "revision.submitted", REVISION, rev.id)
    _commit(db)
    return revision_dict(rev)


def return_draft(db: Session, actor: Actor, article_id: str, comment: str) -> dict:
    """POST /draft/return: in_review → draft with a comment for the author."""
    require(actor, ARTICLE_PUBLISH)
    article, rev = _open(db, actor, article_id)
    state = _domain(rules.give_back, rev.state if rev else None)
    rev.state, rev.reviewed_by, rev.review_comment = state, actor.user_id, comment
    _audit(db, actor, "revision.returned", REVISION, rev.id, comment)
    _commit(db)
    return revision_dict(rev)


def discard_draft(db: Session, actor: Actor, article_id: str) -> dict:
    """POST /draft/discard: the open revision becomes discarded; the published one is unaffected."""
    require(actor, ARTICLE_WRITE, ARTICLE_PUBLISH)
    article, rev = _open(db, actor, article_id)
    state = _domain(rules.discard, rev.state if rev else None)
    if rev.author_id != actor.user_id and not actor.can(ARTICLE_PUBLISH):
        raise forbidden(f"discarding another author's draft needs {ARTICLE_PUBLISH}")
    rev.state = state
    article.open_revision_no = None
    _audit(db, actor, "revision.discarded", REVISION, rev.id)
    _commit(db)
    return revision_dict(rev)


def publish(db: Session, actor: Actor, article_id: str, review_by: date | None = None) -> dict:
    """POST /publish: the open revision becomes the published one; the previous becomes superseded. review_by: the
    one sent, else the existing date, else KNOWLEDGE_BASE_DEFAULT_REVIEW_MONTHS from today. The revision's category
    must still be active (422), so an inactive category never holds published articles."""
    require(actor, ARTICLE_PUBLISH)
    article, rev = _open(db, actor, article_id)
    _domain(rules.check_publishable, article.status, rev.state if rev else None)
    _check_category(db, rev.category_id)
    now = clock()
    previous = _rev(db, article, article.published_revision_no)
    if previous is not None:
        previous.state = rules.SUPERSEDED
    rev.state, rev.published_at = rules.PUBLISHED, now
    rev.reviewed_by = rev.reviewed_by or actor.user_id
    first = article.first_published_at is None
    article.status = rules.PUBLISHED
    article.published_revision_no, article.open_revision_no = rev.revision_no, None
    article.published_at = now
    article.first_published_at = article.first_published_at or now
    if review_by is not None:
        article.review_by = review_by
    elif article.review_by is None:
        article.review_by = rules.add_months(today(), load_settings().default_review_months)
    _audit(db, actor, "article.published", ARTICLE, article.id)
    _publish_published(db, actor, article, rev, first)
    _commit(db)
    return _detail(db, actor, article, rev)


def _publish_published(db: Session, actor: Actor, article: Article, rev: Revision, first: bool) -> None:
    _publish(
        db,
        actor,
        "published",
        {
            "article_id": article.id,
            "slug": article.slug,
            "revision_no": rev.revision_no,
            "type": rev.type,
            "category_id": rev.category_id,
            "audience": rev.audience,
            "first_publication": first,
            "published_at": iso(article.published_at),
        },
    )


def archive(db: Session, actor: Actor, article_id: str, reason: str) -> dict:
    """POST /archive: leaves browse and search, stays readable by id; an open draft is kept."""
    require(actor, ARTICLE_PUBLISH)
    article, open_rev = _open(db, actor, article_id)
    was_published = article.status == rules.PUBLISHED
    article.status = _domain(rules.archive, article.status)
    article.archived_at = clock()
    _audit(db, actor, "article.archived", ARTICLE, article.id, reason)
    _publish(
        db,
        actor,
        "archived",
        {
            "article_id": article.id,
            "slug": article.slug,
            "was_published": was_published,
            "archived_at": iso(article.archived_at),
        },
    )
    _commit(db)
    return article_dict(article, open_rev, today())


def restore(db: Session, actor: Actor, article_id: str) -> dict:
    """POST /restore: to published if it was ever published (its published revision readers saw), otherwise draft."""
    require(actor, ARTICLE_PUBLISH)
    article, open_rev = _open(db, actor, article_id)
    article.status = _domain(rules.restore, article.status, article.published_revision_no is not None)
    article.archived_at = None
    _audit(db, actor, "article.restored", ARTICLE, article.id)
    if article.status == rules.PUBLISHED:
        _publish_published(db, actor, article, _rev(db, article, article.published_revision_no), False)
    _commit(db)
    return article_dict(article, open_rev, today())


def list_revisions(db: Session, actor: Actor, article_id: str) -> list[dict]:
    require(actor, ARTICLE_WRITE)
    article = _article(db, article_id)
    _visible(db, actor, article)
    return [summary_dict(r) for r in repo.revisions_of(db, article.id)]


def get_revision(db: Session, actor: Actor, article_id: str, revision_no: int) -> dict:
    require(actor, ARTICLE_WRITE)
    article = _article(db, article_id)
    _visible(db, actor, article)
    rev = _rev(db, article, revision_no)
    if rev is None:
        raise _not_found("revision")
    return revision_dict(rev)


# ---------------------------------------------------------------- browse and search


def list_articles(db: Session, actor: Actor, f: dict) -> dict:
    """GET /articles. Readers get published articles whose audience they may read. status, owner, stale and in_review
    need knowledge-base:article:write (403 otherwise). status defaults to published; with owner or in_review it
    defaults to draft and published, the articles someone is working on. Archived articles appear only when asked for
    with status. sort defaults to relevance with q, newest otherwise; relevance without q is 422."""
    require(actor, ARTICLE_READ)
    writer = actor.can(ARTICLE_WRITE)
    if not writer and any(f.get(k) is not None for k in ("status", "owner", "stale", "in_review")):
        raise forbidden(f"the status, owner, stale and in_review filters need {ARTICLE_WRITE}")
    if f.get("audience") == rules.STAFF and not actor.can(READ_INTERNAL):
        raise forbidden(f"staff articles need {READ_INTERNAL}")
    q = f.get("q")
    sort = f.get("sort") or ("relevance" if q else "newest")
    if sort == "relevance" and not q:
        raise _invalid("relevance_needs_q", "sort=relevance needs q", "sort")
    offset = repo.decode_cursor(f.get("cursor"))
    if offset is None:
        raise _invalid("invalid_cursor", "the cursor is not one this API returned", "cursor")
    statuses = f.get("status")
    if statuses is None:
        statuses = (
            [rules.DRAFT, rules.PUBLISHED] if (f.get("owner") or f.get("in_review") is not None) else [rules.PUBLISHED]
        )

    rows = repo.articles(db, statuses)
    keys = [(a.id, _display_no(a)) for a in rows if _display_no(a)]
    keys += [(a.id, a.open_revision_no) for a in rows if writer and a.open_revision_no]
    revs = repo.revisions_by_key(db, keys)
    categories = None
    if f.get("category_id"):
        categories = {f["category_id"]} | {c.id for c in repo.categories(db) if c.parent_id == f["category_id"]}
    owner = actor.user_id if f.get("owner") == "me" else f.get("owner")
    words = search.terms(q) if q else []
    on = today()
    hits = []
    for a in rows:
        r = revs.get((a.id, _display_no(a)))
        if r is None or not actor.may_read(r.audience):
            continue
        open_rev = revs.get((a.id, a.open_revision_no)) if a.open_revision_no else None
        open_state = open_rev.state if open_rev is not None else None
        if (
            (f.get("type") and r.type != f["type"])
            or (categories is not None and r.category_id not in categories)
            or (f.get("tag") and f["tag"].strip().casefold() not in {t.casefold() for t in r.tags or []})
            or (f.get("audience") and r.audience != f["audience"])
            or (f.get("slug") and a.slug != f["slug"])
            or (owner and a.owner_id != owner)
            or (f.get("stale") is not None and rules.is_stale(a.status, a.review_by, on) is not f["stale"])
            or (f.get("in_review") is not None and (open_state == rules.IN_REVIEW) is not f["in_review"])
        ):
            continue
        relevance = 0
        if words:
            relevance = search.score(words, r.title, r.summary, r.body, list(r.tags or []))
            if not relevance:
                continue
        hits.append((a, r, open_state, relevance))

    def newest(h):
        return -(as_utc(h[0].published_at or h[0].created_at) or datetime.min.replace(tzinfo=UTC)).timestamp()

    orders = {
        "relevance": lambda h: (-h[3], newest(h), h[0].id),
        "newest": lambda h: (newest(h), h[0].id),
        "popular": lambda h: (-h[0].view_count, newest(h), h[0].id),
        "helpful": lambda h: (
            rules.helpful_share(h[0].helpful_count, h[0].not_helpful_count) is None,
            -(rules.helpful_share(h[0].helpful_count, h[0].not_helpful_count) or 0),
            -(h[0].helpful_count + h[0].not_helpful_count),
            h[0].id,
        ),
        "title": lambda h: (h[1].title.casefold(), h[0].id),
    }
    hits.sort(key=orders[sort])
    page, next_cursor = repo.page_of(hits, offset, f.get("limit") or 20)
    items = [
        list_item(
            a,
            r,
            on,
            writer=writer,
            open_state=open_state,
            snippet=search.snippet(words, r.title, r.summary, r.body) if words else None,
        )
        for a, r, open_state, _ in page
    ]
    return {"items": items, "next_cursor": next_cursor}


# ---------------------------------------------------------------- feedback


def _counts(article: Article, mine: Feedback | None) -> dict:
    return {
        "helpful_count": article.helpful_count,
        "not_helpful_count": article.not_helpful_count,
        "my_vote": None if mine is None else mine.helpful,
    }


def give_feedback(db: Session, actor: Actor, article_id: str, body: dict) -> dict:
    """POST /articles/{id}/feedback: one vote per person per article, a new vote replaces the earlier one. An article
    that is not published is 409 for a caller who may see unpublished articles, and 404 for a reader, who may not."""
    require(actor, ARTICLE_READ)
    article = _article(db, article_id, lock=True)
    if article.status != rules.PUBLISHED or article.published_revision_no is None:
        if actor.can(ARTICLE_WRITE):
            raise _conflict("not_published", "feedback is accepted on published articles only")
        raise _not_found("article")
    rev = _rev(db, article, article.published_revision_no)
    if rev is None or not actor.may_read(rev.audience):
        raise _not_found("article")
    mine = repo.feedback_of(db, article.id, actor.user_id)
    if mine is None:
        mine = Feedback(organisation_id=actor.organisation_id, article_id=article.id, person_id=actor.user_id)
        db.add(mine)
    elif mine.helpful:
        article.helpful_count -= 1
    else:
        article.not_helpful_count -= 1
    mine.helpful, mine.comment = body["helpful"], body.get("comment")
    mine.revision_no, mine.created_at = article.published_revision_no, clock()
    if mine.helpful:
        article.helpful_count += 1
    else:
        article.not_helpful_count += 1
    _commit(db, _conflict("vote_in_progress", "another vote of yours on this article was being saved; try again"))
    return _counts(article, mine)


def list_feedback(db: Session, actor: Actor, article_id: str, f: dict) -> dict:
    """GET /articles/{id}/feedback: votes with comments, newest first."""
    require(actor, STATS_READ)
    article = _article(db, article_id)
    _visible(db, actor, article)
    offset = repo.decode_cursor(f.get("cursor"))
    if offset is None:
        raise _invalid("invalid_cursor", "the cursor is not one this API returned", "cursor")
    rows = repo.feedback_list(db, article.id, f.get("helpful"))
    page, next_cursor = repo.page_of(rows, offset, f.get("limit") or 20)
    items = [
        {
            "person_id": fb.person_id,
            "helpful": fb.helpful,
            "comment": fb.comment,
            "revision_no": fb.revision_no,
            "created_at": iso(fb.created_at),
        }
        for fb in page
    ]
    return {
        "counts": _counts(article, repo.feedback_of(db, article.id, actor.user_id)),
        "items": items,
        "next_cursor": next_cursor,
    }


# ---------------------------------------------------------------- statistics


def top_articles_stats(
    db: Session, actor: Actor, period: str = "30d", metric: str = "views", limit: int | None = None
) -> dict:
    """GET /stats/top-articles: views counted over the period's days up to today; staff articles only for callers who
    may read them."""
    require(actor, STATS_READ)
    settings = load_settings()
    views = repo.views_since(db, today() - timedelta(days=PERIOD_DAYS[period] - 1))
    rows = [a for a in repo.articles(db, [rules.PUBLISHED]) if a.published_revision_no]
    revs = repo.revisions_by_key(db, [(a.id, a.published_revision_no) for a in rows])
    candidates = []
    for a in rows:
        r = revs.get((a.id, a.published_revision_no))
        if r is None or not actor.may_read(r.audience):
            continue
        candidates.append(
            Candidate(
                a.id,
                a.slug,
                r.title,
                r.type,
                r.category_id,
                r.audience,
                views.get(a.id, 0),
                a.helpful_count,
                a.not_helpful_count,
            )
        )
    items = top_articles(candidates, metric, limit or settings.top_articles_limit, settings.helpful_min_votes)
    return {"period": period, "metric": metric, "items": items}
