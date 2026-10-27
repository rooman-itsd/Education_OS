# Changelog — asset-management

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contract draft: asset register, transfers, verification, depreciation and disposal API, events and permissions; PRD (#65).
- Backend (#127): domain rules (generated tags, transfers only for what changes, verification due dates and
  windows, straight-line and written-down-value depreciation pro-rated by month and floored at residual, run
  periods that follow the last posted one, disposal steps, decimal money); use cases for categories, the register,
  status, transfers, the depreciation schedule, verification cycles (plan, start, record by id or scanned tag,
  close and apply), depreciation runs (calculate, replace, delete, post and lock), disposals (request, approve,
  reject, cancel, complete with catch-up depreciation and gain or loss) and the summary; outbox events for every
  state change; scheduler sweep for verification-overdue; API router for every path in the contract.
- Alembic chain `am_0001`: eight `asset_management_*` tables with `organisation_id`, RLS policy on Postgres.
- Tests: domain unit tests, API integration tests, cross-tenant leak test, migration test (25 passing).
- Widget `asset-management.audit-due` (GET /verifications/due) with loading, empty and error states following the
  widget error convention; typed API client in `frontend/src/api/client.ts`; vitest widget tests.
- `docs/user-stories.md`.
