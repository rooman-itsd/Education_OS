"""Article and revision rules (PRD "Statuses", "Main flows" 2-8 and 11). Pure Python: no database, no clock.

Article:   draft → published → archived;  draft → archived;  archived → published (if ever published) or draft
Revision:  draft → in_review → published → superseded;  in_review → draft (returned);
           draft or in_review → discarded;  draft → published (an editor publishes directly)

An article has at most one open revision (draft or in_review). Content always lives in revisions; a revision cannot be
changed once it leaves draft."""

from __future__ import annotations

import calendar
import re
from datetime import date

from .errors import DomainRuleError

# Article statuses (contract ArticleStatus).
DRAFT, PUBLISHED, ARCHIVED = "draft", "published", "archived"
ARTICLE_STATUSES = (DRAFT, PUBLISHED, ARCHIVED)

# Revision states (contract RevisionState).
IN_REVIEW, SUPERSEDED, DISCARDED = "in_review", "superseded", "discarded"
REVISION_STATES = (DRAFT, IN_REVIEW, PUBLISHED, SUPERSEDED, DISCARDED)
OPEN_STATES = (DRAFT, IN_REVIEW)

ARTICLE_TYPES = ("article", "faq", "how_to")
AUDIENCES = ("everyone", "staff")
EVERYONE, STAFF = AUDIENCES

# Content fields of a revision (contract RevisionFields) and the ones RevisionContent requires.
CONTENT_FIELDS = (
    "type",
    "title",
    "summary",
    "body",
    "category_id",
    "tags",
    "audience",
    "related_article_ids",
    "references",
)
REQUIRED_CONTENT_FIELDS = ("type", "title", "body", "category_id", "audience")

SLUG_MAX = 120


def missing_content(fields: dict) -> list[str]:
    """Required content fields absent (or null) from a body that must hold every one: create, and saving an open
    draft (PUT /articles/{id}/draft "must hold every content field")."""
    return [f for f in REQUIRED_CONTENT_FIELDS if fields.get(f) is None]


def check_complete(fields: dict) -> None:
    missing = missing_content(fields)
    if missing:
        raise DomainRuleError(
            "content_fields_required",
            f"saving an open draft needs every content field; missing {', '.join(missing)}",
            kind="invalid",
            field=missing[0],
        )


def check_draft_editable(open_state: str | None, from_revision: int | None) -> None:
    """PUT /draft with an open revision: 409 when it is in review, or when from_revision asks for a new draft."""
    if open_state == IN_REVIEW:
        raise DomainRuleError("revision_in_review", "the open revision is in review; return it first", kind="conflict")
    if open_state == DRAFT and from_revision is not None:
        raise DomainRuleError(
            "draft_open", "from_revision starts a new draft and is refused while a draft is open", kind="conflict"
        )


def submit(open_state: str | None) -> str:
    """draft → in_review (409 "No open draft")."""
    if open_state != DRAFT:
        raise DomainRuleError("no_open_draft", "the article has no open draft", kind="conflict")
    return IN_REVIEW


def give_back(open_state: str | None) -> str:
    """in_review → draft (POST /draft/return; 409 "No revision in review")."""
    if open_state != IN_REVIEW:
        raise DomainRuleError("no_revision_in_review", "the article has no revision in review", kind="conflict")
    return DRAFT


def discard(open_state: str | None) -> str:
    """draft or in_review → discarded (409 "No open revision")."""
    if open_state not in OPEN_STATES:
        raise DomainRuleError("no_open_revision", "the article has no open revision", kind="conflict")
    return DISCARDED


def check_publishable(status: str, open_state: str | None) -> None:
    """POST /publish: 409 "No open revision, or the article is archived"."""
    if status == ARCHIVED:
        raise DomainRuleError(
            "article_archived", "an archived article cannot be published; restore it first", kind="conflict"
        )
    if open_state not in OPEN_STATES:
        raise DomainRuleError("no_open_revision", "the article has no open revision to publish", kind="conflict")


def archive(status: str) -> str:
    """draft or published → archived (409 "Already archived")."""
    if status == ARCHIVED:
        raise DomainRuleError("already_archived", "the article is already archived", kind="conflict")
    return ARCHIVED


def restore(status: str, has_published_revision: bool) -> str:
    """archived → published if it was ever published, otherwise draft (409 "Not archived")."""
    if status != ARCHIVED:
        raise DomainRuleError("not_archived", "only an archived article can be restored", kind="conflict")
    return PUBLISHED if has_published_revision else DRAFT


# ---------------------------------------------------------------- slugs, dates, shares


def slugify(text: str) -> str:
    """Lowercase ASCII letters and digits joined by single hyphens (contract slug pattern), at most SLUG_MAX
    characters; "article" when the title has no such character (a title in another script)."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:SLUG_MAX].strip("-")
    return slug or "article"


def with_suffix(slug: str, n: int) -> str:
    """slug-2, slug-3, ... kept within SLUG_MAX."""
    tail = f"-{n}"
    return slug[: SLUG_MAX - len(tail)].rstrip("-") + tail


def add_months(day: date, months: int) -> date:
    """The same day `months` later, on the last day of the month when it has fewer days; date.max when it would
    pass the end of the calendar."""
    index = day.month - 1 + months
    year = day.year + index // 12
    if year > date.max.year:
        return date.max
    month = index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def is_stale(status: str, review_by: date | None, today: date) -> bool:
    """Published and review_by has passed (worked out when read)."""
    return status == PUBLISHED and review_by is not None and review_by < today


def helpful_share(helpful: int, not_helpful: int) -> float | None:
    """helpful / (helpful + not helpful), null with no votes (contract ArticleListItem.helpful_share)."""
    votes = helpful + not_helpful
    return None if votes == 0 else round(helpful / votes, 4)


def clean_tags(tags: list[str] | None) -> list[str]:
    """Surrounding spaces removed, empty tags dropped, duplicates (ignoring case) kept once, first spelling wins."""
    seen: set[str] = set()
    out: list[str] = []
    for tag in tags or []:
        t = tag.strip()
        if t and t.casefold() not in seen:
            seen.add(t.casefold())
            out.append(t)
    return out
