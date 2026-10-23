"""Who is calling and what they may do. Keys are the ones in contracts/permissions.yaml; the API layer resolves
the caller's keys through the platform (eos_core.permissions_for), as facility-booking does.

Which profile roles receive these keys (platform role ids or module role names) is pending with Faizan on
issue #100; nothing here maps roles to keys. The caller's department (HoD scope) is pending too, so Actor carries
no department."""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import forbidden

MODULE = "academic-management"
TERM_READ = f"{MODULE}:term:read"
TERM_WRITE = f"{MODULE}:term:write"
PROGRAMME_READ = f"{MODULE}:programme:read"
PROGRAMME_WRITE = f"{MODULE}:programme:write"
CURRICULUM_READ = f"{MODULE}:curriculum:read"
CURRICULUM_WRITE = f"{MODULE}:curriculum:write"
CURRICULUM_PUBLISH = f"{MODULE}:curriculum:publish"
COURSE_READ = f"{MODULE}:course:read"
COURSE_WRITE = f"{MODULE}:course:write"
OFFERING_READ = f"{MODULE}:offering:read"
OFFERING_WRITE = f"{MODULE}:offering:write"
FACULTY_ASSIGNMENT_READ = f"{MODULE}:faculty-assignment:read"
FACULTY_ASSIGNMENT_WRITE = f"{MODULE}:faculty-assignment:write"
ROSTER_READ = f"{MODULE}:roster:read"
ROSTER_READ_ALL = f"{MODULE}:roster:read-all"
FACULTY_LOAD_READ = f"{MODULE}:faculty-load:read"

PERMISSION_KEYS = (
    TERM_READ,
    TERM_WRITE,
    PROGRAMME_READ,
    PROGRAMME_WRITE,
    CURRICULUM_READ,
    CURRICULUM_WRITE,
    CURRICULUM_PUBLISH,
    COURSE_READ,
    COURSE_WRITE,
    OFFERING_READ,
    OFFERING_WRITE,
    FACULTY_ASSIGNMENT_READ,
    FACULTY_ASSIGNMENT_WRITE,
    ROSTER_READ,
    ROSTER_READ_ALL,
    FACULTY_LOAD_READ,
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
