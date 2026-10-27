# Changelog — student-information

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
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
