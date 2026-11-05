"""Discussion threads and posts, and their moderation (FR-14, FR-15). Members (the space's instructors and students)
post while the space is active and the thread open; LMS administrators may too. Hidden content is kept for audit and
shown only to moderators."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..domain import rules
from ..infrastructure import repository as repo
from ..infrastructure.models import CourseSpace, DiscussionPost, DiscussionThread, as_utc, iso
from . import access as k
from . import common as c
from .access import Actor
from .errors import conflict, forbidden, not_found


def thread_dict(t: DiscussionThread, post_count: int) -> dict:
    return {
        "id": t.id,
        "organisation_id": t.organisation_id,
        "course_space_id": t.course_space_id,
        "title": t.title,
        "body": t.body,
        "created_by": t.created_by,
        "created_at": iso(t.created_at),
        "state": rules.thread_state(t.locked, t.hidden),
        "post_count": post_count,
        "last_activity_at": iso(t.last_activity_at),
    }


def post_dict(p: DiscussionPost) -> dict:
    return {
        "id": p.id,
        "organisation_id": p.organisation_id,
        "thread_id": p.thread_id,
        "body": p.body,
        "created_by": p.created_by,
        "created_at": iso(p.created_at),
        "state": p.state,
    }


def _moderates(db: Session, a: Actor, space: CourseSpace) -> bool:
    return c.staff_of(db, a, space, k.DISCUSSION_MODERATE_ASSIGNED)


def _may_post(db: Session, a: Actor, space: CourseSpace) -> None:
    """Members of the space, and holders of discussion:moderate-all (the LMS administrator), take part."""
    view = c.viewer(db, a, space)
    member = view.learner or c.teaches(db, a, space)
    if not (member or a.can(k.DISCUSSION_MODERATE_ALL)):
        raise forbidden("only members of the course space take part in its discussions", "not_a_member")
    if space.status != "active":
        raise conflict("course_space_not_active", "the course space is not active")


def list_threads(db: Session, a: Actor, space_id: str, limit: int, offset: int) -> dict:
    space = c.space_of(db, space_id)
    c.viewer(db, a, space)
    query = repo.threads(db, [space.id], include_hidden=_moderates(db, a, space))
    total = repo.count(db, query)
    rows = list(db.scalars(query.offset(offset).limit(limit)))
    counts = repo.post_counts(db, [t.id for t in rows])
    return {"items": [thread_dict(t, counts.get(t.id, 0)) for t in rows], "total": total}


def create_thread(db: Session, a: Actor, space_id: str, body: dict) -> dict:
    space = c.get(db, CourseSpace, space_id, "course space", for_update=True)
    _may_post(db, a, space)
    now = c.clock()
    t = DiscussionThread(
        organisation_id=a.organisation_id,
        course_space_id=space.id,
        title=body["title"],
        body=body["body"],
        created_by=a.user_id,
        locked=False,
        hidden=False,
        last_activity_at=now,
        created_at=now,
    )
    db.add(t)
    db.flush()
    c.audit(db, a, "discussion-thread.created", "discussion-thread", t.id, a.organisation_id)
    c.publish(
        db,
        a,
        "discussion-thread.created",
        a.organisation_id,
        {
            "thread_id": t.id,
            "course_space_id": space.id,
            "title": t.title,
            "created_by": a.user_id,
            "created_at": iso(t.created_at),
        },
    )
    db.commit()
    return thread_dict(t, 0)


def _thread(db: Session, a: Actor, thread_id: str, *, for_update: bool = False):
    t = c.get(db, DiscussionThread, thread_id, "thread", for_update=for_update)
    space = c.space_of(db, t.course_space_id)
    c.viewer(db, a, space)
    moderator = _moderates(db, a, space)
    if t.hidden and not moderator:
        raise not_found("thread")
    return t, space, moderator


def get_thread(db: Session, a: Actor, thread_id: str, limit: int, offset: int) -> dict:
    t, _, moderator = _thread(db, a, thread_id)
    query = repo.posts(db, t.id, include_hidden=moderator)
    total = repo.count(db, query)
    posts = list(db.scalars(query.offset(offset).limit(limit)))
    return {
        "thread": thread_dict(t, repo.post_counts(db, [t.id]).get(t.id, 0)),
        "posts": [post_dict(p) for p in posts],
        "total": total,
    }


def create_post(db: Session, a: Actor, thread_id: str, body: dict) -> dict:
    t, space, _ = _thread(db, a, thread_id, for_update=True)
    _may_post(db, a, space)
    if t.locked or t.hidden:
        raise conflict("thread_closed", f"the thread is {rules.thread_state(t.locked, t.hidden)}")
    now = c.clock()
    p = DiscussionPost(
        organisation_id=a.organisation_id,
        thread_id=t.id,
        body=body["body"],
        created_by=a.user_id,
        state="visible",
        created_at=now,
    )
    db.add(p)
    t.last_activity_at = max(as_utc(t.last_activity_at), now)
    db.flush()
    c.audit(db, a, "discussion-post.created", "discussion-post", p.id, a.organisation_id)
    db.commit()
    return post_dict(p)


def moderate_thread(db: Session, a: Actor, thread_id: str, action: str) -> dict:
    t = c.get(db, DiscussionThread, thread_id, "thread", for_update=True)
    space = c.space_of(db, t.course_space_id)
    c.require_scope(db, a, space, k.DISCUSSION_MODERATE_ASSIGNED)
    c.require_writable(space)
    t.locked, t.hidden = c.check(rules.moderate_thread, action, t.locked, t.hidden)
    past = {"lock": "locked", "unlock": "unlocked", "hide": "hidden", "unhide": "unhidden"}[action]
    c.audit(db, a, f"discussion-thread.{past}", "discussion-thread", t.id, a.organisation_id)
    db.commit()
    return thread_dict(t, repo.post_counts(db, [t.id]).get(t.id, 0))


def moderate_post(db: Session, a: Actor, post_id: str, action: str) -> dict:
    """Hiding a hidden post (or showing a visible one) changes nothing and answers the post as it is."""
    p = c.get(db, DiscussionPost, post_id, "post", for_update=True)
    t = c.get(db, DiscussionThread, p.thread_id, "thread")
    space = c.space_of(db, t.course_space_id)
    c.require_scope(db, a, space, k.DISCUSSION_MODERATE_ASSIGNED)
    state = "hidden" if action == "hide" else "visible"
    if p.state != state:
        c.require_writable(space)
        p.state = state
        action_done = "hidden" if state == "hidden" else "unhidden"
        c.audit(db, a, f"discussion-post.{action_done}", "discussion-post", p.id, a.organisation_id)
        db.commit()
    return post_dict(p)
