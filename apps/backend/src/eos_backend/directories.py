"""Lookups a feature module needs from a platform service it may not import (rule 2: a module imports only from itself
and packages/). The host wires them here, the way it wires identity's hooks in main.py.

academic-management shows a faculty member's name on the faculty-load widget but has no way to ask identity for it.
Its `faculty_directory` dependency refuses by default (503), so the widget failed as soon as anyone was assigned.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable

from eos_core.db import get_db
from eos_core.tenant import resolve_organisation
from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

UNKNOWN_FACULTY = "Unknown user"


def faculty_directory(db: Session = Depends(get_db)) -> Callable[[str], str]:
    """Display names of the caller's own organisation's users, looked up in identity.

    identity.get_user reads in platform scope, so any organisation's user comes back; a name is only given for a
    user of the caller's organisation, and anyone else (or an id identity does not know) shows as a neutral label,
    never as another tenant's name and never as an error that takes the whole report down."""
    from eos_identity.application import service as identity

    organisation_id = resolve_organisation(db)
    cache: dict[str, str] = {}

    def name(faculty_id: str) -> str:
        if faculty_id not in cache:
            user = identity.get_user(db, faculty_id)
            same_organisation = (
                user is not None and organisation_id is not None and user.organisation_id == organisation_id
            )
            cache[faculty_id] = (user.name or user.email) if same_organisation else UNKNOWN_FACULTY
        return cache[faculty_id]

    return name


def wire(app: FastAPI, mounted_modules: set[str]) -> None:
    """Override the module's refusing default, for the modules this host mounts."""
    if "academic-management" in mounted_modules:
        router = importlib.import_module("eos_academic_management.api.router")
        app.dependency_overrides[router.faculty_directory] = faculty_directory
