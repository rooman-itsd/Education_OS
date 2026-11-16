# packages/core

Python package `eos_core`. The only shared code a backend module may import besides its own and `eos_sdk`.

| Module | Purpose |
|---|---|
| `settings` | Environment-driven settings (`EOS_DATABASE_URL`, `EOS_JWT_SECRET`, `EOS_DEV_MODE`, `EOS_SUPER_ADMIN_*`, `BILLING_PAYMENT_ADAPTER`) |
| `db` | SQLAlchemy base, `TenantMixin` (organisation_id on every table), session factory, `scoped()` query helper, `init_db()` |
| `tenant` | Request-scoped organisation context; `organisation_scope()` and the audited `platform_scope()` bypass |
| `rls` | Row-level-security policies for every tenant table on Postgres (`app.organisation_id`, `app.bypass_rls`) |
| `security` | Password hashing (PBKDF2), JWT create and decode |
| `config` | Loaders for academy profiles, plans and permission catalogues from the repo's YAML |
| `entitlement` | The rule `profile ∩ plan ∪ overrides − disabled`, identical to the web shell's copy |
| `events` | Transactional outbox (`publish()`), relayed by platform/event-bus |
| `notify` | Email stub until platform/notification ships |
| `workflow` | `submit()`: send a record for approval through platform/workflow without importing it (hook wired by `apps/backend`) |

## Submitting for approval: `eos_core.workflow`

```python
from eos_core import workflow

req = workflow.submit(
    db,
    organisation_id,  # the caller's own session and organisation
    chain_code="examinations.results",  # the organisation's chain; its admin creates it (POST /chains)
    entity_type="examinations.result_set",  # what workflow's events will carry back, with entity_id
    entity_id=result_set.id,
    title="Semester 1 results, B.Sc. Physics",
    requested_by=principal.user_id,  # the requester: idempotency is per requester, and they cannot approve it
    context={"students": 42},  # optional, shown to approvers
    client_token=f"results:{result_set.id}",  # optional; a replay returns the first request
)
# {"id": ..., "status": "pending", "current_step_order": 1, "created": True}
```

The request and its `workflow.request.submitted` event are written in the caller's transaction; the caller
commits. `WorkflowUnavailableError` means workflow is not wired in this process (only the API wires it: not the
event-bus relay or a script); `WorkflowRefusedError.code` is `unknown_chain` (no active chain with that code in
the organisation), `chain_has_no_steps` or `invalid_request` (a field missing, blank or too long). The calling
module checks its own permission for the action first: `submit()` does not check `workflow:request:create`.
React to the outcome by consuming `workflow.request.approved` / `workflow.request.rejected`, filtered on
`entity_type`. Details: [platform/workflow/README.md](../../platform/workflow/README.md#calling-workflow-from-a-module).

Tenant scoping is enforced twice on purpose: in Postgres by RLS and in code by `scoped()`, so SQLite
tests catch a missing filter and production catches a missing `scoped()`.
