"""The daily jobs: pass expiry, document expiry flags, position purge (docs/user-stories.md JB)."""

from datetime import UTC, date, datetime, timedelta

from conftest import NOW, at, events
from eos_core.db import SessionLocal
from eos_transport.application import jobs
from eos_transport.infrastructure.models import Position
from sqlalchemy import func, select


def test_expire_passes_once(campus):
    c = campus
    _, me, p = c.rider()
    with SessionLocal() as db:
        assert jobs.expire_passes(db, date(2027, 3, 31)) == 0  # still valid on its last day
    with SessionLocal() as db:
        assert jobs.expire_passes(db, date(2027, 4, 1)) >= 1
    assert c.get("/me/passes", me).json()[0]["status"] == "expired"
    assert [e["pass_id"] for e in events("transport.pass.expired", c.org.id)] == [p["id"]]
    with SessionLocal() as db:
        jobs.expire_passes(db, date(2027, 4, 2))
    assert len(events("transport.pass.expired", c.org.id)) == 1


def test_flag_expiring_documents_once_per_expiry_date(campus):
    c = campus
    body = {"registration_no": "KA01AB1234", "capacity": 2, "insurance_expires_on": "2026-11-20"}
    c.patch(f"/vehicles/{c.vehicle['id']}", body, c.admin)
    with SessionLocal() as db:
        jobs.flag_expiring_documents(db, date(2026, 10, 27), days=30)
    flagged = [e for e in events("transport.document.expiry-flagged", c.org.id)]
    assert flagged == [
        {
            "organisation_id": c.org.id,
            "subject": "vehicle",
            "subject_id": c.vehicle["id"],
            "document": "insurance",
            "expires_on": "2026-11-20",
        }
    ]
    with SessionLocal() as db:
        jobs.flag_expiring_documents(db, date(2026, 10, 28), days=30)
    assert len(events("transport.document.expiry-flagged", c.org.id)) == 1
    # Renewed, then close to the new date: flagged again.
    c.patch(f"/vehicles/{c.vehicle['id']}", {**body, "insurance_expires_on": "2027-11-20"}, c.admin)
    with SessionLocal() as db:
        jobs.flag_expiring_documents(db, date(2027, 11, 1), days=30)
    docs = {(e["document"], e["expires_on"]) for e in events("transport.document.expiry-flagged", c.org.id)}
    assert ("insurance", "2027-11-20") in docs
    assert ("licence", "2028-01-31") not in docs  # outside the window
    with SessionLocal() as db:
        jobs.flag_expiring_documents(db, date(2028, 1, 10), days=30)
    docs = {(e["subject"], e["document"]) for e in events("transport.document.expiry-flagged", c.org.id)}
    assert ("driver", "licence") in docs


def test_purge_old_positions(campus):
    c = campus
    trip = c.post("/trips", {"route_id": c.route["id"]}, c.driver).json()
    old = (NOW - timedelta(days=40)).isoformat()
    c.post(
        f"/trips/{trip['id']}/positions",
        [
            {"recorded_at": old, "latitude": 12.9, "longitude": 77.6},
            {"recorded_at": at(7), "latitude": 12.9, "longitude": 77.6},
        ],
        c.driver,
    )

    def count() -> int:
        with SessionLocal() as db:
            return db.scalar(select(func.count()).select_from(Position).where(Position.trip_id == trip["id"]))

    assert count() == 2
    with SessionLocal() as db:
        jobs.purge_positions(db, datetime(2026, 10, 27, 8, tzinfo=UTC), retention_days=30)
    assert count() == 1


def test_run_daily_reads_the_environment(monkeypatch):
    monkeypatch.setenv("TRANSPORT_POSITION_RETENTION_DAYS", "not-a-number")
    assert jobs._days("TRANSPORT_POSITION_RETENTION_DAYS", 30) == 30
    monkeypatch.setenv("TRANSPORT_POSITION_RETENTION_DAYS", "7")
    assert jobs._days("TRANSPORT_POSITION_RETENTION_DAYS", 30) == 7
    with SessionLocal() as db:
        assert set(jobs.run_daily(db)) == {"passes_expired", "documents_flagged", "positions_purged"}
