# government-portals: data model

Own schema, prefix `government_portals_`; Alembic chain `gp_0001` with its own version table
`government_portals_alembic_version`. Every table carries `organisation_id` and the forced `tenant_isolation`
row-level-security policy (`eos_core.rls.POLICY`).

| Table | Purpose | Notes |
|---|---|---|
| `government_portals_package` | One prepared package: form, period, status, issues, checklist, filing record | Partial unique index `(organisation_id, package_key) WHERE status != 'superseded'`: one live package per caller key |
| `government_portals_package_file` | A file of the package by `document_id`, with role and (for evidence) metric | Evidence rows reference the caller's own document; only generated files are new documents |

Status flow: `prepared` or `invalid` on preparation; `prepared` to `acknowledged` (filing recorded with an
acknowledgement document) or `uploaded_manually` (without one); `superseded` when the same `package_key` is prepared
again. A filed package is read-only. `draft` and `submitted` exist in the port's vocabulary for the day a portal has an
API; nothing sets them today.

Not kept: the data the package was prepared from (it belongs to the calling module, which prepares again). Issues hold
`{path, code, severity}` only, never a value. Every state change writes an outbox event
(`government-portals.package.prepared`, `.filed`) in the same transaction, which is the audit trail.
