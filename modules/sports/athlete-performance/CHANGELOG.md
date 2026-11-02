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
- Event: publish athlete.updated with user_id when an athlete's user changes.
- Clearance: lapses by the institution's local date (ATHLETE_PERFORMANCE_TIMEZONE) rather than the UTC date.
- Frontend: dashboard widgets `squad-overview` (coach; squad summary with metric names and units),
  `fitness-clearances` (medical staff; every active athlete's clearance, most urgent first, lapsing within 14 days
  flagged), `performance-trend` (athlete; own results over time for the four most recently
  measured metrics, with the matching benchmark) and `body-composition-trend` (nutritionist; body-composition
  metrics, by fitness test name or metric name, from the squad summary). API client, vitest unit tests.
- API: `GET /reports/clearances` (`clearance:read`): every active athlete's clearance, most urgent first, with counts;
  athletes see their own row. Replaces one request per athlete in the clearance widget.
- Permissions: the sports-college `nutritionist` profile role reads the catalogue, athletes and summary reports.
- Enabled in `apps/backend/config/modules.enabled.yaml` (mounted at `/api/v1/athlete-performance`) and
  `apps/frontend/config/modules.enabled.yaml` (its four widgets on the coach, medical staff, athlete and
  nutritionist dashboards) (#330).
