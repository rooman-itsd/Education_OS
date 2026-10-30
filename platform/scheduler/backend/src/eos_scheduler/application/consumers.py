"""What scheduler consumes: `<module>.job.finished` from every module that declares a job, which closes the run
the module was handed. Registered on event-bus's `eos.event_consumers` entry point; the mapping is computed from
the installed job declarations when the relay reads it, since scheduler cannot know the modules in advance.

The handler is idempotent on the run: a finished event for a run that is already closed (redelivered, or after
the timeout failed it) changes nothing."""

from __future__ import annotations

from collections.abc import Iterator, Mapping

from eos_core.db import utcnow
from sqlalchemy.orm import Session

from ..domain.models import Run
from . import jobs
from .ticker import close

OUTCOMES = ("succeeded", "failed")


def on_job_finished(db: Session, event) -> None:
    payload = event.payload or {}
    run = db.get(Run, str(payload.get("run_id", "")))
    if run is None or run.status != "running":
        return
    if not run.job.startswith(f"{event.name.split('.', 1)[0]}."):
        return  # only the module that owns the job may close its run
    outcome = payload.get("outcome")
    if outcome not in OUTCOMES:
        close(db, run, "failed", f"the module reported an unknown outcome {str(outcome)[:40]!r}", utcnow())
        return
    close(db, run, outcome, str(payload.get("detail") or ""), utcnow())


class _FinishedEvents(Mapping):
    """{"<module>.job.finished": on_job_finished} for every module with a declared job."""

    def _names(self) -> list[str]:
        return sorted({f"{job.module}.job.finished" for job in jobs.discover().values()})

    def __getitem__(self, name: str):
        if name in self._names():
            return on_job_finished
        raise KeyError(name)

    def __iter__(self) -> Iterator[str]:
        return iter(self._names())

    def __len__(self) -> int:
        return len(self._names())


CONSUMERS = _FinishedEvents()
