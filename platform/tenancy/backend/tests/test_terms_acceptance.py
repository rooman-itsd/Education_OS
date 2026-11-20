"""Consent at registration (DPDP, #148): a registration that does not accept the terms is refused, and one that
does records which version was accepted, when and by whom. Runs with the module alone on SQLite."""

from datetime import UTC, datetime

from conftest import organisation
from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_identity.domain.models import User
from eos_tenancy.application import service as tenancy
from eos_tenancy.domain.models import Organisation
from sqlalchemy import select

BASE = "/api/v1/tenancy/admin/organisations"


def registration(slug: str, **extra) -> dict:
    return {
        "organisation_name": slug.replace("-", " ").title(),
        "slug": slug,
        "academy_type": "music-academy",
        "admin": {"name": "Admin", "email": f"admin@{slug}.example.com", "password": "Passw0rd!x"},
        **extra,
    }


def stored(slug: str) -> Organisation | None:
    with SessionLocal() as db, platform_scope():
        return db.scalar(select(Organisation).where(Organisation.slug == slug))


def test_a_registration_without_accepting_the_terms_is_refused_and_nothing_is_kept(client):
    for body in (registration("terms-missing"), registration("terms-false", accepted_terms=False)):
        r = client.post("/api/v1/tenancy/register", json=body)
        assert r.status_code == 400, r.text
        assert "terms" in r.json()["detail"]
        assert stored(body["slug"]) is None


def test_the_accepted_version_time_and_administrator_are_recorded(client, monkeypatch, fake_events):
    moment = datetime(2026, 11, 20, 9, 30, tzinfo=UTC)
    monkeypatch.setattr(tenancy, "clock", lambda: moment)
    r = client.post("/api/v1/tenancy/register", json=registration("terms-kept", accepted_terms=True))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["terms_version"] == tenancy.DEFAULT_TERMS_VERSION
    assert body["terms_accepted_at"].startswith("2026-11-20T09:30")

    with SessionLocal() as db, platform_scope():
        admin = db.scalar(select(User).where(User.email == "admin@terms-kept.example.com"))
    assert body["terms_accepted_by"] == admin.id
    fake_events.assert_published("tenancy.organisation.registered", organisation_id=body["id"])
    ev = fake_events.find("tenancy.organisation.registered", organisation_id=body["id"])[-1]
    assert ev["payload"]["terms_version"] == tenancy.DEFAULT_TERMS_VERSION


def test_the_version_comes_from_the_environment_when_set(client, monkeypatch):
    monkeypatch.setenv("EOS_TERMS_VERSION", " 2027-01-01 ")
    r = client.post("/api/v1/tenancy/register", json=registration("terms-env", accepted_terms=True))
    assert r.status_code == 201, r.text
    assert r.json()["terms_version"] == "2027-01-01"
    assert stored("terms-env").terms_version == "2027-01-01"


def test_the_record_is_shown_to_the_organisation_and_in_its_export(client, super_admin):
    a = organisation(client, "terms-export")
    mine = client.get("/api/v1/tenancy/organisation", headers=a["headers"])
    assert mine.status_code == 200, mine.text
    assert mine.json()["terms_version"] == tenancy.DEFAULT_TERMS_VERSION
    assert mine.json()["terms_accepted_at"]

    r = client.get(f"{BASE}/{a['org']['id']}/export", headers=super_admin)
    assert r.status_code == 200, r.text
    row = r.json()["tables"]["tenancy_organisation"][0]
    assert row["terms_version"] == tenancy.DEFAULT_TERMS_VERSION
    assert row["terms_accepted_by"] == mine.json()["terms_accepted_by"]
    assert row["terms_accepted_at"]
