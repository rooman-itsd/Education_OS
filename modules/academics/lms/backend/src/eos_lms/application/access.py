"""Who is calling and what they may do. Keys are the ones in contracts/permissions.yaml (a test compares them); the API
layer resolves the caller's keys through the platform (eos_core.permissions_for), as academic-management,
timetable-attendance and examinations do.

Scope keys (`*-own`, `*-assigned`, `*-department`, `*-all`) are plain keys: each always means the same scope whoever
holds it, and holding a wider key of the same action widens the scope (contracts/permissions.yaml). Membership of a
course space comes from the read models the consumed events fill: the caller teaches a space when an active
instructor assignment names them for its course offering, and belongs to it as a student when an active course
registration names them (in a visible section, where the space limits sections).

How the caller's department is known is open (docs/prd.md LQ13), so Actor carries no department and no
`*-department` key widens anything yet: a `department_id` is a filter and data, never a grant."""

from __future__ import annotations

from dataclasses import dataclass, field

MODULE = "lms"
COURSE_SPACE_READ_OWN = f"{MODULE}:course-space:read-own"
COURSE_SPACE_READ_DEPARTMENT = f"{MODULE}:course-space:read-department"
COURSE_SPACE_READ_ALL = f"{MODULE}:course-space:read-all"
COURSE_SPACE_MANAGE_ASSIGNED = f"{MODULE}:course-space:manage-assigned"
COURSE_SPACE_MANAGE_ALL = f"{MODULE}:course-space:manage-all"
MATERIAL_MANAGE_ASSIGNED = f"{MODULE}:material:manage-assigned"
MATERIAL_MANAGE_ALL = f"{MODULE}:material:manage-all"
ASSIGNMENT_MANAGE_ASSIGNED = f"{MODULE}:assignment:manage-assigned"
ASSIGNMENT_MANAGE_ALL = f"{MODULE}:assignment:manage-all"
QUIZ_MANAGE_ASSIGNED = f"{MODULE}:quiz:manage-assigned"
QUIZ_MANAGE_ALL = f"{MODULE}:quiz:manage-all"
SUBMISSION_SUBMIT_OWN = f"{MODULE}:submission:submit-own"
SUBMISSION_READ_OWN = f"{MODULE}:submission:read-own"
SUBMISSION_READ_ASSIGNED = f"{MODULE}:submission:read-assigned"
SUBMISSION_READ_ALL = f"{MODULE}:submission:read-all"
QUIZ_ATTEMPT_ATTEMPT_OWN = f"{MODULE}:quiz-attempt:attempt-own"
QUIZ_ATTEMPT_READ_OWN = f"{MODULE}:quiz-attempt:read-own"
QUIZ_ATTEMPT_READ_ASSIGNED = f"{MODULE}:quiz-attempt:read-assigned"
QUIZ_ATTEMPT_READ_ALL = f"{MODULE}:quiz-attempt:read-all"
GRADE_READ_OWN = f"{MODULE}:grade:read-own"
GRADE_READ_ASSIGNED = f"{MODULE}:grade:read-assigned"
GRADE_READ_DEPARTMENT = f"{MODULE}:grade:read-department"
GRADE_READ_ALL = f"{MODULE}:grade:read-all"
GRADE_MANAGE_ASSIGNED = f"{MODULE}:grade:manage-assigned"
GRADE_MANAGE_ALL = f"{MODULE}:grade:manage-all"
DISCUSSION_POST_OWN = f"{MODULE}:discussion:post-own"
DISCUSSION_MODERATE_ASSIGNED = f"{MODULE}:discussion:moderate-assigned"
DISCUSSION_MODERATE_ALL = f"{MODULE}:discussion:moderate-all"
REPORT_READ_DEPARTMENT = f"{MODULE}:report:read-department"
REPORT_READ_ALL = f"{MODULE}:report:read-all"

PERMISSION_KEYS = (
    COURSE_SPACE_READ_OWN,
    COURSE_SPACE_READ_DEPARTMENT,
    COURSE_SPACE_READ_ALL,
    COURSE_SPACE_MANAGE_ASSIGNED,
    COURSE_SPACE_MANAGE_ALL,
    MATERIAL_MANAGE_ASSIGNED,
    MATERIAL_MANAGE_ALL,
    ASSIGNMENT_MANAGE_ASSIGNED,
    ASSIGNMENT_MANAGE_ALL,
    QUIZ_MANAGE_ASSIGNED,
    QUIZ_MANAGE_ALL,
    SUBMISSION_SUBMIT_OWN,
    SUBMISSION_READ_OWN,
    SUBMISSION_READ_ASSIGNED,
    SUBMISSION_READ_ALL,
    QUIZ_ATTEMPT_ATTEMPT_OWN,
    QUIZ_ATTEMPT_READ_OWN,
    QUIZ_ATTEMPT_READ_ASSIGNED,
    QUIZ_ATTEMPT_READ_ALL,
    GRADE_READ_OWN,
    GRADE_READ_ASSIGNED,
    GRADE_READ_DEPARTMENT,
    GRADE_READ_ALL,
    GRADE_MANAGE_ASSIGNED,
    GRADE_MANAGE_ALL,
    DISCUSSION_POST_OWN,
    DISCUSSION_MODERATE_ASSIGNED,
    DISCUSSION_MODERATE_ALL,
    REPORT_READ_DEPARTMENT,
    REPORT_READ_ALL,
)

# The "manage everything" key of each resource: holding it is acting as the LMS administrator for that resource.
MANAGE_ALL = {
    COURSE_SPACE_MANAGE_ASSIGNED: COURSE_SPACE_MANAGE_ALL,
    MATERIAL_MANAGE_ASSIGNED: MATERIAL_MANAGE_ALL,
    ASSIGNMENT_MANAGE_ASSIGNED: ASSIGNMENT_MANAGE_ALL,
    QUIZ_MANAGE_ASSIGNED: QUIZ_MANAGE_ALL,
    GRADE_MANAGE_ASSIGNED: GRADE_MANAGE_ALL,
    DISCUSSION_MODERATE_ASSIGNED: DISCUSSION_MODERATE_ALL,
    SUBMISSION_READ_ASSIGNED: SUBMISSION_READ_ALL,
    QUIZ_ATTEMPT_READ_ASSIGNED: QUIZ_ATTEMPT_READ_ALL,
    GRADE_READ_ASSIGNED: GRADE_READ_ALL,
}


@dataclass
class Actor:
    """Who is calling. Built by the API layer from the verified token."""

    user_id: str
    organisation_id: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions

    def can_any(self, *permissions: str) -> bool:
        return any(p in self.permissions for p in permissions)
