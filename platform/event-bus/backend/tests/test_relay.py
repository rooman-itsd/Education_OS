"""The relay: delivery, scope, retries with backoff, dead letters, the stall signal and pruning."""

from __future__ import annotations

import uuid

from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_core.tenant import get_current_organisation, is_bypass, platform_scope
from eos_event_bus.application.relay import DEAD_LETTERED, STALLED, backoff
from eos_event_bus.domain.models import state_of
from event_bus_support import NOW, Clock, names, raise_event, relay, row

ORG_A = str(uuid.uuid4())
ORG_B = str(uuid.uuid4())


def test_an_event_reaches_its_consumer_and_is_marked_published():
    seen = []
    eid = raise_event("hostel.room.allocated", ORG_A, {"room_id": "r1"})
    result = relay({"fees": {"hostel.room.allocated": lambda db, ev: seen.append(ev)}}, Clock()).run_once()
    assert result.claimed == 1 and result.delivered == 1
    (ev,) = seen
    assert ev.id == eid and ev.organisation_id == ORG_A and ev.payload == {"room_id": "r1"} and ev.version == 1
    stored = row(eid)
    assert stored.published and stored.published_at is not None and stored.attempts == 0


def test_an_event_nobody_consumes_is_still_published():
    eid = raise_event("tenancy.organisation.registered", ORG_A)
    assert relay({}, Clock()).run_once().delivered == 1
    assert row(eid).published


def test_a_consumer_runs_in_the_events_organisation_and_its_writes_commit_there():
    seen = []

    def handler(db, ev):
        seen.append((get_current_organisation(), is_bypass()))
        from eos_core.events import publish

        publish(db, "fees.invoice.raised", ev.organisation_id, {"for": ev.id})

    raise_event("hostel.room.allocated", ORG_A)
    relay({"fees": {"hostel.room.allocated": handler}}, Clock()).run_once()
    assert seen == [(ORG_A, False)]
    with platform_scope(), SessionLocal() as db:
        (written,) = db.query(OutboxEvent).filter(OutboxEvent.name == "fees.invoice.raised").all()
        assert written.organisation_id == ORG_A


def test_a_platform_event_runs_in_platform_scope():
    seen = []
    raise_event("scheduler.job.due", None, {"job": "billing.expire-trials"})
    relay(
        {"billing": {"scheduler.job.due": lambda db, ev: seen.append((get_current_organisation(), is_bypass()))}},
        Clock(),
    ).run_once()
    assert seen == [(None, True)]


def test_oldest_first_and_no_more_than_the_batch():
    order = []
    clock = Clock()
    ids = [raise_event("a.b.c", ORG_A, {"n": n}, at=NOW.replace(minute=n)) for n in (3, 1, 2)]
    r = relay({"x": {"a.b.c": lambda db, ev: order.append(ev.payload["n"])}}, clock, batch_size=2)
    assert r.run_once().claimed == 2 and order == [1, 2]
    assert r.run_once().claimed == 1 and order == [1, 2, 3]
    assert all(row(i).published for i in ids)


def test_a_failure_is_counted_backed_off_and_retried_after_the_wait():
    calls = []

    def flaky(db, ev):
        calls.append(ev.id)
        if len(calls) == 1:
            raise RuntimeError("secret-address@example.com bounced")

    clock = Clock()
    eid = raise_event("a.b.c", ORG_A)
    r = relay({"mod": {"a.b.c": flaky}}, clock)
    assert r.run_once().failed == 1
    stored = row(eid)
    assert not stored.published and stored.attempts == 1
    assert stored.last_error == "mod: RuntimeError"  # the type only: the message can carry personal data
    assert r.run_once().claimed == 0  # still inside its 1 s backoff
    clock.advance(1)
    assert r.run_once().delivered == 1 and row(eid).published and row(eid).last_error is None
    assert calls == [eid, eid]


def test_backoff_doubles_and_is_capped():
    assert [backoff(n, 300).total_seconds() for n in (1, 2, 3, 4)] == [1, 2, 4, 8]
    assert backoff(20, 300).total_seconds() == 300


