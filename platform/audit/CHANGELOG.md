# Changelog — audit

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Contact details never reach an immutable record (review of #434). `tenancy.organisation.registered` carries
  `admin_email` and the consumer stored the payload verbatim in `after`; a record cannot be edited or deleted, so the
  address could never be removed on a DPDP erasure request. The consumer now drops a key that names a contact detail
  (`email`, `phone`, `mobile`, in any spelling) and any string value that contains an email address, under any key
  and at any depth, including items of a list. The record keeps the key's name in `context.dropped_keys`, never the
  address. Tested for every one of the audited events, in the organisation's record and in the platform copy.
- Audit is fed by the outbox (#317 follow-up). Nothing called `record()` outside this module and audit consumed no
  events, so the store and both widgets stayed empty. `application/consumers.py` (entry point
  `eos.event_consumers`) records 32 state-change events from tenancy, identity, billing, workflow, documents and
  reporting, idempotent on the event id, with the event's actor and time (`record()` takes `occurred_at`). Super
  admin operations also get a platform-level record for `audit.super-admin-actions`. Secret-looking payload keys
  are dropped and named in `context.dropped_keys` rather than refusing the record.
- Retention runs: the platform job `audit.prune` (`30 2 * * *`, entry point `eos.scheduler_jobs`) consumes
  `scheduler.job.due`, runs `prune()` and reports `audit.job.finished`. `prune()` existed but nothing ran it.
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
