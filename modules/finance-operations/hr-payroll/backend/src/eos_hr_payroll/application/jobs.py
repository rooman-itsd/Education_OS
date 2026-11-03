"""hr-payroll's scheduled job, declared for platform/scheduler (entry point `eos.scheduler_jobs`).

`hr-payroll.publish-due-exits` publishes `hr-payroll.employee.exited` for every employee whose last working day has
come. It is a platform job, so the scheduler gives it a default schedule with no setup per organisation: 13:30 UTC is
19:00 in India, after the working day, on the last working day itself. It is idempotent: an exit is published once."""

JOBS = {
    "hr-payroll.publish-due-exits": {
        "scope": "platform",
        "default_cron": "30 13 * * *",
        "idempotent": True,
        "description": "Employees whose last working day has come exit: hr-payroll.employee.exited is published.",
    },
}
