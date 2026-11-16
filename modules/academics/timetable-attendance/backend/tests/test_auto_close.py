"""FR-11, the system's half: the scheduler job `timetable-attendance.close-expired-sessions`. It is delivered the way the
relay delivers `scheduler.job.due` (conftest.deliver), against sessions opened through the real API; the clock is moved
past a session's marking deadline with the module's own `service.clock`."""

import tomllib
from datetime import timedelta
from pathlib import Path

import pytest
import yaml

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import BASE, VIEWER, Classroom, active_term, audit_entries, deliver, ok, outbox  # noqa: E402
from eos_core.db import SessionLocal, new_id  # noqa: E402
from eos_core.tenant import organisation_scope  # noqa: E402
from eos_timetable_attendance.application import auto_close, consumers, service  # noqa: E402
from eos_timetable_attendance.application.auto_close import JOB_FINISHED, JOB_KEY, JOBS  # noqa: E402
from eos_timetable_attendance.infrastructure import repository as repo  # noqa: E402
from eos_timetable_attendance.infrastructure.models import (  # noqa: E402
    AttendanceRecordRow,
    AttendanceSessionRow,
    ProcessedEvent,
    ScheduledClassRow,
)

MODULE = Path(__file__).resolve().parents[2]
CLOSED_EVENT = "timetable-attendance.attendance-session.closed"


def due_payload(run_id: str | None = None) -> dict:
    """scheduler.job.due (platform/scheduler/contracts/events.yaml)."""
    return {
        "run_id": run_id or new_id(),
        "schedule_id": new_id(),
        "job": JOB_KEY,
        "scope": "organisation",
        "trigger": "schedule",
        "arguments": {},
        "missed_windows": 0,
    }


def run_job(org_id: str, **envelope) -> str:
    return deliver(org_id, "scheduler.job.due", due_payload(envelope.pop("run_id", None)), **envelope)


def after(session: dict, minutes: int = 1):
    """The instant just past a session's marking deadline."""
    from datetime import datetime

    return datetime.fromisoformat(session["marking_deadline"]) + timedelta(minutes=minutes)


def move_clock(monkeypatch, instant) -> None:
    monkeypatch.setattr(service, "clock", lambda: instant)


def session_row(org_id: str, session_id: str) -> AttendanceSessionRow:
    with organisation_scope(org_id), SessionLocal() as db:
        row = db.scalars(repo.q(db, AttendanceSessionRow).where(AttendanceSessionRow.id == session_id)).one()
        db.expunge(row)
        return row


def statuses(org_id: str, session_id: str) -> dict:
    with organisation_scope(org_id), SessionLocal() as db:
        rows = db.scalars(
            repo.q(db, AttendanceRecordRow).where(AttendanceRecordRow.attendance_session_id == session_id)
        )
        return {r.student_id: r.status for r in rows}


def class_status(org_id: str, class_id: str) -> str:
    with organisation_scope(org_id), SessionLocal() as db:
        return db.scalars(repo.q(db, ScheduledClassRow).where(ScheduledClassRow.id == class_id)).one().status


def finished(org_id: str) -> list[dict]:
    return outbox(JOB_FINISHED, org_id)


@pytest.fixture
def lesson(client, org):
    """A classroom of three students with one open session, one student marked present."""
    room = Classroom(client, org, students=3)
    cls = room.new_class()
    session = room.open(cls["id"])
    room.mark(session["id"], {room.students[0]: "present"})
    return room, cls, session


# ---------------------------------------------------------------- which sessions are closed


def test_an_open_session_past_its_deadline_is_closed_and_the_unmarked_become_absent(client, lesson, monkeypatch):
    room, cls, session = lesson
    move_clock(monkeypatch, after(session))
    run_job(room.org.id)
    closed = session_row(room.org.id, session["id"])
    assert (closed.status, closed.closed_by) == ("closed", None)
    assert closed.closed_at.replace(tzinfo=None) == after(session).replace(tzinfo=None)
    first, *unmarked = room.students
    assert statuses(room.org.id, session["id"]) == {first: "present", unmarked[0]: "absent", unmarked[1]: "absent"}
    assert class_status(room.org.id, cls["id"]) == "completed"
    body = ok(client.get(f"{BASE}/attendance-sessions/{session['id']}", headers=room.faculty))
    assert (body["status"], body["closed_by"]) == ("closed", None)
    records = ok(client.get(f"{BASE}/attendance-sessions/{session['id']}/records", headers=room.faculty))["items"]
    assert sorted(r["status"] for r in records) == ["absent", "absent", "present"]


