# Changelog — web-portal-cms

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- CMS contract revised for issue #106 before the backend (nothing consumed it, so no version bump), with the
  decisions in docs/prd.md §11: reading needs a signed-in member (new keys `page:read` and `announcement:read`,
  granted to the implicit `member` role) instead of anonymous public routes, which the host gateway refuses; no
  pre-organisation pages (`scope=public` and the `signup_marketing` type removed); plain-text bodies with length
  limits; a `status` filter for editors to list drafts; drafts and out-of-window announcements answer 404 without
  the manage key; `x-permission` on every operation; ConflictError and RuleError codes; event payloads without
  `organisation_id` or body text. PRD, data model, screens, integration points and user stories updated to match.
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
  After submitting, the administrator's email is verified with the token tenancy emails them
  (`POST /register/verify`; in dev mode the register response carries it and the page verifies at
  once), and only then does the page show that the registration is waiting for approval, with the
  short name needed at sign-in. The token can also be opened as a link, `/#/verify?token=…`. Error
  colours come from the kit's `--eos-danger*` tokens. The plans page and the sign-in page link here.
  Frontend test setup (Vitest, jsdom, Testing Library) and tests.
