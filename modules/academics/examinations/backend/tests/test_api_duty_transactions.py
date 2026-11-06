"""Assigning and cancelling a duty change everything or nothing: a failure at any step leaves no duty row, status change,
audit entry or event behind, and the audit entry and the event are written in the same transaction as the change."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BASE,
    all_outbox,
    audit_entries,
    make_duty,
    make_session_for_duties,
    ok,
    session_for,
    uid,
)
from eos_examinations.application import duties, service  # noqa: E402
from eos_examinations.application.access import Actor  # noqa: E402
from eos_examinations.application.errors import ExaminationsError  # noqa: E402
from eos_examinations.infrastructure import repository as repo  # noqa: E402
from eos_examinations.infrastructure.models import ExamDutyRow  # noqa: E402


class InjectedError(RuntimeError):
    pass


def actor(org) -> Actor:
    return Actor(user_id=uid(), organisation_id=org.id, permissions=set())


def fail(*args, **kwargs):
    raise InjectedError("down")


def state(org) -> tuple:
    with session_for(org.id) as db:
        duty_rows = sorted((d.id, d.status, d.cancel_reason) for d in db.scalars(repo.q(db, ExamDutyRow)))
    return duty_rows, len(audit_entries(org.id)), len(all_outbox(org.id))


@pytest.fixture
def world(client, h):
    return make_session_for_duties(client, h)


def assign_body(session_id, staff=None):
    return {"staff_id": staff or uid(), "duty_type": "invigilation", "exam_session_id": session_id}


@pytest.mark.parametrize("target", ["_audit", "_publish"])
def test_a_failing_audit_or_event_rolls_back_an_assignment(client, org, h, world, monkeypatch, target):
    cycle, session, paper = world
    make_duty(
        client, h, uid(), "evaluation", paper_id=paper["id"]
    )  # a duty exists, so a rollback has something to keep
    before = state(org)
    monkeypatch.setattr(service, target, fail)
    with session_for(org.id) as db, pytest.raises(InjectedError):
        duties.assign_exam_duty(db, actor(org), assign_body(session["id"]))
    with session_for(org.id) as db, pytest.raises(InjectedError):
        duties.assign_exam_duty(
            db, actor(org), {"staff_id": uid(), "duty_type": "moderation", "exam_paper_id": paper["id"]}
        )
    assert state(org) == before


@pytest.mark.parametrize("target", ["_audit", "_publish"])
def test_a_failing_audit_or_event_leaves_a_duty_assigned_when_cancelling(client, org, h, world, monkeypatch, target):
    cycle, session, paper = world
    duty = make_duty(client, h, uid(), "invigilation", session_id=session["id"])
    before = state(org)
    monkeypatch.setattr(service, target, fail)
    with session_for(org.id) as db, pytest.raises(InjectedError):
        duties.cancel_exam_duty(db, actor(org), duty["id"], {"reason": "unwell"})
    assert state(org) == before
    monkeypatch.undo()
    assert ok(client.get(f"{BASE}/duties?status=assigned", headers=h))["items"] == [duty]
    # and the duty can still be cancelled afterwards: nothing half-done is left in the way
    assert (
        ok(client.post(f"{BASE}/duties/{duty['id']}/cancel", json={"reason": "unwell"}, headers=h))["status"]
        == "cancelled"
    )


def test_a_failing_event_after_the_audit_entry_still_leaves_nothing(client, org, h, world, monkeypatch):
    """The audit entry is written before the event: failing on the event undoes the entry and the row too."""
    cycle, session, paper = world
    before = state(org)
    monkeypatch.setattr(service, "_publish", fail)
    with session_for(org.id) as db, pytest.raises(InjectedError):
        duties.assign_exam_duty(db, actor(org), assign_body(session["id"]))
    assert state(org) == before
    assert len(audit_entries(org.id)) == before[1]


def test_a_refused_request_changes_nothing(client, org, h, world):
    cycle, session, paper = world
    staff = uid()
    duty = make_duty(client, h, staff, "invigilation", session_id=session["id"])
    before = state(org)
    for call in (
        lambda db: duties.assign_exam_duty(db, actor(org), {}),
        lambda db: duties.assign_exam_duty(db, actor(org), assign_body(session["id"], staff)),  # a duplicate
        lambda db: duties.assign_exam_duty(db, actor(org), assign_body(uid())),  # an unknown session
        lambda db: duties.cancel_exam_duty(db, actor(org), duty["id"], {}),
        lambda db: duties.cancel_exam_duty(db, actor(org), uid(), {"reason": "x"}),
    ):
        with session_for(org.id) as db, pytest.raises(ExaminationsError):
            call(db)
    assert state(org) == before


def test_a_session_that_failed_is_clean_for_the_next_request(client, org, h, world, monkeypatch):
    cycle, session, paper = world
    staff = uid()
    with session_for(org.id) as db:
        with monkeypatch.context() as m:
            m.setattr(service, "_publish", fail)
            with pytest.raises(InjectedError):
                duties.assign_exam_duty(db, actor(org), assign_body(session["id"], staff))
        created = duties.assign_exam_duty(
            db, actor(org), assign_body(session["id"], staff)
        )  # same session, no leftovers
    assert [d["id"] for d in ok(client.get(f"{BASE}/duties", headers=h))["items"]] == [created["id"]]
    assert all_outbox(org.id).count("examinations.duty.assigned") == 1
