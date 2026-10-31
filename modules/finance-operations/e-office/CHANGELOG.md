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
