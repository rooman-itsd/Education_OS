# scheduler — PRD

Owner: Himanshu (@himanshu-rooman) · Tier: core · Status: planned

## What this is

The service that makes things happen **later**, or **repeatedly**, without anyone clicking
anything: nightly jobs, reminders, expiries, digests, retries of long-running work.

There is already a job waiting for it. `platform/billing` has:

```python
def expire_trials(db: Session) -> int:
    """Run by the scheduler daily. Trials past their end go read-only or suspended per the plan policy."""
```

Nothing runs it. Every trial in the product therefore lasts forever, and
`billing.trial.expired` — which `notification` is contracted to turn into a "your trial ended"
mail — is never published. Making that function run on a schedule is this module's first job.

## What it is explicitly NOT

| Not this | That belongs to |
|---|---|
| Doing the work itself | The owning module. Scheduler decides *when*, never *what* |
| Sending the reminder | `platform/notification` |
| Moving events from the outbox to consumers | `platform/event-bus`. Its relay runs continuously; it is not a scheduled job |
| A general background-task queue for one request | `arq` directly, inside the module. Scheduler is for work on a clock, not work offloaded from a request |
| Workflow, approvals, escalations and SLA timers | `platform/workflow`. It may *use* scheduler for its timers |
| A retry mechanism for failed deliveries | The module that owns the delivery |

The boundary that matters: **scheduler owns the clock, modules own the work.** It must never
contain business logic, because the moment it does, every module's rules start leaking into one
service.

## How a job runs, given module boundaries

Scheduler cannot import `billing` — module-to-module imports are forbidden
(`ARCHITECTURE.md`), and that is the whole point of the architecture. So when a schedule fires,
scheduler **publishes `scheduler.job.due`** and the owning module consumes it and does the work.

```
schedule fires -> scheduler.job.due { job: "billing.expire-trials" }
               -> billing consumes it -> expire_trials() -> billing.trial.expired
               -> notification consumes that -> "your trial ended" mail
```

This reuses the bus rather than inventing a second delivery path, and it keeps scheduler
ignorant of what any job means. It has one consequence that must be designed for, not
discovered: **bus delivery is at-least-once, so a job handler must be idempotent.**
`expire_trials` already is — it only acts on subscriptions past their end date — and that is
the standard every handler is held to.

The alternative, scheduler calling the module's HTTP endpoint through the gateway, is listed as
an open question below.

## Platform jobs and organisation jobs

Two kinds, and conflating them would be a tenancy bug:

| Kind | `organisation_id` | Example |
|---|---|---|
| Platform | null | `billing.expire-trials` — runs once per deployment, across all tenants, in platform scope |
| Organisation | set | A fee-reminder sweep for one academy, on that academy's calendar and timezone |

A platform job runs once no matter how many organisations exist. An organisation job runs per
organisation, with `app.organisation_id` set before the handler sees it, so row-level security
applies exactly as it does to a request.

## Guarantees

- **At-least-once, never "about right".** A missed window (deployment, outage) is caught up on
  restart rather than skipped silently.
- **No overlap by default.** A schedule does not start again while its previous run is still
  going, unless it opts in. Overlapping nightly jobs is a classic way to corrupt data.
- **A run is recorded** — started, finished, outcome, duration — because "did the nightly job
  run?" must be answerable without reading logs.
- **Timezones are explicit.** A cron with no timezone is a bug; academies are not all in one.

## Users

| Who | Needs |
|---|---|
| Every module | To declare "run this daily" once, and never write a timer |
| `platform/workflow` | Timers for escalations and SLA breaches |
| `platform/notification` | Reminders and digests, which have no triggering event |
| Super Admin | Which jobs exist, when they last ran, which failed |
| Organisation Admin | Their own academy's scheduled work |

## Scope, week by week

| When | What |
|---|---|
| Week 1 (this) | Contracts, PRD, the job model and the firing mechanism |
| Week 2 | Backend on `arq`, cron and one-off schedules, run history, `billing.expire-trials` as the first real job, trial reminders |
| Later | Organisation-scoped schedules with per-academy timezones, digests, a Super Admin widget, catch-up policy tuning |

## Dependencies

- **`platform/event-bus`** — how a due job reaches its owner. Mine.
- **`platform/identity`** — permission checks.
- **`platform/audit`** — creating, changing or manually running a schedule is recorded.
- **`arq`** — the approved job runner (`approved-stack.yaml`), on Redis.

## Success

- No module contains a timer, a cron expression or a sleep loop.
- A job that was missed during a deployment still runs.
- A job never runs twice in a way that matters, because handlers are idempotent.
- "Did the nightly job run, and what happened?" is answerable from the API.

## Open questions for review

1. **Event or HTTP call?** Proposed: publish `scheduler.job.due` and let the owner consume it.
   The alternative — scheduler calling the module's endpoint through the gateway — gives a
   synchronous result and exactly-once-ish semantics, but makes scheduler depend on every
   module's API and on the gateway being up. Worth Faizan's view, since it touches the
   gateway.
2. **Catch-up policy.** After a four-hour outage, does an hourly job run four times or once?
   Proposed: once, with the missed count recorded — but a reminder job and a billing job may
   genuinely differ, so this may need to be per-schedule.
3. **Who may schedule?** Proposed: job *definitions* are declared in code by the owning module
   and are not user-editable; only their timing is. Otherwise an admin can invent a job nothing
   handles.
