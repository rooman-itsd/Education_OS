"""Top articles behind the Support Staff widget knowledge-base.top-articles (PRD "Dashboard widget"). Pure Python.

- metric views (default): published articles with at least one view in the period, most views first.
- metric helpful: published articles with at least `min_votes` votes, highest helpful share first, then more votes.
Ties go to the title, then the id, so the order never changes between two reads."""

from __future__ import annotations

from dataclasses import dataclass

from .articles import helpful_share

PERIOD_DAYS = {"7d": 7, "30d": 30, "90d": 90}
METRICS = ("views", "helpful")


@dataclass(frozen=True)
class Candidate:
    article_id: str
    slug: str
    title: str
    type: str
    category_id: str
    audience: str
    views: int
    helpful_count: int
    not_helpful_count: int


def top_articles(candidates: list[Candidate], metric: str, limit: int, min_votes: int) -> list[dict]:
    if metric == "helpful":
        pool = [c for c in candidates if c.helpful_count + c.not_helpful_count >= min_votes]
        pool.sort(
            key=lambda c: (
                -(helpful_share(c.helpful_count, c.not_helpful_count) or 0),
                -(c.helpful_count + c.not_helpful_count),
                c.title.casefold(),
                c.article_id,
            )
        )
    else:
        pool = [c for c in candidates if c.views > 0]
        pool.sort(key=lambda c: (-c.views, c.title.casefold(), c.article_id))
    return [
        {
            "article_id": c.article_id,
            "slug": c.slug,
            "title": c.title,
            "type": c.type,
            "category_id": c.category_id,
            "audience": c.audience,
            "views": c.views,
            "helpful_count": c.helpful_count,
            "not_helpful_count": c.not_helpful_count,
            "helpful_share": helpful_share(c.helpful_count, c.not_helpful_count),
        }
        for c in pool[:limit]
    ]