def test_a_session_whose_deadline_has_not_passed_stays_open(lesson, monkeypatch):
    room, _, session = lesson
    move_clock(monkeypatch, after(session, -1))
    run_job(room.org.id)
    assert session_row(room.org.id, session["id"]).status == "open"
    assert len(statuses(room.org.id, session["id"])) == 3
    assert None in statuses(room.org.id, session["id"]).values()
    assert outbox(CLOSED_EVENT, room.org.id) == []
    assert finished(room.org.id)[0]["detail"] == "0 attendance session(s) closed"


def test_the_deadline_itself_is_not_past(lesson, monkeypatch):
    """FR-11 closes a session when `now` is after the deadline, the domain's own rule."""
    room, _, session = lesson
    move_clock(monkeypatch, after(session, 0))
    run_job(room.org.id)
    assert session_row(room.org.id, session["id"]).status == "open"


def test_a_closed_session_is_skipped(client, lesson, monkeypatch):
    room, _, session = lesson
    room.close(session["id"])
    before = (len(outbox(CLOSED_EVENT, room.org.id)), len(audit_entries(room.org.id, session["id"])))
    closed_by = session_row(room.org.id, session["id"]).closed_by
    move_clock(monkeypatch, after(session))
    run_job(room.org.id)
    assert (len(outbox(CLOSED_EVENT, room.org.id)), len(audit_entries(room.org.id, session["id"]))) == before
    assert session_row(room.org.id, session["id"]).closed_by == closed_by == room.instructor_id


def test_a_cancelled_session_is_skipped_and_its_students_stay_unmarked(client, lesson, monkeypatch):
    room, cls, session = lesson
    ok(client.post(f"{BASE}/scheduled-classes/{cls['id']}/cancel", json={"reason": "holiday"}, headers=room.admin))
    assert session_row(room.org.id, session["id"]).status == "cancelled"
    move_clock(monkeypatch, after(session))
    run_job(room.org.id)
    assert session_row(room.org.id, session["id"]).status == "cancelled"
    assert class_status(room.org.id, cls["id"]) == "cancelled"
    assert list(statuses(room.org.id, session["id"]).values()).count(None) == 2
    assert outbox(CLOSED_EVENT, room.org.id) == []


def test_another_organisations_sessions_are_untouched(client, org, other_org, monkeypatch):
    mine, theirs = Classroom(client, org, students=2), Classroom(client, other_org, students=2)
    sessions = {}
    for room in (mine, theirs):
        cls = room.new_class()
        sessions[room] = room.open(cls["id"])
    move_clock(monkeypatch, after(sessions[mine]) + timedelta(days=1))
    run_job(org.id)
    assert session_row(org.id, sessions[mine]["id"]).status == "closed"
    assert session_row(other_org.id, sessions[theirs]["id"]).status == "open"
    assert None in statuses(other_org.id, sessions[theirs]["id"]).values()
    assert outbox(CLOSED_EVENT, other_org.id) == [] and finished(other_org.id) == []
    assert audit_entries(other_org.id, sessions[theirs]["id"])[-1].action != "attendance-session.closed"
    run_job(other_org.id)
    assert session_row(other_org.id, sessions[theirs]["id"]).status == "closed"


def test_every_due_session_of_the_organisation_is_closed_in_one_run(client, org, monkeypatch):
    room = Classroom(client, org, students=2)
    opened = [room.open(room.new_class(f"2026-11-03T0{h}:00:00+00:00")["id"], headers=room.admin) for h in (6, 7, 8)]
    late = room.open(room.new_class("2026-11-03T20:00:00+00:00")["id"], headers=room.admin)
    move_clock(monkeypatch, after(opened[-1]))
    run_job(org.id)
    assert [session_row(org.id, s["id"]).status for s in opened] == ["closed"] * 3
    assert session_row(org.id, late["id"]).status == "open"
    assert finished(org.id)[0]["detail"] == "3 attendance session(s) closed"


# ---------------------------------------------------------------- what closing records


