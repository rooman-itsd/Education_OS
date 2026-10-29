from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from eos_admissions.domain import enums as e
from eos_admissions.infrastructure.models import (
    PREFIX,
    TABLES,
    Application,
    ApplicationDocument,
    MeritList,
    MeritListEntry,
    Offer,
)
from eos_core.db import new_id
from sqlalchemy.exc import IntegrityError

CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml"
ORG_A, ORG_B = new_id(), new_id()


def schema_properties(name: str) -> set[str]:
    schemas = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))["components"]["schemas"]
    schema = schemas[name]
    parts = schema.get("allOf", [schema])
    props: set[str] = set()
    for part in parts:
        if "$ref" in part:
            props |= schema_properties(part["$ref"].rsplit("/", 1)[1])
        props |= set(part.get("properties", {}))
    return props


def application(org: str = ORG_A, reference: str = "ADM-2026-000001", **overrides) -> Application:
    """Unsaved, so constraint tests control exactly when it reaches the database."""
    values = {
        "organisation_id": org,
        "reference_number": reference,
        "applicant_first_name": "Ana",
        "applicant_last_name": "Silva",
        "applicant_email": "ana@example.com",
        "programme_id": new_id(),
        "academic_year": "2026-27",
    }
    return Application(**values | overrides)


def offer(app: Application, status: str = e.OFFER_OPEN) -> Offer:
    return Offer(organisation_id=app.organisation_id, application_id=app.id, status=status, offered_by="staff-1")


def test_every_table_is_prefixed_and_tenant_scoped():
    assert len(TABLES) == 6
    for table in TABLES:
        assert table.name.startswith(PREFIX)
        assert table.c.organisation_id.nullable is False


def test_reference_number_unique_per_organisation(fresh_db):
    fresh_db.add_all([application(ORG_A), application(ORG_B)])
    fresh_db.commit()

    fresh_db.add(application(ORG_A))
    with pytest.raises(IntegrityError):
        fresh_db.commit()


def test_only_one_open_offer_per_application(fresh_db):
    app = application()
    fresh_db.add(app)
    fresh_db.flush()
    fresh_db.add_all([offer(app, e.OFFER_EXPIRED), offer(app, e.DECLINED), offer(app)])
    fresh_db.commit()

    fresh_db.add(offer(app))
    with pytest.raises(IntegrityError):
        fresh_db.commit()


def merit_list_with(fresh_db) -> tuple[MeritList, Application, Application]:
    first, second = application(reference="ADM-2026-000001"), application(reference="ADM-2026-000002")
    merit = MeritList(organisation_id=ORG_A, programme_id=new_id(), academic_year="2026-27", created_by="staff-1")
    fresh_db.add_all([first, second, merit])
    fresh_db.flush()
    return merit, first, second


def entry(merit: MeritList, app: Application, rank: int) -> MeritListEntry:
    return MeritListEntry(organisation_id=ORG_A, merit_list_id=merit.id, application_id=app.id, rank=rank)


def test_application_appears_once_per_merit_list(fresh_db):
    merit, first, _ = merit_list_with(fresh_db)
    fresh_db.add_all([entry(merit, first, 1), entry(merit, first, 2)])
    with pytest.raises(IntegrityError):
        fresh_db.commit()


def test_rank_appears_once_per_merit_list(fresh_db):
    merit, first, second = merit_list_with(fresh_db)
    fresh_db.add_all([entry(merit, first, 1), entry(merit, second, 1)])
    with pytest.raises(IntegrityError):
        fresh_db.commit()


def test_defaults(fresh_db):
    app = application()
    fresh_db.add(app)
    fresh_db.flush()
    doc = ApplicationDocument(organisation_id=ORG_A, application_id=app.id, type="other", document_id="doc-1")
    merit = MeritList(organisation_id=ORG_A, programme_id=new_id(), academic_year="2026-27", created_by="staff-1")
    open_offer = offer(app)
    fresh_db.add_all([doc, merit, open_offer])
    fresh_db.commit()
    assert app.status == e.SUBMITTED
    assert doc.verification_status == e.PENDING
    assert open_offer.status == e.OFFER_OPEN
    assert merit.status == e.DRAFT


def test_to_dict_keys_match_the_contract(fresh_db):
    app = application(applicant_phone="+971500000000")
    fresh_db.add(app)
    fresh_db.flush()
    doc = ApplicationDocument(organisation_id=ORG_A, application_id=app.id, type="other", document_id="doc-1")
    merit = MeritList(organisation_id=ORG_A, programme_id=new_id(), academic_year="2026-27", created_by="staff-1")
    open_offer = offer(app)
    fresh_db.add_all([doc, merit, open_offer])
    fresh_db.flush()
    merit_entry = entry(merit, app, 1)
    fresh_db.add(merit_entry)
    fresh_db.commit()

    data = app.to_dict()
    assert set(data) == schema_properties("Application") - {"documents", "offer"}
    assert set(data["applicant"]) == schema_properties("ApplicantDetails")
    assert data["submitted_at"].endswith("+00:00")
    assert set(doc.to_dict()) == schema_properties("ApplicationDocument")
    assert set(open_offer.to_dict()) == schema_properties("Offer")
    assert set(merit.to_dict()) == schema_properties("MeritList") - {"entries"}
    assert set(merit_entry.to_dict()) == schema_properties("MeritListEntry") - {"reference_number"}
