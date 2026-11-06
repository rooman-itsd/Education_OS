"""platform/search opt-in: the declaration, the document provider and the trigger events."""

from __future__ import annotations

from pathlib import Path

import yaml
from eos_core.db import SessionLocal, new_id
from eos_student_information.infrastructure.models import Person
from eos_student_information.search import DECLARATION, PROVIDER

MODULE = Path(__file__).resolve().parents[2]
SEARCHABLE = yaml.safe_load((MODULE / "contracts" / "searchable.yaml").read_text(encoding="utf-8"))
EVENTS = {
    e["name"]: e for e in yaml.safe_load((MODULE / "contracts" / "events.yaml").read_text(encoding="utf-8"))["events"]
}
TYPE = SEARCHABLE["types"][0]
ENTRY_POINT = (MODULE / "backend" / "pyproject.toml").read_text(encoding="utf-8")


def add_person(org: str, **values) -> Person:
    values.setdefault("first_name", "Asha")
    values.setdefault("last_name", "Menon")
    values.setdefault("status", "active")
    with SessionLocal() as db:
        person = Person(organisation_id=org, **values)
        db.add(person)
        db.commit()
        return person


def test_the_provider_is_registered_under_the_module_name():
    assert '[project.entry-points."eos.search_documents"]' in ENTRY_POINT
    assert 'student-information = "eos_student_information.search:PROVIDER"' in ENTRY_POINT
    assert SEARCHABLE["module"] == "student-information"
    assert PROVIDER.declaration == DECLARATION and DECLARATION.is_file()


def test_the_declared_triggers_exist_with_the_id_field_in_their_payload():
    assert TYPE["name"] == "person"
    assert [t["event"] for t in TYPE["triggers"]] == [
        "student-information.person.created",
        "student-information.person.updated",
        "student-information.person.status-changed",
    ]
    for trigger in TYPE["triggers"]:
        assert trigger["action"] == "upsert" and trigger["id_field"] == "person_id"
        assert trigger["event"] in EVENTS
        assert trigger["id_field"] in EVENTS[trigger["event"]]["payload"]
    assert TYPE["read_permissions"]["any_of"] == ["student-information:person:read"]


def test_the_read_permission_is_in_the_permission_catalogue():
    catalogue = (MODULE / "contracts" / "permissions.yaml").read_text(encoding="utf-8")
    assert "student-information:person:read" in catalogue


def test_the_declared_fields_are_exactly_what_the_provider_returns():
    org = new_id()
    person = add_person(org)
    document = PROVIDER.get_document(org, "person", person.id)
    assert set(document["fields"]) == set(TYPE["fields"]) == {"name", "status"}


def test_the_provider_returns_the_name_and_status_and_nothing_sensitive():
    org = new_id()
    person = add_person(
        org,
        preferred_name="Ash",
        identity_number="PASSPORT-998877",
        contact={"email": "asha@example.org", "phone": "+971500000000"},
        guardians=[{"name": "Guardian One", "phone": "+971511111111"}],
        gender="female",
    )
    document = PROVIDER.get_document(org, "person", person.id)
    assert document["record_id"] == person.id
    assert document["fields"] == {"name": "Asha Menon", "status": "active"}
    assert "read_any_of" not in document
    flat = repr(document)
    for secret in ("PASSPORT-998877", "asha@example.org", "+971500000000", "Guardian One", "female"):
        assert secret not in flat


def test_the_persons_own_user_may_read_the_record():
    org, user = new_id(), new_id()
    linked = add_person(org, identity_user_id=user)
    unlinked = add_person(org)
    assert PROVIDER.get_document(org, "person", linked.id)["read_users"] == [user]
    assert "read_users" not in PROVIDER.get_document(org, "person", unlinked.id)


def test_a_missing_person_or_other_type_is_none():
    org = new_id()
    person = add_person(org)
    assert PROVIDER.get_document(org, "person", new_id()) is None
    assert PROVIDER.get_document(org, "document", person.id) is None
    assert PROVIDER.iter_documents(org, "document", None, 10) == []


def test_a_provider_call_for_one_organisation_never_returns_another_organisations_person():
    org_a, org_b = new_id(), new_id()
    person_a = add_person(org_a, first_name="Alice")
    person_b = add_person(org_b, first_name="Bob")
    assert PROVIDER.get_document(org_a, "person", person_b.id) is None
    assert PROVIDER.get_document(org_b, "person", person_a.id) is None
    assert [d["record_id"] for d in PROVIDER.iter_documents(org_a, "person", None, 100)] == [person_a.id]
    assert [d["record_id"] for d in PROVIDER.iter_documents(org_b, "person", None, 100)] == [person_b.id]
    assert PROVIDER.get_document("", "person", person_a.id) is None


def test_iter_documents_pages_in_id_order():
    org = new_id()
    ids = sorted(add_person(org, first_name=f"S{i}").id for i in range(5))
    first = PROVIDER.iter_documents(org, "person", None, 2)
    second = PROVIDER.iter_documents(org, "person", first[-1]["record_id"], 2)
    rest = PROVIDER.iter_documents(org, "person", second[-1]["record_id"], 2)
    assert [d["record_id"] for d in first + second + rest] == ids
