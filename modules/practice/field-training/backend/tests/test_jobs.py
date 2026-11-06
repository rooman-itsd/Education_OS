"""The daily start job (docs/user-stories.md JB-1)."""

from datetime import date

from conftest import events
from eos_core.db import SessionLocal
from eos_field_training.application import jobs


def test_assigned_placements_start_on_their_start_date(prog):
    c = prog
    later = c.new_opening(title="Next week", starts_on="2026-11-10", ends_on="2026-11-30")
    trainee_id, me, due = c.assigned()  # starts 2026-11-02, already past
    _, _, waiting = c.assigned(later)
    with SessionLocal() as db:
        started = jobs.start_due_placements(db)
    assert started >= 1
    assert c.ok(c.get(f"/placements/{due['id']}", me))["status"] == "active"
    assert c.ok(c.get(f"/placements/{waiting['id']}", c.coordinator))["status"] == "assigned"
    assert events("field-training.placement.started", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "placement_id": due["id"],
        "trainee_id": trainee_id,
        "supervisor_id": c.supervisor_id,
        "started_on": "2026-11-03",
    }
    with SessionLocal() as db:
        jobs.start_due_placements(db)  # nothing new to start
        assert jobs.start_due_placements(db, on=date(2026, 11, 10)) >= 1
    assert c.ok(c.get(f"/placements/{waiting['id']}", c.coordinator))["status"] == "active"
    assert len(events("field-training.placement.started", c.org.id)) == 2


def test_run_daily_reports_counts(prog):
    with SessionLocal() as db:
        assert set(jobs.run_daily(db)) == {"placements_started"}
