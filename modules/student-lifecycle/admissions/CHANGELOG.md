# Changelog — admissions

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
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
  - Added `GET /documents` (verification queue) for the `admissions.pending-documents` widget.
  - `MeritListInput.scores` (optional) and the ranking rule.
  - `RuleError` (422) on status change and merit list generation; offer status `withdrawn`.
  - `admissions.application-status` and `admissions.pending-documents` are staff widgets;
    applicants stay anonymous and use the public Track application page.
- Module scaffolded.
- PRD and contracts published for Issue #62 (Week 1): `contracts/openapi.yaml`,
  `contracts/events.yaml`, `contracts/permissions.yaml`, `docs/prd.md`, `docs/user-stories.md`,
  `docs/data-model.md`, `docs/screens.md`, `docs/integration-points.md`. Submission, tracking,
  document upload and offer decisions are public/anonymous by design; no applicant account is
  created. No backend/frontend code yet.
