"""Course spaces, content units and course materials (FR-1 to FR-5), and the Student widget's recent materials
(FR-17). Each change checks the domain rules, writes an audit entry and publishes its event to the outbox in the same
transaction."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from ..domain import rules
from ..infrastructure import repository as repo
from ..infrastructure.models import ContentUnit, CourseMaterial, CourseSpace, OfferingRef, iso
from . import access as k
from . import common as c
from .access import Actor
from .errors import conflict, not_found, unprocessable

# ---------------------------------------------------------------- serialisation


def _offering_facts(offering: OfferingRef | None) -> dict:
    out = {}
    if offering is not None and offering.course_code:
        out["course_code"] = offering.course_code
    if offering is not None and offering.course_title:
        out["course_title"] = offering.course_title
    return out


def space_dict(space: CourseSpace, offering: OfferingRef | None, caller_is_instructor: bool) -> dict:
    return {
        "id": space.id,
        "organisation_id": space.organisation_id,
        "course_offering_id": space.course_offering_id,
        **_offering_facts(offering),
        "department_id": space.department_id,
        "title": space.title,
        "description": space.description,
        "visible_section_ids": list(space.visible_section_ids or []),
        "status": space.status,
        "caller_is_instructor": caller_is_instructor,
    }


def course_title(space: CourseSpace, offering: OfferingRef | None) -> str:
    return offering.course_title if offering is not None and offering.course_title else space.title


def unit_dict(u: ContentUnit) -> dict:
    return {
        "id": u.id,
        "organisation_id": u.organisation_id,
        "course_space_id": u.course_space_id,
        "title": u.title,
        "position": u.position,
        "published": u.published,
    }


def material_dict(m: CourseMaterial) -> dict:
    out = {
        "id": m.id,
        "organisation_id": m.organisation_id,
        "course_space_id": m.course_space_id,
        "material_type": m.material_type,
        "title": m.title,
        "visible_section_ids": list(m.visible_section_ids or []),
        "status": m.status,
        "published_at": iso(m.published_at),
    }
    for name in ("unit_id", "document_id", "url", "body", "scheduled_class_id"):
        if getattr(m, name) is not None:
            out[name] = getattr(m, name)
    return out


def _page(rows: list, limit: int, offset: int) -> dict:
    return {"items": rows[offset : offset + limit], "total": len(rows)}


# ---------------------------------------------------------------- course spaces


def _my_spaces(db: Session, a: Actor) -> list[CourseSpace]:
    """The spaces the caller teaches, and the active or archived spaces they learn in (visible section)."""
    taught = repo.taught_offerings(db, a.user_id)
    registered = repo.registrations(db, c.learner_ids(db, a))
    out = []
    for space in repo.spaces_for_offerings(db, taught | set(registered)):
        if space.course_offering_id in taught:
            out.append(space)
        elif space.status != "draft" and c.learner_sections(db, a, space) is not None:
            out.append(space)
    return out


def list_spaces(db: Session, a: Actor, filters: dict, limit: int, offset: int) -> dict:
    if a.can(k.COURSE_SPACE_READ_ALL):
        spaces = list(db.scalars(repo.spaces_query(db, filters)))
    else:
        mine = {s.id for s in _my_spaces(db, a)}
        spaces = [s for s in db.scalars(repo.spaces_query(db, filters)) if s.id in mine]
    taught = repo.taught_offerings(db, a.user_id)
    offerings = repo.offerings(db, {s.course_offering_id for s in spaces})
    rows = [space_dict(s, offerings.get(s.course_offering_id), s.course_offering_id in taught) for s in spaces]
    return _page(rows, limit, offset)


def _space_out(db: Session, a: Actor, space: CourseSpace) -> dict:
    return space_dict(space, repo.offering(db, space.course_offering_id), c.teaches(db, a, space))


def create_space(db: Session, a: Actor, body: dict) -> dict:
    offering = repo.offering(db, body["course_offering_id"])
    if offering is None or offering.academic_period_id is None:
        raise unprocessable("unknown_course_offering", "the course offering is not known to lms yet")
    if repo.space_by_offering(db, offering.course_offering_id) is not None:
        raise conflict("course_space_exists", "the course offering already has a course space")
    space = CourseSpace(
        organisation_id=a.organisation_id,
        course_offering_id=offering.course_offering_id,
        title=body["title"],
        description=body.get("description"),
        visible_section_ids=body.get("visible_section_ids") or [],
        department_id=offering.department_id,
        status="draft",
        created_by=a.user_id,
        created_at=c.clock(),
    )
    db.add(space)
    c.flush_unique(db, "course_space_exists", "the course offering already has a course space")
    c.audit(db, a, "course-space.created", "course-space", space.id, a.organisation_id)
    c.publish(
        db,
        a,
        "course-space.created",
        a.organisation_id,
        {
            "course_space_id": space.id,
            "course_offering_id": space.course_offering_id,
            "title": space.title,
            "visible_section_ids": list(space.visible_section_ids),
        },
    )
    db.commit()
    return _space_out(db, a, space)


def get_space(db: Session, a: Actor, space_id: str) -> dict:
    space = c.space_of(db, space_id)
    c.viewer(db, a, space)
    return _space_out(db, a, space)


def update_space(db: Session, a: Actor, space_id: str, body: dict) -> dict:
    space = c.get(db, CourseSpace, space_id, "course space", for_update=True)
    c.require_scope(db, a, space, k.COURSE_SPACE_MANAGE_ASSIGNED)
    c.require_writable(space)
    for name in ("title", "description", "visible_section_ids"):
        if name in body:
            setattr(space, name, body[name] if name != "visible_section_ids" else list(body[name] or []))
    c.audit(db, a, "course-space.updated", "course-space", space.id, a.organisation_id)
    db.commit()
    return _space_out(db, a, space)


def change_space_status(db: Session, a: Actor, space_id: str, status: str) -> dict:
    space = c.get(db, CourseSpace, space_id, "course space", for_update=True)
    c.require_scope(db, a, space, k.COURSE_SPACE_MANAGE_ASSIGNED)
    space.status = c.check(rules.transition, rules.COURSE_SPACE_TRANSITIONS, status, space.status, "course space")
    action = "activated" if status == "active" else "archived"
    c.audit(db, a, f"course-space.{action}", "course-space", space.id, a.organisation_id)
    db.commit()
    return _space_out(db, a, space)


# ---------------------------------------------------------------- content units


def list_units(db: Session, a: Actor, space_id: str) -> dict:
    space = c.space_of(db, space_id)
    view = c.viewer(db, a, space)
    units = repo.units(db, space.id)
    if not view.staff:
        units = [u for u in units if u.published]
    return {"items": [unit_dict(u) for u in units]}


def create_unit(db: Session, a: Actor, space_id: str, body: dict) -> dict:
    space = c.get(db, CourseSpace, space_id, "course space", for_update=True)
    c.require_scope(db, a, space, k.MATERIAL_MANAGE_ASSIGNED)
    c.require_writable(space)
    position = body.get("position")
    unit = ContentUnit(
        organisation_id=a.organisation_id,
        course_space_id=space.id,
        title=body["title"],
        position=repo.next_unit_position(db, space.id),
        published=bool(body.get("published", False)),
        created_at=c.clock(),
    )
    db.add(unit)
    db.flush()
    if position is not None:
        _move(db, space.id, unit, position)
    c.audit(db, a, "content-unit.created", "content-unit", unit.id, a.organisation_id)
    db.commit()
    return unit_dict(unit)


def update_unit(db: Session, a: Actor, unit_id: str, body: dict) -> dict:
    unit = c.get(db, ContentUnit, unit_id, "content unit", for_update=True)
    space = c.space_of(db, unit.course_space_id)
    c.require_scope(db, a, space, k.MATERIAL_MANAGE_ASSIGNED)
    c.require_writable(space)
    was_published = unit.published
    for name in ("title", "published"):
        if body.get(name) is not None:
            setattr(unit, name, body[name])
    if body.get("position") is not None:
        _move(db, space.id, unit, body["position"])
    action = "updated"
    if unit.published != was_published:
        action = "published" if unit.published else "unpublished"
    c.audit(db, a, f"content-unit.{action}", "content-unit", unit.id, a.organisation_id)
    db.commit()
    return unit_dict(unit)


def _move(db: Session, space_id: str, unit: ContentUnit, position: int) -> None:
    """Reorder: the unit goes to `position` among the space's units (the end if past it) and the others close up, so
    positions stay 0..n-1."""
    others = [u for u in repo.units(db, space_id) if u.id != unit.id]
    others.insert(min(position, len(others)), unit)
    for i, u in enumerate(others):
        u.position = i


# ---------------------------------------------------------------- course materials


def _unit_in(db: Session, space: CourseSpace, unit_id: str | None) -> None:
    if unit_id is None:
        return
    unit = repo.get(db, ContentUnit, unit_id)
    if unit is None or unit.course_space_id != space.id:
        raise unprocessable("unknown_unit", "the content unit is not in this course space")


def _learner_visible(view: c.Viewer, m: CourseMaterial, published_units: set[str]) -> bool:
    if m.status != "published":
        return False
    if m.unit_id is not None and m.unit_id not in published_units:
        return False
    return view.sees(m.visible_section_ids or [])


def list_materials(db: Session, a: Actor, space_id: str, filters: dict, limit: int, offset: int) -> dict:
    space = c.space_of(db, space_id)
    view = c.viewer(db, a, space)
    rows = repo.materials(db, [space.id], unit_id=filters.get("unit_id"), material_type=filters.get("material_type"))
    if not view.staff:
        published = {u.id for u in repo.units(db, space.id) if u.published}
        rows = [m for m in rows if _learner_visible(view, m, published)]
    return _page([material_dict(m) for m in rows], limit, offset)


def create_material(db: Session, a: Actor, space_id: str, body: dict) -> dict:
    space = c.get(db, CourseSpace, space_id, "course space", for_update=True)
    c.require_scope(db, a, space, k.MATERIAL_MANAGE_ASSIGNED)
    c.require_writable(space)
    content = (body.get("document_id"), body.get("url"), body.get("body"))
    c.check(rules.check_material_content, body["material_type"], *content)
    _unit_in(db, space, body.get("unit_id"))
    m = CourseMaterial(
        organisation_id=a.organisation_id,
        course_space_id=space.id,
        unit_id=body.get("unit_id"),
        material_type=body["material_type"],
        title=body["title"],
        document_id=body.get("document_id"),
        url=body.get("url"),
        body=body.get("body"),
        scheduled_class_id=body.get("scheduled_class_id"),
        visible_section_ids=body.get("visible_section_ids") or [],
        status="draft",
        created_by=a.user_id,
        created_at=c.clock(),
    )
    db.add(m)
    db.flush()
    c.audit(db, a, "material.created", "material", m.id, a.organisation_id)
    db.commit()
    return material_dict(m)


def get_material(db: Session, a: Actor, material_id: str) -> dict:
    m = c.get(db, CourseMaterial, material_id, "course material")
    space = c.space_of(db, m.course_space_id)
    view = c.viewer(db, a, space)
    if not view.staff:
        published = {u.id for u in repo.units(db, space.id) if u.published}
        if not _learner_visible(view, m, published):
            raise not_found("course material")
    return material_dict(m)


def update_material(db: Session, a: Actor, material_id: str, body: dict) -> dict:
    m = c.get(db, CourseMaterial, material_id, "course material", for_update=True)
    space = c.space_of(db, m.course_space_id)
    c.require_scope(db, a, space, k.MATERIAL_MANAGE_ASSIGNED)
    c.require_writable(space)
    if "unit_id" in body:
        _unit_in(db, space, body["unit_id"])
    for name in ("title", "unit_id", "document_id", "url", "body", "visible_section_ids", "scheduled_class_id"):
        if name in body:
            value = body[name]
            setattr(m, name, list(value or []) if name == "visible_section_ids" else value)
    c.check(rules.check_material_content, m.material_type, m.document_id, m.url, m.body)
    c.audit(db, a, "material.updated", "material", m.id, a.organisation_id)
    db.commit()
    return material_dict(m)


def change_material_status(db: Session, a: Actor, material_id: str, status: str) -> dict:
    m = c.get(db, CourseMaterial, material_id, "course material", for_update=True)
    space = c.space_of(db, m.course_space_id)
    c.require_scope(db, a, space, k.MATERIAL_MANAGE_ASSIGNED)
    c.require_writable(space)
    m.status = c.check(rules.transition, rules.MATERIAL_TRANSITIONS, status, m.status, "material")
    c.audit(db, a, f"material.{status}", "material", m.id, a.organisation_id)
    if status == "published":
        m.published_at = c.clock()
        c.publish(
            db,
            a,
            "material.published",
            a.organisation_id,
            {
                "material_id": m.id,
                "course_space_id": space.id,
                "course_offering_id": space.course_offering_id,
                "unit_id": m.unit_id,
                "material_type": m.material_type,
                "title": m.title,
                "visible_section_ids": list(m.visible_section_ids or []),
                "published_at": iso(m.published_at),
            },
        )
    db.commit()
    return material_dict(m)


# ---------------------------------------------------------------- the Student widget (FR-17)


def my_course_materials(db: Session, a: Actor, since, limit: int) -> dict:
    """Published materials in the active course spaces the caller belongs to, newest first."""
    since = since or (c.clock() - timedelta(days=rules.RECENT_MATERIALS_DAYS))
    taught = repo.taught_offerings(db, a.user_id)
    spaces = [s for s in _my_spaces(db, a) if s.status == "active"]
    offerings = repo.offerings(db, {s.course_offering_id for s in spaces})
    items = []
    for space in spaces:
        if space.course_offering_id in taught:
            view = c.Viewer(c.STAFF)
        else:
            view = c.Viewer(c.LEARNER, c.learner_sections(db, a, space) or set())
        published_units = {u.id for u in repo.units(db, space.id) if u.published}
        for m in repo.materials(db, [space.id], status="published", published_since=since):
            if view.staff or _learner_visible(view, m, published_units):
                items.append(
                    {
                        "material_id": m.id,
                        "course_space_id": space.id,
                        "course_title": course_title(space, offerings.get(space.course_offering_id)),
                        "title": m.title,
                        "material_type": m.material_type,
                        "published_at": iso(m.published_at),
                    }
                )
    items.sort(key=lambda i: (i["published_at"], i["material_id"]), reverse=True)
    return {"items": items[:limit]}
