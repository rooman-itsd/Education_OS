"""A state change is all or nothing: a failure at any step leaves no timetable, slot, audit entry or event behind, and the
audit entry and the event are written in the same transaction as the change."""

import uuid

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import ADMIN, BASE, audit_entries, make_timetable, ok, outbox, slot  # noqa: E402
from eos_core.db import SessionLocal  # noqa: E402
from eos_timetable_attendance.application import service  # noqa: E402
from eos_timetable_attendance.application.access import Actor  # noqa: E402
from eos_timetable_attendance.infrastructure import repository as repo  # noqa: E402
from eos_timetable_attendance.infrastructure.models import TimetableRow, TimetableSlotRow  # noqa: E402
from sqlalchemy import func, select  # noqa: E402


class InjectedError(RuntimeError):
    pass


def actor(org) -> Actor:
    return Actor(user_id=str(uuid.uuid4()), organisation_id=org.id, permissions=set())


def session_for(org):
    db = SessionLocal()
    db.info["organisation_id"] = org.id
    return db


def counts(org) -> tuple[int, int, int, int]:
    with session_for(org) as db:
        timetables = len(list(db.scalars(repo.q(db, TimetableRow))))
        slots = len(list(db.scalars(repo.q(db, TimetableSlotRow))))
    return timetables, slots, len(audit_entries(org.id)), len(outbox("timetable-attendance.timetable.created", org.id))


def test_a_failing_audit_rolls_back_the_timetable_its_slots_and_the_event(org, monkeypatch):
    ids = org.academic()

    def fail(*args, **kwargs):
        raise InjectedError("audit store down")

    monkeypatch.setattr(service, "_audit", fail)
    before = counts(org)
    body = {"academic_period_id": ids["period"], "name": "x", "slots": [slot(ids)]}
    with session_for(org) as db, pytest.raises(InjectedError):
        service.create_timetable(db, actor(org), body)
    assert counts(org) == before


def test_a_failing_event_rolls_back_the_audit_entry_and_the_rows(org, monkeypatch):
    ids = org.academic()

    def fail(*args, **kwargs):
        raise InjectedError("outbox down")

    monkeypatch.setattr(service, "_publish", fail)
    before = counts(org)
    with session_for(org) as db, pytest.raises(InjectedError):
        service.create_timetable(
            db, actor(org), {"academic_period_id": ids["period"], "name": "x", "slots": [slot(ids)]}
        )
    assert counts(org) == before


def test_a_failing_slot_replacement_keeps_the_old_slots(client, org, monkeypatch):
    _, h = org.user(ADMIN)
    ids = org.academic()
    t = make_timetable(client, h, ids["period"], slots=[slot(ids), slot(ids, day="friday")])
    audits = len(audit_entries(org.id, t["id"]))

    def fail(*args, **kwargs):
        raise InjectedError("audit store down")

    monkeypatch.setattr(service, "_audit", fail)
    with session_for(org) as db, pytest.raises(InjectedError):
        service.replace_slots(db, actor(org), t["id"], {"slots": [slot(ids, day="tuesday")]})
    monkeypatch.undo()
    stored = ok(client.get(f"{BASE}/timetables/{t['id']}", headers=h))
    assert [s["day_of_week"] for s in stored["slots"]] == ["monday", "friday"]
    assert len(audit_entries(org.id, t["id"])) == audits


def test_a_failing_update_keeps_the_old_details(client, org, monkeypatch):
    _, h = org.user(ADMIN)
    t = make_timetable(client, h, name="Original")

    def fail(*args, **kwargs):
        raise InjectedError("outbox down")

    monkeypatch.setattr(service, "_publish", fail)
    with session_for(org) as db, pytest.raises(InjectedError):
        service.update_timetable(db, actor(org), t["id"], {"name": "Changed"})
    monkeypatch.undo()
    assert ok(client.get(f"{BASE}/timetables/{t['id']}", headers=h))["name"] == "Original"


def test_the_audit_entry_and_the_event_are_committed_with_the_change_not_before(client, org, monkeypatch):
    """Nothing is committed until the last step: when the commit itself fails, the earlier flushed steps vanish too."""
    ids = org.academic()
    before = counts(org)
    with session_for(org) as db:
        monkeypatch.setattr(db, "commit", lambda: (_ for _ in ()).throw(InjectedError("commit failed")))
        with pytest.raises(InjectedError):
            service.create_timetable(db, actor(org), {"academic_period_id": ids["period"], "name": "x"})
    assert counts(org) == before


def test_one_audit_client_token_records_once_even_when_replayed(org):
    ids = org.academic()
    with session_for(org) as db:
        row = TimetableRow(
            organisation_id=org.id, academic_period_id=ids["period"], name="t", version=0, status="draft"
        )
        db.add(row)
        first = service._audit(db, actor(org), "timetable.created", "timetable", row, client_token="replayed")
        again = service._audit(db, actor(org), "timetable.created", "timetable", row, client_token="replayed")
        db.commit()
        assert again.id == first.id
        assert (
            db.scalar(
                select(func.count()).select_from(first.__class__).where(first.__class__.client_token == "replayed")
            )
            == 1
        )


