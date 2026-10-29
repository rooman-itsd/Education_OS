# Changelog — maintenance

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contract draft: tickets, assignment, SLA, work log and preventive schedules API, events and permissions; PRD (#65).
- Backend (#126): domain rules (ticket lifecycle, SLA due times paused on hold, breach detection, reopen window,
  duplicate guard, preventive intervals without drift, decimal money); use cases for categories, tickets
  (raise, triage, assign to a technician or vendor, start, hold, resume, resolve, close, reopen, cancel), the
  append-only work log with time and cost totals, preventive schedules (create, pause, delete, raise now) and the
  widget summary; outbox events for every state change; scheduler sweeps for preventive tickets, SLA breaches and
  auto-close; API router for every path in the contract.
- Alembic chain `mt_0001`: four `maintenance_*` tables with `organisation_id`, RLS policy on Postgres.
- Tests: domain unit tests, API integration tests, cross-tenant leak test, migration test (31 passing).
- Widget `maintenance.tickets` (GET /tickets?scope=managed&open=true, GET /summary) with loading, empty and
  error states; typed API client in `frontend/src/api/client.ts`; vitest widget tests.
- `docs/user-stories.md`.
- Contract: the `facility-staff` profile role gets the grants of `maintenance-manager`, so the Facility / Inventory
  Staff dashboard (#6) can read this module's data.
- Contract: the academy profile roles whose dashboards show this module's widgets get the grants of the module role
  the PRD names for them (follow-up to #288 from Faizan's review; part of #331).
