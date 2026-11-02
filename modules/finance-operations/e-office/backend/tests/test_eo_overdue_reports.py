"""Overdue: computed on every read, flagged and published once per holding by the scheduler job. The pendency report."""

from types import SimpleNamespace

import pytest
from eo_support import BASE, forward, open_file, outbox
from eos_core.db import SessionLocal
from eos_core.tenant import organisation_scope, platform_scope
from eos_e_office.application import consumers, jobs, service


def flag() -> int:
    with SessionLocal() as db, platform_scope():
        return service.flag_overdue(db)


def overdue_events(org) -> list[dict]:
    return outbox("e-office.file.overdue", org.id)


def test_a_file_past_its_due_date_is_flagged_once(client, org, clock):
    f = open_file(client, org)
    forward(client, org, f, "hr", "finance", due_on="2026-11-02")
    clock.advance(days=2)  # 2 November: due today, not overdue
    flag()
    assert overdue_events(org) == []
    assert client.get(f"{BASE}/me/inbox", headers=org.finance).json()["overdue"] == 0
    clock.advance(days=1)  # 3 November
    assert client.get(f"{BASE}/me/inbox", headers=org.finance).json()["overdue"] == 1
    flag()
    flag()  # at-least-once delivery: a second run publishes nothing more
    assert overdue_events(org) == [
        {
            "organisation_id": org.id,
            "file_id": f["id"],
            "number": f["number"],
            "holder_id": org.ids["finance"],
            "due_on": "2026-11-02",
        }
    ]
    # a new holding starts again, with the default days for the priority
    forward(client, org, f, "finance", "dept")
    flag()
    assert len(overdue_events(org)) == 1
    clock.advance(days=8)  # 11 November: received 3 November + 7 days = 10 November
    flag()
    assert overdue_events(org)[-1]["due_on"] == "2026-11-10" and overdue_events(org)[-1]["holder_id"] == org.ids["dept"]


@pytest.mark.parametrize("priority, days_late", [("normal", 8), ("urgent", 3), ("immediate", 2)])
def test_default_days_by_priority(client, org, clock, priority, days_late):
    f = open_file(client, org, priority=priority)
    clock.advance(days=days_late - 1)
    flag()
    assert [e["file_id"] for e in overdue_events(org)] == []
    clock.advance(days=1)
    flag()
    assert [e["file_id"] for e in overdue_events(org)] == [f["id"]]


def test_default_days_follow_the_settings(client, org, clock, monkeypatch):
    monkeypatch.setenv("E_OFFICE_DEFAULT_DUE_DAYS_NORMAL", "1")
    f = open_file(client, org)
    clock.advance(days=2)
    flag()
    assert [e["file_id"] for e in overdue_events(org)] == [f["id"]]


def test_closed_files_are_never_overdue(client, org, clock):
    f = open_file(client, org)
    client.post(f"{BASE}/files/{f['id']}/close", json={"remark": "Done"}, headers=org.hr)
    clock.advance(days=30)
    flag()
    assert overdue_events(org) == []
    assert client.get(f"{BASE}/files/{f['id']}", headers=org.hr).json()["overdue"] is False


def test_an_organisation_scope_flags_only_that_organisation(client, org, other_org, clock):
    mine, theirs = open_file(client, org), open_file(client, other_org)
    clock.advance(days=10)
    with SessionLocal() as db, organisation_scope(org.id):
        assert service.flag_overdue(db) == 1
    assert [e["file_id"] for e in overdue_events(org)] == [mine["id"]]
    assert overdue_events(other_org) == []
    flag()
    assert [e["file_id"] for e in overdue_events(other_org)] == [theirs["id"]]


def test_the_scheduler_job_is_declared_and_handled(client, org, clock):
    from eos_core.events import OutboxEvent
    from sqlalchemy import select

    assert jobs.JOBS["e-office.flag-overdue"]["scope"] == "platform"
    assert jobs.JOBS["e-office.flag-overdue"]["idempotent"] is True
    assert set(consumers.CONSUMERS) == {"scheduler.job.due"}
    f = open_file(client, org)
    clock.advance(days=10)
    run_id = "11111111-1111-1111-1111-111111111111"
    with SessionLocal() as db, platform_scope():
        consumers.on_job_due(db, SimpleNamespace(organisation_id=None, payload={"job": "billing.expire-trials"}))
        consumers.on_job_due(
            db, SimpleNamespace(organisation_id=None, payload={"job": "e-office.flag-overdue", "run_id": run_id})
        )
        db.commit()
        finished = [
            e.payload
            for e in db.scalars(select(OutboxEvent).where(OutboxEvent.name == "e-office.job.finished"))
            if e.payload.get("run_id") == run_id
        ]
    assert f["id"] in [e["file_id"] for e in overdue_events(org)]
    assert len(finished) == 1 and finished[0]["outcome"] == "succeeded" and "flagged overdue" in finished[0]["detail"]


def test_pendency_report(client, org, clock):
    old = open_file(client, org, department_id="d1")
    forward(client, org, old, "hr", "finance", due_on="2026-11-01")
    clock.advance(days=5)  # 5 November
    fresh = open_file(client, org, department_id="d2")
    forward(client, org, fresh, "hr", "finance")
    mine = open_file(client, org)
    secret = open_file(client, org, confidential=True, department_id="d1")
    closed = open_file(client, org)
    client.post(f"{BASE}/files/{closed['id']}/close", json={"remark": "x"}, headers=org.hr)
    assert client.get(f"{BASE}/reports/pendency", headers=org.hr).status_code == 403
    r = client.get(f"{BASE}/reports/pendency", headers=org.dept)
    assert r.status_code == 200
    report = r.json()
    assert (report["open_files"], report["overdue"]) == (4, 1)
    assert report["by_age"] == [
        {"bucket": "0-3d", "count": 3},
        {"bucket": "4-7d", "count": 1},
        {"bucket": "8-15d", "count": 0},
        {"bucket": "16-30d", "count": 0},
        {"bucket": "30d+", "count": 0},
    ]
    holders = {h["holder"]["user_id"]: h for h in report["by_holder"]}
    assert (holders[org.ids["finance"]]["open"], holders[org.ids["finance"]]["overdue"]) == (2, 1)
    assert holders[org.ids["hr"]]["open"] == 2
    assert report["by_holder"][0]["holder"]["user_id"] == org.ids["finance"]  # the most overdue first
    assert report["by_department"] == [
        {"department_id": "d1", "open": 2, "overdue": 1},
        {"department_id": "d2", "open": 1, "overdue": 0},
        {"department_id": None, "open": 1, "overdue": 0},
    ]
    assert "subject" not in str(report) and secret["subject"] not in str(report) and mine["id"] not in str(report)
    only = client.get(f"{BASE}/reports/pendency?department_id=d2", headers=org.manager).json()
    assert only["open_files"] == 1
