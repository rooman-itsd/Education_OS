"""Papers and sessions change all or nothing: a failure at any step leaves no paper, session, link, status change, audit
entry or event behind."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BASE,
    all_outbox,
    audit_entries,
    make_cycle,
    make_grading,
    make_papers,
    make_session,
    ok,
    session_body,
    session_for,
    uid,
)
from eos_examinations.application import schedule, service  # noqa: E402
from eos_examinations.application.access import Actor  # noqa: E402
from eos_examinations.application.errors import ExaminationsError  # noqa: E402
from eos_examinations.infrastructure import repository as repo  # noqa: E402
from eos_examinations.infrastructure.models import (  # noqa: E402
    ExamPaperRow,
    ExamSessionPaperRow,
    ExamSessionRow,
)
from sqlalchemy.exc import IntegrityError  # noqa: E402


class InjectedError(RuntimeError):
    pass


def actor(org) -> Actor:
    return Actor(user_id=uid(), organisation_id=org.id, permissions=set())


def fail(*args, **kwargs):
    raise InjectedError("down")


def state(org) -> tuple:
    """Everything a paper or session change can touch, for before/after comparison."""
    with session_for(org.id) as db:
        papers = sorted((p.id, p.status, p.duration_minutes, p.title) for p in db.scalars(repo.q(db, ExamPaperRow)))
        sessions = sorted(
            (s.id, s.status, s.cancel_reason, s.venue_label, s.starts_at, s.invigilators_required)
            for s in db.scalars(repo.q(db, ExamSessionRow))
        )
        links = sorted(
            (link.exam_session_id, link.exam_paper_id) for link in db.scalars(repo.q(db, ExamSessionPaperRow))
        )
    return papers, sessions, links, len(audit_entries(org.id)), len(all_outbox(org.id))


@pytest.fixture
def cycle(client, h) -> dict:
    scheme = make_grading(client, h)
    ok(client.post(f"{BASE}/grading-schemes/{scheme['id']}/set-default", headers=h))
    return make_cycle(client, h)


def test_a_failing_audit_rolls_back_paper_creation_and_update(client, org, h, cycle, monkeypatch):
    offering = uid()
    papers = make_papers(client, h, cycle["id"], offering, ["INT"])
    before = state(org)
    monkeypatch.setattr(service, "_audit", fail)
    with session_for(org.id) as db, pytest.raises(InjectedError):
        schedule.create_exam_papers(
            db,
            actor(org),
            {"exam_cycle_id": cycle["id"], "course_offering_id": offering, "component_codes": ["END"]},
        )
    with session_for(org.id) as db, pytest.raises(InjectedError):
        schedule.update_exam_paper(db, actor(org), papers[0]["id"], {"title": "Paper I", "duration_minutes": 10})
    assert state(org) == before


def test_a_failing_audit_or_event_rolls_back_scheduling_including_the_paper_status(client, org, h, cycle, monkeypatch):
    papers = make_papers(client, h, cycle["id"])
    ids = [p["id"] for p in papers]
    before = state(org)
    for target in ("_audit", "_publish"):
        with monkeypatch.context() as m:
            m.setattr(service, target, fail)
            with session_for(org.id) as db, pytest.raises(InjectedError):
                schedule.schedule_exam_session(db, actor(org), session_body(cycle["id"], ids))
        assert state(org) == before
    assert {p["status"] for p in ok(client.get(f"{BASE}/papers?exam_cycle_id={cycle['id']}", headers=h))["items"]} == {
        "draft"
    }


def test_a_failure_after_the_audit_entries_still_leaves_nothing(client, org, h, cycle, monkeypatch):
    """The paper entries are written before the session's: failing on the session's own entry undoes them too."""
    papers = make_papers(client, h, cycle["id"])
    before = state(org)
    real = service._audit

    def fail_on_session(db, a, action, entity_type, row, **kw):
        if entity_type == "exam_session":
            raise InjectedError("down")
        return real(db, a, action, entity_type, row, **kw)

    monkeypatch.setattr(service, "_audit", fail_on_session)
    with session_for(org.id) as db, pytest.raises(InjectedError):
        schedule.schedule_exam_session(db, actor(org), session_body(cycle["id"], [p["id"] for p in papers]))
    assert state(org) == before


def test_a_failing_audit_or_event_leaves_a_session_as_it_was_on_reschedule_and_cancel(
    client, org, h, cycle, monkeypatch
):
    papers = make_papers(client, h, cycle["id"])
    session = make_session(client, h, cycle["id"], [p["id"] for p in papers])
    before = state(org)
    patch = {
        "venue_label": "Elsewhere",
        "starts_at": "2026-11-26T09:00:00+00:00",
        "ends_at": "2026-11-26T11:00:00+00:00",
    }
    for target in ("_audit", "_publish"):
        with monkeypatch.context() as m:
            m.setattr(service, target, fail)
            with session_for(org.id) as db, pytest.raises(InjectedError):
                schedule.reschedule_exam_session(db, actor(org), session["id"], patch)
            with session_for(org.id) as db, pytest.raises(InjectedError):
                schedule.cancel_exam_session(db, actor(org), session["id"], {"reason": "flood"})
        assert state(org) == before
    assert ok(client.get(f"{BASE}/sessions/{session['id']}", headers=h)) == session  # papers still linked and scheduled
    assert {p["status"] for p in ok(client.get(f"{BASE}/papers", headers=h))["items"]} == {"scheduled"}


def test_a_refused_request_changes_nothing(client, org, h, cycle):
    papers = make_papers(client, h, cycle["id"])
    session = make_session(client, h, cycle["id"], [papers[0]["id"]])
    before = state(org)
    for call in (
        lambda db: schedule.schedule_exam_session(db, actor(org), session_body(cycle["id"], [papers[0]["id"]])),
        lambda db: schedule.schedule_exam_session(db, actor(org), session_body(cycle["id"], [papers[1]["id"], uid()])),
        lambda db: schedule.reschedule_exam_session(
            db, actor(org), session["id"], {"ends_at": "2000-01-01T00:00:00+00:00"}
        ),
        lambda db: schedule.cancel_exam_session(db, actor(org), session["id"], {}),
        lambda db: schedule.create_exam_papers(db, actor(org), {}),
        lambda db: schedule.update_exam_paper(db, actor(org), papers[1]["id"], {"title": " "}),
    ):
        with session_for(org.id) as db, pytest.raises(ExaminationsError):
            call(db)
    assert state(org) == before


def test_a_session_that_failed_is_clean_for_the_next_request(client, org, h, cycle, monkeypatch):
    papers = make_papers(client, h, cycle["id"])
    ids = [p["id"] for p in papers]
    with session_for(org.id) as db:
        with monkeypatch.context() as m:
            m.setattr(service, "_publish", fail)
            with pytest.raises(InjectedError):
                schedule.schedule_exam_session(db, actor(org), session_body(cycle["id"], ids))
        created = schedule.schedule_exam_session(
            db, actor(org), session_body(cycle["id"], ids)
        )  # same session, no leftovers
    assert [s["id"] for s in ok(client.get(f"{BASE}/sessions", headers=h))["items"]] == [created["id"]]


def _violation(table_and_columns: str) -> IntegrityError:
    class OrigError(Exception):
        pass

    return IntegrityError("insert", {}, OrigError(f"UNIQUE constraint failed: {table_and_columns}"))


@pytest.mark.parametrize(
    ("columns", "code"),
    [
        (
            "examinations_session_paper.organisation_id, examinations_session_paper.exam_paper_id",
            "paper_already_scheduled",
        ),
        (
            "examinations_exam_paper.organisation_id, examinations_exam_paper.exam_cycle_id, "
            "examinations_exam_paper.assessment_component_id",
            "paper_exists",
        ),
    ],
)
def test_a_concurrent_uniqueness_violation_is_a_409_and_rolls_back(client, org, h, cycle, monkeypatch, columns, code):
    """Two requests racing for the same paper or component: the loser gets the contract's 409, not a server error."""
    offering = uid()
    papers = make_papers(client, h, cycle["id"], offering, ["INT"])
    before = state(org)
    monkeypatch.setattr(service, "_audit", lambda *a, **k: (_ for _ in ()).throw(_violation(columns)))
    with session_for(org.id) as db, pytest.raises(ExaminationsError) as caught:
        schedule.schedule_exam_session(db, actor(org), session_body(cycle["id"], [papers[0]["id"]]))
    assert (caught.value.status, caught.value.code) == (409, code)
    assert state(org) == before


def test_a_failing_audit_rolls_back_a_cancellation_during_the_examination(client, org, h, cycle, monkeypatch):
    from conftest import set_row
    from eos_examinations.infrastructure.models import ExamCycleRow

    papers = make_papers(client, h, cycle["id"])
    session = make_session(client, h, cycle["id"], [p["id"] for p in papers])
    set_row(org.id, ExamCycleRow, cycle["id"], status="in_progress")
    before = state(org)
    for target in ("_audit", "_publish"):
        with monkeypatch.context() as m:
            m.setattr(service, target, fail)
            with session_for(org.id) as db, pytest.raises(InjectedError):
                schedule.cancel_exam_session(db, actor(org), session["id"], {"reason": "flood"})
        assert state(org) == before
    assert ok(client.get(f"{BASE}/sessions/{session['id']}", headers=h)) == session