def test_the_closing_event_and_audit_entry_are_those_of_a_manual_close_without_an_actor(client, org, monkeypatch):
    room = Classroom(client, org, students=3)
    manual_class = room.new_class("2026-11-03T08:00:00+00:00")
    manual = room.open(manual_class["id"])
    room.mark(manual["id"], {room.students[0]: "present"})
    room.close(manual["id"])
    cls = room.new_class()
    session = room.open(cls["id"])
    room.mark(session["id"], {room.students[0]: "present", room.students[1]: "late"})
    move_clock(monkeypatch, after(session))
    run_job(org.id)

    by_session = {p["attendance_session_id"]: p for p in outbox(CLOSED_EVENT, org.id)}
    manual_event, auto_event = by_session[manual["id"]], by_session[session["id"]]
    assert set(auto_event) == set(manual_event)  # the contract's payload, field for field
    assert auto_event == {
        "organisation_id": org.id,
        "attendance_session_id": session["id"],
        "scheduled_class_id": cls["id"],
        "course_offering_id": room.ids["offering"],
        "section_id": room.ids["section"],
        "class_date": "2026-11-03",
        "closed_by": None,
        "closed_at": after(session).isoformat(),
        "present": 1,
        "absent": 1,
        "late": 1,
        "excused": 0,
    }
    assert manual_event["closed_by"] == room.instructor_id

    [entry] = [e for e in audit_entries(org.id, session["id"]) if e.action == "attendance-session.closed"]
    [manual_entry] = [e for e in audit_entries(org.id, manual["id"]) if e.action == "attendance-session.closed"]
    assert entry.actor is None and manual_entry.actor == room.instructor_id
    assert (entry.entity_type, entry.before) == (manual_entry.entity_type, {"status": "open"})
    assert entry.after == {
        "status": "closed",
        "marked_absent_at_close": 1,
        "eligible": 3,
        "unmarked": 0,
        **{"present": 1, "absent": 1, "late": 1, "excused": 0},
    }
    assert set(entry.after) == set(manual_entry.after)


def test_the_event_and_the_audit_entry_name_the_session_once_each(lesson, monkeypatch):
    room, _, session = lesson
    move_clock(monkeypatch, after(session))
    run_job(room.org.id)
    assert [p["attendance_session_id"] for p in outbox(CLOSED_EVENT, room.org.id)] == [session["id"]]
    closing = [e for e in audit_entries(room.org.id, session["id"]) if e.action == "attendance-session.closed"]
    assert len(closing) == 1


def test_the_run_is_reported_so_the_scheduler_can_close_it(lesson, monkeypatch):
    room, _, session = lesson
    move_clock(monkeypatch, after(session))
    run_id = new_id()
    run_job(room.org.id, run_id=run_id)
    assert finished(room.org.id) == [
        {"run_id": run_id, "outcome": "succeeded", "detail": "1 attendance session(s) closed"}
    ]


def test_the_reports_count_the_absences_the_job_created(client, org, monkeypatch):
    room = Classroom(client, org, students=2)
    active_term(org.id, room.ids["period"])
    cls = room.new_class()
    session = room.open(cls["id"])
    present, silent = room.students
    room.mark(session["id"], {present: "present"})
    _, viewer = org.user(VIEWER)
    url = f"{BASE}/reports/students/{silent}/attendance-summary"
    assert ok(client.get(url, headers=viewer))["items"] == []  # nothing counted while the session is open
    move_clock(monkeypatch, after(session))
    run_job(org.id)
    [row] = ok(client.get(url, headers=viewer))["items"]
    assert (row["classes_held"], row["attended"], row["percentage"]) == (1, 0, 0.0)
    [row] = ok(client.get(f"{BASE}/reports/students/{present}/attendance-summary", headers=viewer))["items"]
    assert (row["classes_held"], row["attended"], row["percentage"]) == (1, 1, 100.0)
    history = ok(client.get(f"{BASE}/reports/students/{silent}/attendance-history", headers=viewer))["items"]
    assert [i["status"] for i in history] == ["absent"]


# ---------------------------------------------------------------- at-least-once delivery


def test_the_same_delivery_twice_closes_and_reports_once(lesson, monkeypatch):
    room, _, session = lesson
    move_clock(monkeypatch, after(session))
    event_id = new_id()
    assert run_job(room.org.id, event_id=event_id, run_id="r1") == "applied"
    snapshot = (
        len(outbox(CLOSED_EVENT, room.org.id)),
        len(audit_entries(room.org.id)),
        len(finished(room.org.id)),
        statuses(room.org.id, session["id"]),
    )
    assert run_job(room.org.id, event_id=event_id, run_id="r1") == "duplicate"
    assert snapshot == (
        len(outbox(CLOSED_EVENT, room.org.id)),
        len(audit_entries(room.org.id)),
        len(finished(room.org.id)),
        statuses(room.org.id, session["id"]),
    )


