"""Who is calling and what they may do. Keys are the ones in contracts/permissions.yaml (a test compares them); the
API layer resolves the caller's keys through the platform (eos_core.permissions_for), as academic-management does.

How the caller's department is known is open (PRD Q9), so Actor carries no department and no key is treated as
department-scoped: `department_id` is a filter, never a grant."""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import forbidden

MODULE = "timetable-attendance"
TIMETABLE_READ = f"{MODULE}:timetable:read"
TIMETABLE_WRITE = f"{MODULE}:timetable:write"
TIMETABLE_PUBLISH = f"{MODULE}:timetable:publish"
SCHEDULED_CLASS_READ = f"{MODULE}:scheduled-class:read"
SCHEDULED_CLASS_READ_OWN = f"{MODULE}:scheduled-class:read-own"
SCHEDULED_CLASS_WRITE = f"{MODULE}:scheduled-class:write"
SCHEDULED_CLASS_CANCEL = f"{MODULE}:scheduled-class:cancel"
ATTENDANCE_SESSION_READ = f"{MODULE}:attendance-session:read"
ATTENDANCE_SESSION_OPEN = f"{MODULE}:attendance-session:open"
ATTENDANCE_SESSION_CLOSE = f"{MODULE}:attendance-session:close"
ATTENDANCE_SESSION_OVERRIDE = f"{MODULE}:attendance-session:override"
ATTENDANCE_RECORD_READ = f"{MODULE}:attendance-record:read"
ATTENDANCE_RECORD_READ_OWN = f"{MODULE}:attendance-record:read-own"
ATTENDANCE_RECORD_MARK = f"{MODULE}:attendance-record:mark"
ATTENDANCE_RECORD_CORRECT = f"{MODULE}:attendance-record:correct"
ATTENDANCE_RECORD_CORRECT_DEPARTMENT = f"{MODULE}:attendance-record:correct-department"
REPORT_READ_OWN = f"{MODULE}:report:read-own"
REPORT_READ_DEPARTMENT = f"{MODULE}:report:read-department"
REPORT_READ_ALL = f"{MODULE}:report:read-all"
REPORT_READ_ELIGIBILITY = f"{MODULE}:report:read-eligibility"

PERMISSION_KEYS = (
    TIMETABLE_READ,
    TIMETABLE_WRITE,
    TIMETABLE_PUBLISH,
    SCHEDULED_CLASS_READ,
    SCHEDULED_CLASS_READ_OWN,
    SCHEDULED_CLASS_WRITE,
    SCHEDULED_CLASS_CANCEL,
    ATTENDANCE_SESSION_READ,
    ATTENDANCE_SESSION_OPEN,
    ATTENDANCE_SESSION_CLOSE,
    ATTENDANCE_SESSION_OVERRIDE,
    ATTENDANCE_RECORD_READ,
    ATTENDANCE_RECORD_READ_OWN,
    ATTENDANCE_RECORD_MARK,
    ATTENDANCE_RECORD_CORRECT,
    ATTENDANCE_RECORD_CORRECT_DEPARTMENT,
    REPORT_READ_OWN,
    REPORT_READ_DEPARTMENT,
    REPORT_READ_ALL,
    REPORT_READ_ELIGIBILITY,
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
