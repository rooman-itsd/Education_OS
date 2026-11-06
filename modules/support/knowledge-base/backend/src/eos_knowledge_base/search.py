"""Document provider for platform/search, registered on the `eos.search_documents` entry point in
backend/pyproject.toml. Search calls it, in the organisation of the event or reindex, to learn what to index; this
module imports nothing from search and returns plain mappings.

Indexed: the title, body and slug of a published article's published revision, and its category. A staff-only article
carries `read_any_of: [knowledge-base:article:read-internal]`. Drafts and archived articles return None (the
`article.archived` event deletes the document, and a reindex must not restore it). Feedback, counts and people are
never indexed."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from eos_core.db import SessionLocal
from eos_core.tenant import organisation_scope
from sqlalchemy import select

from .application.access import READ_INTERNAL
from .domain.articles import PUBLISHED, STAFF
from .infrastructure.models import Article, Revision

TYPE = "article"
DECLARATION = Path(__file__).resolve().parents[3] / "contracts" / "searchable.yaml"


def _document(article: Article, revision: Revision) -> dict[str, Any]:
    document: dict[str, Any] = {
        "record_id": article.id,
        "fields": {
            "title": revision.title,
            "body": revision.body,
            "slug": article.slug,
            "category_id": revision.category_id,
            "published": True,
        },
    }
    if revision.audience == STAFF:
        document["read_any_of"] = [READ_INTERNAL]
    return document


def _published(db, organisation_id: str, query, limit: int | None = None):
    """(article, revision) rows of published articles whose published revision exists, in this organisation."""
    joined = (
        query.join(
            Revision,
            (Revision.article_id == Article.id) & (Revision.revision_no == Article.published_revision_no),
        )
        .where(
            Article.organisation_id == organisation_id,
            Revision.organisation_id == organisation_id,
            Article.status == PUBLISHED,
        )
        .order_by(Article.id)
    )
    return db.execute(joined.limit(limit) if limit else joined)


class KnowledgeBaseSearch:
    declaration = DECLARATION

    def get_document(self, organisation_id: str, type: str, record_id: str) -> dict[str, Any] | None:
        if type != TYPE or not organisation_id:
            return None
        with organisation_scope(organisation_id), SessionLocal() as db:
            db.info["organisation_id"] = organisation_id
            row = _published(db, organisation_id, select(Article, Revision).where(Article.id == record_id)).first()
            return _document(*row) if row else None

    def iter_documents(self, organisation_id: str, type: str, after_id: str | None, limit: int) -> list[dict[str, Any]]:
        if type != TYPE or not organisation_id:
            return []
        query = select(Article, Revision)
        if after_id:
            query = query.where(Article.id > after_id)
        with organisation_scope(organisation_id), SessionLocal() as db:
            db.info["organisation_id"] = organisation_id
            rows = _published(db, organisation_id, query, limit)
            return [_document(a, r) for a, r in rows]


PROVIDER = KnowledgeBaseSearch()
