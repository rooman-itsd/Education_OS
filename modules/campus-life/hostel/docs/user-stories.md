# hostel: user stories

Owner: Tejaswini (@tejaswini-rooman) · Status: draft for review · Issue #110

Stories by role for the hostel module. Each story follows `prd.md` and is bounded by the contract in
`contracts/openapi.yaml`, `events.yaml` and `permissions.yaml`; where a need is not in the contract it is
listed under [Gaps](#gaps-not-in-the-contract) instead of being written as a story. Paths are relative to
`/api/v1/hostel`.

## Roles

| Role (`permissions.yaml`) | Who | Grants |
|---|---|---|
| `student` (profile role) | Every student; identity gives new users this role by default | `self:read`, `self:request` |
| `hostel-resident` | Residents who are not students, for example staff living in | `self:read`, `self:request` |
| `hostel-warden` | Warden of one or more hostels | `hostel:read`, `allocation:read`, `allocation:manage`, `leave:approve`, `gate:record`, `visitor:read`, `visitor:record`, `incident:read`, `incident:manage`, `notice:publish` |
| `hostel-admin` | Hostel office | `hostel:read`, `hostel:manage`, `allocation:read`, `allocation:manage`, `mess:manage`, `leave:approve`, `visitor:read`, `incident:read`, `incident:manage`, `notice:publish` |
| `hostel-security` | Security desk | `hostel:read`, `gate:record`, `visitor:read`, `visitor:record` |
| `hostel-viewer` | Management and org admin, read only | `hostel:read`, `allocation:read` |

Wherever a story says "resident" or "student", the caller holds `student` or `hostel-resident`; both carry the
same two self-service keys and every endpoint behind them is limited to the caller's own records.

All keys above are short for `hostel:<resource>:<action>`. A call without the permission named for its
endpoint is refused with 403 and changes nothing.

## Rules every story inherits

These apply to every story below and are tested once per endpoint, not repeated in each story.

- **R1 Tenant isolation.** Every record carries `organisation_id` and is protected by row-level security.
  A user sees and changes only their own organisation's records; another organisation's record is never
  listed and a request for it by id answers 404. The cross-tenant leak test from `eos_testing` passes for
  every table.
- **R2 Events carry the tenant.** Every published event carries `organisation_id`.
- **R3 Audit.** Every state change writes an audit record through `packages/sdk`, with the actor.
- **R4 Nothing is deleted.** Allocations are cancelled or vacated, leave is withdrawn or rejected, notices
  expire or are withdrawn, rooms are closed, hostels are deactivated.
- **R5 Own data only.** `/me/*` returns only the caller's own allocation, leave, visitors and notices.
- **R6 Personal data.** Incidents and visitor records are never in an event payload; they go to audit only.
- **R7 No hard dependency.** Hostel works when fees-accounts is not enabled; allocations simply raise no invoice.
- **R8 Test data.** No real resident data in tests or seeds.

## 1. Hostels and rooms

**HR-1 Create a hostel.** As the hostel office, I create a hostel so that rooms and residents can be managed in it.
- `POST /hostels` with `hostel:hostel:manage` creates a hostel with `name`, `occupancy_type` (an
  organisation label such as men, women or mixed), optional `warden_ids`, and `active` true by default.
- `name` and `occupancy_type` are required; a request without them is rejected.

**HR-2 Update or deactivate a hostel.** As the hostel office, I change a hostel's name, occupancy type or
wardens, or deactivate it.
- `PATCH /hostels/{id}` with `hostel:hostel:manage` updates the fields; setting `active` false deactivates
  the hostel without deleting it (R4).
- `GET /hostels?active=true` lists only active hostels.

**HR-3 See hostels and occupancy.** As hostel staff or management, I see each hostel and how full it is.
- `GET /hostels` and `GET /hostels/{id}` need `hostel:hostel:read` (granted to every staff role).
- `GET /hostels/{id}` returns the number of rooms, beds, beds occupied, and beds confirmed but not yet checked in.
- An unknown id, or another organisation's hostel, answers 404.

**HR-4 Add a room.** As the hostel office, I add rooms to a hostel.
- `POST /hostels/{id}/rooms` with `hostel:hostel:manage` creates a room with `number`, optional `floor`,
  `room_type` (an organisation label such as single, double or dormitory) and `capacity` of at least 1.
- A second room with the same number in the same hostel answers 409.

**HR-5 Change a room.** As the hostel office, I change a room's type or capacity.
- `PATCH /rooms/{id}` with `hostel:hostel:manage` updates `room_type` and `capacity`.
- Lowering `capacity` below the room's current occupancy answers 409 and changes nothing.

**HR-6 Close and reopen a room.** As the hostel office, I close a room for maintenance so that nobody is
allocated to it, and reopen it afterwards.
- Setting `status` to `closed` requires a `reason` and publishes `hostel.room.closed` with the room, hostel and reason.
- While a room is closed, its free beds cannot be allocated: direct allocation and confirmation to it answer 409.
- Setting `status` to `open` publishes `hostel.room.reopened`, and its free beds are allocatable again.

**HR-7 Find free beds.** As a warden or the hostel office, I find rooms with free beds so that I can allocate quickly.
- `GET /hostels/{id}/rooms` with `hostel:hostel:read` lists rooms with their `free_beds`.
- `?status=open|closed` and `?has_free_bed=true` filter the list.

## 2. Room requests and allocation

**AL-1 Request a room.** As a student, I request a hostel room for an academic year.
- `POST /me/room-requests` with `hostel:self:request` creates an allocation in status `requested` with
  `academic_year` and optional `preferred_hostel_id`, `preferred_room_type` and `notes`.
- Publishes `hostel.allocation.requested`.
- A second open request, or a request when an allocation already exists for that year, answers 409.

**AL-2 Cancel my own request.** As a student, I cancel my room request before it is allocated.
- `POST /allocations/{id}/cancel` with `hostel:self:request` cancels the caller's own request with a
  `reason` of at least 3 characters; status becomes `cancelled`.
- Publishes `hostel.allocation.cancelled` with `was_confirmed` false.
- A resident cannot cancel another person's request.

**AL-3 See requests and allocations.** As a warden, the hostel office or management, I see room requests
and allocations.
- `GET /allocations` with `hostel:allocation:read` returns a page of allocations with `next_cursor`.
- Filters: `status`, `hostel_id`, `academic_year`, `person_id`; `limit` is 1 to 100, default 20.
- `GET /allocations/{id}` returns one allocation, or 404.

**AL-4 Allocate a bed to a request.** As a warden or the hostel office, I allocate a bed to a student's request.
- `POST /allocations/{id}/confirm` with `hostel:allocation:manage`, a `room_id` and a `bed` (optional
  `from` and `to`) moves the allocation from `requested` to `confirmed`.
- Publishes `hostel.allocation.confirmed` with person, hostel, room, room type, academic year and dates.
- Answers 409 when the allocation is not `requested`, the bed is taken, or the room is closed.

**AL-5 Allocate a bed directly.** As a warden or the hostel office, I allocate a bed to a person who made no request.
- `POST /allocations` with `hostel:allocation:manage` and `person_id`, `room_id`, `bed`, `academic_year`,
  `from` and `to` creates a `confirmed` allocation and publishes `hostel.allocation.confirmed`.
- Answers 409 when the bed is taken, the room is closed, or the person is already allocated for the period.

**AL-6 Capacity is never exceeded.** As the hostel office, I rely on the system to never double-book a bed.
- A bed holds at most one active allocation for any date.
- A room never holds more active allocations than its capacity, including when two allocations are made at the same time.

**AL-7 Check a resident in.** As a warden, I record that the student has moved in.
- `POST /allocations/{id}/check-in` with `hostel:allocation:manage` moves `confirmed` to `occupied` and
  records `checked_in_at`.
- Publishes `hostel.allocation.occupied`.
- Answers 409 when the allocation is not `confirmed`.

**AL-8 Check a resident out.** As a warden, I record that the resident has left the room and its condition.
- `POST /allocations/{id}/check-out` with `hostel:allocation:manage` and optional `condition_notes` moves
  `occupied` to `vacated` and records `checked_out_at`; the bed is free again.
- Publishes `hostel.allocation.vacated`.
- Answers 409 when the allocation is not `occupied`.

**AL-9 Cancel an allocation before check-in.** As a warden or the hostel office, I cancel a request or a
confirmed allocation that will not be taken up.
- `POST /allocations/{id}/cancel` with `hostel:allocation:manage` and a `reason` sets status `cancelled`
  and stores `cancel_reason`.
- Publishes `hostel.allocation.cancelled`; `was_confirmed` tells fees-accounts whether an invoice may need cancelling.
- Answers 409 when the allocation is already `occupied`, `vacated` or `cancelled`.

**AL-10 Change a resident's room.** As a warden, I move a resident to another room.
- A room change is a check-out from the current bed (AL-8) followed by a new allocation (AL-5) and check-in
  (AL-7); there is no separate move operation.

**AL-11 See my room.** As a student, I see my hostel room or my pending request.
- `GET /me/allocation` with `hostel:self:read` returns the caller's current or upcoming allocation and open
  room request, if any, with its hostel.
- With neither, `allocation` and `hostel` are null.

## 3. Mess menu

**ME-1 Set the mess menu.** As the hostel office, I publish what each hostel's mess serves.
- `PUT /mess-menus` with `hostel:mess:manage` sets the items for each hostel, date and meal given (meal is
  an organisation label such as breakfast, lunch, snacks or dinner).
- What was set before for the same hostel, date and meal is replaced, not duplicated.

**ME-2 Read the mess menu.** As a resident or hostel staff, I see what the mess serves.
- `GET /mess-menus?hostel_id=&from=&to=` with `hostel:hostel:read` or `hostel:self:read` returns the menu
  for that hostel and date range; all three parameters are required.

## 4. Leave and gate passes

In this module a leave request is the gate pass, including a short day pass: `from` and `to` are date-times,
so a pass for a few hours on one day is a leave request like any other. Residents apply, wardens approve, and
security records the departure and the return. Statuses are `requested`, `approved`, `rejected`, `withdrawn`,
`out` and `returned`.

### Lifecycle

| Step | Who | Call | Status after | Event |
|---|---|---|---|---|
| Apply | Resident | `POST /me/leave-requests` | `requested` | `hostel.leave.requested` |
| Withdraw (before a decision) | Resident | `POST /me/leave-requests/{id}/withdraw` | `withdrawn` | none |
| Approve | Warden or office | `POST /leave-requests/{id}/decision` `approved` | `approved` | `hostel.leave.approved` |
| Reject | Warden or office | `POST /leave-requests/{id}/decision` `rejected` | `rejected` | `hostel.leave.rejected` |
| Leaves through the gate | Security (or warden) | `POST /leave-requests/{id}/gate-out` | `out` | `hostel.leave.departed` |
| Comes back through the gate | Security (or warden) | `POST /leave-requests/{id}/gate-in` | `returned` | `hostel.leave.returned` |
| Back, not recorded at the gate | Warden or office | `POST /leave-requests/{id}/return` | `returned` | `hostel.leave.returned` |
| Not back by `to` | Daily job | scheduler | unchanged (`approved` or `out`) | `hostel.leave.overdue` (once) |

**LV-1 Apply for leave or a day pass.** As a resident, I apply to leave the hostel so that the warden knows
where I am going and when I will be back.
- `POST /me/leave-requests` with `hostel:self:request` and `from`, `to`, `destination`, `reason`, optional
  `contact_phone` creates a request in status `requested` against the caller's hostel.
- Publishes `hostel.leave.requested`; notification tells the warden.
- Answers 409 when the caller is not a current resident, or the dates overlap another of their leave requests.

**LV-2 Withdraw my request.** As a resident, I withdraw a leave request I no longer need.
- `POST /me/leave-requests/{id}/withdraw` with `hostel:self:request` sets `withdrawn`.
- Answers 409 once the request has been approved or rejected.

**LV-3 See my leave.** As a resident, I see my leave requests and their decisions.
- `GET /me/leave-requests` with `hostel:self:read` returns only the caller's requests, newest first, with
  status, `decision_reason` and `returned_at`.

**LV-4 Review leave requests.** As a warden or the hostel office, I see leave requests waiting for a decision.
- `GET /leave-requests` with `hostel:leave:approve` or `hostel:gate:record` returns a page; filters `status`
  and `hostel_id`.
- Viewer and resident roles cannot list leave requests (403).

**LV-5 Approve leave.** As a warden, I approve a leave request.
- `POST /leave-requests/{id}/decision` with `decision: approved` and optional `reason` sets `approved` and
  records `decided_by`.
- Publishes `hostel.leave.approved`; notification tells the resident.
- Answers 409 when the request is not `requested`.
- Nobody can decide their own leave request, even with `hostel:leave:approve`.

**LV-6 Reject leave.** As a warden, I reject a leave request and say why.
- `decision: rejected` with optional `reason` sets `rejected`, records `decided_by` and `decision_reason`.
- Publishes `hostel.leave.rejected`; notification tells the resident.
- Same 409 and own-request rules as LV-5.

**LV-7 Mark the return.** As a warden, I record that a resident is back when the gate did not record it, for
example in a hostel without a security desk.
- `POST /leave-requests/{id}/return` with `hostel:leave:approve` moves `approved` or `out` to `returned`, and
  records `returned_at` and `return_recorded_by`.
- Publishes `hostel.leave.returned`.
- Answers 409 when the leave is neither `approved` nor `out`.

**LV-8 Flag residents not back.** As a warden, I am told when a resident has not returned on time.
- A daily scheduler job finds `approved` or `out` leave whose `to` has passed with no return and publishes
  `hostel.leave.overdue` once per leave, never twice for the same leave.
- `GET /leave-requests?overdue=true` lists that leave; security can see it too.
- Recording the return later (GP-3 or LV-7) still works for an overdue leave.

**GP-1 See who may leave.** As the security desk, I see the approved gate passes so that I let out only
residents who hold one.
- `GET /leave-requests?status=approved` with `hostel:gate:record` lists approved passes; `?status=out` lists
  residents who are away.
- Security cannot approve or reject a pass (403 on `/decision`).

**GP-2 Record a departure.** As the security desk, I record a resident leaving through the gate.
- `POST /leave-requests/{id}/gate-out` with `hostel:gate:record` moves `approved` to `out` and records
  `departed_at` and `departure_recorded_by`.
- Publishes `hostel.leave.departed` with the leave, person, hostel and `departed_at`.
- Answers 409 when the pass is not `approved` (requested, rejected, withdrawn, already out or returned).
- Once `out`, the resident can no longer withdraw the pass, and a new leave over the same dates is refused (409).

**GP-3 Record a return.** As the security desk, I record a resident coming back through the gate.
- `POST /leave-requests/{id}/gate-in` with `hostel:gate:record` moves `out` to `returned` and records
  `returned_at` and `return_recorded_by` (which may be a different guard from the one at departure).
- Publishes `hostel.leave.returned`.
- Answers 409 when the leave is not `out`.

**GP-4 Gate roles.** As the hostel, I let only the gate record movements.
- `hostel:gate:record` is held by `hostel-security` and `hostel-warden`. Residents, the viewer and the hostel
  office get 403 on `gate-out` and `gate-in`.

## 5. Visitors

**VI-1 Record a visitor arriving.** As the security desk, I log a visitor coming to see a resident.
- `POST /visits` with `hostel:visitor:record` and `person_id` (the resident), `visitor_name`, optional
  `relation` and `id_document_note` records `in_at`, the resident's hostel and `recorded_by`.
- `id_document_note` holds the document type and last digits only, never the full number.
- Answers 409 when the person is not a current resident.

**VI-2 Record a visitor leaving.** As the security desk, I log when the visitor leaves.
- `POST /visits/{id}/out` with `hostel:visitor:record` records `out_at`.
- Answers 409 when the visitor is already out.

**VI-3 See the visitor log.** As a warden, the hostel office or security, I see who visited.
- `GET /visits` with `hostel:visitor:read` returns a page; filters `hostel_id`, `person_id`, `date`.
- Visits are never published as events (R6).

**VI-4 See my visitors.** As a resident, I see the visitors recorded for me.
- `GET /me/visits` with `hostel:self:read` returns only visits where the caller is the resident.

## 6. Discipline incidents

**IN-1 Record an incident.** As a warden or the hostel office, I record a discipline incident against a resident.
- `POST /incidents` with `hostel:incident:manage` and `person_id`, `occurred_at`, `category` (from the
  organisation's hostel rules), `description`, optional `action_taken` creates an `open` incident with the
  resident's hostel and `recorded_by`.

**IN-2 Update or close an incident.** As a warden or the hostel office, I record the action taken and close the incident.
- `PATCH /incidents/{id}` with `hostel:incident:manage` updates `action_taken` or sets `status` to `closed`,
  recording `closed_at`.

**IN-3 Restricted access.** As a resident, I trust that incidents about me are seen only by those who need to.
- `GET /incidents` needs `hostel:incident:read` (warden and office only); filters `hostel_id`, `person_id`, `status`.
- Security, viewer and resident roles get 403; there is no `/me` endpoint for incidents.
- Incidents are never in an event payload (R6).

## 7. Notices

**NO-1 Publish a notice.** As a warden or the hostel office, I publish a notice to residents.
- `POST /notices` with `hostel:notice:publish` and `title` (at most 120 characters), `body`, optional
  `hostel_id` and `expires_at` creates a `current` notice with `published_at` and `published_by`.
- `hostel_id` null sends the notice to every hostel.
- Publishes `hostel.notice.published`; notification may alert residents.

**NO-2 Withdraw a notice.** As a warden or the hostel office, I withdraw a notice that is wrong or no longer applies.
- `POST /notices/{id}/withdraw` with `hostel:notice:publish` sets status `withdrawn`; it is no longer shown to residents.

**NO-3 Notices expire.** As a resident, I see only notices that still apply.
- A notice whose `expires_at` has passed has status `expired` and is not shown to residents.

**NO-4 See all notices.** As a publisher, I see notices I and others have published, including old ones.
- `GET /notices` with `hostel:notice:publish` returns current, expired and withdrawn notices; filter `hostel_id`.

**NO-5 Read my notices.** As a student, I read the notices that apply to me.
- `GET /me/notices` with `hostel:self:read` returns current notices only: those for the caller's hostel plus
  those for every hostel, newest first. `limit` is 1 to 100, default 20.
- A student with no allocation sees only the notices for every hostel.
- Notices for another hostel, and expired or withdrawn notices, are never returned.

## 8. Student dashboard widget

**WI-1 Hostel notices on my dashboard.** As a student, I see hostel notices on my dashboard without opening the hostel module.
- The widget `hostel.notices` is exported from `frontend/src/widgets/index.ts` and is listed on the Student
  dashboard layout.
- It shows what `GET /me/notices` returns (NO-5), newest first, and declares the permission `hostel:self:read`.
- With no notices it shows an empty state, not an error.

## Gaps not in the contract

The following were asked for but are not in the PRD or the contract, so there are no stories for them. Each needs
a decision, and if accepted a `contract/hostel/...` PR first, before any code.

Gate-out and gate-in by security were gaps until contract 0.2.0 added them (GP-1 to GP-4).

1. **A separate day-pass type.** There is no distinction between a day pass and longer leave; both are leave
   requests with date-times. A type field, different approval rules or a same-day return deadline would need
   contract changes.
2. **Check-in after leave.** Returning from leave is `returned` on the leave request; the allocation stays
   `occupied` throughout. The allocation check-in (AL-7) is only for moving in.
3. **Gate timing.** Security may record a departure before the pass's `from` or after its `to` (PRD question 5,
   proposed: no limit in wave A).

## Open questions

1. **Warden scope.** `hostel-warden` is "warden of one or more hostels" and hostels carry `warden_ids`, but the
   contract does not say whether a warden may act only on their own hostels. Proposed: yes, enforced in the
   application layer. To confirm with Faizan.
2. **"Current resident".** Leave (LV-1) and visits (VI-1) need a current resident. Proposed: a person with an
   `occupied` allocation today. To confirm.
3. **Fee payload** (PRD question 1). Whether `hostel.allocation.confirmed` carries enough for fees-accounts. To
   agree with Gokula Lakshmi.
4. **Mess opt-in** (PRD question 3). Not in wave A unless the PRD changes.
5. **Field learner roles** (PRD question 4). Whether `medical-student`, `athlete` and the other field roles also
   hold `student`. To agree with Faizan.
