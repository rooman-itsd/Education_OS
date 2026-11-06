# Changelog — projects

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contracts proposed (generic pattern): proposals and approval, teams and guides, milestones with versioned
  submissions and reviews, final submission and evaluation, cancellation, and the endpoints behind the widgets
  `projects.my-projects`, `milestones-due`, `to-review` and `active`; events; permissions and generic roles.
- PRD (`docs/prd.md`).
- User stories (`docs/user-stories.md`): proposals and decisions, teams and guides, milestones, submissions and
  reviews, final submission and evaluation, cancel, self-service, the daily job and the four widgets.
- Backend (`eos_projects`): all 20 operations of contract 0.1.0 in domain, application, infrastructure and api layers;
  events to the outbox in the same transaction; an audit entry for every state change; the project or milestone row
  locked (FOR UPDATE) for transitions, team and guide changes and reviews; self-service limited to the caller's own
  projects and guide actions to the projects the caller guides; business dates in Asia/Kolkata; the daily job that
  publishes `projects.milestone.overdue` once per milestone. Ids in paths, queries and bodies must be uuids (422
  otherwise); strings, lists and numbers are bounded and dates lie between 1900 and 9998; NUL characters are refused
  (404 in a path, 422 `invalid_query` in a query, 422 in a body); title search escapes `%` and `_`; cursors past
  1,000,000 start from the top; a duplicate write that slips past the locks is a 409, not a 500.
- Migration `projects_0001`: seven tables, each with `organisation_id` and the row-level-security policy.
- Tests: domain rules, every user-story area, 403 for every operation a role does not hold, real profile-role tokens,
  the keys each role gets through `permissions_for`, the cross-tenant leak test, and the migration against the models.
- Widgets `projects.my-projects`, `projects.milestones-due`, `projects.to-review` and `projects.active`, built on
  `@eos/ui-kit`, with tests; their error states say why a load failed (`describeFailure`) and offer a retry only where
  one can help.
- Enabled in `apps/backend/config/modules.enabled.yaml` (mounted at `/api/v1/projects`) and
  `apps/frontend/config/modules.enabled.yaml` (its four widgets on the student, guide and coordinator dashboards) (#339).
