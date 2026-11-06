"""Document provider for platform/search, registered on the `eos.search_documents` entry point in
backend/pyproject.toml. Search calls it, in the organisation of the event or reindex, to learn what to index; this
module imports nothing from search and returns plain mappings.

Indexed: a course's title, code, description, status and credits. Archived courses return None (their
`course.archived` event deletes the document, and a reindex must not restore it)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from eos_core.db import SessionLocal
from eos_core.tenant import organisation_scope
from sqlalchemy import select

from .domain.courses import ARCHIVED
from .infrastructure.models import CourseRow

TYPE = "course"
DECLARATION = Path(__file__).resolve().parents[3] / "contracts" / "searchable.yaml"


def _document(course: CourseRow) -> dict[str, Any]:
    return {
        "record_id": course.id,
        "fields": {
            "title": course.title,
            "code": course.code,
            "description": course.description or "",
            "status": course.status,
            "credits": float(course.credits),
        },
    }


class AcademicManagementSearch:
    declaration = DECLARATION

    def get_document(self, organisation_id: str, type: str, record_id: str) -> dict[str, Any] | None:
        if type != TYPE or not organisation_id:
            return None
        with organisation_scope(organisation_id), SessionLocal() as db:
            db.info["organisation_id"] = organisation_id
            course = db.scalars(
                select(CourseRow).where(CourseRow.organisation_id == organisation_id, CourseRow.id == record_id)
            ).first()
            return _document(course) if course and course.status != ARCHIVED else None

    def iter_documents(self, organisation_id: str, type: str, after_id: str | None, limit: int) -> list[dict[str, Any]]:
        if type != TYPE or not organisation_id:
            return []
        query = select(CourseRow).where(CourseRow.organisation_id == organisation_id, CourseRow.status != ARCHIVED)
        if after_id:
            query = query.where(CourseRow.id > after_id)
        with organisation_scope(organisation_id), SessionLocal() as db:
            db.info["organisation_id"] = organisation_id
            return [_document(c) for c in db.scalars(query.order_by(CourseRow.id).limit(limit))]


PROVIDER = AcademicManagementSearch()
