# helpdesk: user stories

Owner: Madhumita (@madhumitha-rooman) · Status: draft for review · Issue #113

Stories by role for the helpdesk module. Each story follows `prd.md` and is bounded by the contract in
`contracts/openapi.yaml`, `events.yaml` and `permissions.yaml`; where the PRD and the contract leave a rule
open, it is listed under [Open questions](#open-questions) instead of being decided in a story. Paths are
relative to `/api/v1/helpdesk`.

## Roles

| Role (`permissions.yaml`) | Who (PRD) | Grants |
|---|---|---|
| `helpdesk-requester` | Every signed-in person: student, faculty, staff, applicant. Default for all profile roles | `self:read`, `self:raise` |
| `helpdesk-agent` | Support Staff (`support-staff` profile role), working tickets in their queues | `self:read`, `self:raise`, `ticket:read`, `ticket:work` |
| `helpdesk-lead` | Support lead, working and managing tickets across every queue | `self:read`, `self:raise`, `ticket:read`, `ticket:read-all`, `ticket:work`, `ticket:manage` |
| `helpdesk-admin` | Org admin (`org-admin`), setting up queues and categories | `self:read`, `self:raise`, `ticket:read`, `ticket:read-all`, `settings:manage` |
| `helpdesk-viewer` | Management (`management`), read only across every queue | `self:read`, `self:raise`, `ticket:read`, `ticket:read-all` |

All keys above are short for `helpdesk:<resource>:<action>`. Every role can raise and follow its own tickets.
A call without the permission named for its endpoint is refused with 403 and changes nothing.

"Requester" below means the person the ticket is for (`requester_id`). "Agent" means a caller with
`ticket:work`; which tickets an agent can see follows R6, and any further queue or assignee condition is stated
in the story that needs it. "Lead" means a caller with `ticket:manage`.

## Rules every story inherits

These apply to every story below and are tested once per endpoint, not repeated in each story.

- **R1 Tenant isolation.** Every record carries `organisation_id` and is protected by row-level security.
  A user sees and changes only their own organisation's records; another organisation's record is never
  listed and a request for it by id answers 404. The cross-tenant leak test from `eos_testing` passes for
  every table.
- **R2 Events carry the tenant.** Every published event carries `organisation_id`.
- **R3 Audit.** Every state change writes an audit record through `packages/sdk`, with the actor (see open
  question 11).
- **R4 Nothing is deleted.** Tickets are cancelled or closed; queues and categories are deactivated. The one
  exception in the contract is a ticket link recorded by mistake (AG-9), whose removal is audited.
- **R5 Own tickets only.** `/me/*` returns only tickets whose requester is the caller, with public replies
  only. Internal notes and links are never returned on `/me/*`.
- **R6 Queue visibility.** With `ticket:read`, a caller sees tickets in the queues they are a member of. With
  `ticket:read-all`, they see every queue. A ticket outside what the caller may see answers 404.
- **R7 Personal data.** Titles, descriptions, replies and internal notes are personal data and are never in an
  event payload. Each event carries exactly the payload fields listed for it in `contracts/events.yaml`, so
  resolution notes and feedback are not published either.
- **R8 Fixed priorities, own categories.** Priority is always one of `low`, `medium`, `high`, `urgent`.
  Categories and queues are the organisation's own labels; nothing assumes one kind of academy.
- **R9 No SLA logic.** Helpdesk computes no response or resolution due times and no breaches; sla-management
  does that from the events.
- **R10 No hard dependency.** Helpdesk works when sla-management, maintenance or knowledge-base is not enabled.
- **R11 Times.** Times are stored in UTC and returned as RFC 3339 with offset.
- **R12 Test data.** No real requester data in tests or seeds.

Grievances, RTI requests and harassment complaints are not helpdesk tickets; they belong to `grievance` and
`rti`.

## Ticket lifecycle

Statuses are `new`, `in_progress`, `on_hold`, `resolved`, `closed` and `cancelled`. `closed` and `cancelled` are
final. Assignment is separate from status: assigning or unassigning never changes the status.

| Step | Who | Call | Status after | Event |
|---|---|---|---|---|
| Raise for myself | Requester | `POST /me/tickets` | `new` | `helpdesk.ticket.created` |
| Raise on someone's behalf | Agent | `POST /tickets` | `new` | `helpdesk.ticket.created` |
| Pick up, assign, unassign or move | Agent (self) or lead | `POST /tickets/{id}/assign` | unchanged | `helpdesk.ticket.assigned` |
| First public reply by an agent | Agent | `POST /tickets/{id}/comments` | `in_progress` if it was `new` | `helpdesk.ticket.responded` (once), `status-changed` if it was `new` |
| Start work | Agent | `POST /tickets/{id}/status` `in_progress` | `in_progress` (from `new` or `on_hold`) | `helpdesk.ticket.status-changed` |
| Put on hold | Agent | `POST /tickets/{id}/status` `on_hold` | `on_hold` (from `in_progress`) | `helpdesk.ticket.status-changed` |
| Requester replies while waiting on them | Requester | `POST /me/tickets/{id}/comments` | `in_progress` (from `on_hold`, `waiting_requester`) | `helpdesk.ticket.status-changed` |
| Change category or priority | Agent (own ticket, priority only) or lead | `PATCH /tickets/{id}` | unchanged | `helpdesk.ticket.reclassified` |
| Resolve | Agent | `POST /tickets/{id}/resolve` | `resolved` (from `new`, `in_progress` or `on_hold`) | `helpdesk.ticket.resolved` |
| Confirm the fix | Requester | `POST /me/tickets/{id}/confirm` | `closed` | `helpdesk.ticket.closed` |
| Not confirmed in time | Daily job | auto-close | `closed` | `helpdesk.ticket.closed` (`closed_by` null) |
| Reopen within the window | Requester | `POST /me/tickets/{id}/reopen` | `in_progress` | `helpdesk.ticket.reopened` |
| Withdraw | Requester | `POST /me/tickets/{id}/withdraw` | `cancelled` | `helpdesk.ticket.cancelled` |
| Cancel, or cancel as a duplicate | Lead | `POST /tickets/{id}/cancel` | `cancelled` | `helpdesk.ticket.cancelled` |

## 1. Support queues

**QU-1 Create a support queue.** As the org admin, I create a support queue so that tickets are routed to the
right team.
- `POST /queues` with `helpdesk:settings:manage` creates a queue with `name` (at most 80 characters, the
  organisation's own label such as IT, Academic office or Accounts help), optional `description`, `member_ids`
  (person ids of the agents in it) and `active` true by default.
- A second queue with the same name answers 409.

**QU-2 Change a queue and its members.** As the org admin, I rename a queue, change who is in it, or deactivate it.
- `PATCH /queues/{id}` with `helpdesk:settings:manage` updates `name`, `description`, `member_ids` and `active`.
- Setting `active` false on a queue that still has open tickets (`new`, `in_progress` or `on_hold`) answers 409
  and changes nothing (R4: queues are deactivated, never deleted).

**QU-3 See the queues.** As support staff or the org admin, I see the organisation's queues and how many open
tickets each has.
- `GET /queues` with `helpdesk:ticket:read` or `helpdesk:settings:manage` returns every queue of the
  organisation, not only the caller's, each with `open_count` (tickets in `new`, `in_progress` or `on_hold`).
- `?active=true` or `?active=false` filters the list.

## 2. Ticket categories

**CA-1 Create a category or sub-category.** As the org admin, I set up the categories requesters choose from,
each sending tickets to a queue with a default priority.
- `POST /categories` with `helpdesk:settings:manage` creates a category. `name` (at most 80 characters),
  `default_queue_id` and `default_priority` are required; `description` is optional and `active` is true by
  default.
- `parent_id` null makes a top-level category; a `parent_id` makes a sub-category under it.
- Only two levels: a sub-category under a sub-category answers 409.
- A second category with the same name under the same parent answers 409.

**CA-2 Change or deactivate a category.** As the org admin, I change a category's name, default queue or default
priority, or deactivate it.
- `PATCH /categories/{id}` with `helpdesk:settings:manage` updates the fields; setting `active` false
  deactivates it without deleting it (R4).
- Tickets already raised keep the queue and priority they were given.

**CA-3 Choose a category.** As a requester or support staff, I see the categories so that I can pick the right one.
- `GET /categories` with `helpdesk:self:raise`, `helpdesk:ticket:read` or `helpdesk:settings:manage` returns
  the two-level list; `?active=true` returns only active categories.

## 3. Raising tickets

**RA-1 Raise a ticket for myself.** As any signed-in person, I raise a ticket so that someone helps me with an IT,
account, administrative or document request.
- `POST /me/tickets` with `helpdesk:self:raise` and `category_id`, `title` (3 to 200 characters), `description`
  (at least 3 characters) and optional `attachment_document_ids` creates a ticket.
- The ticket gets the next per-organisation number (`HD-000123`, prefix from `HELPDESK_TICKET_NUMBER_PREFIX`),
  the category's default queue and default priority, status `new`, channel `portal`, and the caller as both
  `requester_id` and `raised_by_id`.
- Publishes `helpdesk.ticket.created` with the ticket id, number, requester, raised by, channel, category,
  queue, priority and `created_at`.
- Answers 422 when the category is inactive or there are more than `HELPDESK_MAX_ATTACHMENTS` attachments.
- Attachments are ids from `platform/documents`; helpdesk stores the ids only.
- Raising a ticket works from a phone in under a minute: category, title, description, photo (PRD,
  Non-functional). This applies to the screen where a requester raises a ticket. Whether that screen is in
  scope for issue #113 needs confirmation: the issue lists only the `helpdesk.open-by-priority` widget as
  frontend work.

**RA-2 Raise a ticket on someone's behalf.** As support staff, I raise a ticket for someone who phoned, walked in
or emailed.
- `POST /tickets` with `helpdesk:ticket:work` takes the same fields as RA-1 plus `requester_id`, `channel`
  (`portal`, `email`, `phone` or `walk_in`), optional `priority` and `assign_to_me` (false by default).
- `raised_by_id` is the agent; `requester_id` is the person the ticket is for, who then follows it under
  `/me/tickets`.
- `priority` defaults to the category's default priority. With `assign_to_me` true, the ticket is assigned to
  the caller (see open question 2 for the event and open question 3 for queue membership).
- Publishes `helpdesk.ticket.created`. Same 422 rules as RA-1.

**RA-3 Ticket numbers.** As support staff, I refer to tickets by a short number that is unique in my organisation.
- Every ticket gets the next number of its organisation's sequence; two tickets of one organisation never
  share a number, including when they are raised at the same time.
- Numbering is per organisation: the same number can exist in two organisations.

## 4. Following my own ticket

**RQ-1 See my tickets.** As a requester, I see the tickets where I am the requester, whether I raised them
myself or support staff raised them on my behalf.
- `GET /me/tickets` with `helpdesk:self:read` returns only the caller's tickets (R5), newest first, as a page
  with `next_cursor`.
- `?status=` filters by one or more statuses; `limit` is 1 to 100, default 20.

**RQ-2 Read my ticket.** As a requester, I open one of my tickets and read the replies.
- `GET /me/tickets/{id}` with `helpdesk:self:read` returns the ticket with its public replies only, oldest
  first. Internal notes and links are never returned (R5).
- `can_reopen` is true while the ticket is `resolved` and inside the reopen window.
- Another person's ticket answers 404.

**RQ-3 Reply on my ticket.** As a requester, I answer the agent's question or add information.
- `POST /me/tickets/{id}/comments` with `helpdesk:self:raise` and `body` (at least 1 character), optional
  `attachment_document_ids`, adds a public reply.
- When the ticket is `on_hold` with hold reason `waiting_requester`, the reply moves it to `in_progress` and
  publishes `helpdesk.ticket.status-changed`. In every other status the reply changes no status.
- Answers 409 when the ticket is `closed` or `cancelled`.

**RQ-4 Confirm the fix.** As a requester, I confirm that my problem is solved and say how the help was.
- `POST /me/tickets/{id}/confirm` with `helpdesk:self:raise` and optional `satisfaction_rating` (1 to 5) and
  `feedback` moves `resolved` to `closed`.
- Publishes `helpdesk.ticket.closed` with `closed_by` the requester, the rating and `closed_at`. The feedback
  text is not in the event (R7). When the ticket's own `closed_at` field is set is open question 10.
- Answers 409 when the ticket is not `resolved`.

**RQ-5 Reopen.** As a requester, I reopen a ticket that was resolved but is not fixed.
- `POST /me/tickets/{id}/reopen` with `helpdesk:self:raise` and a `reason` (at least 3 characters) moves
  `resolved` to `in_progress`.
- Allowed only within `HELPDESK_REOPEN_WINDOW_DAYS` of the resolution.
- Publishes `helpdesk.ticket.reopened` with the assignee, `reopen_count` and `reopened_at`. How the ticket's own
  `reopen_count` changes is open question 10.
- Answers 409 when the ticket is not `resolved` or the window has passed.

**RQ-6 Withdraw my ticket.** As a requester, I withdraw a ticket I no longer need.
- `POST /me/tickets/{id}/withdraw` with `helpdesk:self:raise` and a `reason` (at least 3 characters) moves
  `new`, `in_progress` or `on_hold` to `cancelled`.
- Publishes `helpdesk.ticket.cancelled` with `cancelled_by` the requester.
- Answers 409 when the ticket is already `resolved`, `closed` or `cancelled`.

## 5. Working tickets

**AG-1 See my queues' tickets.** As support staff, I see the tickets in my queues so that I can pick the next one.
- `GET /tickets` with `helpdesk:ticket:read` returns tickets in the caller's queues (R6), newest first, as a
  page with `next_cursor`; `limit` is 1 to 100, default 20.
- Filters: `status` (one or more), `priority`, `queue_id`, `category_id`, `assignee` (a person id, `me` or
  `unassigned`), `requester_id`, `q` (ticket number or title), `created_from`, `created_to`.
- `sort` is `newest` (default), `oldest` or `priority`.

**AG-2 Open a ticket.** As support staff, I open a ticket and see everything on it.
- `GET /tickets/{id}` with `helpdesk:ticket:read` returns the ticket with its public replies and internal notes,
  oldest first, and its links.
- A ticket outside the caller's queues answers 404 unless the caller has `helpdesk:ticket:read-all`.

**AG-3 Pick up a ticket.** As support staff, I take an unassigned ticket from my queue.
- `POST /tickets/{id}/assign` with `helpdesk:ticket:work` assigns an unassigned ticket in the caller's queue to
  the caller: an empty body, or `assignee_id` set to the caller without `queue_id`. The status does not change.
- Publishes `helpdesk.ticket.assigned` with the queue, the assignee, the previous assignee (null) and
  `assigned_by`. Notification tells the new assignee.
- Assigning someone else, unassigning, moving to another queue, or taking a ticket that is already assigned
  needs `helpdesk:ticket:manage` (LD-2).
- Answers 409 when the ticket is `closed` or `cancelled`, or the caller is not a member of the queue.

**AG-4 Reply to the requester.** As support staff, I reply to the requester on the ticket.
- `POST /tickets/{id}/comments` with `helpdesk:ticket:work`, `visibility: public`, `body` and optional
  `attachment_document_ids` adds a reply the requester sees.
- The first public reply by an agent on a ticket publishes `helpdesk.ticket.responded` once; later replies
  never publish it again.
- A public reply on a `new` ticket also moves it to `in_progress` and publishes `helpdesk.ticket.status-changed`.
- Answers 409 when the ticket is `closed` or `cancelled`.

**AG-5 Add an internal note.** As support staff, I add a note for other agents that the requester never sees.
- `POST /tickets/{id}/comments` with `visibility: internal` adds a note, returned on `GET /tickets/{id}` and never
  on `/me/*` (R5).
- An internal note is not a response: it publishes no `responded` event and changes no status.

**AG-6 Start work, put on hold, resume.** As support staff, I show that I am working on a ticket, or that it is
waiting on someone.
- `POST /tickets/{id}/status` with `helpdesk:ticket:work` and `status: in_progress` moves `new` or `on_hold` to
  `in_progress`.
- `status: on_hold` with a `hold_reason` (`waiting_requester`, `waiting_third_party` or `waiting_internal`) moves
  `in_progress` to `on_hold`; without a hold reason the request is rejected.
- An optional `note` is saved as a public reply to the requester. It is a public reply by an agent, so when it
  is the ticket's first one it publishes `helpdesk.ticket.responded`, as AG-4 does.
- Publishes `helpdesk.ticket.status-changed` with `from_status`, `to_status`, `hold_reason` and `changed_at`;
  sla-management pauses and resumes the resolution clock from it.
- Any other move answers 409.

**AG-7 Change the priority of my ticket.** As support staff, I raise or lower the priority of a ticket assigned to me.
- `PATCH /tickets/{id}` with `helpdesk:ticket:work` changes `title` or `priority` on a ticket assigned to the
  caller. A category change, or any change to a ticket not assigned to the caller, needs
  `helpdesk:ticket:manage` (LD-3).
- A priority change needs a `reason`, kept in the audit record, and publishes `helpdesk.ticket.reclassified` with
  the new and previous priority and category and `changed_by`.
- Answers 409 when the ticket is `resolved`, `closed` or `cancelled`.

**AG-8 Resolve a ticket.** As support staff, I resolve a ticket and tell the requester what was done.
- `POST /tickets/{id}/resolve` with `helpdesk:ticket:work` and a `resolution_note` (at least 3 characters, shown
  to the requester) moves `new`, `in_progress` or `on_hold` to `resolved`.
- A question answered at once can be resolved straight from `new`.
- Publishes `helpdesk.ticket.resolved` with the requester, `resolved_by` and `resolved_at`; notification asks the
  requester to confirm. When the ticket's own `resolved_at` field is set is open question 10.
- Answers 409 when the ticket is already `resolved`, `closed` or `cancelled`.

**AG-9 Link a ticket to another module's record.** As support staff, I record that a ticket is connected to a
maintenance work order, a knowledge-base article or an incident.
- `POST /tickets/{id}/links` with `helpdesk:ticket:work` and `module`, `entity`, `ref_id` and optional `note`
  records the reference with `created_by` and `created_at`. Helpdesk stores the reference only and never reads
  the other module.
- The same link twice answers 409.
- `DELETE /tickets/{id}/links/{link_id}` with `helpdesk:ticket:work` removes a link recorded by mistake (204);
  the removal is audited. An unknown link answers 404.
- Links appear on `GET /tickets/{id}` and never on `/me/*`.

## 6. Leading the support team

**LD-1 See every queue.** As the support lead, I see tickets across all queues.
- With `helpdesk:ticket:read-all`, `GET /tickets` and `GET /tickets/{id}` cover every queue (R6), with the same
  filters as AG-1.

**LD-2 Assign, unassign and move tickets.** As the support lead, I send a ticket to the right agent or queue.
- `POST /tickets/{id}/assign` with `helpdesk:ticket:manage`:
  - `assignee_id` only: assign within the current queue;
  - `assignee_id` null: unassign, staying in the current queue;
  - `queue_id` only: move to that queue, unassigned;
  - both: move to that queue and assign to that agent.
- The assignee must be a member of the target queue; otherwise 409 and nothing changes.
- The status never changes. Publishes `helpdesk.ticket.assigned` with the new and previous queue and assignee and
  `assigned_by`; notification tells the new assignee.
- Answers 409 when the ticket is `closed` or `cancelled`.

**LD-3 Reclassify any ticket.** As the support lead, I correct the category or priority of any ticket.
- `PATCH /tickets/{id}` with `helpdesk:ticket:manage` changes `title`, `category_id` or `priority` on any ticket
  the lead can see.
- A category or priority change needs a `reason`, kept in the audit record, and publishes
  `helpdesk.ticket.reclassified` with the previous values so SLA targets can be recalculated.
- Changing the category does not move the ticket to another queue; moving is LD-2.
- Answers 409 when the ticket is `resolved`, `closed` or `cancelled`.

**LD-4 Cancel a ticket or a duplicate.** As the support lead, I cancel a ticket raised by mistake or twice.
- `POST /tickets/{id}/cancel` with `helpdesk:ticket:manage` and a `reason` (at least 3 characters), optionally
  `duplicate_of` another open ticket, moves `new`, `in_progress` or `on_hold` to `cancelled`.
- Publishes `helpdesk.ticket.cancelled` with `cancelled_by` and `duplicate_of`; sla-management discards any clock.
- Answers 409 when the ticket is already `resolved`, `closed` or `cancelled`, or `duplicate_of` is the ticket itself.

## 7. Management oversight

**VW-1 Read-only view of every queue.** As management, I see ticket volume and backlog across every queue
without changing anything.
- With `helpdesk-viewer`, `GET /tickets`, `GET /tickets/{id}`, `GET /queues` and
  `GET /stats/open-by-priority?scope=all` work across every queue.
- Every call that changes a ticket (`POST /tickets`, `/assign`, `/comments`, `/status`, `/resolve`, `/cancel`,
  `/links`, `PATCH /tickets/{id}`) answers 403.

## 8. Support Staff dashboard widget

**WI-1 Open tickets by priority.** As support staff, I see at a glance how many open tickets are waiting, by
priority, so that I pick up the most urgent first.
- The widget `helpdesk.open-by-priority` is exported from `frontend/src/widgets/index.ts`, declares the
  permission `helpdesk:ticket:read`, and is listed on the Support Staff dashboard layout
  (`platform/identity/config/dashboards/support-staff.yaml`).
- It shows what `GET /stats/open-by-priority` returns: `total_open` and one row per priority, `urgent` first,
  with `open` (`new` + `in_progress` + `on_hold`), `unassigned`, `assigned_to_me`, `on_hold` and
  `oldest_created_at`. Priorities with no open tickets show zero counts.
- `scope` is `my_queues` by default, `mine` for tickets assigned to the caller, and `all` for every queue;
  `scope=all` without `helpdesk:ticket:read-all` answers 403. `queue_id` narrows the counts to one queue the
  caller may see.
- Each row links to the filtered ticket list.
- A lead sees the same widget with `scope=all`.
- The counts come from an index on (`organisation_id`, `status`, `priority`, `queue_id`) and never scan closed
  tickets.

## 9. System

**SY-1 Close tickets nobody confirmed.** As support staff, I do not keep resolved tickets open for ever when the
requester never answers.
- A daily job closes tickets that have been `resolved` for more than `HELPDESK_AUTO_CLOSE_DAYS`.
- Publishes `helpdesk.ticket.closed` with `closed_by` null, once per ticket.
- How the scheduler triggers the job is open question 12.

## Gaps not in the contract

The following are mentioned in the PRD as later work, so there are no stories for them in this version. Each
needs a decision first. Any change to helpdesk's API, events or permissions goes through a
`contract/helpdesk/...` PR before any code. For item 3 the PRD says only that it is "decided with the
sla-management contract (a non-breaking addition)" (PRD open question 2); whether helpdesk's own contract changes
depends on which option is chosen.

1. **A "my tickets" widget for the Student dashboard** (PRD, Users table: "later").
2. **A management widget** for volume and backlog (PRD, Users table: "later wave").
3. **SLA due times on tickets** (PRD open question 2: neither in v1).
4. **Tickets from inbound email, chat or WhatsApp**, **automatic assignment rules**, and **suggesting
   knowledge-base articles while raising a ticket** (PRD, Out of scope).

## Open questions

Questions 1 to 10 are where the PRD and the contract do not settle a rule the code needs. Questions 11 to 13
are already open in the PRD or wait on platform services.

1. **Assignee or any agent.** The contract requires only `helpdesk:ticket:work` for `POST /tickets/{id}/comments`,
   `/status` and `/resolve`. The PRD says the assignee replies, adds internal notes and resolves (main flows 4
   and 6; `events.yaml` also describes `resolved` as "The assignee resolved the ticket"), says "the agent" starts
   work and puts a ticket on hold (main flow 4), and its Users table gives all of these to Support Staff. Must
   the caller be the ticket's assignee for these actions, and may a lead act on a ticket assigned to someone
   else? Changing priority is settled: the contract and the PRD both limit `helpdesk:ticket:work` to tickets
   assigned to the caller.
2. **Assign at creation.** When an agent raises a ticket with `assign_to_me`, is `helpdesk.ticket.assigned`
   published after `helpdesk.ticket.created`? `created` carries no assignee, so sla-management cannot know it
   otherwise. sla-management PRD open question 6 says this is to be settled in the helpdesk contract, in a
   separate PR. The order in which the two events reach consumers is not guaranteed yet either (sla-management
   PRD open question on out-of-order events).
3. **Assign at creation outside the queue.** A ticket raised with `assign_to_me` goes to its category's default
   queue. For `POST /tickets/{id}/assign` the contract says "The assignee must be a member of the target queue",
   but it gives no such rule for `assign_to_me`. What happens when the agent raising the ticket is not a member
   of that queue?
4. **Inactive default queue.** What happens when a ticket is raised in an active category whose default queue is
   inactive? The contract only names an inactive category (422).
5. **Deactivating a queue that is a category's default.** The contract only blocks a queue with open tickets.
6. **Removing an agent from a queue** while tickets in that queue are assigned to them.
7. **Ticket number width.** Only the example `HD-000123` is given: six digits, zero padded, and what after
   999999?
8. **An invalid duplicate.** `duplicate_of` must be "another open ticket", but the contract names an error only
   for `duplicate_of` being the ticket itself. Which answer for a closed, cancelled or unknown ticket?
9. **Assigning a resolved ticket.** The PRD says a ticket can be assigned "in any open status"; the contract
   refuses `/assign` only for `closed` and `cancelled`. Is a `resolved` ticket assignable?
10. **Ticket time and count fields.** The `Ticket` schema lists `first_responded_at`, `resolved_at`, `closed_at`
    and `reopen_count`, and the events carry `responded_at`, `resolved_at`, `closed_at` and `reopen_count`.
    Neither the PRD nor the contract says when the ticket's own fields are set or changed, or whether they take
    the same values as the events.
11. **Audit path.** `packages/sdk` has no audit client yet and the audit write path is still open
    (`platform/audit/docs/prd.md`, open question 3). To decide with Faizan.
12. **Auto-close trigger** (PRD open question 6). The scheduler contract now says a schedule publishes
    `scheduler.job.due` for the owning module to consume, but the scheduler is not built yet. To agree with
    Himanshu.
13. **Role names** (PRD open question 4). Module roles (`helpdesk-agent` and so on) mapped to profile roles, or
    roles named after profile roles. To agree with Faizan.
