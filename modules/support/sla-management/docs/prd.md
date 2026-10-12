# sla-management: product requirements

Owner: Madhumita (@madhumitha-rooman) · Status: draft for review · Week 1 task (issue linked in the PR)
Global support suite · tier `common` (every academy type enables it)

## Purpose

SLA definitions, timers, escalation and breach tracking (`module.yaml`) for helpdesk tickets: how fast
support must first respond and how fast it must resolve, counted in the organisation's business hours.
sla-management owns business-hours calendars, SLA policies, one response clock and one resolution clock per
ticket, warnings before a target is missed, breach records and escalation notices. It never changes a
ticket: it learns everything from helpdesk's events and publishes its own. The contract is
`contracts/openapi.yaml`, `events.yaml` and `permissions.yaml`.

v1 covers helpdesk tickets only. Other modules keep their own targets (see Out of scope).

## Users and what they need

| Role (profile role → module role) | Needs | Dashboard widget |
|---|---|---|
| Support Staff (`support-staff` → `sla-management-viewer`) | See which of their tickets have breached or are about to, and the due times on a ticket | `sla-management.breaches` (`GET /stats/breaches`) |
| Support lead, management (→ `sla-management-viewer`) | The same across every ticket | `sla-management.breaches` with `scope=all` |
| Org admin (`org-admin` → `sla-management-admin`) | Set up business-hours calendars and SLA policies with escalation levels | — |

Requesters have no sla-management screens in v1.

## Main flows

1. **Set up calendars.** The org admin creates business-hours calendars: a time zone, working intervals per
   weekday (more than one per day is allowed, for example 09:00–13:00 and 14:00–18:00) and dated holidays.
   A calendar can be marked `always_open` for round-the-clock cover.
2. **Set up policies.** A policy applies to one helpdesk priority and either one helpdesk category or every
   category (`category_id` null). It names a calendar, a response target and a resolution target in business
   minutes, a warning threshold (percent of the target used), which helpdesk hold reasons pause the clocks, and
   up to `SLA_MANAGEMENT_MAX_ESCALATION_LEVELS` escalation levels. At most one active policy per
   (priority, category) pair. Editing a policy affects tickets created afterwards; running clocks keep the
   targets they started with. Category ids are helpdesk's; sla-management stores them as given and does not
   check them against helpdesk (the admin screen can list categories through helpdesk's published API).
3. **Start clocks** (`helpdesk.ticket.created`). The most specific active policy is chosen: category and
   priority first, then priority with every category. If none matches, the ticket is not tracked and nothing
   is published (open question 5). Otherwise a response clock and a resolution clock start at the ticket's
   `created_at`, with due times computed in the policy's calendar. Publishes `sla-management.clock.started`
   per clock.
4. **Stop the response clock** (`helpdesk.ticket.responded`) at `responded_at`. Publishes
   `sla-management.clock.stopped` with outcome `met` or `breached`.
5. **Pause and resume** (`helpdesk.ticket.status-changed`). Moving to `on_hold` with a hold reason the policy
   lists pauses every running clock of the ticket (`clock.paused`); moving off hold resumes them with a
   new due time (`clock.resumed`). Holds for other reasons do not pause.
6. **Recalculate** (`helpdesk.ticket.reclassified`). Running and paused clocks switch to the policy for the
   new category and priority, keep the business time already used, and get a new due time
   (`clock.recalculated`). A breach already recorded stays recorded. If no policy matches the new values, the
   clocks keep their current targets.
7. **Warn** (timer). When the warning threshold of a running clock passes, publishes `clock.warning-raised`
   and, if the ticket has an assignee, notifies them through notification.
8. **Breach and escalate** (timer). When the due time of a running clock passes, the clock is marked breached
   (`clock.breached`) and keeps running so lateness is measured. Each escalation level fires its configured
   business minutes after the due time (level 1 usually at 0) and notifies its recipients through
   notification: the ticket's assignee if the level says so and there is one, plus the people named on the
   level. Publishes `clock.escalated`. Escalation never reassigns or changes the ticket.
9. **Resolve** (`helpdesk.ticket.resolved`). Stops the resolution clock (`clock.stopped`). If the response
   clock is still running (a ticket resolved without a public reply first), resolving stops it too.
10. **Reopen** (`helpdesk.ticket.reopened`). Resumes the resolution clock from where it stopped, with a new due
    time (`clock.resumed`); a clock that was met can still breach after a reopen.
11. **Close or cancel.** `helpdesk.ticket.closed` makes the clocks final: no further reopen is expected.
    `helpdesk.ticket.cancelled` cancels every clock that is still running or paused (`clock.cancelled`).
12. **Track assignment** (`helpdesk.ticket.assigned`). The cached assignee and queue are updated so the widget's
    `mine` scope and escalation recipients are current (see open question 6).

### Clock states

```
running ──pause──► paused ──resume──► running
   │                                     │
   ├──stop──► stopped ──reopen (resolution only)──► running
   └──cancel (also from paused)──► cancelled

breached: a flag set once when due_at passes; the clock keeps running until stopped.
```

## Rules

- Every table carries `organisation_id` with row-level security; every event carries `organisation_id`.
- Every state change and every escalation writes an audit record through `packages/sdk`.
- Clocks use the times in helpdesk's payloads (`created_at`, `responded_at`, `changed_at`, `resolved_at`,
  `reopened_at`, `closed_at`, `cancelled_at`), or the event envelope's `occurred_at` when a payload has none
  (`assigned`, `reclassified`), never the time an event happens to be processed. Each helpdesk event is
  applied once, by event id. Out-of-order delivery is open question 1.