def test_a_failing_consumer_holds_back_only_itself():
    """Delivery is per module (#83): b failing does not stop a, and the retry re-runs b only."""
    ok, tries = [], []

    def flaky(db, ev):
        tries.append(1)
        if len(tries) == 1:
            raise ValueError("no")

    clock = Clock()
    eid = raise_event("a.b.c", ORG_A)
    r = relay({"a": {"a.b.c": lambda db, ev: ok.append(1)}, "b": {"a.b.c": flaky}}, clock)
    r.run_once()
    assert ok == [1] and not row(eid).published and row(eid).last_error == "b: ValueError"
    clock.advance(1)
    assert r.run_once().delivered == 1 and row(eid).published
    assert ok == [1] and len(tries) == 2  # a was never handed the event again


def test_a_failing_consumer_leaves_none_of_its_own_writes():
    from eos_core.events import publish

    def half_done(db, ev):
        publish(db, "fees.invoice.raised", ev.organisation_id, {})
        db.flush()
        raise RuntimeError("after writing")

    raise_event("a.b.c", ORG_A)
    relay({"fees": {"a.b.c": half_done}}, Clock()).run_once()
    assert names("fees.") == []


def test_after_the_last_attempt_the_event_is_dead_lettered_and_announced_once():
    clock = Clock()

    def boom(db, ev):
        raise RuntimeError("down")

    eid = raise_event("a.b.c", ORG_B)
    r = relay({"mod": {"a.b.c": boom}}, clock, max_attempts=3)
    for _ in range(3):
        r.run_once()
        clock.advance(60)
    stored = row(eid)
    assert stored.attempts == 3 and state_of(stored, 3) == "dead_lettered" and stored.next_attempt_at is None
    assert r.run_once().claimed == 1  # that is the dead-lettered notice itself, delivered to nobody
    assert r.run_once().claimed == 0  # the dead event is never claimed again
    with platform_scope(), SessionLocal() as db:
        (notice,) = db.query(OutboxEvent).filter(OutboxEvent.name == DEAD_LETTERED).all()
        assert notice.organisation_id == ORG_B
        assert notice.payload == {
            "event_id": eid,
            "event_name": "a.b.c",
            "attempts": 3,
            "last_error": "mod: RuntimeError",
            "failed_modules": ["mod"],
        }


def test_the_bus_never_announces_its_own_dead_letters():
    clock = Clock()

    def boom(db, ev):
        raise RuntimeError("monitoring down")

    raise_event(DEAD_LETTERED, ORG_A, {"event_id": "x"})
    r = relay({"monitor": {DEAD_LETTERED: boom}}, clock, max_attempts=1)
    assert r.run_once().dead_lettered == 1
    assert names(DEAD_LETTERED) == [DEAD_LETTERED]  # still only the original


def test_a_stall_is_announced_once_until_it_clears():
    clock = Clock()

    def boom(db, ev):
        raise RuntimeError("down")

    raise_event("a.b.c", ORG_A, at=NOW)
    r = relay({"mod": {"a.b.c": boom}}, clock, stall_threshold_s=30, max_attempts=50)
    r.run_once()
    assert names(STALLED) == []
    clock.advance(31)
    r.run_once()
    clock.advance(31)
    r.run_once()
    assert names(STALLED) == [STALLED]
    with platform_scope(), SessionLocal() as db:
        (notice,) = db.query(OutboxEvent).filter(OutboxEvent.name == STALLED).all()
        assert notice.organisation_id is None and notice.payload["transport"] == "inprocess"
        assert notice.payload["backlog"] >= 1


def test_prune_removes_only_delivered_events_past_retention():
    clock = Clock()

    def boom(db, ev):
        raise RuntimeError("down")

    delivered = raise_event("x.y.z", ORG_A)
    dead = raise_event("a.b.c", ORG_A)
    r = relay({"mod": {"a.b.c": boom}}, clock, max_attempts=1, retention_days=30)
    r.run_once()
    clock.advance(31 * 86400)
    pending = raise_event("x.y.z", ORG_A, at=clock.now)
    assert r.prune() == 1
    assert row(delivered) is None and row(dead) is not None and row(pending) is not None


# --- Per-module delivery (#83's consumer group per module) ---------------------------------------------------


def _deliveries(event_id: str) -> dict[str, tuple[str, int, str | None]]:
    from eos_event_bus.domain.models import EventDelivery

    with platform_scope(), SessionLocal() as db:
        rows = db.query(EventDelivery).filter(EventDelivery.event_id == event_id).all()
        return {d.module: (d.status, d.attempts, d.last_error) for d in rows}


