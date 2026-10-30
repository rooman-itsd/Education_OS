"""Job definitions. Scheduler never imports the module that does the work: a module declares its jobs on the
`eos.scheduler_jobs` entry-point group, consumes `scheduler.job.due` for them, and reports the outcome by
publishing `<module>.job.finished` (payload: run_id, outcome succeeded|failed, detail).

    # platform/billing/backend/pyproject.toml
    [project.entry-points."eos.scheduler_jobs"]
    billing = "eos_billing.application.jobs:JOBS"

    # eos_billing/application/jobs.py
    JOBS = {
        "billing.expire-trials": {
            "scope": "platform", "default_cron": "15 0 * * *", "idempotent": True,
            "description": "Trials past their end go read-only or suspended.",
        },
    }

A job key is <module>.<job-name> and must start with the declaring entry point's name. Only an idempotent job
can be scheduled: delivery is at-least-once."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib import metadata

from ..domain.cron import Cron, CronError

GROUP = "eos.scheduler_jobs"
SCOPES = ("platform", "organisation")


@dataclass(frozen=True)
class Job:
    key: str
    module: str
    scope: str
    description: str = ""
    default_cron: str | None = None
    idempotent: bool = False
    arguments_schema: dict = field(default_factory=dict)

    @classmethod
    def declare(cls, module: str, key: str, spec: Mapping) -> Job:
        if not key.startswith(f"{module}.") or len(key) > 120:
            raise ValueError(f"{module}: job {key!r} must be named {module}.<job-name>")
        if spec.get("scope") not in SCOPES:
            raise ValueError(f"{key}: scope must be platform or organisation")
        cron = spec.get("default_cron")
        if cron:
            try:
                Cron.parse(cron)
            except CronError as e:
                raise ValueError(f"{key}: default_cron: {e}") from e
        return cls(
            key=key,
            module=module,
            scope=spec["scope"],
            description=spec.get("description", ""),
            default_cron=cron,
            idempotent=bool(spec.get("idempotent", False)),
            arguments_schema=dict(spec.get("arguments_schema") or {}),
        )

    def out(self) -> dict:
        return {
            "key": self.key,
            "module": self.module,
            "scope": self.scope,
            "description": self.description,
            "arguments_schema": self.arguments_schema,
            "default_cron": self.default_cron,
            "idempotent": self.idempotent,
        }


def discover() -> dict[str, Job]:
    """Every installed module's jobs. A bad declaration fails at start, not when its window comes."""
    jobs: dict[str, Job] = {}
    for point in metadata.entry_points(group=GROUP):
        declared = point.load()
        if not isinstance(declared, Mapping):
            raise TypeError(f"{point.name}: {point.value} must be a mapping of job key to definition")
        for key, spec in declared.items():
            jobs[key] = Job.declare(point.name, key, spec)
    return jobs
