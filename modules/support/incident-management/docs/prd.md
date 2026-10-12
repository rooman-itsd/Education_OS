# incident-management: product requirements

Owner: Madhumita (@madhumitha-rooman) · Status: draft for review · Week 1 task (issue linked in the PR)
Global support suite · tier `common` (every academy type enables it)

## Purpose

Incident and problem records, root cause analysis (`module.yaml`). An **incident** is an unplanned
disruption or degradation of a service that affects users, such as campus Wi-Fi, the LMS or email going
down. A **problem** is the underlying cause behind one or more incidents. A **root-cause analysis (RCA)**
explains a problem, and **corrective actions** follow from it. Individual requests stay in helpdesk; this
module handles the shared disruption behind them. The contract is `contracts/openapi.yaml`, `events.yaml`
and `permissions.yaml`.

## Users and what they need

| Role (profile role → module role) | Needs | Dashboard widget |
|---|---|---|
| Support Staff (`support-staff` → `incident-management-responder`) | Report incidents, lead or respond to them, post timeline updates, record related tickets and assets, see problems | `incident-management.open` (`GET /stats/open`) |
| Support lead (→ `incident-management-problem-manager`) | Everything a responder does, plus open and run problems, write and publish RCAs, assign corrective actions | `incident-management.open` |
| Management, org admin (`management`, `org-admin` → `incident-management-viewer`) | Read incidents and problems | — |

## Main flows

1. **Report.** A responder reports an incident with a title, description, affected services (free-text labels),
   severity and start time. It gets a per-organisation number (`INC-000123`) and status `open`. The reporter is
   the lead unless another lead is named. Publishes `incident-management.incident.reported`.
2. **Respond.** The lead moves the incident through `investigating` and `mitigated` (service restored or a
   workaround in place, cause not yet fixed), adds responders and posts timeline updates. Every status move
   publishes `incident-management.incident.status-changed`. Raising or lowering severity publishes
   `incident-management.incident.severity-changed`.
3. **Record references.** Responders record related records in other modules by id: helpdesk tickets raised about
   the outage, affected assets, maintenance work orders. Nothing is read from or written to those modules.
4. **Resolve and close.** The lead resolves the incident with a resolution summary, and closes it once nothing
   more is needed. A resolved incident can be reopened to `investigating` until it is closed. An incident reported
   in error is cancelled from `open` or `investigating`. All of these publish `incident.status-changed`.
5. **Open a problem.** A problem manager opens a problem for the cause behind one or more incidents
   (`PRB-000045`) and links incidents to it; an incident links to at most one problem. Problem status moves
   publish `incident-management.problem.status-changed`.
6. **Known error.** When a workaround is known but the cause is not fixed, the problem moves to `known_error`
   with the workaround recorded.
7. **Root-cause analysis.** The problem manager drafts the RCA (summary, root cause, contributing factors,
   attachments) and publishes it, after which it is read-only. Publishes
   `incident-management.problem.rca-published`.
8. **Corrective actions.** Actions from the RCA are assigned to an owner with a due date, optionally pointing to a
   record elsewhere (for example a maintenance work order). Assigning an owner publishes
   `incident-management.action.assigned`. An owner can mark their own action done with
   `incident-management:problem:read`; other changes need `incident-management:problem:manage`. An open action past
   its due date is overdue.
9. **Resolve the problem.** With the RCA published, the problem is resolved and later closed.

### Statuses

```
Incident:  open → investigating ⇄ mitigated
           investigating or mitigated → resolved → closed
           resolved → investigating (reopen, until closed)
           open or investigating → cancelled

Problem:   open → investigating → known_error (optional) → resolved → closed
           investigating → resolved (when no known error was recorded)

RCA:              draft ──► published
CorrectiveAction: open ──► done | cancelled
Severity:         critical, high, medium, low
```

## Rules

- Every table carries `organisation_id` with row-level security; every event carries `organisation_id`.
- Every state change, timeline update, reference change, problem link, RCA publication and action change writes an
  audit record through `packages/sdk`. Linking an incident to a problem publishes no event.
- Resolving an incident needs a resolution summary; cancelling or reopening one needs a note, saved as a timeline
  update. Moving a problem to `known_error` needs a workaround; resolving
  a problem needs a published RCA. A published RCA cannot be edited.
- Overdue corrective actions are worked out when read; there are no timers in v1.
- References use `{module, entity, id}` plus a `relation`, by id only. They are not checked against the other
  module, and no foreign keys cross modules.
