"""The class and attendance state changes are all or nothing: when the audit or the event fails, no class, session,
record, change, audit entry or event of that call is left behind."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import BASE, Classroom, audit_entries, ok, outbox  # noqa: E402
from eos_core.db import SessionLocal  # noqa: E402
from eos_timetable_attendance.application import service  # noqa: E402
from eos_timetable_attendance.infrastructure import repository as repo  # noqa: E402
from eos_timetable_attendance.infrastructure.models import (  # noqa: E402
    AttendanceRecordChangeRow,
    AttendanceRecordRow,
    AttendanceSessionRow,
    ScheduledClassRow,
)

EVENTS = (
    "scheduled-class.created",
    "scheduled-class.updated",
    "scheduled-class.cancelled",
    "attendance-session.opened",
    "attendance-record.marked",
    "attendance-session.closed",
    "attendance-record.updated",
)


class InjectedError(RuntimeError):
    pass


def snapshot(org_id: str) -> tuple:
    """Every row of the organisation, as plain values, with its audit entries and events."""
    with SessionLocal() as db:
        db.info["organisation_id"] = org_id
        classes = sorted((r.id, r.status, r.location_label) for r in db.scalars(repo.q(db, ScheduledClassRow)))
        sessions = sorted((r.id, r.status) for r in db.scalars(repo.q(db, AttendanceSessionRow)))
        records = sorted((r.id, r.status) for r in db.scalars(repo.q(db, AttendanceRecordRow)))
        changes = len(list(db.scalars(repo.q(db, AttendanceRecordChangeRow))))
    events = tuple(len(outbox(f"timetable-attendance.{name}", org_id)) for name in EVENTS)
    return classes, sessions, records, changes, len(audit_entries(org_id)), events


def fail(*args, **kwargs):
    raise InjectedError("store down")


@pytest.fixture
def setup(client, org):
    room = Classroom(client, org, students=2)
    planned = room.new_class("2026-11-03T09:05:00+00:00")
    marking = room.new_class("2026-11-03T08:30:00+00:00")
    open_session = room.open(marking["id"])
    closing = room.new_class("2026-11-03T08:40:00+00:00")
    to_close = room.open(closing["id"])
    held, closed = room.held({room.students[0]: "absent"}, "2026-11-03T08:00:00+00:00")
    record = next(
        r
        for r in ok(client.get(f"{BASE}/attendance-sessions/{closed['id']}/records", headers=room.faculty))["items"]
        if r["student_id"] == room.students[0]
    )
    return room, planned, open_session, to_close, record


@pytest.mark.parametrize("broken", ["_audit", "_publish"])
def test_every_state_change_rolls_back_whole(client, setup, monkeypatch, broken):
    room, planned, open_session, to_close, record = setup
    calls = [
        lambda: client.post(
            f"{BASE}/scheduled-classes",
            json={
                "course_offering_id": room.ids["offering"],
                "section_id": room.ids["section"],
                "instructor_assignment_id": room.ids["assignment"],
                "starts_at": "2026-11-04T09:00:00+00:00",
                "ends_at": "2026-11-04T10:00:00+00:00",
            },
            headers=room.admin,
        ),
        lambda: client.patch(
            f"{BASE}/scheduled-classes/{planned['id']}", json={"location_label": "Lab"}, headers=room.admin
        ),
        lambda: client.post(
            f"{BASE}/scheduled-classes/{open_session['scheduled_class_id']}/cancel", headers=room.admin
        ),
        lambda: client.post(f"{BASE}/scheduled-classes/{planned['id']}/attendance-session", headers=room.faculty),
        lambda: client.put(
            f"{BASE}/attendance-sessions/{open_session['id']}/records",
            json={"records": [{"student_id": room.students[0], "status": "present"}]},
            headers=room.faculty,
        ),
        lambda: client.post(f"{BASE}/attendance-sessions/{to_close['id']}/close", headers=room.faculty),
        lambda: client.patch(
            f"{BASE}/attendance-records/{record['id']}", json={"status": "present", "reason": "x"}, headers=room.faculty
        ),
    ]
    monkeypatch.setattr(service, broken, fail)
    for call in calls:
        before = snapshot(room.org.id)
        with pytest.raises(InjectedError):
            call()
        assert snapshot(room.org.id) == before
