"""HTTP surface of knowledge-base, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/knowledge-base (apps/backend/config/modules.enabled.yaml). Handlers only map HTTP to the use cases in
application/service.py; each declares the permission the contract names for it. Error bodies are
{code, message[, field]} inside FastAPI's `detail`."""

from __future__ import annotations

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from ..application import access as perm
from ..application import service as svc
from ..application.access import Actor
from ..application.errors import KnowledgeBaseError
from ..domain.articles import ARTICLE_STATUSES, ARTICLE_TYPES, AUDIENCES
from ..domain.stats import METRICS, PERIOD_DAYS
from ..infrastructure.config import MAX_TOP_LIMIT, MIN_TOP_LIMIT
from . import schemas as s
from .deps import require

router = APIRouter(tags=["knowledge-base"])

MAX_INT = 2**31 - 1  # Integer columns; larger numbers can name no revision
LIMIT = Query(20, ge=1, le=100)
CURSOR = Query(None, max_length=200)
READ = require(perm.ARTICLE_READ)
WRITE = require(perm.ARTICLE_WRITE)
WRITE_OR_PUBLISH = require(perm.ARTICLE_WRITE, perm.ARTICLE_PUBLISH)
PUBLISH = require(perm.ARTICLE_PUBLISH)
MANAGE = require(perm.CATEGORY_MANAGE)
STATS = require(perm.STATS_READ)


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except KnowledgeBaseError as e:
        raise HTTPException(e.status, e.body()) from e


def _bad(field: str, message: str) -> HTTPException:
    return HTTPException(422, {"code": f"invalid_{field}", "message": message, "field": field})


def _listed(value: str | None, allowed: tuple[str, ...], field: str) -> list[str] | None:
    """`status` is an array in form style without explode: status=draft,published."""
    if not value:
        return None
    values = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [v for v in values if v not in allowed]
    if unknown:
        raise _bad(field, f"unknown {field} {', '.join(unknown)}")
    return values


def _single(value: str | None, allowed: tuple[str, ...], field: str) -> str | None:
    """A parameter the contract types as one value: a comma list is a 422, never a partial result."""
    if not value:
        return None
    if value not in allowed:
        raise _bad(field, f"unknown {field} {value}")
    return value


# ---------------------------------------------------------------- categories


@router.get("/categories")
def list_categories(active: bool | None = None, a: Actor = Depends(READ), db: Session = Depends(get_db)):
    return _run(svc.list_categories, db, a, active)


@router.post("/categories", status_code=201)
def create_category(body: s.CategoryInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)):
    return _run(svc.create_category, db, a, s.as_dict(body, partial=False))


@router.patch("/categories/{category_id}")
def update_category(
    category_id: str, body: s.CategoryUpdateInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)
):
    return _run(svc.update_category, db, a, category_id, s.as_dict(body, partial=True))


# ---------------------------------------------------------------- articles


@router.get("/articles")
def list_articles(
    q: str | None = Query(None, min_length=2, max_length=200),
    type: str | None = None,
    category_id: str | None = Query(None, max_length=36),
    tag: str | None = Query(None, max_length=40),
    audience: str | None = None,
    slug: str | None = Query(None, max_length=120),
    status: str | None = None,
    owner: str | None = Query(None, max_length=36),
    stale: bool | None = None,
    in_review: bool | None = None,
    sort: str | None = None,
    cursor: str | None = CURSOR,
    limit: int = LIMIT,
    a: Actor = Depends(READ),
    db: Session = Depends(get_db),
):
    filters = {
        "q": q,
        "type": _single(type, ARTICLE_TYPES, "type"),
        "category_id": category_id,
        "tag": tag,
        "audience": _single(audience, AUDIENCES, "audience"),
        "slug": slug,
        "status": _listed(status, ARTICLE_STATUSES, "status"),
        "owner": owner,
        "stale": stale,
        "in_review": in_review,
        "sort": _single(sort, svc.SORTS, "sort"),
        "cursor": cursor,
        "limit": limit,
    }
    return _run(svc.list_articles, db, a, filters)


@router.post("/articles", status_code=201)
def create_article(body: s.ArticleCreateInput, a: Actor = Depends(WRITE), db: Session = Depends(get_db)):
    return _run(svc.create_article, db, a, s.as_dict(body, partial=False))


