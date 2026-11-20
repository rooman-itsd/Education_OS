# Changelog — student-information

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]

## [0.3.0] - 2026-11-20
- Guardian's consent for minors (DPDP gap D7; the institution obtains verifiable consent offline, the platform records
  it and blocks nothing on it):
  - `Person.minor` (read-only, derived from `date_of_birth`: under 18 today; null when the date of birth is unknown)
    and `Person.guardian_consent` (`{obtained, obtained_on, recorded_by, note}`).
  - `PUT /people/{id}/guardian-consent` (permission `student-information:person:write`: registrar, org-admin,
    admissions-staff): `obtained: true` records it (`obtained_on` defaults to today, never in the future;
    `recorded_by` is the caller), `obtained: false` withdraws it and clears the record. New 422 codes
    `consent_date_in_future`, `consent_date_not_allowed`, `consent_not_recorded`.
  - `GET /people/{id}/guardian-consent` (`student-information:person:read`): the append-only history.
  - `GET /people` filters `minor` and `guardian_consent`: `?minor=true&guardian_consent=false` lists the minors whose
    consent is missing.
  - Event `student-information.person.guardian-consent-changed` (`{organisation_id, person_id,
    guardian_consent_obtained, obtained_on}`; no note, no guardian data).
  - Migration `student_information_0002`: four nullable columns on `student_information_person` and the table
    `student_information_guardian_consent_history` (organisation_id, row-level security).
- Contract versions: openapi `0.3.0`, module `0.3.0`; `events.yaml` stays at payload version 1 (additive only).

## [0.2.0] - 2026-11-06
- Added `student-information.person.account-linked` (`{organisation_id, person_id, identity_user_id, linked,
  previous_identity_user_id}`), published in the transaction of every write that sets, changes or clears a person's
  `identity_user_id`. Modules that key data on `person_id` use it to map a student's sign-in user to their person for
  `/me` reads. Additive: no existing payload loses a field.
- `student-information.person.created` now also carries `identity_user_id` (null when no account is linked).
- Added `POST /account-links/republish` (permission `student-information:person:write`): republishes the current link
  of every linked person in the organisation, the backfill for links made before the event existed.
- A blank `identity_user_id` is stored as no account (null), never as ''.
- Contract versions: openapi `0.2.0`, module `0.2.0`; `events.yaml` stays at payload version 1 (additive only).
- Searchable for platform/search: `contracts/searchable.yaml` (type `person`, triggers `person.created`, `person.updated`, `person.status-changed`) and a document provider on the `eos.search_documents` entry point. Indexes name and status only; the person's own user may read the record.
- Backend package `eos-student-information` implemented with domain models, application service, infrastructure models, and FastAPI router.
- Domain enums and logic: `PersonStatus` state machine, `DocumentType`, `IdCardStatus`, and collision-resistant card number generator (`IDC-{ORG4}-{YYYYMM}-{RANDOM6}`).
- Database & Alembic: Dedicated migration chain (`student_information_alembic_version`, revision `20261026_0001_initial`) creating 4 tables (`student_information_person`, `student_information_status_history`, `student_information_document`, `student_information_id_card`) with multi-tenant row-level security (`app.organisation_id`).
- Contract conformance: REST endpoints under `/api/v1/student-information` adhering to `contracts/openapi.yaml`, role-permission checks from `contracts/permissions.yaml`, and domain event outbox generation for 5 events (`person.created`, `updated`, `status-changed`, `id-card.issued`, `id-card.revoked`).
- Comprehensive test suite: Domain rules, CRUD/search, duplicate prevention (409 Conflict), status transitions (422 RuleError), document attachments, card issuance/revocation, event outbox dispatch, OpenAPI contract drift, Alembic upgrade/downgrade, and cross-tenant leak test using `eos_testing`.
- Monorepo integration: Installed package editable into repository `.venv` and registered in `apps/backend/config/modules.enabled.yaml`. Verified host mounting and startup smoke checks.
- Documentation & metadata: Updated `module.yaml` status to `in-progress`, expanded `README.md`, `CHANGELOG.md`, and `config/env.example`.
- Frontend widgets: Export verified as empty widget array in `frontend/src/widgets/index.ts`.
- Module scaffolded.
- PRD and contracts published for Issue #62 (Week 1): `contracts/openapi.yaml`,
  `contracts/events.yaml`, `contracts/permissions.yaml`, `docs/prd.md`, `docs/user-stories.md`,
  `docs/data-model.md`, `docs/screens.md`, `docs/integration-points.md`.
