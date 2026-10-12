# helpdesk: product requirements

Owner: Madhumita (@madhumitha-rooman) · Status: draft for review · Issue #68
Global support suite · tier `common` (every academy type enables it)

## Purpose

One place where anyone in an organisation (students, faculty, staff) asks for help and gets an answer:
IT problems, account and access issues, administrative questions, certificate and document requests,
general service requests. Helpdesk owns tickets, categories, support queues, assignment, the
conversation on a ticket, resolution and closure. It does not compute service-level targets: it
publishes ticket events that `sla-management` turns into response and resolution clocks. The contract
is `contracts/openapi.yaml`, `events.yaml` and `permissions.yaml`.

## Users and what they need

| Role (profile role → module role) | Needs | Dashboard widget |
|---|---|---|
| Any signed-in user: student, faculty, staff, applicant (→ `helpdesk-requester`) | Raise a ticket, follow it, reply, attach files, confirm the fix or reopen, rate the help | — (later: a "my tickets" widget for Student) |
| Support Staff (`support-staff` → `helpdesk-agent`) | See the queue by priority, pick up tickets, reply, add internal notes, put on hold, resolve, raise tickets for walk-in and phone requests | `helpdesk.open-by-priority` (`GET /stats/open-by-priority`) |
| Support lead (→ `helpdesk-lead`) | Everything an agent does across all queues, reassign between queues, change category and priority, cancel duplicates | `helpdesk.open-by-priority` with `scope=all` |
| Org admin (`org-admin` → `helpdesk-admin`) | Set up categories and support queues and who is in each | — |
| Management (`management` → `helpdesk-viewer`) | Ticket volume and backlog across every queue, read only | — (later wave) |

## Main flows

1. **Set up.** The org admin creates support queues (for example IT, Academic office, Accounts help),
   each with member agents, and categories (two levels: category and optional sub-category). Each
   category has a default queue and a default priority. Category labels are the organisation's own; nothing
   in the module assumes one kind of academy.
2. **Raise.** A requester picks a category, writes a title and description, and may attach files (stored
   through `platform/documents`). The ticket gets a per-organisation number (`HD-000123`), the category's
   default queue and priority, status `new` and channel `portal`. An agent can raise a ticket on behalf of
   someone who phoned or walked in (channel `phone`, `walk_in` or `email`). Publishes `helpdesk.ticket.created`.
3. **Assign.** An agent picks a ticket from their queue ("assign to me") or a lead assigns it to an agent
   or moves it to another queue. Moving a ticket to another queue without naming an assignee leaves it
   unassigned there. Publishes `helpdesk.ticket.assigned`. Assigning never changes the status.
4. **Work.** The assignee replies publicly (seen by the requester) or adds internal notes (agents only).
   The **first public reply by an agent** publishes `helpdesk.ticket.responded` once; that stops the
   response clock in sla-management. Every status move between `new`, `in_progress` and `on_hold` publishes
   `helpdesk.ticket.status-changed`, whichever way it happens: the agent starts work or puts the ticket on
   hold (waiting on the requester, a third party or an internal team), a public agent reply on a `new` ticket
   moves it to `in_progress`, or a requester's reply to a ticket waiting on them moves it back to
   `in_progress`. sla-management pauses and resumes the resolution clock from this event.
5. **Reclassify.** The assignee can change the priority of a ticket assigned to them; a lead changes the
   category or the priority of any ticket. Changing the category does not move the ticket to another queue.
   Publishes `helpdesk.ticket.reclassified` with the previous values, so SLA targets can be recalculated.
6. **Resolve.** The assignee resolves the ticket with a resolution note, from `new`, `in_progress` or
   `on_hold` (a question answered at once can be resolved straight from `new`). Publishes
   `helpdesk.ticket.resolved` and notifies the requester.
7. **Confirm, reopen or auto-close.** The requester confirms the fix (optionally rating it 1 to 5 with a
   comment), which closes the ticket, or reopens it within `HELPDESK_REOPEN_WINDOW_DAYS` with a reason
   (`helpdesk.ticket.reopened`). A daily scheduler job closes tickets resolved more than
   `HELPDESK_AUTO_CLOSE_DAYS` ago (see open question 6). Closing publishes `helpdesk.ticket.closed`.
8. **Cancel.** The requester can withdraw their own ticket before it is resolved. A lead can cancel a
   ticket as a duplicate of another (`duplicate_of`). Publishes `helpdesk.ticket.cancelled`.
9. **Link.** An agent records a link from a ticket to a record in another module (for example a
   maintenance work order or a knowledge-base article) by module name and id. Helpdesk stores the reference
   only; it never reads another module's tables.

### Ticket states

```
new ──start / first public reply──► in_progress ◄──hold / resume──► on_hold
 │                                      │                               │
 ├──resolve─────────────────────────────┼──resolve──────────────────────┘
 │                                      ▼
 │                                   resolved ──confirm / auto-close──► closed
 │                                      │
 │                                      └──reopen (within window)──► in_progress
 └──────── cancel (from new, in_progress, on_hold) ──► cancelled
```

Assignment is independent of status: a ticket can be assigned or unassigned in any open status.

## Rules

- Every table carries `organisation_id` with row-level security; every event carries `organisation_id`.
- Every state change writes an audit record through `packages/sdk`.
- A requester sees only their own tickets and the public replies on them (`/me/*`); internal notes are
  never returned on `/me/*` endpoints.
- An agent sees tickets of the queues they belong to (`helpdesk:ticket:read`); leads, admins and management
  see every queue (`helpdesk:ticket:read-all`).
- Ticket titles, descriptions and replies are personal data and are never in an event payload; events
  carry ids, the ticket number, category, priority and status only.
