"""Routes from contracts/openapi.yaml, mounted by the host at /api/v1/web-portal-cms. Each route names the permission
key it needs; the service filters every query by the caller's organisation and hides unpublished content from
callers without the manage key."""

from __future__ import annotations

from typing import Any, Literal

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, CmsError
from . import schemas as s
from .deps import (
    PERM_ANNOUNCEMENT_MANAGE,
    PERM_ANNOUNCEMENT_READ,
    PERM_PAGE_MANAGE,
    PERM_PAGE_READ,
    require,
)

router = APIRouter(tags=["web-portal-cms"])

Status = Literal["visible", "draft", "published", "all"]
SlugPath = Path(pattern=r"^[a-z0-9-]{1,120}$")
PageNumber = Query(1, ge=1)
PageSize = Query(50, ge=1, le=200)


def _run(db: Session, fn, *args: Any, conflict: tuple[str, str] | None = None, **kwargs: Any) -> Any:
    """Run a use case, commit, and turn refusals into the contract's {code, message} error body."""
    try:
        result = fn(db, *args, **kwargs)
        db.commit()
        return result
    except CmsError as exc:
        db.rollback()
        raise HTTPException(exc.status, exc.to_dict()) from exc
    except IntegrityError as exc:
        # Two requests passed the same check at once; the unique index decided.
        db.rollback()
        code, message = conflict or ("conflict", "a record with the same unique value already exists")
        raise HTTPException(409, {"code": code, "message": message}) from exc


# ---------------------------------------------------------------- pages


@router.get("/pages")
def list_pages(
    type: Literal["standard", "landing", "terms"] | None = None,
    status: Status = "visible",
    page: int = PageNumber,
    page_size: int = PageSize,
    actor: Actor = Depends(require(PERM_PAGE_READ)),
    db: Session = Depends(get_db),
):
    return _run(db, svc.list_pages, actor, type=type, status=status, page=page, page_size=page_size)


@router.post("/pages", status_code=201)
def create_page(body: s.PageInput, actor: Actor = Depends(require(PERM_PAGE_MANAGE)), db: Session = Depends(get_db)):
    return _run(
        db,
        svc.create_page,
        actor,
        slug=body.slug,
        title=body.title,
        type=body.type,
        body=body.body,
        seo_description=body.seo_description,
        conflict=("duplicate_slug", f"The slug {body.slug!r} is already used in this organisation"),
    )


@router.get("/pages/{slug}")
def get_page(slug: str = SlugPath, actor: Actor = Depends(require(PERM_PAGE_READ)), db: Session = Depends(get_db)):
    return _run(db, svc.get_page, actor, slug)


@router.patch("/pages/{slug}")
def update_page(
    body: s.PageUpdate,
    slug: str = SlugPath,
    actor: Actor = Depends(require(PERM_PAGE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(db, svc.update_page, actor, slug, body.changes())


@router.delete("/pages/{slug}", status_code=204)
def delete_page(slug: str = SlugPath, actor: Actor = Depends(require(PERM_PAGE_MANAGE)), db: Session = Depends(get_db)):
    _run(db, svc.delete_page, actor, slug)
    return Response(status_code=204)


@router.post("/pages/{slug}/publish")
def publish_page(
    body: s.PublishInput,
    slug: str = SlugPath,
    actor: Actor = Depends(require(PERM_PAGE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(db, svc.publish_page, actor, slug, body.published)


# ---------------------------------------------------------------- announcements


@router.get("/announcements")
def list_announcements(
    status: Status = "visible",
    page: int = PageNumber,
    page_size: int = PageSize,
    actor: Actor = Depends(require(PERM_ANNOUNCEMENT_READ)),
    db: Session = Depends(get_db),
):
    return _run(db, svc.list_announcements, actor, status=status, page=page, page_size=page_size)


@router.post("/announcements", status_code=201)
def create_announcement(
    body: s.AnnouncementInput, actor: Actor = Depends(require(PERM_ANNOUNCEMENT_MANAGE)), db: Session = Depends(get_db)
):
    return _run(
        db,
        svc.create_announcement,
        actor,
        title=body.title,
        body=body.body,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
    )


@router.get("/announcements/{id}")
def get_announcement(id: str, actor: Actor = Depends(require(PERM_ANNOUNCEMENT_READ)), db: Session = Depends(get_db)):
    return _run(db, svc.get_announcement, actor, id)


@router.patch("/announcements/{id}")
def update_announcement(
    id: str,
    body: s.AnnouncementUpdate,
    actor: Actor = Depends(require(PERM_ANNOUNCEMENT_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(db, svc.update_announcement, actor, id, body.changes())


@router.delete("/announcements/{id}", status_code=204)
def delete_announcement(
    id: str, actor: Actor = Depends(require(PERM_ANNOUNCEMENT_MANAGE)), db: Session = Depends(get_db)
):
    _run(db, svc.delete_announcement, actor, id)
    return Response(status_code=204)


@router.post("/announcements/{id}/publish")
def publish_announcement(
    id: str,
    body: s.PublishInput,
    actor: Actor = Depends(require(PERM_ANNOUNCEMENT_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(db, svc.publish_announcement, actor, id, body.published)
