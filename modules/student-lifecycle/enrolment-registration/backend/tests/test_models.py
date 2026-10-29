from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
import yaml
from conftest import CONTRACTS
from eos_core.db import new_id
from eos_enrolment_registration.domain import enums as e
from eos_enrolment_registration.infrastructure.models import (
    PREFIX,
    TABLES,
    CourseRegistration,
    ProcessedEvent,
    ProgrammeEnrolment,
    RegistrationWindow,
    RollNumberCounter,
)
from sqlalchemy.exc import IntegrityError

ORG_A, ORG_B = new_id(), new_id()
PROGRAMME, TERM = new_id(), new_id()


def schema_properties(name: str) -> set[str]:
    schemas = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))["components"]["schemas"]
    schema = schemas[name]
    props: set[str] = set()
    for part in schema.get("allOf", [schema]):
        if "$ref" in part:
            props |= schema_properties(part["$ref"].rsplit("/", 1)[1])
        props |= set(part.get("properties", {}))
    return props


def enrolment(org: str = ORG_A, person: str | None = None, roll: str = "RN2026-00001", **over) -> ProgrammeEnrolment:
    values = {
        "organisation_id": org,
        "person_id": person or new_id(),
        "student_name": "Ana Silva",
        "programme_id": PROGRAMME,
        "roll_number": roll,
        "start_academic_period_id": TERM,
        "enrolled_by": "staff-1",
    }
    return ProgrammeEnrolment(**values | over)


def registration(enr: ProgrammeEnrolment, offering: str, **over) -> CourseRegistration:
    values = {
        "organisation_id": enr.organisation_id,
        "programme_enrolment_id": enr.id,
        "person_id": enr.person_id,
        "course_offering_id": offering,
        "section_id": new_id(),
        "academic_period_id": TERM,
        "section_since": date(2026, 10, 1),
        "confirmed_by": "staff-1",
    }
    return CourseRegistration(**values | over)


def test_every_table_is_prefixed_and_tenant_scoped():
    assert len(TABLES) == 9
    for table in TABLES:
        assert table.name.startswith(PREFIX)
        assert table.c.organisation_id.nullable is False


def test_roll_number_unique_per_organisation(fresh_db):
    fresh_db.add_all([enrolment(ORG_A), enrolment(ORG_B)])
    fresh_db.commit()
    fresh_db.add(enrolment(ORG_A))
    with pytest.raises(IntegrityError):
        fresh_db.commit()


def test_one_active_enrolment_per_person_and_programme(fresh_db):
    person = new_id()
    fresh_db.add_all(
        [
            enrolment(person=person, roll="RN2026-00001", status=e.WITHDRAWN),
            enrolment(person=person, roll="RN2026-00002", status=e.COMPLETED),
            enrolment(person=person, roll="RN2026-00003"),
            enrolment(person=person, roll="RN2026-00004", programme_id=new_id()),
        ]
    )
    fresh_db.commit()
    fresh_db.add(enrolment(person=person, roll="RN2026-00005"))
    with pytest.raises(IntegrityError):
        fresh_db.commit()


def test_one_confirmed_registration_per_person_and_offering(fresh_db):
    enr = enrolment()
    fresh_db.add(enr)
    fresh_db.flush()
    offering = new_id()
    fresh_db.add_all(
        [registration(enr, offering, status=e.WITHDRAWN), registration(enr, offering), registration(enr, new_id())]
    )
    fresh_db.commit()
    fresh_db.add(registration(enr, offering))
    with pytest.raises(IntegrityError):
        fresh_db.commit()


def test_one_window_per_term(fresh_db):
    def window():
        return RegistrationWindow(
            organisation_id=ORG_A,
            academic_period_id=TERM,
            opens_at=datetime(2026, 10, 1, tzinfo=UTC),
            closes_at=datetime(2026, 10, 15, tzinfo=UTC),
            updated_by="staff-1",
        )

    fresh_db.add(window())
    fresh_db.commit()
    fresh_db.add(window())
    with pytest.raises(IntegrityError):
        fresh_db.commit()


def test_one_counter_per_organisation_and_year_and_one_processed_event(fresh_db):
    fresh_db.add_all(
        [
            RollNumberCounter(organisation_id=ORG_A, year=2026, last_value=1),
            RollNumberCounter(organisation_id=ORG_A, year=2027, last_value=1),
            ProcessedEvent(organisation_id=ORG_A, event_id="ev-1", name="x"),
            ProcessedEvent(organisation_id=ORG_B, event_id="ev-1", name="x"),
        ]
    )
    fresh_db.commit()
    fresh_db.add(ProcessedEvent(organisation_id=ORG_A, event_id="ev-1", name="x"))
    with pytest.raises(IntegrityError):
        fresh_db.commit()


def test_defaults_and_to_dict_match_the_contract(fresh_db):
    enr = enrolment()
    fresh_db.add(enr)
    fresh_db.flush()
    reg = registration(enr, new_id())
    window = RegistrationWindow(
        organisation_id=ORG_A,
        academic_period_id=TERM,
        opens_at=datetime(2026, 10, 1, tzinfo=UTC),
        closes_at=datetime(2026, 10, 15, tzinfo=UTC),
        updated_by="staff-1",
    )
    fresh_db.add_all([reg, window])
    fresh_db.commit()

    assert (enr.status, reg.status, reg.registration_type, reg.references_verified) == (
        e.ACTIVE,
        e.CONFIRMED,
        e.REGULAR,
        False,
    )
    assert set(enr.to_dict()) == schema_properties("ProgrammeEnrolment")
    assert set(reg.to_dict()) == schema_properties("CourseRegistration") - {"student_name", "roll_number"}
    assert set(window.to_dict()) == schema_properties("RegistrationWindow") - {"is_open"}
    assert enr.to_dict()["enrolled_at"].endswith("+00:00")
    assert reg.to_dict()["section_since"] == "2026-10-01"
