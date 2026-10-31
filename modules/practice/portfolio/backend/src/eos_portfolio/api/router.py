"""HTTP surface of portfolio, matching contracts/openapi.yaml.
Mounted under /api/v1/portfolio."""

from __future__ import annotations

from typing import Literal

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, PortfolioError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["portfolio"])


def _fail(e: PortfolioError) -> HTTPException:
    return HTTPException(e.status, e.body())


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except PortfolioError as e:
        raise _fail(e) from e


# ---------------------------------------------------------------- Item Types


@router.get("/item-types")
def list_item_types(
    actor: Actor = Depends(require(svc.ITEM_TYPE_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_item_types, db, actor)


@router.post("/item-types", status_code=status.HTTP_201_CREATED)
def create_item_type(
    body: s.ItemTypeInput,
    actor: Actor = Depends(require(svc.ITEM_TYPE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.create_item_type, db, actor, body.model_dump())


@router.patch("/item-types/{id}")
def update_item_type(
    id: str,
    body: s.ItemTypeInput,
    actor: Actor = Depends(require(svc.ITEM_TYPE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_item_type, db, actor, id, body.model_dump(exclude_unset=True))


@router.delete("/item-types/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item_type(
    id: str,
    actor: Actor = Depends(require(svc.ITEM_TYPE_MANAGE)),
    db: Session = Depends(get_db),
):
    _run(svc.delete_item_type, db, actor, id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- Items


@router.get("/items")
def list_items(
    scope: Literal["mine", "managed"] = "mine",
    owner_person_id: str | None = None,
    type_id: str | None = None,
    status: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    actor: Actor = Depends(require(svc.ITEM_READ)),
    db: Session = Depends(get_db),
):
    statuses = [s.strip() for s in status.split(",") if s.strip()] if status else None
    return _run(
        svc.list_items,
        db,
        actor,
        scope=scope,
        owner_person_id=owner_person_id,
        type_id=type_id,
        statuses=statuses,
        q=q,
        page=page,
        page_size=page_size,
    )


@router.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(
    body: s.ItemInput,
    actor: Actor = Depends(require(svc.ITEM_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.create_item, db, actor, body.model_dump())


@router.get("/items/{id}")
def get_item(
    id: str,
    actor: Actor = Depends(require(svc.ITEM_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.get_item, db, actor, id)


@router.patch("/items/{id}")
def update_item(
    id: str,
    body: s.ItemInput,
    actor: Actor = Depends(require(svc.ITEM_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_item, db, actor, id, body.model_dump(exclude_unset=True))


@router.delete("/items/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    id: str,
    actor: Actor = Depends(require(svc.ITEM_WRITE)),
    db: Session = Depends(get_db),
):
    _run(svc.delete_item, db, actor, id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/items/{id}/submit")
def submit_item(
    id: str,
    actor: Actor = Depends(require(svc.ITEM_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.submit_item, db, actor, id)


@router.post("/items/{id}/withdraw")
def withdraw_item(
    id: str,
    actor: Actor = Depends(require(svc.ITEM_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.withdraw_item, db, actor, id)


# ---------------------------------------------------------------- Media


@router.get("/items/{id}/media")
def list_media(
    id: str,
    actor: Actor = Depends(require(svc.ITEM_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_media, db, actor, id)


@router.post("/items/{id}/media", status_code=status.HTTP_201_CREATED)
def add_media(
    id: str,
    body: s.ItemMediaInput,
    actor: Actor = Depends(require(svc.ITEM_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.add_media, db, actor, id, body.model_dump())


@router.delete("/items/{id}/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_media(
    id: str,
    media_id: str,
    actor: Actor = Depends(require(svc.ITEM_WRITE)),
    db: Session = Depends(get_db),
):
    _run(svc.delete_media, db, actor, id, media_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- Reviews


@router.get("/items/{id}/reviews")
def list_reviews(
    id: str,
    actor: Actor = Depends(require(svc.ITEM_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_reviews, db, actor, id)


@router.post("/items/{id}/reviews", status_code=status.HTTP_201_CREATED)
def add_review(
    id: str,
    body: s.ReviewInput,
    actor: Actor = Depends(require(svc.REVIEW_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.add_review, db, actor, id, body.model_dump())
