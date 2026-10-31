# tenancy

**Kind:** platform (core)
**Status:** planned

Organisations (tenants), self-service registration, academy type, entitlements. Decision: [ADR-0005](../../docs/architecture/adr/0005-multi-tenant-saas.md).

## Scope
- Public registration: organisation + academy type (the **academic package**, an institution profile) + first admin user. Starts on the trial plan.
- Approval: after email verification the organisation is `pending_approval`; a super admin approves the package before anyone can sign in. A package change is requested by the org admin and approved the same way. `TENANCY_AUTO_APPROVE=true` skips this in development.
- Verification mail through `platform/notification`: recorded with the registration, sent after it commits. If
  notification cannot accept it (no mail transport configured), registration answers 503 and keeps nothing. Not
  durable yet: if the process stops between the commit and the send, the mail is not sent (outbox relay, #83).
- The organisation record and its status (pending, active, suspended, archived).
- The **entitlement**: the modules, integrations and limits an organisation may use right now,
  computed as `profile.modules ∩ plan.modules ∪ overrides − disabled`. The API gateway asks for
  it on every request and refuses anything outside it; apps hide it and show upgrade prompts.
- Super admin operations over organisations: list, suspend, overrides, audited impersonation.
- **Export and deletion per organisation** (DPDP, ADR-0005): see below.

Not in scope: plans, prices, subscriptions and payments (`platform/billing`); users and roles inside an organisation (`platform/identity`).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dashboard widgets
`frontend/src/widgets/index.ts`, placed by the role layouts in `platform/identity/config/dashboards/`:

| Widget | Dashboard | Permission | Shows |
|---|---|---|---|
| `tenancy.enabled-modules` | Organisation Admin | `tenancy:organisation:read` | The modules on now, by suite, and how many a higher plan unlocks |
| `tenancy.approval-queue` | Super Admin | `platform:organisations:read` | Registrations in `pending_approval` and package changes (`requested_academy_type`), oldest first, with the count |
| `tenancy.organisations-by-status` | Super Admin | `platform:organisations:read` | How many organisations are in each status, every status listed |
| `tenancy.recent-registrations` | Super Admin | `platform:organisations:read` | The five newest organisations: package, plan, status |

The three Super Admin widgets read `GET /admin/organisations` and count in the browser; they only display, and
approving happens on the super admin screens (#95). The list looks up each organisation's subscription, so once
there are hundreds of organisations a counting endpoint should replace the full list.

## Export and deletion (DPDP)
Both are super admin operations under `/admin/organisations/{id}`, keys `platform:organisation:export` and
`platform:organisation:delete`, and every step leaves an outbox event (`tenancy.organisation.exported`,
`.deletion_requested`, `.restored`, `.purged`).

- **Export**, `GET .../export`: one JSON document, served as an attachment `<slug>-export-<date>.json`, with
  `organisation` (the record), `tables` (for `tenancy_organisation` and every table that carries
  `organisation_id`, the organisation's rows as column name → value: dates ISO 8601, decimals as strings, JSON
  columns as is, secrets such as password hashes and tokens as `"[redacted]"`), `row_counts`, `files`,
  `exported_at`, `exported_by` and `schema_version` (1). Tables are found from the database itself (known
  models plus reflection of any other table with an `organisation_id` column), so a module needs no export code.
  `files` lists references found in columns named `document_id` / `file_id` (or ending in them);
  `platform/documents` is not built yet, so these are references only and the files follow once it exists.
- **Deletion with retention**, `DELETE .../{id}`: the organisation is archived at once, so its users can no
  longer sign in (identity refuses any status but `active`) and the gateway refuses its module requests, and
  `delete_after` is set to now plus `EOS_ORGANISATION_RETENTION_DAYS` (default 30). An active organisation with
  paid invoices is refused (409) unless the body's `confirm_slug` names it. `POST .../restore` before the purge
  puts the previous status back and clears the clock. `POST .../purge` deletes every row of the organisation in
  every table with `organisation_id` (children first, retried until nothing blocks, deferrable constraints
  deferred on Postgres) and then the organisation row; it runs only after `delete_after`, or at once with
  `{"force": true}`. The purge is irreversible; export first.

**Who runs the purge.** Retention is not enforced automatically: nothing schedules the purge today. The super
admin runs `POST .../purge` once `delete_after` has passed; a scheduler job will call it when platform/scheduler
(#357) is in. The `purged` event carries `requested_by` and `requested_at` from the deletion request, since the
purge also removes that request's own outbox events. If a foreign key blocks the purge it answers 409
`purge_blocked` naming the table, and nothing is deleted.

**Backups (DPDP).** Purged data remains in database backups until they rotate out; the purge does not touch
them. How long backups are kept is in [infra/backup-dr/README.md](../../infra/backup-dr/README.md) (defaults: 14
nightly and 8 weekly copies, plus the second location).

**Legal retention.** Invoices (`billing_invoice`) are included in the export. GST rules may require keeping
them, and a legal-retention exception for `billing_invoice` is a decision for the lead (an issue is to be
opened), so the purge today removes them.

## Data
Schema `tenancy`: `organisation` (with `delete_after`, `deletion_requested_by/at` and `status_before_deletion`
while a deletion is pending), `organisation_module` (toggles and overrides), `registration_token`,
`impersonation_session`. This is the one schema whose tables are not themselves tenant-scoped,
because they define the tenants.

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../docs/architecture/module-standard.md#portability-checklist).
