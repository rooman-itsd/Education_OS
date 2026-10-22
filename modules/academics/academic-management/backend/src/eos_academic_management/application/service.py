"""Use cases of academic-management (docs/prd.md, contracts/openapi.yaml). Each one applies the domain rules, changes
state and publishes the matching event of contracts/events.yaml through eos_core.events.publish in the same
transaction, then commits once. Permission keys are checked by the API layer (api/deps.require).

Known dependencies, not worked around here:
- The shared outbox has no `version` column yet (packages/core, Faizan), so events are published without the
  envelope version declared in contracts/events.yaml.
- The audit SDK does not exist (packages/sdk is empty). Until it does, the outbox rows are the only record of each
  state change; this is not full audit integration (FR-16).
- No trusted department claim exists, so department-level authorisation is not enforced: `department_id` is a filter,
  never a grant."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from decimal import Decimal

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import assignments as asg
from ..domain import courses as crs
from ..domain import curricula as cur
from ..domain import offerings as off
from ..domain import programmes as prg
from ..domain import terms as trm
from ..domain.errors import DomainRuleError
from ..domain.load import LoadEntry
from ..domain.values import ensure_unique_code
from ..infrastructure import repository as repo
from ..infrastructure.models import (
    CourseRow,
    CurriculumItemRow,
    CurriculumRow,
    FacultyAssignmentRow,
    OfferingRow,
    ProgrammeRow,
    RosterEntryRow,
    SectionRow,
    TermRow,
    iso,
)
from .access import ROSTER_READ_ALL, Actor
from .errors import AcademicManagementError, forbidden, from_domain, not_found

MODULE = "academic-management"


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


def _number(value: Decimal | None) -> int | float | None:
    """A contract `type: number` for JSON: whole numbers stay integers."""
    if value is None:
        return None
    value = Decimal(value)
    return int(value) if value == value.to_integral_value() else float(value)


def _domain(fn: Callable, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except DomainRuleError as err:
        raise from_domain(err) from err


def _invalid(code: str, message: str, field: str) -> AcademicManagementError:
    return AcademicManagementError(400, code, message, field=field)


def _publish(db: Session, actor: Actor | None, entity_event: str, payload: dict) -> None:
    """contracts/events.yaml: organisation_id, actor and occurred_at travel on the envelope, never in the payload."""
    events.publish(
        db,
        f"{MODULE}.{entity_event}",
        actor.organisation_id if actor else db.info.get("organisation_id"),
        payload,
        actor=actor.user_id if actor else None,
    )


def _insert_coded(db: Session, row) -> None:
    """Insert a row whose `code` is unique (term, programme, course, section). The pre-check with ensure_unique_code
    gives the usual answer; this covers the race where a concurrent request inserts the same code in between: the
    database's unique constraint refuses it, and that refusal, and only that one, becomes the same 409. Any other
    integrity error is re-raised unchanged."""
    db.add(row)
    try:
        db.flush()
    except IntegrityError as err:
        db.rollback()
        if repo.is_code_conflict(err):
            raise AcademicManagementError(
                409, "duplicate_code", f"code {row.code!r} is already in use", field="code"
            ) from err
        raise


def _changed(row, changes: dict) -> list[str]:
    changed = []
    for field, value in changes.items():
        if getattr(row, field) != value:
            setattr(row, field, value)
            changed.append(field)
    return changed


def _page(items: list, total: int) -> dict:
    return {"items": items, "total": total}


# ---------------------------------------------------------------- serialisation


def term_dict(t: TermRow) -> dict:
    return {
        "id": t.id,
        "organisation_id": t.organisation_id,
        "code": t.code,
        "name": t.name,
        "starts_on": iso(t.starts_on),
        "ends_on": iso(t.ends_on),
        "status": t.status,
    }


def programme_dict(p: ProgrammeRow) -> dict:
    return {
        "id": p.id,
        "organisation_id": p.organisation_id,
        "code": p.code,
        "name": p.name,
        "level": p.level,
        "department_id": p.department_id,
        "duration_terms": p.duration_terms,
        "credits_required": _number(p.credits_required),
        "published_curriculum_id": p.published_curriculum_id,
        "status": p.status,
    }


def course_dict(c: CourseRow) -> dict:
    d = {
        "id": c.id,
        "organisation_id": c.organisation_id,
        "code": c.code,
        "title": c.title,
        "credits": _number(c.credits),
        "course_type": c.course_type,
        "department_id": c.department_id,
        "status": c.status,
    }
    for field in ("description", "lecture_hours", "practical_hours"):
        value = getattr(c, field)
        if value is not None:
            d[field] = value if field == "description" else _number(value)
    return d


def course_summary(c: CourseRow) -> dict:
    return {
        "code": c.code,
        "title": c.title,
        "credits": _number(c.credits),
        "course_type": c.course_type,
        "department_id": c.department_id,
    }


def curriculum_dict(db: Session, c: CurriculumRow) -> dict:
    items = repo.curriculum_items(db, c.id)
    courses = repo.courses_by_id(db, (i.course_id for i in items))
    total = cur.total_credits(_item(i) for i in items)
    return {
        "id": c.id,
        "organisation_id": c.organisation_id,
        "programme_id": c.programme_id,
        "version": c.version,
        "status": c.status,
        "total_credits": _number(total),
        "published_at": iso(c.published_at),
        "items": [
            {
                "id": i.id,
                "course_id": i.course_id,
                "course_code": courses[i.course_id].code,
                "course_title": courses[i.course_id].title,
                "programme_term": i.programme_term,
                "category": i.category,
                "credits": _number(i.credits),
            }
            for i in items
        ],
    }


def section_dict(s: SectionRow, enrolled: int) -> dict:
    return {
        "id": s.id,
        "organisation_id": s.organisation_id,
        "course_offering_id": s.course_offering_id,
        "code": s.code,
        "capacity": s.capacity,
        "enrolled_count": enrolled,
        "status": s.status,
    }


def assignment_dict(a: FacultyAssignmentRow) -> dict:
    """FacultyAssignment. faculty_name and over_load are read-only and optional; faculty names need an identity
    lookup that does not exist yet, so they are left out rather than guessed."""
    return {
        "id": a.id,
        "organisation_id": a.organisation_id,
        "course_offering_id": a.course_offering_id,
        "section_id": a.section_id,
        "faculty_id": a.faculty_id,
        "role": a.role,
        "contact_hours": _number(a.contact_hours),
        "status": a.status,
    }


def offering_dict(db: Session, o: OfferingRow) -> dict:
    course = repo.get(db, CourseRow, o.course_id)
    counts = repo.enrolled_counts(db, o.id)
    return {
        "id": o.id,
        "organisation_id": o.organisation_id,
        "course_id": o.course_id,
        "academic_period_id": o.academic_period_id,
        "status": o.status,
        "programme_ids": list(o.programme_ids or []),
        "course": course_summary(course),
        "sections": [section_dict(s, counts.get(s.id, 0)) for s in repo.sections_of(db, o.id)],
        "faculty": [assignment_dict(a) for a in repo.assignments_of(db, o.id, include_ended=False)],
        "enrolled_count": sum(counts.values()),
    }


# ---------------------------------------------------------------- lookups


def _term(db: Session, term_id: str) -> TermRow:
    row = repo.get(db, TermRow, term_id)
    if row is None:
        raise not_found("not_found", "academic period not found in your organisation")
    return row


def _programme(db: Session, programme_id: str) -> ProgrammeRow:
    row = repo.programme(db, programme_id)
    if row is None:
        raise not_found("not_found", "programme not found in your organisation")
    return row


def _course(db: Session, course_id: str) -> CourseRow:
    row = repo.get(db, CourseRow, course_id)
    if row is None:
        raise not_found("not_found", "course not found in your organisation")
    return row


def _curriculum(db: Session, curriculum_id: str) -> CurriculumRow:
    row = repo.get(db, CurriculumRow, curriculum_id)
    if row is None:
        raise not_found("not_found", "curriculum not found in your organisation")
    return row


def _offering(db: Session, offering_id: str) -> OfferingRow:
    row = repo.offering(db, offering_id)
    if row is None:
        raise not_found("not_found", "course offering not found in your organisation")
    return row


def _section(db: Session, section_id: str) -> SectionRow:
    row = repo.get(db, SectionRow, section_id)
    if row is None:
        raise not_found("not_found", "section not found in your organisation")
    return row


def _domain_term(t: TermRow) -> trm.Term:
    return trm.Term(t.id, t.code, t.name, trm.DateRange(t.starts_on, t.ends_on), t.status)


def _item(i: CurriculumItemRow) -> cur.CurriculumItem:
    return cur.CurriculumItem(i.course_id, i.programme_term, i.category, Decimal(i.credits))


def _domain_assignment(a: FacultyAssignmentRow) -> asg.Assignment:
    return asg.Assignment(a.id, a.faculty_id, a.section_id, a.role, Decimal(a.contact_hours), a.status)


# ---------------------------------------------------------------- terms (FR-1, FR-2)


def list_terms(db: Session, status: str | None, limit: int, offset: int) -> dict:
    query = repo.q(db, TermRow).order_by(TermRow.starts_on)
    if status:
        query = query.where(TermRow.status == status)
    rows, total = repo.page(db, query, limit, offset)
    return _page([term_dict(t) for t in rows], total)


def create_term(db: Session, a: Actor, body: dict) -> dict:
    _domain(ensure_unique_code, body["code"], repo.codes(db, TermRow))
    dates = _domain(trm.DateRange, body["starts_on"], body["ends_on"])
    _domain(trm.ensure_no_overlap, dates, [_domain_term(t) for t in repo.terms(db)])
    row = TermRow(
        organisation_id=a.organisation_id,
        code=body["code"],
        name=body["name"],
        starts_on=dates.starts_on,
        ends_on=dates.ends_on,
        status=trm.UPCOMING,
    )
    _insert_coded(db, row)
    _publish(
        db,
        a,
        "term.created",
        {
            "academic_period_id": row.id,
            "code": row.code,
            "name": row.name,
            "starts_on": iso(row.starts_on),
            "ends_on": iso(row.ends_on),
        },
    )
    db.commit()
    return term_dict(row)


def get_term(db: Session, term_id: str) -> dict:
    return term_dict(_term(db, term_id))


def update_term(db: Session, a: Actor, term_id: str, body: dict) -> dict:
    row = _term(db, term_id)
    dates = _domain(trm.DateRange, body.get("starts_on", row.starts_on), body.get("ends_on", row.ends_on))
    _domain(trm.ensure_no_overlap, dates, [_domain_term(t) for t in repo.terms(db)], ignore_id=row.id)
    _changed(row, {"name": body.get("name", row.name), "starts_on": dates.starts_on, "ends_on": dates.ends_on})
    db.commit()  # contracts/events.yaml declares no term.updated event
    return term_dict(row)


def activate_term(db: Session, a: Actor, term_id: str) -> dict:
    rows = {t.id: t for t in repo.terms(db)}
    plan = _domain(trm.plan_activation, [_domain_term(t) for t in rows.values()], term_id)
    target = rows[plan.activated_id]
    if target.status == trm.ACTIVE and not plan.closed_ids:
        return term_dict(target)  # already the only active term: nothing changes, nothing is published
    for closed in plan.closed_ids:
        rows[closed].status = trm.CLOSED
    target.status = trm.ACTIVE
    _publish(
        db,
        a,
        "term.activated",
        {
            "academic_period_id": target.id,
            "previous_academic_period_id": plan.closed_ids[0] if plan.closed_ids else None,
            "activated_at": iso(clock()),
        },
    )
    db.commit()
    return term_dict(target)


# ---------------------------------------------------------------- programmes (FR-3)


def list_programmes(db: Session, filters: dict, limit: int, offset: int) -> dict:
    query = repo.q(db, ProgrammeRow).order_by(ProgrammeRow.code)
    for field in ("department_id", "level", "status"):
        if filters.get(field):
            query = query.where(getattr(ProgrammeRow, field) == filters[field])
    rows, total = repo.page(db, query, limit, offset)
    return _page([programme_dict(p) for p in rows], total)


def create_programme(db: Session, a: Actor, body: dict) -> dict:
    shape = _domain(
        prg.validate_programme,
        level=body["level"],
        duration_terms=body["duration_terms"],
        credits_required=body["credits_required"],
    )
    _domain(ensure_unique_code, body["code"], repo.codes(db, ProgrammeRow))
    row = ProgrammeRow(
        organisation_id=a.organisation_id,
        code=body["code"],
        name=body["name"],
        level=shape.level,
        department_id=body["department_id"],
        duration_terms=shape.duration_terms,
        credits_required=shape.credits_required,
        status=prg.ACTIVE,
    )
    _insert_coded(db, row)
    _publish(
        db,
        a,
        "programme.created",
        {
            "programme_id": row.id,
            "code": row.code,
            "name": row.name,
            "level": row.level,
            "department_id": row.department_id,
            "duration_terms": row.duration_terms,
            "credits_required": _number(row.credits_required),
        },
    )
    db.commit()
    return programme_dict(row)


def get_programme(db: Session, programme_id: str) -> dict:
    return programme_dict(_programme(db, programme_id))


def update_programme(db: Session, a: Actor, programme_id: str, body: dict) -> dict:
    row = _programme(db, programme_id)
    shape = _domain(
        prg.validate_programme,
        level=row.level,
        duration_terms=body.get("duration_terms", row.duration_terms),
        credits_required=body.get("credits_required", row.credits_required),
    )
    changed = _changed(
        row,
        {
            "name": body.get("name", row.name),
            "department_id": body.get("department_id", row.department_id),
            "duration_terms": shape.duration_terms,
            "credits_required": shape.credits_required,
        },
    )
    if changed:
        _publish(db, a, "programme.updated", {"programme_id": row.id, "changed_fields": changed})
    db.commit()
    return programme_dict(row)


def archive_programme(db: Session, a: Actor, programme_id: str) -> dict:
    row = _programme(db, programme_id)
    was = row.status
    row.status = _domain(prg.archive, row.status)
    if was != row.status:
        _publish(db, a, "programme.archived", {"programme_id": row.id, "archived_at": iso(clock())})
    db.commit()
    return programme_dict(row)


# ---------------------------------------------------------------- curricula (FR-4, FR-5)


def list_curricula(db: Session, programme_id: str, status: str | None) -> dict:
    _programme(db, programme_id)
    rows = sorted(repo.curricula_of(db, programme_id), key=lambda c: c.version)
    if status:
        rows = [c for c in rows if c.status == status]
    return _page([curriculum_dict(db, c) for c in rows], len(rows))


def _validated_items(db: Session, items: Iterable[dict], duration_terms: int) -> list[cur.CurriculumItem]:
    items = list(items)
    known = repo.courses_by_id(db, (i.get("course_id") for i in items if isinstance(i.get("course_id"), str)))
    out = []
    for index, item in enumerate(items):
        if item.get("course_id") not in known:
            raise _invalid("unknown_course", f"item {index}: course not found", f"items[{index}].course_id")
        try:
            out.append(
                cur.validate_item(
                    course_id=item["course_id"],
                    programme_term=item.get("programme_term"),
                    category=item.get("category"),
                    credits=item.get("credits"),
                    duration_terms=duration_terms,
                )
            )
        except DomainRuleError as err:
            raise AcademicManagementError(
                400, err.code, f"item {index}: {err.message}", field=f"items[{index}].{err.field}"
            ) from err
    return out


def _replace_items(db: Session, curriculum: CurriculumRow, items: list[cur.CurriculumItem]) -> None:
    for old in repo.curriculum_items(db, curriculum.id):
        db.delete(old)
    for i in items:
        db.add(
            CurriculumItemRow(
                organisation_id=curriculum.organisation_id,
                curriculum_id=curriculum.id,
                course_id=i.course_id,
                programme_term=i.programme_term,
                category=i.category,
                credits=i.credits,
            )
        )


def create_curriculum(db: Session, a: Actor, programme_id: str, body: dict) -> dict:
    programme = _programme(db, programme_id)
    if body.get("items") is not None:
        items = _validated_items(db, body["items"], programme.duration_terms)
    elif body.get("copy_from_curriculum_id"):
        source = _curriculum(db, body["copy_from_curriculum_id"])
        if source.programme_id != programme.id:
            raise _invalid(
                "curriculum_of_another_programme", "copy from a curriculum of this programme", "copy_from_curriculum_id"
            )
        items = [_item(i) for i in repo.curriculum_items(db, source.id)]
    else:
        items = []
    version = cur.next_version(c.version for c in repo.curricula_of(db, programme.id))
    row = CurriculumRow(organisation_id=a.organisation_id, programme_id=programme.id, version=version, status=cur.DRAFT)
    db.add(row)
    db.flush()
    _replace_items(db, row, items)
    db.commit()
    return curriculum_dict(db, row)


def get_curriculum(db: Session, curriculum_id: str) -> dict:
    return curriculum_dict(db, _curriculum(db, curriculum_id))


def replace_curriculum_items(db: Session, a: Actor, curriculum_id: str, body: dict) -> dict:
    row = _curriculum(db, curriculum_id)
    _domain(cur.ensure_editable, row.status)
    programme = _programme(db, row.programme_id)
    _replace_items(db, row, _validated_items(db, body["items"], programme.duration_terms))
    db.commit()
    return curriculum_dict(db, row)


def publish_curriculum(db: Session, a: Actor, curriculum_id: str) -> dict:
    row = _curriculum(db, curriculum_id)
    programme = _programme(db, row.programme_id)
    items = [_item(i) for i in repo.curriculum_items(db, row.id)]
    _domain(
        cur.ensure_publishable,
        row.status,
        items,
        credits_required=Decimal(programme.credits_required),
        duration_terms=programme.duration_terms,
    )
    row.status, row.published_at = cur.PUBLISHED, clock()
    programme.published_curriculum_id = row.id
    _publish(
        db,
        a,
        "curriculum.published",
        {
            "curriculum_id": row.id,
            "programme_id": programme.id,
            "curriculum_version": row.version,
            "total_credits": _number(cur.total_credits(items)),
            "published_at": iso(row.published_at),
        },
    )
    db.commit()
    return curriculum_dict(db, row)


# ---------------------------------------------------------------- courses (FR-6, FR-7)


def list_courses(db: Session, filters: dict, limit: int, offset: int) -> dict:
    query = repo.q(db, CourseRow).order_by(CourseRow.code)
    for field in ("department_id", "course_type", "status"):
        if filters.get(field):
            query = query.where(getattr(CourseRow, field) == filters[field])
    if filters.get("q"):
        like = f"%{filters['q'].lower()}%"
        query = query.where(CourseRow.code.ilike(like) | CourseRow.title.ilike(like))
    rows, total = repo.page(db, query, limit, offset)
    return _page([course_dict(c) for c in rows], total)


def create_course(db: Session, a: Actor, body: dict) -> dict:
    shape = _domain(
        crs.validate_course,
        credits=body["credits"],
        course_type=body["course_type"],
        lecture_hours=body.get("lecture_hours"),
        practical_hours=body.get("practical_hours"),
    )
    _domain(ensure_unique_code, body["code"], repo.codes(db, CourseRow))
    row = CourseRow(
        organisation_id=a.organisation_id,
        code=body["code"],
        title=body["title"],
        description=body.get("description"),
        credits=shape.credits,
        lecture_hours=shape.lecture_hours,
        practical_hours=shape.practical_hours,
        course_type=shape.course_type,
        department_id=body["department_id"],
        status=crs.ACTIVE,
    )
    _insert_coded(db, row)
    _publish(
        db,
        a,
        "course.created",
        {
            "course_id": row.id,
            "code": row.code,
            "title": row.title,
            "credits": _number(row.credits),
            "course_type": row.course_type,
            "department_id": row.department_id,
        },
    )
    db.commit()
    return course_dict(row)


def get_course(db: Session, course_id: str) -> dict:
    return course_dict(_course(db, course_id))


def update_course(db: Session, a: Actor, course_id: str, body: dict) -> dict:
    row = _course(db, course_id)
    shape = _domain(
        crs.validate_course,
        credits=body.get("credits", row.credits),
        course_type=body.get("course_type", row.course_type),
        lecture_hours=body.get("lecture_hours", row.lecture_hours),
        practical_hours=body.get("practical_hours", row.practical_hours),
    )
    changed = _changed(
        row,
        {
            "title": body.get("title", row.title),
            "description": body.get("description", row.description),
            "credits": shape.credits,
            "lecture_hours": shape.lecture_hours,
            "practical_hours": shape.practical_hours,
            "course_type": shape.course_type,
            "department_id": body.get("department_id", row.department_id),
        },
    )
    if changed:
        _publish(db, a, "course.updated", {"course_id": row.id, "changed_fields": changed})
    db.commit()
    return course_dict(row)


def archive_course(db: Session, a: Actor, course_id: str) -> dict:
    row = _course(db, course_id)
    was = row.status
    row.status = _domain(crs.archive, row.status)
    if was != row.status:
        _publish(db, a, "course.archived", {"course_id": row.id, "archived_at": iso(clock())})
    db.commit()
    return course_dict(row)


# ---------------------------------------------------------------- offerings and sections (FR-8, FR-9, FR-10)


def list_offerings(db: Session, filters: dict, limit: int, offset: int) -> dict:
    query = repo.q(db, OfferingRow).order_by(OfferingRow.created_at, OfferingRow.id)
    for field in ("academic_period_id", "course_id", "status"):
        if filters.get(field):
            query = query.where(getattr(OfferingRow, field) == filters[field])
    rows = list(db.scalars(query))
    if filters.get("programme_id"):
        rows = [o for o in rows if filters["programme_id"] in (o.programme_ids or [])]
    if filters.get("department_id"):
        courses = repo.courses_by_id(db, (o.course_id for o in rows))
        rows = [o for o in rows if courses[o.course_id].department_id == filters["department_id"]]
    if filters.get("faculty_id"):
        taught = {x.course_offering_id for x in repo.active_assignments_of_faculty(db, filters["faculty_id"])}
        rows = [o for o in rows if o.id in taught]
    return _page([offering_dict(db, o) for o in rows[offset : offset + limit]], len(rows))


def _section_codes_unique(codes: list[str]) -> None:
    seen: list[str] = []
    for code in codes:
        _domain(ensure_unique_code, code, seen)
        seen.append(code)


def create_offering(db: Session, a: Actor, body: dict) -> dict:
    course = repo.get(db, CourseRow, body["course_id"])
    if course is None:
        raise _invalid("unknown_course", "course not found in your organisation", "course_id")
    if repo.get(db, TermRow, body["academic_period_id"]) is None:
        raise _invalid(
            "unknown_academic_period", "academic period not found in your organisation", "academic_period_id"
        )
    sections = body.get("sections") or []
    shapes = _domain(
        off.validate_new_offering, course_status=course.status, section_capacities=[s.get("capacity") for s in sections]
    )
    _section_codes_unique([s["code"] for s in sections])
    row = OfferingRow(
        organisation_id=a.organisation_id,
        course_id=course.id,
        academic_period_id=body["academic_period_id"],
        status=off.PLANNED,
        programme_ids=list(body.get("programme_ids") or []),
    )
    db.add(row)
    db.flush()
    _publish(
        db,
        a,
        "offering.created",
        {
            "course_offering_id": row.id,
            "course_id": course.id,
            "academic_period_id": row.academic_period_id,
            "programme_ids": row.programme_ids,
            "course_code": course.code,
            "course_title": course.title,
            "credits": _number(course.credits),
            "course_type": course.course_type,
            "department_id": course.department_id,
        },
    )
    for s, shape in zip(sections, shapes, strict=True):
        _add_section(db, a, row, s["code"], shape.capacity)
    db.commit()
    return offering_dict(db, row)


def _add_section(db: Session, a: Actor, offering: OfferingRow, code: str, capacity: int) -> SectionRow:
    section = SectionRow(
        organisation_id=a.organisation_id,
        course_offering_id=offering.id,
        code=code,
        capacity=capacity,
        status=off.SECTION_OPEN,
    )
    _insert_coded(db, section)
    _publish(
        db,
        a,
        "section.created",
        {"section_id": section.id, "course_offering_id": offering.id, "code": code, "capacity": capacity},
    )
    return section


def get_offering(db: Session, offering_id: str) -> dict:
    return offering_dict(db, _offering(db, offering_id))


def update_offering(db: Session, a: Actor, offering_id: str, body: dict) -> dict:
    row = _offering(db, offering_id)
    changed = _changed(row, {"programme_ids": list(body.get("programme_ids", row.programme_ids) or [])})
    if changed:
        _publish(db, a, "offering.updated", {"course_offering_id": row.id, "changed_fields": changed})
    db.commit()
    return offering_dict(db, row)


def change_offering_status(db: Session, a: Actor, offering_id: str, body: dict) -> dict:
    row = _offering(db, offering_id)
    primaries = asg.count_active_primaries(_domain_assignment(x) for x in repo.assignments_of(db, row.id))
    target = _domain(off.ensure_transition, row.status, body.get("status"), active_primaries=primaries)
    previous, row.status = row.status, target
    _publish(
        db,
        a,
        "offering.status-changed",
        {"course_offering_id": row.id, "from_status": previous, "to_status": target, "changed_at": iso(clock())},
    )
    db.commit()
    return offering_dict(db, row)


def list_sections(db: Session, offering_id: str) -> dict:
    row = _offering(db, offering_id)
    counts = repo.enrolled_counts(db, row.id)
    items = [section_dict(s, counts.get(s.id, 0)) for s in repo.sections_of(db, row.id)]
    return _page(items, len(items))


def create_section(db: Session, a: Actor, offering_id: str, body: dict) -> dict:
    row = _offering(db, offering_id)
    _domain(off.ensure_sections_can_be_added, row.status)
    shape = _domain(off.validate_section, capacity=body.get("capacity"))
    _domain(ensure_unique_code, body["code"], [s.code for s in repo.sections_of(db, row.id)])
    section = _add_section(db, a, row, body["code"], shape.capacity)
    db.commit()
    return section_dict(section, 0)


def update_section(db: Session, a: Actor, section_id: str, body: dict) -> dict:
    """Capacity and status. A section is never deleted (FR-10; the contract has no delete): one with enrolled
    students is closed instead, which stops new registrations and keeps its roster."""
    section = _section(db, section_id)
    shape = _domain(
        off.validate_section,
        capacity=body.get("capacity", section.capacity),
        status=body.get("status", section.status),
    )
    changed = _changed(section, {"capacity": shape.capacity, "status": shape.status})
    if changed:
        _publish(
            db,
            a,
            "section.updated",
            {
                "section_id": section.id,
                "course_offering_id": section.course_offering_id,
                "capacity": section.capacity,
                "status": section.status,
            },
        )
    db.commit()
    counts = repo.enrolled_counts(db, section.course_offering_id)
    return section_dict(section, counts.get(section.id, 0))


# ---------------------------------------------------------------- faculty assignment (FR-11, FR-12)


def list_assignments(db: Session, offering_id: str, include_ended: bool) -> dict:
    row = _offering(db, offering_id)
    items = [assignment_dict(x) for x in repo.assignments_of(db, row.id, include_ended=include_ended)]
    return _page(items, len(items))


def create_assignment(db: Session, a: Actor, offering_id: str, body: dict) -> dict:
    row = _offering(db, offering_id)
    made = _domain(
        asg.validate_assignment,
        faculty_id=body.get("faculty_id"),
        role=body.get("role"),
        contact_hours=body.get("contact_hours"),
        section_id=body.get("section_id"),
        offering_section_ids=[s.id for s in repo.sections_of(db, row.id)],
        offering_status=row.status,
        existing=[_domain_assignment(x) for x in repo.assignments_of(db, row.id)],
    )
    assignment = FacultyAssignmentRow(
        organisation_id=a.organisation_id,
        course_offering_id=row.id,
        section_id=made.section_id,
        faculty_id=made.faculty_id,
        role=made.role,
        contact_hours=made.contact_hours,
        status=asg.ACTIVE,
    )
    db.add(assignment)
    db.flush()
    _publish(
        db,
        a,
        "faculty-assignment.created",
        {
            "instructor_assignment_id": assignment.id,
            "course_offering_id": row.id,
            "section_id": assignment.section_id,
            "faculty_id": assignment.faculty_id,
            "role": assignment.role,
            "contact_hours": _number(assignment.contact_hours),
        },
    )
    db.commit()
    return assignment_dict(assignment)


def end_assignment(db: Session, a: Actor, assignment_id: str) -> dict:
    assignment = repo.get(db, FacultyAssignmentRow, assignment_id)
    if assignment is None:
        raise not_found("not_found", "faculty assignment not found in your organisation")
    row = _offering(db, assignment.course_offering_id)
    assignment.status = _domain(asg.ensure_can_end, _domain_assignment(assignment), offering_status=row.status)
    assignment.ended_at = clock()
    _publish(
        db,
        a,
        "faculty-assignment.ended",
        {
            "instructor_assignment_id": assignment.id,
            "course_offering_id": row.id,
            "section_id": assignment.section_id,
            "faculty_id": assignment.faculty_id,
            "ended_at": iso(assignment.ended_at),
        },
    )
    db.commit()
    return assignment_dict(assignment)


# ---------------------------------------------------------------- roster and my offerings (FR-14, FR-15)


def get_roster(db: Session, a: Actor, offering_id: str, section_id: str | None, limit: int, offset: int) -> dict:
    """roster:read-all reads every roster of the organisation; department restriction is not enforced because no
    trusted department claim exists. roster:read reads only offerings the caller is actively assigned to."""
    row = _offering(db, offering_id)
    if not a.can(ROSTER_READ_ALL):
        mine = [x for x in repo.assignments_of(db, row.id, include_ended=False) if x.faculty_id == a.user_id]
        if not mine:
            raise forbidden("you are not assigned to this offering")
    sections = {s.id: s for s in repo.sections_of(db, row.id)}
    query = repo.q(db, RosterEntryRow).where(
        RosterEntryRow.course_offering_id == row.id, RosterEntryRow.status == repo.ENROLLED
    )
    if section_id:
        query = query.where(RosterEntryRow.section_id == section_id)
    entries, total = repo.page(db, query.order_by(RosterEntryRow.roll_number, RosterEntryRow.person_id), limit, offset)
    items = []
    for e in entries:
        item = {
            "person_id": e.person_id,
            "section_id": e.section_id,
            "section_code": sections[e.section_id].code,
            "enrolled_at": iso(e.enrolled_at),
        }
        if e.student_name is not None:
            item["student_name"] = e.student_name
        if e.roll_number is not None:
            item["roll_number"] = e.roll_number
        items.append(item)
    return {"course_offering_id": row.id, "items": items, "total": total}


def list_my_offerings(db: Session, a: Actor, academic_period_id: str | None) -> dict:
    period = academic_period_id or (repo.active_term(db).id if repo.active_term(db) else None)
    mine = repo.active_assignments_of_faculty(db, a.user_id)
    by_offering: dict[str, list[FacultyAssignmentRow]] = {}
    for x in mine:
        by_offering.setdefault(x.course_offering_id, []).append(x)
    items = []
    for offering_id, assigned in by_offering.items():
        row = repo.offering(db, offering_id)
        if row is None or (period and row.academic_period_id != period):
            continue
        counts = repo.enrolled_counts(db, row.id)
        sections = repo.sections_of(db, row.id)
        whole = any(x.section_id is None for x in assigned)
        taught = sections if whole else [s for s in sections if s.id in {x.section_id for x in assigned}]
        items.append(
            {
                "course_offering_id": row.id,
                "course": course_summary(repo.get(db, CourseRow, row.course_id)),
                "role": assigned[0].role,
                "status": row.status,
                "sections": [
                    {"section_id": s.id, "code": s.code, "enrolled_count": counts.get(s.id, 0)} for s in taught
                ],
                "enrolled_count": sum(counts.get(s.id, 0) for s in taught),
            }
        )
    return {"academic_period_id": period, "items": items}


# ---------------------------------------------------------------- faculty load (FR-13)


def faculty_load_inputs(
    db: Session, academic_period_id: str | None, department_id: str | None
) -> tuple[trm.Term | None, list[LoadEntry]]:
    """The term (the requested one, else the active one; None when it does not exist) and its assignment rows.
    department_id narrows the rows to offerings of courses owned by that department; it authorises nothing."""
    if academic_period_id:
        term = repo.get(db, TermRow, academic_period_id)
    else:
        term = repo.active_term(db)
    if term is None:
        return None, []
    offerings = list(db.scalars(repo.q(db, OfferingRow).where(OfferingRow.academic_period_id == term.id)))
    if department_id:
        courses = repo.courses_by_id(db, (o.course_id for o in offerings))
        offerings = [o for o in offerings if courses[o.course_id].department_id == department_id]
    entries = [
        LoadEntry(x.faculty_id, x.course_offering_id, x.role, Decimal(x.contact_hours), x.status)
        for o in offerings
        for x in repo.assignments_of(db, o.id)
    ]
    return _domain_term(term), entries
