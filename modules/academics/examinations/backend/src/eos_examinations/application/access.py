"""Who is calling and what they may do. Keys are the ones in contracts/permissions.yaml (a test compares them); the API
layer resolves the caller's keys through the platform (eos_core.permissions_for), as academic-management and
timetable-attendance do.

Scope keys (`*-own`, `*-assigned`, `*-department`, `*-all`) are plain keys: each always means the same scope whoever holds
it, and holding a wider key of the same action widens the scope (contracts/permissions.yaml). How the caller's
department is known is open (PRD Q13), so Actor carries no department and no `*-department` key is enforced as
department-scoped: a `department_id` is a filter and data, never a grant."""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import forbidden

MODULE = "examinations"
EXAM_CYCLE_READ = f"{MODULE}:exam-cycle:read"
EXAM_CYCLE_MANAGE = f"{MODULE}:exam-cycle:manage"
ASSESSMENT_SCHEME_READ = f"{MODULE}:assessment-scheme:read"
ASSESSMENT_SCHEME_WRITE_DEPARTMENT = f"{MODULE}:assessment-scheme:write-department"
ASSESSMENT_SCHEME_WRITE_ALL = f"{MODULE}:assessment-scheme:write-all"
GRADING_SCHEME_READ = f"{MODULE}:grading-scheme:read"
GRADING_SCHEME_MANAGE = f"{MODULE}:grading-scheme:manage"
PAPER_READ = f"{MODULE}:paper:read"
PAPER_MANAGE = f"{MODULE}:paper:manage"
SESSION_READ = f"{MODULE}:session:read"
SESSION_READ_OWN = f"{MODULE}:session:read-own"
SESSION_MANAGE = f"{MODULE}:session:manage"
CANDIDATE_READ_DEPARTMENT = f"{MODULE}:candidate:read-department"
CANDIDATE_READ_ALL = f"{MODULE}:candidate:read-all"
CANDIDATE_DETERMINE = f"{MODULE}:candidate:determine"
CANDIDATE_OVERRIDE = f"{MODULE}:candidate:override"
HALL_TICKET_READ_OWN = f"{MODULE}:hall-ticket:read-own"
HALL_TICKET_READ_ALL = f"{MODULE}:hall-ticket:read-all"
HALL_TICKET_ISSUE = f"{MODULE}:hall-ticket:issue"
HALL_TICKET_WITHHOLD = f"{MODULE}:hall-ticket:withhold"
HALL_TICKET_REVOKE = f"{MODULE}:hall-ticket:revoke"
DUTY_READ_OWN = f"{MODULE}:duty:read-own"
DUTY_READ_DEPARTMENT = f"{MODULE}:duty:read-department"
DUTY_READ_ALL = f"{MODULE}:duty:read-all"
DUTY_ASSIGN = f"{MODULE}:duty:assign"
MARKS_READ_ASSIGNED = f"{MODULE}:marks:read-assigned"
MARKS_READ_DEPARTMENT = f"{MODULE}:marks:read-department"
MARKS_READ_ALL = f"{MODULE}:marks:read-all"
MARKS_ENTER_ASSIGNED = f"{MODULE}:marks:enter-assigned"
MARKS_ENTER_ALL = f"{MODULE}:marks:enter-all"
MARKS_MODERATE_ASSIGNED = f"{MODULE}:marks:moderate-assigned"
MARKS_MODERATE_DEPARTMENT = f"{MODULE}:marks:moderate-department"
MARKS_LOCK = f"{MODULE}:marks:lock"
RESULT_READ_OWN = f"{MODULE}:result:read-own"
RESULT_READ_DEPARTMENT = f"{MODULE}:result:read-department"
RESULT_READ_ALL = f"{MODULE}:result:read-all"
RESULT_COMPUTE = f"{MODULE}:result:compute"
RESULT_APPROVE_DEPARTMENT = f"{MODULE}:result:approve-department"
RESULT_APPROVE_ALL = f"{MODULE}:result:approve-all"
RESULT_PUBLISH = f"{MODULE}:result:publish"
RESULT_REVISE = f"{MODULE}:result:revise"
REPORT_READ_DEPARTMENT = f"{MODULE}:report:read-department"
REPORT_READ_ALL = f"{MODULE}:report:read-all"

PERMISSION_KEYS = (
    EXAM_CYCLE_READ,
    EXAM_CYCLE_MANAGE,
    ASSESSMENT_SCHEME_READ,
    ASSESSMENT_SCHEME_WRITE_DEPARTMENT,
    ASSESSMENT_SCHEME_WRITE_ALL,
    GRADING_SCHEME_READ,
    GRADING_SCHEME_MANAGE,
    PAPER_READ,
    PAPER_MANAGE,
    SESSION_READ,
    SESSION_READ_OWN,
    SESSION_MANAGE,
    CANDIDATE_READ_DEPARTMENT,
    CANDIDATE_READ_ALL,
    CANDIDATE_DETERMINE,
    CANDIDATE_OVERRIDE,
    HALL_TICKET_READ_OWN,
    HALL_TICKET_READ_ALL,
    HALL_TICKET_ISSUE,
    HALL_TICKET_WITHHOLD,
    HALL_TICKET_REVOKE,
    DUTY_READ_OWN,
    DUTY_READ_DEPARTMENT,
    DUTY_READ_ALL,
    DUTY_ASSIGN,
    MARKS_READ_ASSIGNED,
    MARKS_READ_DEPARTMENT,
    MARKS_READ_ALL,
    MARKS_ENTER_ASSIGNED,
    MARKS_ENTER_ALL,
    MARKS_MODERATE_ASSIGNED,
    MARKS_MODERATE_DEPARTMENT,
    MARKS_LOCK,
    RESULT_READ_OWN,
    RESULT_READ_DEPARTMENT,
    RESULT_READ_ALL,
    RESULT_COMPUTE,
    RESULT_APPROVE_DEPARTMENT,
    RESULT_APPROVE_ALL,
    RESULT_PUBLISH,
    RESULT_REVISE,
    REPORT_READ_DEPARTMENT,
    REPORT_READ_ALL,
)


@dataclass
class Actor:
    """Who is calling. Built by the API layer from the verified token."""

    user_id: str
    organisation_id: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


def require(actor: Actor, permission: str) -> None:
    """403 unless the caller holds `permission` (the operation's x-permission in contracts/openapi.yaml)."""
    if not actor.can(permission):
        raise forbidden(f"missing permission {permission}")