- Business time counts only inside the calendar's working intervals, in its time zone, skipping its holidays.
  An `always_open` calendar counts every minute.
- A clock's targets are copied from the policy when the clock starts or is recalculated.
- sla-management stores ticket ids, numbers, category, priority, queue and assignee only. It never holds ticket
  titles, descriptions or replies, and none appear in its events.
- Nothing is deleted: calendars and policies are deactivated; clocks are stopped or cancelled.
- No dependency on another module being enabled: if helpdesk is off, no clocks start and the module is idle.
- No real ticket data in tests or seeds.

## Data model (summary)

| Entity | Key fields |
|---|---|
| Calendar | id, name, time_zone, always_open, working_hours [weekday, start, end], holidays [date, name], active |
| Policy | id, name, priority, category_id (null = every category), calendar_id, response_target_minutes, resolution_target_minutes, warning_percent, pause_on_hold_reasons, escalation_levels [level, after_breach_minutes, notify_assignee, notify_person_ids], active |
| Clock | id, ticket_id, ticket_number, kind (response, resolution), policy_id, calendar_id, target_minutes, state (running, paused, stopped, cancelled), started_at, warn_at, due_at, paused_at, business_minutes_used, stopped_at, outcome (met, breached), warned, breached, breached_at |
| TicketRef | ticket_id, number, category_id, priority, queue_id, assignee_id (cached from helpdesk events) |
| Escalation | id, clock_id, level, sent_at, recipient_ids |
| ProcessedEvent | event_id, processed_at |

## Dashboard widget

| Widget id | Dashboard | Endpoint | Permission | Shows |
|---|---|---|---|---|
| `sla-management.breaches` | Support Staff | `GET /stats/breaches?scope=mine\|all` | `sla-management:clock:read` | Running clocks that are breached or at risk, breaches in the last 24 hours, and the most overdue clocks with ticket number, kind, priority and due time; each links to the ticket in helpdesk |

The widget itself is built in week 2 or later in `frontend/src/widgets/`; this PR only fixes the endpoint.

## Integration points

