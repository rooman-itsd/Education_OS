# Changelog — nad

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- 0.3.0, built on the draft contracts: the adapter (`eos.integration_adapters` entry point) with the manual channel,
  which is the v1.0 default: `publish_awards`, `correct_awards` and `publish_credits` validate every row (a batch with
  any invalid row is refused whole, with `[row, field, code]`), then write NAD's award CSV and ABC's credit CSV
  (template version 1, golden-file tested, split at `NAD_MAX_ROWS_PER_FILE`) into platform/documents and return
  `manual_action_required` with the steps; `record_manual_upload`, `get_submission`; `verify_learner_id` answers
  `unverifiable` until the API specs arrive. Own schema `nad_*` with RLS and its own Alembic chain, the read-only
  `GET /submissions` view, docs, and `NAD_APAAR_HASH_PEPPER` in `config/env.example`. The API channel is not built (no
  public specification).
- Contracts proposed (0.2.0), no code: PRD with NAD and ABC sources; implements the academic-records port (copies of
  the hub's port files in `contracts/ports/`); a read-only submissions view in `contracts/openapi.yaml`; no events of
  its own (the hub publishes port events); `nad:submission:read` for org-admin; `config/env.example`.
