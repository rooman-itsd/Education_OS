# Changelog — sports-facilities

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Moved from Akshata to Ashritha in sprint v1.0 (#331): `module.yaml` owner and status `in-progress`, as in
  `docs/team/ownership.md` and CODEOWNERS.
- Contract review before the backend (#331):
  - `permissions.yaml`: the sports-college profile roles get the grants of the module role the PRD names for their
    users: `facility-staff` and `org-admin` as `sports-facilities-admin`, `coach` as `sports-facilities-coach`,
    `athlete` as `sports-facilities-viewer`. Without them no signed-in user held any key.
  - `openapi.yaml`: `Facility.status` is required and starts `operational`, with `status_until`; `Space` carries
    `facility_id` and `active`; 404 on the spaces of an unknown facility; `UpdateFacilityRequest` needs one field;
    capacity and headcount are at least 1; the rules for usage (window, space of the facility), operating hours
    (local time, closes after opens, empty means always open) and utilisation (inclusive local dates, at most 366
    days) are written down; `listFacilitys` renamed `listFacilities`.
  - `config/env.example`: `SPORTS_FACILITIES_TIMEZONE` (default `Asia/Kolkata`).
- Backend (#331): use cases for facilities, spaces, weekly operating hours, availability, usage records and
  utilisation, implementing every operation of `contracts/openapi.yaml`; the four events of `contracts/events.yaml`
  through the outbox; an audit entry for every state change; local dates in `SPORTS_FACILITIES_TIMEZONE`; ids in
  request bodies validated as UUIDs; API router mounted under `/api/v1/sports-facilities`.
- Alembic chain `sf_0001`: five `sports_facilities_*` tables with `organisation_id`, RLS policy on Postgres, own
  version table `sports_facilities_alembic_version`.
- Tests: domain, API, cross-tenant leak, migration, contract drift and profile-role tests.
