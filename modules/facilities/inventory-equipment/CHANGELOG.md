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
- Widgets (#109): `inventory-equipment.low-stock` (GET /low-stock), `inventory-equipment.my-loans`
  (GET /loans?scope=mine&open=true) and `inventory-equipment.overdue-loans` (GET /loans?scope=managed&status=overdue),
  each with loading, empty and error states; typed API client in `frontend/src/api/client.ts`; vitest widget tests (13 passing).
- Contract: the `facility-staff` profile role gets the grants of `inventory-equipment-manager`, so the Facility / Inventory
  Staff dashboard (#6) can read this module's data.
- Contract: the academy profile roles whose dashboards show this module's widgets get the grants of the module role
  the PRD names for them (follow-up to #288 from Faizan's review; part of #331).
