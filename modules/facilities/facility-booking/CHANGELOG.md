# Changelog — facility-booking

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contract draft: resource-booking API, events and permissions; PRD (#65).
- Backend (#108): domain rules (conflicts with buffer and concurrency, opening hours, closures, slot grid,
  recurrence, availability), use cases for resource types, resources, opening hours, closures, bookings with
  approval, reschedule, cancel, check-in, no-show, series cancel and widget summary; outbox events for every
  state change; scheduler sweeps; API router for every path in the contract.
- Alembic chain `fb_0001`: six `facility_booking_*` tables with `organisation_id`, RLS policy on Postgres.
- Tests: domain unit tests, API integration tests, cross-tenant leak test, migration test (29 passing).
- `docs/user-stories.md`; `FACILITY_BOOKING_TIMEZONE` config key.
- Widget `facility-booking.bookings-today` (#6, Facility / Inventory Staff dashboard): today's bookings on the
  resources the viewer manages or approves, earliest first, with a counts line (GET /bookings?scope=managed&date=today,
  GET /summary); loading, empty and error states following the widget error convention; typed API client in
  `frontend/src/api/client.ts`; an overnight booking that overlaps today shows its date, and with nothing booked the
  counts stay visible while requests await approval or resources are out of service; vitest widget tests (10 passing).
- Contract: the `facility-staff` profile role gets the grants of `facility-booking-manager`, so the Facility / Inventory
  Staff dashboard (#6) can read this module's data.
- Contract: the academy profile roles whose dashboards show this module's widgets get the grants of the module role
  the PRD names for them (follow-up to #288 from Faizan's review; part of #331).
- Widgets `facility-booking.bookings` (coach and medical-staff dashboards) and `facility-booking.my-bookings` (ten
  learner and performer dashboards), part of #331: bookings not yet over on the resources the viewer approves, or the
  viewer's own, earliest first with day, time window and status in words (GET /bookings?scope=managed|mine&from=now);
  one shared list with loading, empty and error states; status words shared with bookings-today; 13 new vitest tests.
