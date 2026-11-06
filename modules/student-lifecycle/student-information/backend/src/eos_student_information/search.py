"""Document provider for platform/search, registered on the `eos.search_documents` entry point in
backend/pyproject.toml. Search calls it, in the organisation of the event or reindex, to learn what to index; this
module imports nothing from search and returns plain mappings.

Indexed: the person's full name and status. Never indexed: contact details, guardians, date of birth, gender and
identity_number (a national ID or passport number). The person's own sign-in account (identity_user_id) is returned as
`read_users`, so a student finds their own record even without person:read.

A missing person yields None. The module has no erasure marker and no delete today (a person is withdrawn, never
removed), so a person that is gone from the table is the only erased case; when erasure exists it must return None
here too."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from eos_core.db import SessionLocal
from eos_core.tenant import organisation_scope
from sqlalchemy import select

from .infrastructure.models import Person

TYPE = "person"
DECLARATION = Path(__file__).resolve().parents[3] / "contracts" / "searchable.yaml"


def _document(person: Person) -> dict[str, Any]:
    document: dict[str, Any] = {
        "record_id": person.id,
        "fields": {
            "name": f"{person.first_name} {person.last_name}".strip(),
            "status": person.status,
        },
    }
    if person.identity_user_id:
        document["read_users"] = [person.identity_user_id]
    return document


class StudentInformationSearch:
    declaration = DECLARATION

    def get_document(self, organisation_id: str, type: str, record_id: str) -> dict[str, Any] | None:
        if type != TYPE or not organisation_id:
            return None
        with organisation_scope(organisation_id), SessionLocal() as db:
            db.info["organisation_id"] = organisation_id
            person = db.scalars(
                select(Person).where(Person.organisation_id == organisation_id, Person.id == record_id)
            ).first()
            return _document(person) if person else None

    def iter_documents(self, organisation_id: str, type: str, after_id: str | None, limit: int) -> list[dict[str, Any]]:
        if type != TYPE or not organisation_id:
            return []
        query = select(Person).where(Person.organisation_id == organisation_id)
        if after_id:
            query = query.where(Person.id > after_id)
        with organisation_scope(organisation_id), SessionLocal() as db:
            db.info["organisation_id"] = organisation_id
            return [_document(p) for p in db.scalars(query.order_by(Person.id).limit(limit))]


PROVIDER = StudentInformationSearch()
