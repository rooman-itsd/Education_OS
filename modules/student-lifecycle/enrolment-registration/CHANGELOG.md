# Changelog — enrolment-registration

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Backend (issue #105): own Alembic chain (`enrolment_registration_alembic_version`) with nine
  `enrolment_registration_*` tables, each with `organisation_id` and the forced `tenant_isolation` policy; programme
  enrolment with per-organisation roll numbers, registration windows, single and bulk course registration applying
  the roster's checks (offering open, section open and not full) when academic-management's data is known, section
  changes with an effective date; 14 routes guarded by `permissions.yaml` keys; an audit row for every change and
  the five `events.yaml` events (no `organisation_id` in payloads). Consumers keep local copies of
  academic-management's terms, offerings and sections, once per envelope. Tests cover domain, service, HTTP,
  events (including every field academic-management's roster requires), tenancy, migrations, contract drift and
  consumers; two live PostgreSQL RLS tests run when `ENROLMENT_REGISTRATION_TEST_POSTGRES_URL` is set.
- Frontend: widget `enrolment-registration.registered-candidates` (Examination Staff dashboard) with tests.
- Registered in `apps/backend` and `apps/frontend` `modules.enabled.yaml`.
- PRD, user stories, data model, screens and integration points for issue #105, with the decisions taken
  without a review reply (PRD §11).
- Contracts: 14 operations (`openapi.yaml`), five events including the three course-registration events
  academic-management's roster consumes (`events.yaml`), four permission keys and the `registration-staff` role
  (`permissions.yaml`); `module.yaml` lists the academic-management events consumed.
- Module scaffolded.