| Direction | With | How |
|---|---|---|
| Consumes | helpdesk | `helpdesk.ticket.created`, `assigned`, `responded`, `status-changed`, `reclassified`, `resolved`, `reopened`, `closed`, `cancelled` (helpdesk `contracts/events.yaml`) |
| Publishes | helpdesk, notification, reporting, anyone | `sla-management.clock.started`, `paused`, `resumed`, `recalculated`, `warning-raised`, `breached`, `escalated`, `stopped`, `cancelled` (`events.yaml`) |
| Platform | identity, audit, notification, scheduler | through `packages/sdk`: permission checks; audit; warning and escalation notices; timers at `warn_at`, `due_at` and each escalation time (open question 1) |
| Serves | helpdesk frontend | `GET /tickets/{ticket_id}` gives a ticket's clocks, so helpdesk screens can show due times without caching them (proposed answer to helpdesk open question 2) |

## Configuration

`config/env.example`: `SLA_MANAGEMENT_DEFAULT_WARNING_PERCENT`, `SLA_MANAGEMENT_MAX_ESCALATION_LEVELS`,
`SLA_MANAGEMENT_BREACH_LIST_LIMIT`.

## Non-functional

- How soon after its time a warning or breach is detected depends on how the scheduler delivers timers (open
  question 1).
- Due times respect each calendar's time zone, including daylight-saving changes.
- Times are stored in UTC, RFC 3339 with offset.

## Out of scope (v1)

- Tickets themselves, their status and assignment (`helpdesk`). sla-management never calls helpdesk to change a ticket.
- SLAs of other modules: maintenance work orders keep their own targets (`maintenance.ticket.sla-breached`);
  incident-management and amc-vendor-support response times stay in those modules.
- Deadlines on approval steps (`platform/workflow`).
- Escalation through workflow (reassigning, approvals). v1 escalation is notification only.
- Waiving breaches and compliance reports (open question 7).
- Requester-facing SLA promises and penalties, and per-requester or per-group SLAs.
- Shared academic calendars as holiday sources; v1 calendars are maintained here.

## Open questions (for review)

1. **Timers and event delivery (Himanshu, scheduler and event-bus contracts).** Both contracts are still empty,
   and the event broker is an open decision in `docs/architecture/ARCHITECTURE.md`. Proposed: sla-management asks
   the scheduler for a one-off job at each `warn_at`, `due_at` and escalation time, and cancels or reschedules it
   on pause, resume, recalculate and stop. Is that the scheduler's model, and is the job delivered as an event to
   consume or a callback through the gateway? Can helpdesk events for one ticket arrive out of order (for example
   `responded` before `created`), and if so should sla-management hold early events until `created` arrives?
   Until this is agreed, nothing scheduler-related is in `openapi.yaml` or `consumes_events`.
2. **Boundary with workflow (Himanshu, Faizan).** `platform/workflow` describes itself as handling "SLAs" for state
   machines and approvals. Proposed: workflow keeps deadlines on its own steps; sla-management covers helpdesk
   tickets only.
3. **Maintenance SLAs (Ashritha).** Maintenance computes its own SLA in its merged contract. Should it move to
   sla-management later, which would need policies keyed by module rather than by helpdesk category? v1: no.
4. **Who sees which clocks.** Clock data carries no ticket text, so this draft lets anyone with
   `sla-management:clock:read` see every clock. Should visibility follow helpdesk queue membership instead? That
   would need helpdesk to publish queue membership.
5. **Untracked tickets.** When no policy matches, the ticket has no clocks. Should every organisation be required
   to have a policy per priority for every category, so that this cannot happen?
6. **Assignee at creation (helpdesk contract).** `helpdesk.ticket.created` carries no `assignee_id`, and the
   helpdesk contract does not say whether a ticket raised with `assign_to_me` also publishes
   `helpdesk.ticket.assigned`. Without one or the other, sla-management cannot know that ticket's assignee for
   warnings, escalation and the `mine` scope. To settle in the helpdesk contract (a separate PR).
7. **Waivers and compliance reporting.** Should a lead be able to waive a breach that was not support's fault (for
   example a campus-wide outage), and should sla-management report compliance by priority, category or queue?
   Neither is specified anywhere yet, so neither is in this contract; both can be added without breaking it.
8. **Role convention (Faizan).** Same question as helpdesk: module roles (`sla-management-viewer`) mapped to profile
   roles, or roles named after profile roles (`support-staff`)?
