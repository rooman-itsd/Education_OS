"""What every use case shares: the clock, audit entries, outbox events, lookups that answer 404, and who may see or
change a course space (application/access.py explains the scopes).

A course space is seen in one of three views:
- `staff`: the space's instructors and LMS administrators (lms:course-space:manage-all). Drafts, unpublished and hidden
  content included.
- `learner`: a student registered in the offering, in a visible section. Only active or archived spaces, published
  content in published units, for their section.
- `reader`: holders of lms:course-space:read-all who neither teach nor learn there (for example a viewer). Published
  content of every section, no drafts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.rules import RuleViolationError, section_visible
from ..infrastructure import repository as repo
from ..infrastructure.models import AuditEntry, CourseSpace
from . import access as k
from .access import Actor
from .errors import LmsError, conflict, forbidden, from_rule, not_found

UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

STAFF, LEARNER, READER = "staff", "learner", "reader"


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


def audit(db: Session, actor: Actor | None, action: str, entity: str, entity_id: str, organisation_id: str) -> None:
    db.add(
        AuditEntry(
            organisation_id=organisation_id,
            actor=actor.user_id if actor else None,
            action=action,
            entity=entity,
            entity_id=entity_id,
            occurred_at=clock(),
        )
    )


def publish(db: Session, actor: Actor | None, name: str, organisation_id: str, payload: dict) -> None:
    """To the outbox, in the caller's transaction. Every payload carries organisation_id (contracts/events.yaml)."""
    events.publish(
        db,
        f"{k.MODULE}.{name}",
        organisation_id,
        {"organisation_id": organisation_id, **payload},
        actor=actor.user_id if actor else None,
    )


def get(db: Session, model, row_id: str, what: str, *, for_update: bool = False):
    """The row in the caller's organisation, or 404. An id that is not a uuid cannot exist."""
    if not isinstance(row_id, str) or not UUID.match(row_id):
        raise not_found(what)
    row = repo.get_for_update(db, model, row_id) if for_update else repo.get(db, model, row_id)
    if row is None:
        raise not_found(what)
    return row


def check(fn, *args):
    try:
        return fn(*args)
    except RuleViolationError as v:
        raise from_rule(v) from v


def flush_unique(db: Session, code: str, message: str) -> None:
    """Write now, so a duplicate that slipped past the check (two requests at once) is a 409, not a 500."""
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise conflict(code, message) from None


# ---------------------------------------------------------------- membership and views


@dataclass
class Viewer:
    kind: str
    sections: set[str | None] = field(default_factory=set)

    @property
    def staff(self) -> bool:
        return self.kind == STAFF

    @property
    def learner(self) -> bool:
        return self.kind == LEARNER

    def sees(self, visible_section_ids: list[str]) -> bool:
        """Whether a section-limited item reaches this viewer. Staff and readers see every section."""
        if not self.learner:
            return True
        return any(section_visible(visible_section_ids or [], s) for s in self.sections)


def teaches(db: Session, a: Actor, space: CourseSpace) -> bool:
    return space.course_offering_id in repo.taught_offerings(db, a.user_id)


def learner_sections(db: Session, a: Actor, space: CourseSpace) -> set[str | None] | None:
    """The caller's sections when they are a student of the space (registered, in a visible section), else None."""
    sections = repo.registrations(db, a.user_id).get(space.course_offering_id)
    if not sections:
        return None
    visible = {s for s in sections if section_visible(space.visible_section_ids or [], s)}
    return visible or None


def viewer(db: Session, a: Actor, space: CourseSpace) -> Viewer:
    """How the caller sees the space; 403 when they have no business there, 404 for a student before activation."""
    if a.can(k.COURSE_SPACE_MANAGE_ALL) or teaches(db, a, space):
        return Viewer(STAFF)
    sections = learner_sections(db, a, space)
    if sections is not None:
        if space.status == "draft":
            raise not_found("course space")
        return Viewer(LEARNER, sections)
    if a.can(k.COURSE_SPACE_READ_ALL):
        return Viewer(READER)
    raise forbidden("you do not belong to this course space", "not_in_scope")


def require_scope(db: Session, a: Actor, space: CourseSpace, assigned_key: str) -> None:
    """The `-assigned` key covers spaces the caller teaches; its `-all` key covers every space."""
    if a.can(k.MANAGE_ALL[assigned_key]):
        return
    if a.can(assigned_key) and teaches(db, a, space):
        return
    raise forbidden(f"{assigned_key} covers only the course spaces you teach", "not_in_scope")


def require_writable(space: CourseSpace) -> None:
    if space.status == "archived":
        raise conflict("course_space_archived", "the course space is archived and read-only")


def space_of(db: Session, space_id: str) -> CourseSpace:
    return get(db, CourseSpace, space_id, "course space")


def staff_of(db: Session, a: Actor, space: CourseSpace, assigned_key: str) -> bool:
    """Whether the caller manages this resource in this space (for showing drafts, answer keys and hidden posts)."""
    try:
        require_scope(db, a, space, assigned_key)
    except LmsError:
        return False
    return True