def test_every_mutating_use_case_is_transactional():
    for name in ("create_timetable", "update_timetable", "replace_slots", "publish_timetable", "unpublish_timetable"):
        assert getattr(service, name).__wrapped__, name  # functools.wraps(transactional)


# ---------------------------------------------------------------- publishing (classes are seeded rows: see
# test_api_publication.py for why)


def published(client, org, h):
    """A published timetable of a known term with two future classes."""
    from conftest import deliver, term_created
    from eos_timetable_attendance.application.consumers import TERM_CREATED
    from test_api_publication import seed_class, when

    ids = org.academic()
    deliver(org.id, TERM_CREATED, term_created(ids["period"]))
    t = make_timetable(client, h, ids["period"], slots=[slot(ids)])
    ok(client.post(f"{BASE}/timetables/{t['id']}/publish", headers=h))
    classes = [seed_class(org, t["id"], ids, when(days=7)), seed_class(org, t["id"], ids, when(days=14))]
    return t, ids, classes


def state(org, timetable_id: str) -> tuple:
    from test_api_publication import class_states, stored

    return (
        stored(org, timetable_id),
        class_states(org),
        len(audit_entries(org.id)),
        len(outbox("timetable-attendance.timetable.published", org.id)),
        len(outbox("timetable-attendance.timetable.unpublished", org.id)),
        len(outbox("timetable-attendance.scheduled-class.cancelled", org.id)),
    )


def draft_ready(client, org, h):
    from conftest import deliver, term_created
    from eos_timetable_attendance.application.consumers import TERM_CREATED

    ids = org.academic()
    deliver(org.id, TERM_CREATED, term_created(ids["period"]))
    return make_timetable(client, h, ids["period"], slots=[slot(ids)])


@pytest.mark.parametrize("failing", ["_audit", "_publish"])
def test_a_failing_publication_leaves_the_timetable_a_draft_with_no_audit_or_event(client, org, monkeypatch, failing):
    _, h = org.user(ADMIN)
    t = draft_ready(client, org, h)
    before = state(org, t["id"])

    def fail(*args, **kwargs):
        raise InjectedError(f"{failing} down")

    monkeypatch.setattr(service, failing, fail)
    with session_for(org) as db, pytest.raises(InjectedError):
        service.publish_timetable(db, actor(org), t["id"])
    monkeypatch.undo()
    assert state(org, t["id"]) == before
    assert before[0] == ("draft", 0)


def test_a_failing_commit_leaves_the_publication_unrecorded(client, org, monkeypatch):
    _, h = org.user(ADMIN)
    t = draft_ready(client, org, h)
    before = state(org, t["id"])
    with session_for(org) as db:
        monkeypatch.setattr(db, "commit", lambda: (_ for _ in ()).throw(InjectedError("commit failed")))
        with pytest.raises(InjectedError):
            service.publish_timetable(db, actor(org), t["id"])
    assert state(org, t["id"]) == before


def test_a_failure_on_the_second_class_undoes_the_first_cancellation_and_the_unpublication(client, org, monkeypatch):
    """The timetable's status, every cancelled class, their audit entries and their events stand or fall together."""
    _, h = org.user(ADMIN)
    t, _, _ = published(client, org, h)
    before = state(org, t["id"])
    real = service._audit
    calls = {"classes": 0}

    def fail_on_the_second_class(db, actor_, action, entity_type, *args, **kwargs):
        if action == "scheduled-class.cancelled":
            calls["classes"] += 1
            if calls["classes"] == 2:
                raise InjectedError("audit store down")
        return real(db, actor_, action, entity_type, *args, **kwargs)

    monkeypatch.setattr(service, "_audit", fail_on_the_second_class)
    with session_for(org) as db, pytest.raises(InjectedError):
        service.unpublish_timetable(db, actor(org), t["id"], {"reason": "re-plan"})
    monkeypatch.undo()
    assert calls["classes"] == 2
    after = state(org, t["id"])
    assert after == before
    assert before[0] == ("published", 1) and all(s == ("scheduled", None) for s in before[1].values())


@pytest.mark.parametrize("failing", ["_audit", "_publish"])
def test_a_failing_unpublication_keeps_it_published_with_its_classes(client, org, monkeypatch, failing):
    _, h = org.user(ADMIN)
    t, _, _ = published(client, org, h)
    before = state(org, t["id"])

    def fail(*args, **kwargs):
        raise InjectedError(f"{failing} down")

    monkeypatch.setattr(service, failing, fail)
    with session_for(org) as db, pytest.raises(InjectedError):
        service.unpublish_timetable(db, actor(org), t["id"], None)
    monkeypatch.undo()
    assert state(org, t["id"]) == before


def test_a_failing_commit_leaves_the_unpublication_unrecorded(client, org, monkeypatch):
    _, h = org.user(ADMIN)
    t, _, _ = published(client, org, h)
    before = state(org, t["id"])
    with session_for(org) as db:
        monkeypatch.setattr(db, "commit", lambda: (_ for _ in ()).throw(InjectedError("commit failed")))
        with pytest.raises(InjectedError):
            service.unpublish_timetable(db, actor(org), t["id"], {})
    assert state(org, t["id"]) == before