def test_a_later_run_finds_nothing_left_and_changes_nothing(lesson, monkeypatch):
    room, _, session = lesson
    move_clock(monkeypatch, after(session))
    run_job(room.org.id)
    first_closed = session_row(room.org.id, session["id"]).closed_at
    absent = statuses(room.org.id, session["id"])
    move_clock(monkeypatch, after(session, 90))
    run_job(room.org.id)
    assert len(outbox(CLOSED_EVENT, room.org.id)) == 1
    assert len([e for e in audit_entries(room.org.id) if e.action == "attendance-session.closed"]) == 1
    assert session_row(room.org.id, session["id"]).closed_at == first_closed
    assert statuses(room.org.id, session["id"]) == absent
    assert [f["detail"] for f in finished(room.org.id)] == [
        "1 attendance session(s) closed",
        "0 attendance session(s) closed",
    ]


def test_a_session_closed_by_hand_after_the_job_selected_it_is_left_alone(client, lesson, monkeypatch):
    """The job re-checks a session under its row lock: a manual close that lands first wins and is not repeated."""
    room, _, session = lesson
    move_clock(monkeypatch, after(session))
    real = repo.expired_open_sessions

    def selected_then_closed_by_hand(db, now):
        rows = real(db, now)
        for row in rows:  # a manual close lands between the job's read and its lock on the row
            row.status, row.closed_by, row.closed_at = "closed", room.instructor_id, now
        db.flush()
        return rows

    monkeypatch.setattr(repo, "expired_open_sessions", selected_then_closed_by_hand)
    run_job(room.org.id)
    assert session_row(room.org.id, session["id"]).closed_by == room.instructor_id
    assert outbox(CLOSED_EVENT, room.org.id) == []
    assert finished(room.org.id)[0]["detail"] == "0 attendance session(s) closed"


# ---------------------------------------------------------------- failure leaves nothing behind


def test_a_session_that_cannot_be_closed_leaves_nothing_and_the_others_still_close(client, org, monkeypatch):
    room = Classroom(client, org, students=2)
    broken = room.open(room.new_class("2026-11-03T06:00:00+00:00")["id"], headers=room.admin)
    healthy = room.open(room.new_class("2026-11-03T07:00:00+00:00")["id"], headers=room.admin)
    real = service._audit

    def audit(db, actor, action, entity_type, row, **kwargs):
        if row.id == broken["id"]:
            raise RuntimeError("audit store down")
        return real(db, actor, action, entity_type, row, **kwargs)

    monkeypatch.setattr(service, "_audit", audit)
    move_clock(monkeypatch, after(healthy))
    run_job(org.id)

    stuck = session_row(org.id, broken["id"])
    assert (stuck.status, stuck.closed_at, stuck.closed_by) == ("open", None, None)
    assert None in statuses(org.id, broken["id"]).values()  # nobody was marked absent
    assert class_status(org.id, broken["scheduled_class_id"]) == "scheduled"
    assert session_row(org.id, healthy["id"]).status == "closed"
    assert [p["attendance_session_id"] for p in outbox(CLOSED_EVENT, org.id)] == [healthy["id"]]
    assert audit_entries(org.id, broken["id"])[-1].action != "attendance-session.closed"
    [report] = finished(org.id)
    assert report["outcome"] == "failed" and "1 could not be closed" in report["detail"]

    monkeypatch.setattr(service, "_audit", real)  # the next run closes it
    run_job(org.id)
    assert session_row(org.id, broken["id"]).status == "closed"
    assert finished(org.id)[-1]["outcome"] == "succeeded"


def test_when_the_whole_run_fails_nothing_of_it_is_kept_and_the_redelivery_applies_it(lesson, monkeypatch):
    room, _, session = lesson
    move_clock(monkeypatch, after(session))
    real = auto_close.events.publish

    def publish(db, name, *args, **kwargs):
        if name == JOB_FINISHED:
            raise RuntimeError("event store down")
        return real(db, name, *args, **kwargs)

    monkeypatch.setattr(auto_close.events, "publish", publish)
    event_id = new_id()
    with pytest.raises(RuntimeError, match="event store down"):
        run_job(room.org.id, event_id=event_id)
    assert session_row(room.org.id, session["id"]).status == "open"
    assert outbox(CLOSED_EVENT, room.org.id) == []
    assert None in statuses(room.org.id, session["id"]).values()
    with organisation_scope(room.org.id), SessionLocal() as db:
        assert repo.ref_row(db, ProcessedEvent, ProcessedEvent.event_id, event_id, room.org.id) is None

    monkeypatch.setattr(auto_close.events, "publish", real)
    assert run_job(room.org.id, event_id=event_id) == "applied"
    assert session_row(room.org.id, session["id"]).status == "closed"