- Nothing is deleted: tickets are cancelled or closed, categories and queues are deactivated.
- Priority is a fixed list (`low`, `medium`, `high`, `urgent`) so SLA policies and the widget can rely on it;
  categories are the organisation's own.
- Helpdesk does not compute SLA due times or breaches. That is `sla-management`, from the events above.
- Grievances, RTI requests and harassment complaints are not helpdesk tickets; they go to `grievance` and `rti`
  with their statutory process.
- No dependency on another module being enabled: if sla-management, maintenance or knowledge-base is off,
  helpdesk works on its own.
- No real requester data in tests or seeds.

## Data model (summary)

| Entity | Key fields |
|---|---|
| Queue | id, name, description, member_ids (person ids of agents), active |
| Category | id, parent_id (null = top level), name, default_queue_id, default_priority, active |
| Ticket | id, number (`HD-000123`), requester_id, raised_by_id, channel, category_id, queue_id, assignee_id, priority, status, hold_reason, title, description, attachment_document_ids, resolution_note, duplicate_of, created_at, updated_at, first_responded_at, resolved_at, closed_at, reopen_count, satisfaction_rating, feedback |
| Comment | id, ticket_id, author_id, visibility (public, internal), body, attachment_document_ids, created_at |
| TicketLink | id, ticket_id, module, entity, ref_id, note, created_by, created_at |
| TicketNumberSequence | organisation_id, last_number |

## Dashboard widget

| Widget id | Dashboard | Endpoint | Permission | Shows |
|---|---|---|---|---|
| `helpdesk.open-by-priority` | Support Staff | `GET /stats/open-by-priority?scope=mine\|my_queues\|all` | `helpdesk:ticket:read` | Open tickets (`new`, `in_progress`, `on_hold`) counted per priority, with unassigned and assigned-to-me counts; each row links to the filtered ticket list |

The widget itself is built in week 2 or later in `frontend/src/widgets/`; this PR only fixes the endpoint.

## Integration points

| Direction | With | How |
|---|---|---|
| Publishes | sla-management (clocks), notification, reporting, anyone | `helpdesk.ticket.created`, `assigned`, `responded`, `status-changed`, `reclassified`, `resolved`, `reopened`, `closed`, `cancelled` (`events.yaml`) |
| Consumes | none in v1 | See open question 2 about cached SLA state |
| Platform | identity, audit, notification, documents, scheduler | through `packages/sdk`: permission checks; audit on every state change; notify requester and assignee; attachments; the daily auto-close job (how the scheduler triggers it is open question 6) |
| References | identity / student-information | `requester_id`, `assignee_id`, `member_ids` are person ids; names come from identity |
| Links | maintenance, knowledge-base, incident-management | stored as `{module, entity, ref_id}` only |

## Configuration

`config/env.example`: `HELPDESK_AUTO_CLOSE_DAYS`, `HELPDESK_REOPEN_WINDOW_DAYS`,
`HELPDESK_TICKET_NUMBER_PREFIX`, `HELPDESK_MAX_ATTACHMENTS`.

## Non-functional

- Raising a ticket works from a phone in under a minute (category, title, description, photo).
- Ticket lists are cursor-paginated; the widget endpoint answers from an index on
  (organisation_id, status, priority, queue_id) without scanning closed tickets.
- Times are stored in UTC, RFC 3339 with offset.

## Out of scope (v1)

- Service-level targets, clocks, breaches and escalation (`sla-management`).
- Repairs to buildings and equipment (`maintenance`); helpdesk only links to the work order.
- Major outages affecting many users (`incident-management`); many tickets may link to one incident.
- Help articles and self-service answers (`knowledge-base`); suggesting articles while raising a ticket is later.
- Vendor and AMC calls (`amc-vendor-support`).
- Grievances and RTI (`grievance`, `rti`).
- Creating tickets from inbound email, chat or WhatsApp (later, through `integration-hub`).
- Automatic assignment rules (round robin, skills); v1 is pick-up or manual assignment.

## Open questions (for review)

1. **SLA events (Himanshu, and the sla-management contract).** Are `created`, `responded`, `status-changed`
   (for pause and resume on `on_hold`), `reclassified`, `resolved`, `reopened`, `closed` and `cancelled` enough
   for sla-management to run response and resolution clocks on the scheduler? This draft says yes.
2. **Showing SLA due times on tickets.** Should helpdesk subscribe to sla-management's clock events and cache
   `response_due_at`, `resolution_due_at` and `breached` on the ticket for list views, or should the frontend
   ask sla-management directly? This draft: neither in v1; decided with the sla-management contract (a
   non-breaking addition).
3. **Boundary with maintenance (Ashritha, maintenance PRD question 3).** Proposed: helpdesk does not forward
   repair requests through maintenance's API in v1. The agent raises the work order in maintenance with
   `source = {module: helpdesk, id}` and records the link here with `POST /tickets/{id}/links`.
4. **Role convention (Faizan).** This draft uses module roles (`helpdesk-agent` and so on) like most week 1
   contracts, and maps them to profile roles in the table above. Is that mapping done by identity, or should
   the roles be named after profile roles (`support-staff`) as e-office and hr-payroll do?
5. Should a satisfaction rating be asked on every closed ticket, or sampled? This draft: optional on confirm.
6. **Auto-close trigger (Himanshu, scheduler contract).** The scheduler contract is still empty, so this draft
   neither consumes a `scheduler.*` event nor exposes a callback endpoint for the daily auto-close job. Once the
   scheduler contract says how a module registers and receives a recurring job (an event to subscribe to, or a
   callback the scheduler calls through the gateway), helpdesk adds that to `module.yaml` `consumes_events` or to
   `openapi.yaml` as a non-breaking change. Until then the job is internal to helpdesk.
