# audit — PRD

Owner: Himanshu (@himanshu-rooman) · Tier: core · Status: planned

## What this is

The permanent, append-only record of every state-changing action in Education OS.

`ARCHITECTURE.md` makes this unconditional: *"Every state change writes to `platform/audit`.
Audit records are immutable."* Every one of the 56 modules declares `audit` in its
`depends_on`, so this service is on the critical path for the whole product.

It answers one question, for any object in the system: **who changed this, when, from where,
and what did it look like before and after.**

## What it is explicitly NOT

| Not this | That belongs to |
|---|---|
| Application logs, stack traces, debug output | `structlog` / Sentry. Audit is business facts, not diagnostics |
| A delivery buffer for events | `platform/event-bus`. Its outbox is pruned; audit is kept |
| Analytics, dashboards, MIS reporting | `platform/reporting` |
| A change-data-capture feed of every row | Audit records *intentional actions*, not every write |
| The system of record for the data itself | The owning module. Audit records what happened to it, not the live value |
| A place to store documents | `platform/documents`. Record the document id, never its bytes |

Audit is **not a general log**. A record is written when a human or a system *changes
something that matters*: a grade entered, a fee waived, an organisation approved, a user
impersonated. Reading a page is not an audit event unless the data is sensitive enough that
reading it is itself an action worth recording.

## Immutability

Immutability is the product, so it is enforced in four places, not asserted in a README:

1. **No mutating endpoints.** `contracts/openapi.yaml` has no `PUT`, `PATCH` or `DELETE` on a
   record. There is nothing to call.
2. **Database grants.** The module's role gets `INSERT` and `SELECT` on `audit_record` and
   nothing else. No `UPDATE`, no `DELETE`.
3. **No application path to a change.** The domain layer exposes `record()` and queries. There
   is no update use case to call by mistake.
4. **Retention deletes whole windows, never single records**, and only above the retention
   floor set by the operator. A record cannot be removed because somebody dislikes it.

The one deliberate exception is redaction for a legal erasure request, which replaces a
payload with a tombstone, writes its own audit record, and requires `platform:audit:redact`.
A redaction never removes the fact that something happened.

## Multi-tenancy

Every record carries `organisation_id` with a row-level-security policy (module standard,
rule 11). An organisation sees only its own records. A super admin with `platform:audit:read`
sees across organisations, and **that act is itself audited** — ADR-0005 requires impersonation
and cross-tenant access to leave a trail.

Platform-level actions that belong to no organisation (approving a package, editing a plan)
are recorded with a null `organisation_id`.

## Users

| Who | Needs |
|---|---|
| Every module | One SDK call per state change, cheap enough that nobody is tempted to skip it |
| Organisation Admin | Who changed what inside their organisation |
| Governance / IQAC | Evidence for accreditation and audit |
| Grievance / RTI | What happened to a specific case, defensibly |
| Super Admin | Cross-organisation actions, impersonation trails, platform changes |

## Scope, week by week

| When | What |
|---|---|
| Week 1 (this) | Contracts, PRD, the immutability and retention rules |
| Week 2 | Backend, schema with RLS, the SDK write path, query and export |
| Later | Retention and redaction, an Organisation Admin widget, tamper-evident hash chain |

## Dependencies

- **`platform/identity`** — permission checks, and resolving an actor to a readable name.
- **`packages/sdk`** — how modules write records. Currently empty and owned by the
  architecture lead; the write path depends on it.

## Success

- A module author writes one line per state change and never thinks about audit again.
- No state change anywhere in the product is unexplained.
- No record is ever altered.
- No organisation sees another's records, proven by the cross-tenant leak test.

## Open questions for review

1. **Hash chaining.** Should each record carry a hash of the previous one, making tampering
   detectable rather than merely forbidden? It costs ordering and write throughput. Proposed:
   not in v1, designed so it can be added without a contract change.
2. **Retention floor.** How long must records be kept? Accreditation bodies may dictate this.
   Proposed default 7 years, configurable upward only.
3. **Write path.** Synchronous SDK call, or an event the audit service consumes? Synchronous is
   simpler and guarantees the record exists before the response returns; it also couples every
   module's latency to this service. Proposed: synchronous, with a local outbox fallback.
