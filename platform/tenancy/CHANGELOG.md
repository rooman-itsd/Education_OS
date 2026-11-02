# Changelog — tenancy

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Super Admin dashboard widgets (#346): `tenancy.approval-queue` (registrations awaiting approval and package
  changes, oldest first), `tenancy.organisations-by-status` (a count per status) and `tenancy.recent-registrations`
  (the five newest), all on `platform:organisations:read` from `GET /admin/organisations`. Frontend only; no
  contract change.
- The registration verification mail goes through `platform/notification` (template
  `tenancy.organisation.verify`) instead of the `eos_core.notify` stub (#316). It is recorded in the
  registration's transaction and sent only after that commits, so a failed registration sends nothing. If
  notification refuses it (503 when no mail transport is configured), the registration is refused with the same
  status and nothing is kept. A delivery failure after the commit does not fail the request.
- `organisation_name(db, organisation_id)`, published on the `eos.organisation_directory` entry point, so a
  platform service that may not import tenancy can render an organisation's display name (#316).
  platform/notification needs it for every organisation-facing template. An entry point rather than a hook
  wired by `apps/backend`, because the event-bus relay and the scheduler run as their own processes and never
  execute the API's lifespan.
- Organisation export and deletion with retention (contract 0.2.0, DPDP): `GET /admin/organisations/{id}/export`
  downloads one JSON document with the organisation record and, for every table that carries `organisation_id`
  (found by reflection, so modules need no code) its rows, plus document references; `DELETE
  /admin/organisations/{id}` archives the organisation and sets `delete_after` (`EOS_ORGANISATION_RETENTION_DAYS`,
  default 30; an active organisation with paid invoices needs `confirm_slug`); `POST .../restore` cancels;
  `POST .../purge` deletes every row after retention (or with `force`). Keys `platform:organisation:export` and
  `platform:organisation:delete` for super-admin; events `tenancy.organisation.exported`, `.deletion_requested`,
  `.restored`, `.purged`. Migration `tenancy_0002` adds `delete_after`, `deletion_requested_by`,
  `deletion_requested_at`, `status_before_deletion` to `tenancy_organisation`.
- TODO: schedule the purge once platform/scheduler (#357) is in; until then the super admin runs `POST .../purge`
  after `delete_after`.
- Purge: a foreign-key block is a 409 `purge_blocked` naming the table (was a 500); the `purged` event carries
  `requested_by` and `requested_at`; export also redacts columns ending in `_token`, `_hash`, `_secret`.
- Module scaffolded.
