# Changelog — tenancy

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
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
