# Changelog — inventory-equipment

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contract draft: inventory API (catalogue, units, stock ledger, loans), events and permissions; PRD (#65).
- Backend (#109): domain rules (loan rules, stock never negative, low-stock crossing, loan status from lines);
  use cases for categories, locations, items, tagged units, stock ledger (receipt, issue, transfer,
  adjustment, write-off), low stock, loans (request, approval with reservation, hand-out, partial return
  with condition and damage, extension, lost), summary; outbox events for every state change; scheduler
  sweeps for overdue loans and pickup expiry; API router for every path in the contract.
- Alembic chain `ie_0001`: eight `inventory_equipment_*` tables with `organisation_id`, RLS policy on Postgres.
- Tests: domain unit tests, API integration tests, cross-tenant leak test, migration test (25 passing).
- `docs/user-stories.md`.
