# Changelog — audit

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- `contracts/openapi.yaml`: append a record, search, read one, full history of an entity,
  and a per-organisation compliance export. No PUT, PATCH or DELETE on a record: immutability
  is enforced by the absence of the endpoints, not by convention.
- Writes are idempotent on `client_token`, so a retried request cannot double-record.
- `contracts/events.yaml`: `audit.export.ready`, `audit.record.redacted`,
  `audit.retention.pruned`. Audit is a sink and re-publishes nothing it records.
- `contracts/permissions.yaml`: `audit:record:write|read|export`, plus super-admin
  `platform:audit:read` and `platform:audit:redact`. Applied role-id rule: dropped dead
  `audit-reader` and `audit-officer` blocks; granted `audit:record:read` and `audit:record:export`
  to `org-admin`. Cross-organisation reads are themselves audited.
- Widgets: `audit.recent-activity` for Organisation Admin and `audit.super-admin-actions` for Super Admin.
- `docs/prd.md`: the four places immutability is enforced, the one deliberate redaction
  exception, retention rules, and the scope boundary against logs, reporting and event-bus.
- `depends_on` narrowed to `identity` only, with the reason recorded: audit must stay writable
  when the rest of the platform is not.
- Module scaffolded with models, migrations, API, widgets and tests.
