# Changelog — amc-vendor-support

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contracts proposed: AMC contracts referencing procurement vendors, covered items, activation, renewal and
  termination, expiry worked out when read; engagements (breakdown calls and preventive visits); `GET /coverage`;
  `GET /stats/contracts-expiring` behind the Support Staff widget `amc-vendor-support.contracts-expiring`; three
  contract events; permissions and proposed roles.
- PRD (`docs/prd.md`).
- Backend (#342): domain rules (contract statuses and the fields an active contract may still change, activation,
  renewal into a draft successor that copies the terms and covered items, early termination, expiry worked out when
  read; engagement statuses and moves, notes required to resolve or cancel, whether response and resolution terms were
  met); use cases for every contract operation with an audit entry per state change and outbox events for activation,
  renewal and termination; per-organisation contract and engagement numbers; API router for all 16 operations.
- Alembic chain `amc_vendor_support_0001`: five `amc_vendor_support_*` tables with `organisation_id`, RLS policy on
  Postgres.
- Tests: domain unit tests, API integration tests, contract drift and event payload tests, cross-tenant leak test,
  migration test, settings test, row-level security on Postgres (opt-in).
- Widget `amc-vendor-support.contracts-expiring` (GET /stats/contracts-expiring) with loading, empty and error states
  following the widget error convention; typed API client in `frontend/src/api/client.ts`; vitest widget tests.
