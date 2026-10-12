# hostel: product requirements

Owner: Tejaswini (@tejaswini-rooman) · Status: draft for review · Issue #67
Suite F, Campus life · tier `common` (every academy type enables it)

## Purpose

Residential life on campus: hostels, rooms and beds, allocation of residents, check-in and check-out,
the mess menu, visitors, leave (out-pass) requests, discipline incidents and notices to residents.
Hostel fees are not charged here; hostel publishes allocation events that fees-accounts may use to
raise invoices. The contract is `contracts/openapi.yaml`, `events.yaml` and `permissions.yaml`.

## Users and what they need

| Role | Needs | Dashboard widget |
|---|---|---|
| Student (resident) | Request a room, see the allocation, read hostel notices and the mess menu, apply for leave, see own visitors | `hostel.notices` (`GET /me/notices`) |
| Warden | Allocate rooms, check residents in and out, approve leave, record incidents, publish notices | — (later wave) |
| Hostel office (admin) | Set up hostels and rooms, run allocation for a year, occupancy reports | — (later wave) |
| Security desk | Record visitors in and out; see approved gate passes and record residents leaving and returning | — |
| Management, org admin | Occupancy overview, read only | — |

## Main flows

1. **Set up.** The hostel office creates hostels (name, occupancy type such as men, women or mixed, warden)
   and rooms (number, floor, room type, capacity in beds). A room can be closed for maintenance; its beds
   are then not allocatable.
2. **Request a room.** A student requests a room for an academic year with a preferred room type and
   optional notes. One open request per person per academic year.
3. **Allocate.** The office or a warden allocates a bed to a request, or directly to a person. A bed holds
   one active allocation for any date; an allocation never exceeds room capacity. Publishes
   `hostel.allocation.confirmed`, which carries what fees-accounts needs to raise a hostel fee invoice.
4. **Check in and check out.** The warden records the check-in (`hostel.allocation.occupied`) and the
   check-out with the room's condition (`hostel.allocation.vacated`). An allocation can be cancelled
   before check-in, with a reason. A room change is a check-out from one bed and a new allocation.
5. **Mess menu.** The office publishes the menu per hostel per day and meal. Residents read it.
6. **Leave and gate pass.** A leave request is the gate pass, from a few hours to several days. A resident
   applies with dates, destination and reason, and may withdraw it before it is decided. The warden approves
   or rejects it. At the gate, security sees the approved passes, records the resident leaving
   (`approved -> out`, `hostel.leave.departed`) and coming back (`out -> returned`, `hostel.leave.returned`).
   Where no security desk records it, the warden marks the return. A daily job flags residents on approved or
   out leave who are not back by the end (`hostel.leave.overdue`).
7. **Visitors.** The security desk records a visitor against a resident, with time in and time out.
   A resident sees their own visitor log.
8. **Discipline.** A warden records an incident against a resident with category, description and
   action taken, and closes it later. Incidents are visible only to wardens and the hostel office.
9. **Notices.** Wardens and the office publish notices to one hostel or to every hostel, with an optional
   expiry. A resident sees notices for their hostel plus notices to every hostel; a student with no
   allocation sees only the latter.

## Rules

- Every table carries `organisation_id` with row-level security; every event carries `organisation_id`.
- Every state change writes an audit record through `packages/sdk`.
- A person sees only their own allocation, leave, visitors and notices (`/me/*`); staff access needs the
  permission in `permissions.yaml`. Every student gets the self-service permissions through the profile role
  `student`; no hostel-specific role is needed.
- Incidents are personal data with restricted access (`hostel:incident:read`); they are never in an event payload.
- Nothing is deleted: allocations are cancelled or vacated, leave is withdrawn or rejected, notices expire.
- No real resident data in tests or seeds.
- No dependency on another module being enabled: if fees-accounts is off, hostel works without fee invoices.

## Data model (summary)

| Entity | Key fields |
|---|---|
| Hostel | id, name, occupancy_type, warden_ids, active |
| Room | id, hostel_id, number, floor, room_type, capacity, status (open, closed) |
| Allocation | id, person_id, room_id, bed, academic_year, from, to, status (requested, confirmed, occupied, vacated, cancelled) |
| MessMenu | hostel_id, date, meal, items |
| LeaveRequest | id, person_id, from, to, destination, reason, status (requested, approved, rejected, withdrawn, out, returned), departed_at, returned_at |
| Visit | id, hostel_id, person_id (resident), visitor_name, relation, in_at, out_at |
| Incident | id, person_id, hostel_id, occurred_at, category, description, action_taken, status (open, closed) |
| Notice | id, hostel_id (null = every hostel), title, body, published_at, expires_at |

## Integration points

| Direction | With | How |
|---|---|---|
| Publishes | fees-accounts and anyone | `hostel.allocation.confirmed`, `occupied`, `vacated`, `cancelled` and the rest of `events.yaml` |
| Platform | identity, audit, notification, scheduler | through `packages/sdk` (notices and leave decisions notify; the daily overdue-return job) |
| References | student-information | `person_id` by id; names cached from its events |

## Out of scope

- Charging and collecting hostel and mess fees (fees-accounts).
- Mess inventory, procurement and vendor payments (inventory-equipment, procurement).
- Room repairs (maintenance) and staff payroll (hr-payroll).
- Guest-house or conference room booking (facility-booking).

## Open questions (for review)

1. Does fees-accounts want to raise the hostel invoice from `hostel.allocation.confirmed`, and is the payload
   (person, hostel, room type, academic year, dates) enough? To agree with Gokula Lakshmi.
2. Should residents see the visitor log, or only staff? Proposed: residents see their own.
3. Is a mess opt-in per resident needed (some residents eat outside), or is the menu enough for wave A?
4. Field learner roles (`medical-student`, `athlete`, ...): do those users also hold `student`? If not, should
   hostel grant self-service to them too? To agree with Faizan.
5. Gate pass: may security record a departure before the pass's `from` time, or after its `to` time has passed?
   Proposed: no limit in wave A; the overdue job covers late returns.