def test_a_module_that_keeps_failing_never_blocks_the_modules_after_it():
    """'a' sorts before 'b': before per-module delivery, a failing 'a' meant 'b' never ran at all."""
    ran_b = []

    def boom(db, ev):
        raise RuntimeError("down")

    clock = Clock()
    eid = raise_event("x.y.z", ORG_A)
    r = relay({"a": {"x.y.z": boom}, "b": {"x.y.z": lambda db, ev: ran_b.append(ev.id)}}, clock, max_attempts=3)
    for _ in range(3):
        r.run_once()
        clock.advance(10)
    assert ran_b == [eid]  # once, on the first attempt, never again
    assert _deliveries(eid) == {"a": ("failed", 3, "a: RuntimeError"), "b": ("delivered", 1, None)}
    stored = row(eid)
    assert not stored.published and stored.attempts == 3  # dead-lettered for 'a' only


def test_the_dead_letter_notice_names_the_failed_modules():
    def boom(db, ev):
        raise KeyError("x")

    clock = Clock()
    eid = raise_event("x.y.z", ORG_A)
    r = relay({"a": {"x.y.z": lambda db, ev: None}, "c": {"x.y.z": boom}}, clock, max_attempts=1)
    assert r.run_once().dead_lettered == 1
    with platform_scope(), SessionLocal() as db:
        (notice,) = [e for e in db.query(OutboxEvent).all() if e.name == "event-bus.event.dead-lettered"]
    assert notice.payload["event_id"] == eid and notice.payload["failed_modules"] == ["c"]


def test_a_replay_re_runs_only_the_modules_that_failed():
    from eos_event_bus.application import events as operator
    from eos_event_bus.infrastructure.config import EventBusConfig

    calls = {"a": 0, "b": 0}
    broken = {"b": True}

    def handler(module):
        def run(db, ev):
            calls[module] += 1
            if broken.get(module):
                raise RuntimeError("down")

        return run

    clock = Clock()
    eid = raise_event("x.y.z", ORG_A)
    r = relay({"a": {"x.y.z": handler("a")}, "b": {"x.y.z": handler("b")}}, clock, max_attempts=1)
    r.run_once()
    assert calls == {"a": 1, "b": 1} and not row(eid).published

    broken["b"] = False  # the module is fixed; an operator replays the dead letter
    with platform_scope(), SessionLocal() as db:
        operator.replay(db, operator.Scope(None, every_organisation=True), EventBusConfig(max_attempts=1), eid, "op")
    r.run_once()  # also delivers the dead-letter notice, which nothing consumes
    assert row(eid).published
    assert calls == {"a": 1, "b": 2}
    assert _deliveries(eid) == {"a": ("delivered", 1, None), "b": ("delivered", 2, None)}


def test_a_delivered_mark_exists_only_when_the_handlers_writes_committed():
    from eos_core.events import publish

    def half_done(db, ev):
        publish(db, "fees.invoice.raised", ev.organisation_id, {})
        db.flush()
        raise RuntimeError("after writing")

    eid = raise_event("x.y.z", ORG_A)
    relay({"fees": {"x.y.z": half_done}}, Clock()).run_once()
    assert names("fees.") == [] and _deliveries(eid)["fees"][0] == "failed"


def test_delivery_rows_carry_the_events_organisation_and_go_when_it_is_pruned():
    clock = Clock()
    eid = raise_event("x.y.z", ORG_A)
    r = relay({"a": {"x.y.z": lambda db, ev: None}}, clock, retention_days=1)
    r.run_once()
    from eos_event_bus.domain.models import EventDelivery

    with platform_scope(), SessionLocal() as db:
        (d,) = db.query(EventDelivery).filter(EventDelivery.event_id == eid).all()
        assert d.organisation_id == ORG_A
    clock.advance(2 * 86400)
    assert r.prune() == 1 and _deliveries(eid) == {}


def test_the_default_retry_window_is_about_an_hour_not_two_minutes():
    from eos_event_bus.infrastructure.config import EventBusConfig

    config = EventBusConfig.from_env()
    total = sum(backoff(n, config.retry_cap_s).total_seconds() for n in range(1, config.max_attempts))
    assert config.max_attempts == 20 and 3000 < total < 4000
