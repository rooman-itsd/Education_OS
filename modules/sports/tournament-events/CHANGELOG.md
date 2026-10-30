# Changelog — tournament-events

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Backend: domain rules (tournament lifecycle with ongoing/completed read from the dates in the institution's local
  date, entries open from publishing until the registration deadline, one live entry per athlete and category, entry
  and fixture state machines, fixtures on the tournament's days with its own non-withdrawn entries, results only for
  started fixtures that are scheduled or in progress, placings once per entry of the fixture, travel times in order);
  use cases for every operation in the contract; drafts visible only to tournament:write; athletes see only their own
  entries; cancelling cancels the open fixtures; events from `contracts/events.yaml` through the outbox; an interim
  audit table shaped like platform/audit's Record (no descriptions, notes, reasons, accommodation or officials' names).
- Consumes `athlete-performance.athlete.registered` and `athlete.updated` (user changes only) to link users to
  athletes; idempotent, and only a newer event moves a link.
- Alembic chain `te_0001`: eight `tournament_events_*` tables with `organisation_id`, RLS policy on Postgres.
- Contract: `x-permission` on every operation (non-breaking).
- Config: `TOURNAMENT_EVENTS_TIMEZONE` (replaces the unused `TOURNAMENT_EVENTS_FEATURE_ENABLED` placeholder).
- Tests: domain, API, athlete self-scope, consumers, cross-tenant leak, migration and contract-drift tests.