# ---------------------------------------------------------------- the handler and the declaration


def test_another_modules_job_is_ignored_and_not_recorded(lesson, monkeypatch):
    room, _, session = lesson
    move_clock(monkeypatch, after(session))
    payload = {**due_payload(), "job": "billing.expire-trials"}
    assert deliver(room.org.id, "scheduler.job.due", payload) == "ignored"
    assert session_row(room.org.id, session["id"]).status == "open"
    assert finished(room.org.id) == []
    with organisation_scope(room.org.id), SessionLocal() as db:
        assert repo.ref_row(db, ProcessedEvent, ProcessedEvent.name, "scheduler.job.due", room.org.id) is None


def test_the_job_runs_only_in_the_events_own_organisation(lesson, other_org, monkeypatch):
    room, _, session = lesson
    move_clock(monkeypatch, after(session))
    event = consumers.CONSUMERS["scheduler.job.due"]
    from conftest import FakeEvent

    with organisation_scope(other_org.id), SessionLocal() as db:
        with pytest.raises(RuntimeError, match="not scoped to the event's organisation"):
            event(db, FakeEvent("scheduler.job.due", room.org.id, due_payload()))
    with organisation_scope(room.org.id), SessionLocal() as db:
        assert event(db, FakeEvent("scheduler.job.due", None, due_payload())) == "ignored"
    assert session_row(room.org.id, session["id"]).status == "open"


def test_the_declaration_follows_the_scheduler_contract():
    assert set(JOBS) == {"timetable-attendance.close-expired-sessions"}
    spec = JOBS[JOB_KEY]
    assert (spec["scope"], spec["idempotent"]) == ("organisation", True)
    assert spec["description"]
    project = tomllib.loads((MODULE / "backend" / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    points = project["entry-points"]
    assert points["eos.scheduler_jobs"] == {
        "timetable-attendance": "eos_timetable_attendance.application.auto_close:JOBS"
    }
    (entry_point,) = points["eos.scheduler_jobs"]
    assert JOB_KEY.startswith(f"{entry_point}.")  # the scheduler: a job key starts with its entry point's name
    assert "default_cron" not in spec  # a default is seeded for platform jobs only; none is invented here


def test_the_declaration_is_accepted_by_the_scheduler_itself():
    jobs_module = pytest.importorskip("eos_scheduler.application.jobs", reason="eos_scheduler is not on PYTHONPATH")
    job = jobs_module.Job.declare("timetable-attendance", JOB_KEY, JOBS[JOB_KEY])
    assert (job.scope, job.idempotent, job.default_cron) == ("organisation", True, None)


def test_the_manifest_and_the_contract_declare_the_job():
    manifest = yaml.safe_load((MODULE / "module.yaml").read_text(encoding="utf-8"))
    assert "scheduler.job.due" in manifest["consumes_events"]
    assert "scheduler" in manifest["depends_on"]["platform"]
    assert set(consumers.CONSUMERS) == set(manifest["consumes_events"])
    events = {e["name"]: e for e in yaml.safe_load((MODULE / "contracts" / "events.yaml").read_text("utf-8"))["events"]}
    assert set(events[JOB_FINISHED]["payload"]) == {"run_id", "outcome", "detail"}
    assert events[CLOSED_EVENT]["payload"]["closed_by"] == "uuid?"


def test_the_repository_query_is_scoped_to_the_organisation(lesson, other_org, monkeypatch):
    room, _, session = lesson
    instant = after(session)
    with organisation_scope(room.org.id), SessionLocal() as db:
        assert [s.id for s in repo.expired_open_sessions(db, instant)] == [session["id"]]
    with organisation_scope(other_org.id), SessionLocal() as db:
        assert repo.expired_open_sessions(db, instant) == []
    with SessionLocal() as db:  # no organisation on the session: nothing
        assert repo.expired_open_sessions(db, instant) == []
