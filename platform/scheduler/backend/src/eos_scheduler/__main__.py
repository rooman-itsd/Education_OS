"""Run the scheduler loop as its own process: `python -m eos_scheduler`. It needs no Redis: every
SCHEDULER_TICK_INTERVAL_S it fires the schedules that are due and fails runs nobody closed in time. The arq worker
(`eos_scheduler.worker`) does the same on arq's clock once Redis is in the stack.

One process per deployment (SCHEDULER_ENABLED=false on every other replica); on Postgres a second one is still
safe, because due schedules are claimed FOR UPDATE SKIP LOCKED."""

from __future__ import annotations

import logging
import signal
import threading

from .application.jobs import discover
from .application.ticker import Ticker
from .infrastructure.config import SchedulerConfig

log = logging.getLogger("eos.scheduler")


def build_ticker(config: SchedulerConfig | None = None) -> Ticker:
    ticker = Ticker(discover(), config or SchedulerConfig.from_env())
    seeded = ticker.seed_platform_defaults()
    log.info("scheduler: %s job(s) declared, %s default schedule(s) created", len(ticker.jobs), seeded)
    return ticker


def run_forever(ticker: Ticker, stop: threading.Event, prune_every_s: int = 3600) -> None:
    next_prune = 0.0
    while not stop.is_set():
        try:
            ticker.tick()
            if (now := ticker._now().timestamp()) >= next_prune:
                ticker.prune()
                next_prune = now + prune_every_s
        except Exception:  # noqa: BLE001 - a database blip must not end the loop; the next tick retries
            log.exception("scheduler tick failed")
        stop.wait(ticker.config.tick_interval_s)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    config = SchedulerConfig.from_env()
    if not config.enabled:
        log.info("SCHEDULER_ENABLED is false: this process does not run the scheduler")
        return
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    run_forever(build_ticker(config), stop)


if __name__ == "__main__":
    main()