- Event payloads carry ids, numbers, severity, status and service labels only, never titles, descriptions,
  timeline text or RCA text.
- Nothing is deleted: incidents are closed or cancelled, problems closed, actions cancelled. A reference recorded by
  mistake can be removed, and the removal is audited.
- No dependency on another module being enabled. No real incident data in tests or seeds.

## Data model (summary)

| Entity | Key fields |
|---|---|
| Incident | id, number, title, description, affected_services, severity, status, lead_id, responder_ids, reported_by, started_at, mitigated_at, resolved_at, closed_at, resolution_summary, problem_id, updates [id, author_id, body, created_at] |
| Problem | id, number, title, description, affected_services, status, owner_id, workaround, created_at, resolved_at, closed_at |
| RCA | problem_id, summary, root_cause, contributing_factors, attachment_document_ids, status (draft, published), published_at, published_by |
| CorrectiveAction | id, problem_id, description, owner_id, due_date, status (open, done, cancelled), reference, completed_at |
| Reference | id, incident_id or action_id, module, entity, ref id, relation (related_ticket, affected_asset, work_order), note, created_by |

## Dashboard widget

| Widget id | Dashboard | Endpoint | Permission | Shows |
|---|---|---|---|---|
| `incident-management.open` | Support Staff | `GET /stats/open` | `incident-management:incident:read` | Incidents in `open`, `investigating` or `mitigated`, counted by severity and by status, with the total |

The widget itself is built in week 2 or later in `frontend/src/widgets/`; this PR only fixes the endpoint.

## Integration points

| Direction | With | How |
|---|---|---|
| Publishes | notification, anyone | `incident.reported`, `incident.status-changed`, `incident.severity-changed`, `problem.status-changed`, `problem.rca-published`, `action.assigned` (`events.yaml`) |
| Consumes | none in v1 | |
| Platform | identity, audit, notification, documents | through `packages/sdk`: permission checks; audit; messages to the lead, responders and action owners; RCA attachments |
| References | helpdesk, asset-management, maintenance | `{module: helpdesk, entity: ticket, id}`, `{module: asset-management, entity: asset, id}`, `{module: maintenance, entity: ticket, id}` stored by id only |

## Configuration

`config/env.example`: `INCIDENT_MANAGEMENT_INCIDENT_NUMBER_PREFIX`, `INCIDENT_MANAGEMENT_PROBLEM_NUMBER_PREFIX`.

## Out of scope (v1)

- Individual requests (helpdesk) and SLA clocks (sla-management).
- Carrying out repairs (maintenance) and asset records (asset-management).
- Vendor escalation and AMC calls (amc-vendor-support); knowledge articles (knowledge-base).
- A status board or broadcast to affected users (open question 2).
- Reminders and other timers; the scheduler is not used in v1 (open question 8).
- A managed list of services (open question 6), change management, on-call rosters and paging, ingesting alerts
  from monitoring tools.
- Security breaches and regulatory notifications; hostel discipline incidents (hostel).

## Open questions (for review)

1. **Event format (Himanshu, Faizan).** This contract follows the convention on `main`: `organisation_id` in each
   event payload and a file-level `version`. The event-bus contract proposed in PR #189 puts `organisation_id` in the
   envelope only, says it must not be repeated in a payload, and declares `version` on every event. How will
   existing module contracts move to it if PR #189 merges?
2. **Telling affected users (Himanshu).** v1 has no status board, and notification sends to one recipient per
   message. Should affected users be told through a broadcast or audience feature in notification, per-person
   fan-out from this module, a status board in a later version, or only through their helpdesk tickets?
3. **Helpdesk linkage.** Should helpdesk react to `incident.status-changed` (for example notify or resolve linked
   tickets), and should a ticket–incident link be recorded once instead of in both modules? Either needs a helpdesk
   contract change in its own PR.
4. **Who reports incidents.** Support staff only (this draft), or any signed-in user, which would overlap with helpdesk?
5. **Severity.** Are four fixed levels enough, and should each organisation define what they mean?
6. **Affected services.** Free-text labels in v1. Is a managed service list needed later?
7. **Problem and RCA consumers.** Who consumes `problem.status-changed` and `problem.rca-published`? Candidates:
   knowledge-base (known errors and workarounds as articles) and reporting.
8. **Reminders.** Are corrective-action due-date reminders needed? They would use the scheduler's
   `scheduler.job.due` model proposed in PR #189.
9. **Role convention (Faizan).** Module roles (`incident-management-responder`) mapped to profile roles, or roles
   named after profile roles (`support-staff`), as for helpdesk and sla-management?
