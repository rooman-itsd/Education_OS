# Changelog — athlete-performance

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Backend: domain rules (primary discipline first in an athlete's disciplines, fitness-test metrics once each,
  measurements only for the test's metrics, no future dates, benchmark matching by discipline and gender with the
  most specific winning, gap and status by the metric's direction, trend with a steady band); use cases for every
  operation in the contract; athletes see only their own data; events from `contracts/events.yaml` through the
  outbox; an interim audit table shaped like platform/audit's Record (no names, notes or clearance text).
- Alembic chain `ap_0001`: nine `athlete_performance_*` tables with `organisation_id`, RLS policy on Postgres.
- Contract: `x-permission` on every operation; the sports-college profile roles `coach`, `medical-staff`, `athlete`,
  `management` and `org-admin` granted the same keys as the matching module roles (non-breaking).
- Config: `ATHLETE_PERFORMANCE_TREND_STEADY_PERCENT`.
- Tests: domain, API, athlete self-scope, cross-tenant leak, migration and contract-drift tests.
- Review (#352): a lapsed clearance reads `not_cleared`; ids in request bodies must be UUIDs; same-day assessments
  keep the order they were recorded; dates may be one day ahead of UTC; benchmark matching documented in the README.
