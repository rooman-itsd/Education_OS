# facility-booking: product requirements

**Owner:** Ashritha (@Ashritharooman) · **Tier:** common · **Status:** contract draft (week 1, issue #65)

## 1. Purpose

facility-booking is the **generic resource-booking pattern** of Education OS (ADR-0004). Anyone
in an organisation can find a bookable space, see when it is free, and reserve it, with an
optional approval step. The same module serves every academy type. A music academy books
practice rooms, a medical college books skills labs, a film institute books edit suites, a
hospitality institute books training kitchens.

The contract never uses a field-specific word. The thing being booked is a **resource**, the
reservation is a **booking**, and the words people see come from the profile vocabulary:

| Profile | `facility-booking.resource` |
|---|---|
| music-academy | Practice room |
| medical-college | Lab / skills room |
| film-media-institute | Edit suite / studio |
| hospitality-institute | Training kitchen / lab |
| engineering-college | Laboratory |

## 2. Scope

**In scope**
- Register of bookable resources, grouped into organisation-defined resource types
- Opening hours, closures (blackouts) and booking rules per resource
- Free/busy availability for a date range
- Bookings: single or recurring, for oneself or on behalf of someone else
- Optional approval step, set per resource
- Conflict prevention: a resource is never double-booked beyond its concurrency
- Check-in and no-show recording
- Bookings created by other modules through the API (for example a rehearsal from
  productions), tagged with the source

**Out of scope**
- Sports grounds, courts, pools and gyms: these belong to `sports-facilities` (Akshata), which may
  call this module's API to book them
- Fixed asset register and depreciation: `asset-management`
- Repairs and work orders: `maintenance`. It can take a resource out of service through the status endpoint
- Lending movable items: `inventory-equipment`
- Class timetables: `timetable-attendance`. It may reserve rooms here through the API
- Charging fees for bookings: not in v1

## 3. Users and roles

| Who | What they do | Default module role |
|---|---|---|
| Learner (student and each academy's learner role) | Find a free resource, book it, see and cancel own bookings | `facility-booking-user` |
| Instructor (faculty and each academy's instructor role) | Book for self or a group, recurring bookings | `facility-booking-user` |
| Approver (HoD, lab in-charge, studio instructor) | Approve or reject pending bookings for resources they look after | `facility-booking-approver` |
| Facility / Inventory Staff | Manage resources, hours, closures; see every booking; check-in and no-show; override | `facility-booking-manager` |
| Organisation Admin | Grants the roles above through identity | n/a |

The academy profile maps its roles to these module roles. The dashboard shell hides any widget
whose permission the viewer lacks.

## 4. Main concepts

| Concept | Meaning |
|---|---|
| **ResourceType** | An organisation-defined category, named in the organisation's own words. Has a name, an optional colour and default rules. |
| **Resource** | One bookable thing: name, type, location text, capacity, attributes (free key/value, e.g. `projector: yes`), status, booking rules, approver user ids. |
| **OpeningHours** | Weekly opening hours of a resource (weekday, opens, closes). No entries means open at all times. |
| **Blackout** | A closure window (holiday, exam, repair). Nothing can be booked inside it. |
| **Booking** | One reservation of one resource for a time window, with a status. |
| **BookingSeries** | A recurrence (daily or weekly, until a date or a count) that produced several bookings. |

Every record carries `organisation_id`. All ids are UUIDs. People are referenced by identity user
id only. There are no foreign keys to other modules' tables.

## 5. Booking lifecycle

```
            requires_approval = true            requires_approval = false
create ──► pending ──approve──► confirmed ◄──────────── create
              │                    │
            reject              check-in ──► checked_in ──► completed (end time passes)
              ▼                    │
           rejected           no check-in within grace ──► no_show
   pending/confirmed ──cancel──► cancelled
```

Statuses: `pending`, `confirmed`, `rejected`, `cancelled`, `checked_in`, `completed`, `no_show`.

## 6. Business rules

1. **No double booking.** Pending, confirmed and checked-in bookings count against a resource. A
   new or moved booking that would exceed `max_concurrent_bookings` (default 1) is refused with
   409 and the clashing windows. Pending bookings hold the slot, so two people cannot both
   wait for approval on the same slot.
2. **Opening hours and closures.** A booking must fit inside the resource's opening hours and
   must not overlap a blackout (422).
3. **Booking rules per resource:** `min_duration_minutes`, `max_duration_minutes`,
   `slot_minutes` (start and end align to it), `max_days_ahead`, `buffer_minutes` (gap kept
   after each booking), `requires_approval`, `check_in_required`, `bookable_role_ids` (empty
   means anyone with `facility-booking:booking:create`). A missing rule falls back to the
   resource type's default, then to the organisation default from config.
4. **Approval.** Only a user listed as the resource's approver, or a holder of
   `facility-booking:booking:manage`, may approve or reject. Rejecting needs a reason.
5. **Rescheduling** re-runs every check. If the resource requires approval, a confirmed booking goes
   back to `pending`.
6. **Cancellation.** The booker may cancel their own booking before it starts. Managers may cancel
   any booking at any time and must give a reason.
7. **Recurring bookings** are created all-or-nothing by default. With `skip_conflicts: true`, clashing
   occurrences are skipped and returned in the response. A series has at most
   `FACILITY_BOOKING_MAX_SERIES_OCCURRENCES` occurrences.
8. **Check-in and no-show.** Only for resources with `check_in_required: true`. If a booking is
   not checked in within `FACILITY_BOOKING_NO_SHOW_GRACE_MINUTES` of its start, the scheduler
   marks it `no_show`.
9. **Resource out of service.** Setting a resource to `inactive` or `under_maintenance` blocks new
   bookings. Existing future bookings are returned in the response so staff can move or cancel
   them. They are never cancelled silently. Adding a blackout works the same way.
10. **Privacy of busy slots.** Availability shows that a slot is busy. Who holds it is shown only to
    holders of `facility-booking:booking:read-all`.
11. **Tenant isolation.** Every table has `organisation_id` and a row-level-security policy on
    `app.organisation_id`. Every event carries `organisation_id`.
12. **Audit.** Every state change (resource created or changed, status changed, blackout added,
    booking created, approved, rejected, rescheduled, cancelled, checked in, no-show) is written to
    audit through `packages/sdk`.

## 7. Dashboard widgets

26 role layouts in `platform/identity/config/dashboards/` use these widgets (27 dashboards in the
plan):

| Widget id | Layouts | Shows | API |
|---|---|---|---|
| `facility-booking.my-bookings` | 10 learner roles, and the Faculty layout with the 15 instructor layouts that extend it | The viewer's upcoming bookings, with cancel and check-in | `GET /bookings?scope=mine&from=now` |
| `facility-booking.bookings-today` | 14 staff and instructor roles, incl. facility-staff | Today's bookings for the resources the viewer manages or approves, with counts | `GET /bookings?scope=managed&date=today`, `GET /summary` |
| `facility-booking.bookings` | coach, medical-staff | Upcoming bookings on the resources the viewer approves, any date (their own bookings are in `my-bookings`) | `GET /bookings?scope=managed&from=now` |

Widget titles use the vocabulary term (for example "My practice room bookings" in a music academy).
Each `Booking` carries a `can` list of the actions the viewer may take, so widgets need no
permission logic of their own.

## 8. Integration points

- **Platform services (through `packages/sdk`):** identity (users, permission checks), audit
  (state changes), notification (booking requested, confirmed, rejected, cancelled, reminders),
  scheduler (no-show sweep, completion, reminders), documents (optional resource image).
- **Events published:** see `contracts/events.yaml`. Expected consumers: notification (messages),
  timetable-attendance and productions (status of bookings they made), reporting.
- **Events consumed:** none in v1. Once the maintenance contract is merged, this module may
  subscribe to its work-order events to set a resource to `under_maintenance`. Until then,
  maintenance staff use the status endpoint.
- **Other modules booking here** call `POST /bookings` with `source: { module, entity, id }` and
  filter `facility-booking.booking.*` events by that source.

## 9. Configuration

Organisation-wide defaults, overridable per resource type and per resource. Listed in
`config/env.example`: `FACILITY_BOOKING_MAX_DAYS_AHEAD`, `FACILITY_BOOKING_DEFAULT_SLOT_MINUTES`,
`FACILITY_BOOKING_NO_SHOW_GRACE_MINUTES`, `FACILITY_BOOKING_MAX_SERIES_OCCURRENCES`,
`FACILITY_BOOKING_REMINDER_MINUTES_BEFORE`.

## 10. Non-functional

- Availability for one resource over 7 days returns in under 300 ms at p95.
- The conflict check and the insert run in one transaction with a lock per resource, so two
  simultaneous requests for the same slot cannot both succeed.
- Times are stored in UTC and sent as RFC 3339 with offset. Opening hours are local times in the
  organisation's time zone.

## 11. Open questions (for review)

1. Approvers per resource (this draft) or per resource type?
2. Do sports-facilities grounds book through this module's API, or keep their own calendar?
   To agree with Akshata before this contract merges.
3. Should a no-show count limit future bookings (e.g. three no-shows block booking for a week)? Not in v1 unless asked.
