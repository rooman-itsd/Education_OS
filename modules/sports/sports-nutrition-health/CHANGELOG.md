# Changelog — sports-nutrition-health

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Frontend: dashboard widgets nutrition-plan (athlete), injured-athletes and appointments-today (medical-staff),
  athletes-on-plans and plan-reviews-due (nutritionist), with an API client for the contract's list endpoints and
  vitest tests. Athletes are shown by short id; clinical notes are never shown.
- Backend: domain rules (plan and review dates, a review ending a plan completes it, closed plans stay closed, no
  future dates, appointment status moves, an appointment completed only after its time, an injury linked to an
  appointment belongs to the same athlete); use cases for every operation in the contract; confidential fields
  returned only to the roles that may see them; athletes see only their own rows; events from
  `contracts/events.yaml` through the outbox (ids, statuses and dates only); an interim audit table shaped like
  platform/audit's Record that never copies clinical or free-text fields.
- Consumes `athlete-performance.athlete.registered` (event-bus entry point) to link athletes to their users.
- Alembic chain `snh_0001`: seven `sports_nutrition_health_*` tables with `organisation_id`, RLS policy on Postgres.
- Contract: `x-permission` on every operation; the sports-college profile roles `medical-staff`, `nutritionist`,
  `coach`, `athlete` and `org-admin` (without health records) granted the matching keys (non-breaking).
- Config: `SPORTS_NUTRITION_HEALTH_DEFAULT_APPOINTMENT_MINUTES`.
- Tests: domain, API, confidentiality, athlete self-scope, consumer idempotency, cross-tenant leak, migration and
  contract-drift tests.
- Review (#370): appointment notes are clinical (medical roles, and nutritionists only for nutrition sessions); injury
  `clinical_notes` written or cleared only with `health-record:write`; closing a plan clears `review_due_on` and the
  reviews-due filter skips closed plans; only active plans are reviewed; a scheduled appointment must be in the future
  and no-show waits for its time; a late, older registration event no longer moves an athlete link; pydantic and PyJWT
  declared; the athlete reassignment risk recorded in the README.
