# Changelog — admissions

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
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
