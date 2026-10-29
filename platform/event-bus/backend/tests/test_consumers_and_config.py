"""Consumer discovery by entry point, and the bounds on every setting."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from eos_event_bus.application import consumers as consumers_module
from eos_event_bus.application.consumers import Consumers, discover
from eos_event_bus.infrastructure.config import EventBusConfig


def _point(name, loaded):
    return SimpleNamespace(name=name, value=f"{name}.consumers:CONSUMERS", load=lambda: loaded)


def test_discovery_reads_every_installed_modules_mapping(monkeypatch):
    def a(db, ev): ...

    def b(db, ev): ...

    points = [_point("notification", {"billing.trial.reminder-due": a}), _point("billing", {"scheduler.job.due": b})]
    monkeypatch.setattr(consumers_module.metadata, "entry_points", lambda group: points)
    found = discover()
    assert found.for_event("scheduler.job.due") == [("billing", b)]
    assert found.for_event("billing.trial.reminder-due") == [("notification", a)]
    assert found.for_event("nobody.listens.here") == []


def test_a_broken_registration_fails_at_start(monkeypatch):
    monkeypatch.setattr(consumers_module.metadata, "entry_points", lambda group: [_point("bad", ["not", "a", "map"])])
    with pytest.raises(TypeError, match="mapping"):
        discover()
    with pytest.raises(TypeError, match="not callable"):
        Consumers({"bad": {"a.b.c": "not a function"}})


def test_two_modules_on_one_event_run_in_a_stable_order():
    def a(db, ev): ...

    def b(db, ev): ...

    assert [m for m, _ in Consumers({"zeta": {"e.f.g": a}, "alpha": {"e.f.g": b}}).for_event("e.f.g")] == [
        "alpha",
        "zeta",
    ]


def test_defaults_match_env_example():
    assert EventBusConfig.from_env() == EventBusConfig()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("EVENT_BUS_BATCH_SIZE", "0"),
        ("EVENT_BUS_BATCH_SIZE", "100000"),
        ("EVENT_BUS_MAX_ATTEMPTS", "0"),
        ("EVENT_BUS_POLL_INTERVAL_MS", "1"),
        ("EVENT_BUS_RETRY_CAP_S", "ten"),
        ("EVENT_BUS_TRANSPORT", "kafka"),
    ],
)
def test_an_unusable_setting_is_refused(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match=key):
        EventBusConfig.from_env()
