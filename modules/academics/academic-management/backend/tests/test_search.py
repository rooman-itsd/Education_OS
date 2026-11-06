"""platform/search opt-in: the declaration, the document provider and the trigger events."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see test_api_deps.py)")

from eos_academic_management.infrastructure.models import CourseRow  # noqa: E402
from eos_academic_management.search import DECLARATION, PROVIDER  # noqa: E402
from eos_core.db import SessionLocal, init_db, new_id  # noqa: E402

MODULE = Path(__file__).resolve().parents[2]
SEARCHABLE = yaml.safe_load((MODULE / "contracts" / "searchable.yaml").read_text(encoding="utf-8"))
EVENTS = {
    e["name"]: e for e in yaml.safe_load((MODULE / "contracts" / "events.yaml").read_text(encoding="utf-8"))["events"]
}
TYPE = SEARCHABLE["types"][0]
ENTRY_POINT = (MODULE / "backend" / "pyproject.toml").read_text(encoding="utf-8")


@pytest.fixture(scope="module", autouse=True)
def tables():
    init_db()


def add_course(org: str, **values) -> CourseRow:
    values.setdefault("code", f"CS{new_id()[:6]}")
    values.setdefault("title", "Data Structures")
    values.setdefault("description", "Lists, trees and graphs")
    values.setdefault("credits", Decimal("4.5"))
    values.setdefault("course_type", "theory")
    values.setdefault("department_id", new_id())
    values.setdefault("status", "active")
    with SessionLocal() as db:
        course = CourseRow(organisation_id=org, **values)
        db.add(course)
        db.commit()
        return course


def test_the_provider_is_registered_under_the_module_name():
    assert '[project.entry-points."eos.search_documents"]' in ENTRY_POINT
    assert 'academic-management = "eos_academic_management.search:PROVIDER"' in ENTRY_POINT
    assert SEARCHABLE["module"] == "academic-management"
    assert PROVIDER.declaration == DECLARATION and DECLARATION.is_file()


def test_the_declared_triggers_exist_with_the_id_field_in_their_payload():
    assert TYPE["name"] == "course"
    assert [(t["event"], t["action"]) for t in TYPE["triggers"]] == [
        ("academic-management.course.created", "upsert"),
        ("academic-management.course.updated", "upsert"),
        ("academic-management.course.archived", "delete"),
    ]
    for trigger in TYPE["triggers"]:
        assert trigger["event"] in EVENTS
        assert trigger["id_field"] == "course_id"
        assert trigger["id_field"] in EVENTS[trigger["event"]]["payload"]
    assert TYPE["read_permissions"]["any_of"] == ["academic-management:course:read"]


def test_the_read_permission_is_in_the_permission_catalogue():
    assert "academic-management:course:read" in (MODULE / "contracts" / "permissions.yaml").read_text(encoding="utf-8")


def test_the_declared_fields_are_exactly_what_the_provider_returns():
    org = new_id()
    course = add_course(org)
    document = PROVIDER.get_document(org, "course", course.id)
    assert set(document["fields"]) == set(TYPE["fields"])
    assert document["fields"]["credits"] == 4.5


def test_the_provider_returns_the_course():
    org = new_id()
    course = add_course(org, code="CS-101", title="Algorithms", description=None)
    document = PROVIDER.get_document(org, "course", course.id)
    assert document["record_id"] == course.id
    assert document["fields"] == {
        "title": "Algorithms",
        "code": "CS-101",
        "description": "",
        "status": "active",
        "credits": 4.5,
    }
    assert "read_any_of" not in document and "read_users" not in document


def test_a_missing_archived_or_other_type_is_none():
    org = new_id()
    active = add_course(org)
    archived = add_course(org, status="archived")
    assert PROVIDER.get_document(org, "course", new_id()) is None
    assert PROVIDER.get_document(org, "course", archived.id) is None
    assert PROVIDER.get_document(org, "programme", active.id) is None
    assert [d["record_id"] for d in PROVIDER.iter_documents(org, "course", None, 10)] == [active.id]
    assert PROVIDER.iter_documents(org, "programme", None, 10) == []


def test_a_provider_call_for_one_organisation_never_returns_another_organisations_course():
    org_a, org_b = new_id(), new_id()
    course_a = add_course(org_a, code="A-1")
    course_b = add_course(org_b, code="B-1")
    assert PROVIDER.get_document(org_a, "course", course_b.id) is None
    assert PROVIDER.get_document(org_b, "course", course_a.id) is None
    assert [d["record_id"] for d in PROVIDER.iter_documents(org_a, "course", None, 100)] == [course_a.id]
    assert [d["record_id"] for d in PROVIDER.iter_documents(org_b, "course", None, 100)] == [course_b.id]
    assert PROVIDER.get_document("", "course", course_a.id) is None


def test_iter_documents_pages_in_id_order():
    org = new_id()
    ids = sorted(add_course(org).id for _ in range(5))
    first = PROVIDER.iter_documents(org, "course", None, 2)
    second = PROVIDER.iter_documents(org, "course", first[-1]["record_id"], 2)
    rest = PROVIDER.iter_documents(org, "course", second[-1]["record_id"], 2)
    assert [d["record_id"] for d in first + second + rest] == ids
