# Changelog — iqac-accreditation

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contracts proposed: frameworks and metrics, cycles, metric assignments and responses with link or reference evidence,
  review, action items; `GET /stats/action-items` behind the Governance widget `iqac-accreditation.action-items`; two
  metadata-only events; permissions and proposed roles.
- PRD (`docs/prd.md`).
- Backend (`eos_iqac_accreditation`): every operation of the contract in domain, application, infrastructure and api
  layers; both events to the outbox in the same transaction as the change; an audit entry for every state change;
  `IQAC_ACCREDITATION_DUE_SOON_DAYS` read on every call. Bodies, queries, ids and cursors are bounded and refuse NUL,
  `NaN` and `Infinity` (422, never 500).
- Migration `iqac_accreditation_0001`: seven tables, each with `organisation_id` and the forced row-level-security policy.
- Tests: every route with 401 and 403, error statuses, cross-tenant leak, outbox and audit in one transaction,
  migrations against the models, row-level security on PostgreSQL (opt-in), and contract drift for routes, guards,
  enums, bounds, response bodies and event payloads.
- Widget `iqac-accreditation.action-items` for the Governance dashboard, with vitest tests.
- Docs: `docs/data-model.md`, `docs/integration-points.md`, README backend and frontend sections and "Assumptions to
  revisit".
