"""Who reacts to which event. A module never imports another, so a consumer advertises itself on the
`eos.event_consumers` entry-point group: the entry point's name is the consuming module, and it loads a mapping
of event name to handler.

    # platform/billing/backend/pyproject.toml
    [project.entry-points."eos.event_consumers"]
    billing = "eos_billing.application.consumers:CONSUMERS"

    # eos_billing/application/consumers.py
    def expire_trials_due(db: Session, event: Event) -> None: ...
    CONSUMERS = {"scheduler.job.due": expire_trials_due}

A handler runs in its own transaction, in the event's organisation (platform scope when the event has none), and
must be idempotent on event.id: delivery is at-least-once. The host installs only the enabled modules, so only
their consumers are found."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from importlib import metadata

from sqlalchemy.orm import Session

from ..domain.models import Event

GROUP = "eos.event_consumers"

Handler = Callable[[Session, Event], None]
log = logging.getLogger("eos.event_bus")


class Consumers:
    """event name -> [(consuming module, handler)], in a stable order."""

    def __init__(self, registrations: Mapping[str, Mapping[str, Handler]]):
        self._by_event: dict[str, list[tuple[str, Handler]]] = {}
        for module in sorted(registrations):
            for event_name, handler in registrations[module].items():
                if not callable(handler):
                    raise TypeError(f"{module}: the handler for {event_name} is not callable")
                self._by_event.setdefault(event_name, []).append((module, handler))

    def for_event(self, name: str) -> list[tuple[str, Handler]]:
        return list(self._by_event.get(name, ()))

    def names(self) -> list[str]:
        return sorted(self._by_event)


def discover() -> Consumers:
    """Every installed module's consumers. A broken registration fails the relay at start, not on first use."""
    registrations: dict[str, Mapping[str, Handler]] = {}
    for point in metadata.entry_points(group=GROUP):
        loaded = point.load()
        if not isinstance(loaded, Mapping):
            raise TypeError(f"{point.name}: {point.value} must be a mapping of event name to handler")
        registrations[point.name] = loaded
    consumers = Consumers(registrations)
    log.info("event consumers: %s", ", ".join(consumers.names()) or "none")
    return consumers
