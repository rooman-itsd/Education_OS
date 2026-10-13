"""Courses (contract `Course`; PRD FR-6, FR-7)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .values import require_choice, require_number

COURSE_TYPES = ("theory", "practical", "practicum", "project", "studio")  # contract CourseType
ACTIVE, ARCHIVED = "active", "archived"
COURSE_STATUSES = (ACTIVE, ARCHIVED)  # contract CourseStatus


@dataclass(frozen=True)
class CourseShape:
    """The validated, rule-bearing fields of a course. code, title, description and department_id are carried
    unchanged; code uniqueness is checked with values.ensure_unique_code (FR-6)."""

    credits: Decimal
    lecture_hours: Decimal | None
    practical_hours: Decimal | None
    course_type: str


def validate_course(
    *, credits: object, course_type: object, lecture_hours: object = None, practical_hours: object = None
) -> CourseShape:
    """FR-6 and contract CreateCourseRequest: credits >= 0, lecture and practical hours (optional) >= 0,
    course_type is a CourseType."""
    return CourseShape(
        credits=require_number(credits, "credits", minimum=0),
        lecture_hours=None if lecture_hours is None else require_number(lecture_hours, "lecture_hours", minimum=0),
        practical_hours=(
            None if practical_hours is None else require_number(practical_hours, "practical_hours", minimum=0)
        ),
        course_type=require_choice(course_type, "course_type", COURSE_TYPES),
    )


def archive(status: str) -> str:
    """POST /courses/{id}/archive. FR-7: courses referenced by an offering are archived, never deleted; the
    contract has no delete operation. Archiving an archived course is a no-op (no conflict response defined)."""
    require_choice(status, "status", COURSE_STATUSES)
    return ARCHIVED
