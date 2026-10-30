"""Run the relay as its own process: `python -m eos_event_bus`. It reads EOS_DATABASE_URL and the EVENT_BUS_*
settings, finds every installed consumer, and drains the outbox until it receives SIGTERM or SIGINT.

Several copies may run against one Postgres database: the claim uses FOR UPDATE SKIP LOCKED."""

from __future__ import annotations

import logging
import signal
import threading

from .application.consumers import discover
from .application.relay import Relay
from .application.transport import InProcessTransport
from .infrastructure.config import EventBusConfig


def build_relay(config: EventBusConfig | None = None) -> Relay:
    config = config or EventBusConfig.from_env()
    return Relay(InProcessTransport(discover()), config)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    relay = build_relay()
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    logging.getLogger("eos.event_bus").info("relay started, transport %s", relay.transport.name)
    relay.run_forever(stop)


if __name__ == "__main__":
    main()