@router.get("/articles/{article_id}")
def get_article(article_id: str, view: str | None = None, a: Actor = Depends(READ), db: Session = Depends(get_db)):
    return _run(svc.get_article, db, a, article_id, _single(view, ("published", "open"), "view") or "published")


@router.patch("/articles/{article_id}")
def update_settings(
    article_id: str, body: s.ArticleSettingsInput, a: Actor = Depends(WRITE_OR_PUBLISH), db: Session = Depends(get_db)
):
    return _run(svc.update_settings, db, a, article_id, s.as_dict(body, partial=True))


@router.put("/articles/{article_id}/draft")
def save_draft(
    article_id: str,
    body: s.DraftInput | None = None,
    from_revision: int | None = Query(None, ge=1, le=MAX_INT),
    a: Actor = Depends(WRITE_OR_PUBLISH),
    db: Session = Depends(get_db),
):
    data = body.model_dump(exclude_unset=True) if body is not None else {}
    return _run(svc.save_draft, db, a, article_id, data, from_revision)


@router.post("/articles/{article_id}/draft/submit")
def submit_draft(article_id: str, a: Actor = Depends(WRITE), db: Session = Depends(get_db)):
    return _run(svc.submit_draft, db, a, article_id)


@router.post("/articles/{article_id}/draft/return")
def return_draft(article_id: str, body: s.ReturnInput, a: Actor = Depends(PUBLISH), db: Session = Depends(get_db)):
    return _run(svc.return_draft, db, a, article_id, body.comment)


@router.post("/articles/{article_id}/draft/discard")
def discard_draft(article_id: str, a: Actor = Depends(WRITE_OR_PUBLISH), db: Session = Depends(get_db)):
    return _run(svc.discard_draft, db, a, article_id)


@router.post("/articles/{article_id}/publish")
def publish(
    article_id: str, body: s.PublishInput | None = None, a: Actor = Depends(PUBLISH), db: Session = Depends(get_db)
):
    return _run(svc.publish, db, a, article_id, body.review_by if body is not None else None)


@router.post("/articles/{article_id}/archive")
def archive(article_id: str, body: s.Reason, a: Actor = Depends(PUBLISH), db: Session = Depends(get_db)):
    return _run(svc.archive, db, a, article_id, body.reason)


@router.post("/articles/{article_id}/restore")
def restore(article_id: str, a: Actor = Depends(PUBLISH), db: Session = Depends(get_db)):
    return _run(svc.restore, db, a, article_id)


@router.get("/articles/{article_id}/revisions")
def list_revisions(article_id: str, a: Actor = Depends(WRITE), db: Session = Depends(get_db)):
    return _run(svc.list_revisions, db, a, article_id)


@router.get("/articles/{article_id}/revisions/{revision_no}")
def get_revision(
    article_id: str,
    revision_no: int = Path(ge=1, le=MAX_INT),
    a: Actor = Depends(WRITE),
    db: Session = Depends(get_db),
):
    return _run(svc.get_revision, db, a, article_id, revision_no)


# ---------------------------------------------------------------- feedback


@router.post("/articles/{article_id}/feedback")
def give_feedback(article_id: str, body: s.FeedbackInput, a: Actor = Depends(READ), db: Session = Depends(get_db)):
    return _run(svc.give_feedback, db, a, article_id, s.as_dict(body, partial=False))


@router.get("/articles/{article_id}/feedback")
def list_feedback(
    article_id: str,
    helpful: bool | None = None,
    cursor: str | None = CURSOR,
    limit: int = LIMIT,
    a: Actor = Depends(STATS),
    db: Session = Depends(get_db),
):
    return _run(svc.list_feedback, db, a, article_id, {"helpful": helpful, "cursor": cursor, "limit": limit})


# ---------------------------------------------------------------- statistics


@router.get("/stats/top-articles")
def top_articles(
    period: str | None = None,
    metric: str | None = None,
    limit: int | None = Query(None, ge=MIN_TOP_LIMIT, le=MAX_TOP_LIMIT),
    a: Actor = Depends(STATS),
    db: Session = Depends(get_db),
):
    return _run(
        svc.top_articles_stats,
        db,
        a,
        _single(period, tuple(PERIOD_DAYS), "period") or "30d",
        _single(metric, METRICS, "metric") or "views",
        limit,
    )
