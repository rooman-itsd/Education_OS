# Changelog — admissions

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Applicant dashboard support (Issue #321):
  - Backend: added `applicant_user_id` column to `admissions_application` with migration `admissions_0002_applicant_user`.
  - Added `GET /me/applications` and `POST /me/applications` endpoints guarded by `admissions:self:read`, granted to the `applicant` role.
  - Acceptance event `admissions.application.accepted` includes `user_id` so `fees-accounts` can invoice the applicant upon offer acceptance.
  - Frontend: `admissions.application-status` and `admissions.pending-documents` widgets updated for the Applicant dashboard, showing own applications/offers and pending/rejected documents, with an inline link form when unlinked. Reverses the earlier decision that these widgets were staff-only.
  - Contract bumped to 0.2.0.
- Backend (Issue #104): own Alembic chain (`admissions_alembic_version`) with six `admissions_*` tables, each with
  `organisation_id` and the forced `tenant_isolation` row-level-security policy; domain rules (status transitions,
  offers, merit ranking, funnel); 11 staff routes guarded by `permissions.yaml` keys and 5 public routes under
  `/public/{org_slug}/`; an audit row for every state change and the six `events.yaml` events through the outbox.
  Tests cover domain, service, HTTP, events, tenancy (the `eos_testing` leak check), migrations and contract drift;
  two live PostgreSQL RLS tests run when `ADMISSIONS_TEST_POSTGRES_URL` is set.
- Frontend: widgets `admissions.funnel`, `admissions.application-status`, `admissions.pending-documents`, and the
  public `TrackApplicationPage`, with tests.
- Registered in `apps/backend` and `apps/frontend` `modules.enabled.yaml`.
- Contract revised before the build (nothing consumes it yet, so no version bump):
  - Public routes moved under `/public/{org_slug}/` so every anonymous request names its
    organisation; the host gateway resolves the slug and checks entitlement.
  - Added `GET /reports/funnel` and the `admissions:report:read` permission; new `management` role
    (VC, Registrar) holds only that permission.
  - Added `GET /documents` (verification queue) for the staff queue.
  - `MeritListInput.scores` (optional) and the ranking rule.
  - `RuleError` (422) on status change and merit list generation; offer status `withdrawn`.
- Module scaffolded.
- PRD and contracts published for Issue #62 (Week 1): `contracts/openapi.yaml`,
  `contracts/events.yaml`, `contracts/permissions.yaml`, `docs/prd.md`, `docs/user-stories.md`,
  `docs/data-model.md`, `docs/screens.md`, `docs/integration-points.md`. Submission, tracking,
  document upload and offer decisions are public/anonymous by design; no applicant account is
  created. No backend/frontend code yet.
