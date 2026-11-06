"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security enforces
the same rule underneath."""

from __future__ import annotations

import base64
from datetime import date

from eos_core.db import new_id, scoped
from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .models import Article, Category, Feedback, Revision, ViewDay, ViewSeen

# A cursor is an offset into an ordered result. Anything above this is not one this module handed out.
MAX_OFFSET = 1_000_000


def _scoped(db: Session, model) -> Select:
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str):
    return db.scalars(_scoped(db, model).where(model.id == row_id)).first()


def _insert(db: Session):
    return postgresql_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert


# ---------------------------------------------------------------- cursors


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def decode_cursor(cursor: str | None) -> int | None:
    """The offset of a cursor, 0 for none, None for one this module did not hand out."""
    if not cursor:
        return 0
    try:
        offset = int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except (ValueError, UnicodeDecodeError):
        return None
    return offset if 0 <= offset <= MAX_OFFSET else None


def page_of(rows: list, offset: int, limit: int) -> tuple[list, str | None]:
    """A page of rows already filtered and ordered in Python."""
    chunk = rows[offset : offset + limit]
    return chunk, encode_cursor(offset + limit) if offset + limit < len(rows) else None


# ---------------------------------------------------------------- categories


def categories(db: Session) -> list[Category]:
    return list(db.scalars(_scoped(db, Category)))


# ---------------------------------------------------------------- articles and revisions


def article_for_update(db: Session, article_id: str) -> Article | None:
    """The article row, locked (FOR UPDATE on Postgres) so revision numbers, open-revision moves and counters on one
    article are changed by one request at a time."""
    return db.scalars(_scoped(db, Article).where(Article.id == article_id).with_for_update()).first()


def articles(db: Session, statuses: list[str] | None = None) -> list[Article]:
    query = _scoped(db, Article)
    if statuses:
        query = query.where(Article.status.in_(statuses))
    return list(db.scalars(query))


def articles_by_id(db: Session, ids: list[str]) -> dict[str, Article]:
    if not ids:
        return {}
    return {a.id: a for a in db.scalars(_scoped(db, Article).where(Article.id.in_(ids)))}


def slug_taken(db: Session, slug: str) -> bool:
    return db.scalars(scoped(db, select(Article.id), Article).where(Article.slug == slug)).first() is not None


def slugs_like(db: Session, prefix: str) -> set[str]:
    return set(
        db.scalars(scoped(db, select(Article.slug), Article).where(Article.slug.startswith(prefix, autoescape=True)))
    )


def revision(db: Session, article_id: str, revision_no: int) -> Revision | None:
    return db.scalars(
        _scoped(db, Revision).where(Revision.article_id == article_id, Revision.revision_no == revision_no)
    ).first()


def revisions_of(db: Session, article_id: str) -> list[Revision]:
    """Newest first."""
    return list(
        db.scalars(_scoped(db, Revision).where(Revision.article_id == article_id).order_by(Revision.revision_no.desc()))
    )


def revisions_by_key(db: Session, keys: list[tuple[str, int]]) -> dict[tuple[str, int], Revision]:
    """Revisions for (article_id, revision_no) pairs, in one query."""
    if not keys:
        return {}
    ids = sorted({k[0] for k in keys})
    wanted = set(keys)
    rows = db.scalars(_scoped(db, Revision).where(Revision.article_id.in_(ids)))
    return {(r.article_id, r.revision_no): r for r in rows if (r.article_id, r.revision_no) in wanted}


def published_count_by_category(db: Session) -> dict[str, tuple[int, int]]:
    """Per category id: (published articles for everyone, published staff articles), from published revisions."""
    rows = db.execute(
        scoped(
            db,
            select(Revision.category_id, Revision.audience, func.count())
            .join(Article, Article.id == Revision.article_id)
            .where(Article.status == "published", Revision.revision_no == Article.published_revision_no),
            Revision,
        ).group_by(Revision.category_id, Revision.audience)
    )
    out: dict[str, tuple[int, int]] = {}
    for category_id, audience, n in rows:
        everyone, staff = out.get(category_id, (0, 0))
        out[category_id] = (everyone + n, staff) if audience == "everyone" else (everyone, staff + n)
    return out


# ---------------------------------------------------------------- feedback


def feedback_of(db: Session, article_id: str, person_id: str) -> Feedback | None:
    return db.scalars(
        _scoped(db, Feedback).where(Feedback.article_id == article_id, Feedback.person_id == person_id)
    ).first()


def feedback_list(db: Session, article_id: str, helpful: bool | None) -> list[Feedback]:
    """Newest first."""
    query = _scoped(db, Feedback).where(Feedback.article_id == article_id)
    if helpful is not None:
        query = query.where(Feedback.helpful.is_(helpful))
    return list(db.scalars(query.order_by(Feedback.created_at.desc(), Feedback.id.desc())))


# ---------------------------------------------------------------- views


def count_view(db: Session, organisation_id: str, article_id: str, day: date, reader_key: str) -> bool:
    """Counts one view unless this reader already counted one today. Concurrent first views are safe: the seen row and
    the day row are created with ON CONFLICT DO NOTHING, and the totals change with UPDATE ... + 1. Earlier days'
    seen rows are deleted, so only today's are ever kept. Whether the seen row was new is read from RETURNING, not
    rowcount, which the Postgres driver does not report for INSERT ... ON CONFLICT DO NOTHING here."""
    insert = _insert(db)
    db.execute(delete(ViewSeen).where(ViewSeen.organisation_id == organisation_id, ViewSeen.day < day))
    seen = db.execute(
        insert(ViewSeen)
        .values(id=new_id(), organisation_id=organisation_id, article_id=article_id, day=day, reader_key=reader_key)
        .on_conflict_do_nothing(index_elements=["article_id", "day", "reader_key"])
        .returning(ViewSeen.id)
    ).scalar()
    if seen is None:
        return False
    db.execute(
        insert(ViewDay)
        .values(id=new_id(), organisation_id=organisation_id, article_id=article_id, day=day, views=0)
        .on_conflict_do_nothing(index_elements=["article_id", "day"])
    )
    db.execute(
        update(ViewDay)
        .where(ViewDay.organisation_id == organisation_id, ViewDay.article_id == article_id, ViewDay.day == day)
        .values(views=ViewDay.views + 1)
    )
    db.execute(
        update(Article)
        .where(Article.organisation_id == organisation_id, Article.id == article_id)
        .values(view_count=Article.view_count + 1)
    )
    return True


def views_since(db: Session, first_day: date) -> dict[str, int]:
    """Views per article from first_day on."""
    rows = db.execute(
        scoped(
            db, select(ViewDay.article_id, func.sum(ViewDay.views)).where(ViewDay.day >= first_day), ViewDay
        ).group_by(ViewDay.article_id)
    )
    return {article_id: int(total or 0) for article_id, total in rows}
