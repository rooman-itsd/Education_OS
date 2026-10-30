# Changelog — training-video-analysis

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Backend: domain rules (plan and session status moves with `invalid_transition`, archived plans read-only, closed
  plans take no sessions, sessions on their plan's local days, closed sessions keep their schedule, no completion
  before the start, drill tags and annotations inside the video, no future recording time); use cases for every
  operation in the contract; athletes see only their own sessions, plans, videos and the annotations about them;
  annotations written in the caller's name and changed only by their author; events from `contracts/events.yaml`
  through the outbox; an interim audit table shaped like platform/audit's Record (no titles, notes, annotation text,
  markup or file links).
- Consumers of `athlete-performance.athlete.registered` and `athlete.updated` keep which user is which athlete
  (idempotent, only a newer event moves a link, a removed user clears it).
- Alembic chain `tva_0001`: ten `training_video_analysis_*` tables with `organisation_id`, RLS policy on Postgres.
- Contract: `x-permission` and a 403 response on every operation; an optional free-text `location` on sessions (the
  `session.scheduled` event already carried it); the sports-college profile roles `athlete` and `org-admin` granted
  the same keys as the matching module roles (non-breaking).
- Config: `TRAINING_VIDEO_ANALYSIS_TIMEZONE`.
- Tests: domain, API, athlete self-scope, consumers, cross-tenant leak, migration and contract-drift tests.
