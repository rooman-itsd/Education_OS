"""Workflow's scheduled job, declared for platform/scheduler (entry point `eos.scheduler_jobs`).

`workflow.sla-check` escalates approval steps past their deadline (service.escalate_overdue): one
workflow.step.overdue per step, never twice. A platform job: one run covers every organisation. Idempotent: a step
already escalated is skipped."""

SLA_CHECK = "workflow.sla-check"

JOBS = {
    SLA_CHECK: {
        "scope": "platform",
        "default_cron": "*/15 * * * *",
        "idempotent": True,
        "description": "Escalate approval steps past their SLA deadline (workflow.step.overdue), once per step.",
    },
}
