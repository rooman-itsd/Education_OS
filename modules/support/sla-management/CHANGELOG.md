# Changelog — sla-management

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contracts proposed: business-hours calendars, SLA policies with escalation levels, response and resolution
  clocks per helpdesk ticket, `GET /tickets/{ticket_id}` for helpdesk screens, `GET /stats/breaches` behind the
  Support Staff widget `sla-management.breaches`; clock events; consumed helpdesk ticket events; permissions and
  roles.
- PRD (`docs/prd.md`).
- Backend (#342): business time in a calendar's time zone, working intervals and holidays (daylight saving
  followed, ten-year horizon); calendar and policy rules (overlapping or reversed intervals, unknown time zone,
  resolution shorter than response, escalation levels numbered in order, unreachable targets); clock moves
  (start, pause, resume, reopen, recalculate, stop, cancel) with warnings, breaches and escalation levels recorded
  once each; use cases for all 12 operations with an audit entry per change; clock events to the outbox.
- Helpdesk consumers for the nine `helpdesk.ticket.*` events of `module.yaml`, registered on the
  `eos.event_consumers` entry point: applied once by event id, one ticket at a time, in the event's organisation;
  malformed events ignored.
- Alembic chain `sla_management_0001`: seven `sla_management_*` tables with `organisation_id`, RLS policy on Postgres.
- Tests: domain, API, consumers (duplicates, other organisations, malformed payloads), contract drift and event
  payloads, cross-tenant leak, migrations, settings, row-level security and concurrency on Postgres (opt-in).
- Widget `sla-management.breaches` (GET /stats/breaches) with My tickets / All tickets, loading, empty and error
  states following the widget error convention; typed API client in `frontend/src/api/client.ts`; vitest tests.
- NUL characters never reach the database: Postgres cannot store them in text, so a NUL in a request body is a 422
  and in the URL a 404 (path ids) or 422 (query parameters), instead of a 500 (`api/deps.py` `no_nul`, `Strict`).
