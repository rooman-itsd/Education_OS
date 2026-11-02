# Changelog — e-office

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Frontend (`frontend/`, package `@eos/e-office`): the HR Staff widget `e-office.files-pending` (#336) reads
  `GET /me/inbox` and shows the files pending with the viewer (total, urgent, overdue), letters still to attach, and
  the five files waiting longest with subject, action asked for, due date and overdue badge, with loading, empty and
  error-with-retry states, and its tests (24).
- Module scaffolded.
- Contracts: file categories, files with note sheet, attachments, movement and decisions, inbox behind the
  files-pending widget, inward receipts, outward dispatch and pendency report; events; permissions and roles.
- PRD (`docs/prd.md`).
- Backend (#336): package `eos_e_office` (domain, application, infrastructure, api), router for `/api/v1/e-office`
  serving every operation of the contract: categories; files with numbering, note sheet, attachments, forwarding,
  decisions, close and reopen, movements; `/me/inbox`, `/me/sent`, `/me/receipts`; receipts; dispatches;
  `/reports/pendency`.
  - Alembic chain `e_office_0001` with its own version table: 9 `e_office_*` tables, each with `organisation_id` and
    the `tenant_isolation` policy on Postgres, including `file_holder` and `audit_entry`.
  - Overdue: `flag_overdue` and the platform scheduler job `e-office.flag-overdue` (entry points
    `eos.scheduler_jobs` and `eos.event_consumers`), reporting `e-office.job.finished`. Settings
    `E_OFFICE_DEFAULT_DUE_DAYS_NORMAL`, `_URGENT`, `_IMMEDIATE` in `config/env.example`.
  - Rules from the PRD: the note sheet and movement history are append-only, and every state change writes an
    `audit_entry` row in the same transaction; a file is visible to everyone who has held it, read-all sees every
    non-confidential file and confidential files only their holders; note text never goes into events, which carry
    exactly the payloads of `events.yaml`. Business dates are Indian (Asia/Kolkata), as procurement (#335).
  - Assumptions to revisit (README): attachments and scans are platform/documents ids, stored as given; the central
    registry is whoever holds `e-office:correspondence:manage` (HR staff by default).
  - Tests: holder rules, append-only numbered notings, decisions by permission, close and reopen, confidential and
    read-all visibility, inbox and sent, receipt and dispatch flows, overdue flagged once, permissions, validation,
    state errors, the cross-tenant leak test, the migration chain against the models, and contract drift (routes,
    permissions, error codes, enums, event payloads).
- Contracts 0.2.0 (#336): `openapi.yaml` documents every error code; `organisation_id` on categories, files, receipts
  and dispatches; `FileSummary` gains `category_id`, `department_id`, `confidential`, `action_required`, and `File`
  extends it; `FileInput.receipt_id` opens a file from a receipt; new `GET /me/receipts`; `ReceiptInput.document_id`
  optional until the documents service exists; `Attachment` gains `receipt_id` and a nullable `document_id`; `Receipt`
  gains `registered_by`, `created_at`; `Dispatch` gains `file_number`, `requested_by`, `requested_at`; shared `Mode`
  and `RemarkInput` schemas; length limits; overdue, numbering and visibility spelled out. `events.yaml`:
  `e-office.job.finished` added for the scheduler; `file.overdue` `due_on` is the computed due date;
  `file.forwarded` `due_on` may be null. `module.yaml`: version 0.2.0, status in-progress, consumes
  `scheduler.job.due`.
- Enabled (#336) in `apps/backend/config/modules.enabled.yaml` (mounted at `/api/v1/e-office`; installed, tested and
  migrated in CI and the auto-deploy) and `apps/frontend/config/modules.enabled.yaml` (the dashboard registers the
  module's widgets; `e-office.files-pending`, from #411). The README says how mounting works.
