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
