# Changelog — web-portal-cms

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- PRD and contracts published for Issue #62 (Week 1): `contracts/openapi.yaml`,
  `contracts/events.yaml`, `contracts/permissions.yaml`, `docs/prd.md`, `docs/user-stories.md`,
  `docs/data-model.md`, `docs/screens.md`, `docs/integration-points.md`. Covers CMS pages,
  announcements, and the organisation sign-up page, which composes `platform/billing`'s and
  `platform/tenancy`'s existing public APIs rather than duplicating them. No backend/frontend
  code yet.
- Organisation registration (Issue #98): public page at `/#/register` with an academy package picker
  (single-choice cards from `platform/tenancy` `GET /academy-types`) and the organisation and
  administrator form, submitted to `POST /register`. Client-side validation mirrors the server's
  rules; errors for a taken short name, closed registration, invalid input and network failures.
  After submitting, the page shows that the registration is waiting for approval. The plans page
  and the sign-in page link here. Frontend test setup (Vitest, jsdom, Testing Library) and tests.
