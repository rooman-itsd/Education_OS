# grievance

**Domain:** governance
**Kind:** feature
**Status:** in-progress (backend and widgets built and tested; not yet listed in `modules.enabled.yaml`)

SGRC, anti-ragging and POSH-ICC complaint intake and resolution.

## Scope
Owner: Madhumita (@madhumitha-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** committees (SGRC, anti-ragging, ICC, ombudsperson) and their members; complaints on the student
grievance, ragging and sexual harassment tracks; acknowledgement, inquiry with committee-only proceedings, updates
between committee and complainant, decision, transfer, withdrawal; SGRC appeals to the ombudsperson; configurable due
dates worked out when read; open-case counts behind the Governance widget `grievance.open-by-committee` and the
Management widget `grievance.open`. Case content is visible only to the complainant and the committee handling it.

**Not in scope:** evidence attachments, respondent access, anonymous complaints, appeals on the ragging and sexual
harassment tracks, reminders, helpdesk tickets (helpdesk) and hostel discipline records (hostel).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

## Backend
Package `eos_grievance` in `backend/src/`:

| Layer | Files | What |
|---|---|---|
| domain | `domain/cases.py`, `errors.py` | Tracks, committee kinds, statuses and the moves between them, due dates (calendar or working days), overdue and the appeal window. Pure Python. |
| application | `application/service.py`, `access.py`, `errors.py` | The use case behind every contract operation; permission keys; the committee-membership checks that limit every case operation; errors with their HTTP status. Every change writes an audit entry, and so does every read of case content by a committee member; filing and every final state publish their events from `contracts/events.yaml` to the `eos_core` outbox in the same transaction. |
| infrastructure | `infrastructure/models.py`, `repository.py`, `config.py`, `notifier.py` | The tables of the PRD data model, queries scoped to the caller's organisation, `GRIEVANCE_*` settings, the notice stand-in. |
| api | `api/router.py`, `schemas.py`, `deps.py` | All 19 operations of `contracts/openapi.yaml`, each with the permission the contract names. Error bodies are `{code, message}` in FastAPI's `detail`. A NUL character in a request is a 404 or 422, never a 500 on Postgres. |

Tables are prefixed `grievance_` and created by the module's own Alembic chain in `db/` (revision `grievance_0001`,
version table `grievance_alembic_version`). Every table carries `organisation_id`; on Postgres each gets the
`eos_core.rls` row-level-security policy. As in the other governance modules, a temporary `grievance_audit_entry` table
holds one row per change or read until the audit SDK and `platform/audit` exist. Data model: [docs/data-model.md](docs/data-model.md).

**Access.** A permission is not enough to see or change a case: the use cases check that the caller sits on the
committee that filed-with or was appealed to (reads), or that handles the case now (changes). A case a caller may not see
is "not found". Coordinators and management get counts only. Proceedings never reach the complainant.

### Needs from the host repo
- `packages/core` (`eos_core`); for tests, `packages/testing` (`eos_testing`).
- `governance/grievance` in `apps/backend/config/modules.enabled.yaml` and `apps/frontend/config/modules.enabled.yaml`,
  in a later pull request of #343.
- Permissions come from the roles in the token. The layouts already grant the module roles: Governance
  `grievance-coordinator`, Management `grievance-viewer`. The roles `grievance-complainant` and
  `grievance-committee-member` are not on any layout yet (PRD open question 10), so until identity grants them, nobody
  can file or work a case; see "Assumptions to revisit".
- `platform/notification` through `packages/sdk`: not shipped yet, so notices go through `infrastructure/notifier.py`.

## Frontend
- `frontend/src/widgets/OpenByCommitteeWidget.tsx` is `grievance.open-by-committee` (Governance): open cases per
  committee with their statuses and overdue counts, from `GET /stats/open-by-committee`.
- `frontend/src/widgets/OpenWidget.tsx` is `grievance.open` (Management): open cases per track with overdue counts, from
  `GET /stats/open`.

Both need `grievance:stats:read`, show counts only, and use `@eos/ui-kit` and the widget error convention: 404, 502, 503
or a network failure is "Grievance data is not available yet." with retry; a 401 or 403 offers no retry.
`frontend/src/api/client.ts` is a small typed client matching the contract until the repo has a generated one. Tests are
in `frontend/tests/` (Vitest and Testing Library). Complaint screens are not part of this pull request.

## Run the checks
```
cd modules/governance/grievance/backend
PYTHONPATH=src:../../../../packages/core/src:../../../../packages/testing/src python -m pytest -q tests
ruff check --config tools/config/ruff.toml modules/governance/grievance    # from the repo root
pnpm --filter @eos/grievance typecheck && pnpm --filter @eos/grievance test
```
Row-level security on a real PostgreSQL: `tests/test_rls_postgres.py` runs only when `GRIEVANCE_TEST_POSTGRES_URL` is
set to a superuser URL of a **throwaway** server. It creates its own database and a temporary role that is neither a
superuser nor allowed to bypass RLS, checks the forced `tenant_isolation` policy on every table and each organisation's
isolation, then drops both.

## Assumptions to revisit
Where the PRD leaves a question open, the simplest reading is built; each is one place to change.
1. **No timelines by default (PRD question 1).** The acknowledge-by, decide-by and appeal-window days are empty in
   `config/env.example`. With no value a case has no due date and is never overdue; with no appeal window every appeal
   is refused (409 "Appeal window is not configured") and a decided case closes at once, since nothing can be appealed.
   An empty `GRIEVANCE_DAY_COUNTING` counts calendar days; `working` skips Saturdays and Sundays, with no holiday calendar.
2. **What "due" means.** A submitted case is due `acknowledge_days` after filing; an acknowledged or under-inquiry case is
   due `decide_days` after filing. Decided, appealed and appeal-decided cases have no due date.
3. **Who works a case after an appeal.** From `appealed` on, the ombudsperson committee handles the case (messages, appeal
   decision, closing). The SGRC members still read it but cannot change it (403). With several active ombudsperson
   committees the oldest hears the appeal.
4. **Transfer** keeps the status, moves the case to the new committee and notifies its members; the old committee loses
   access at once. The reason is kept in the audit entry.
5. **Audit.** Besides state changes, `GET /grievances/{id}` and every case returned by `GET /grievances` write an audit
   entry (PRD "Audit": every read of case content by a committee member). Audit entries keep the reasons given for a
   withdrawal, a refusal to admit and a transfer, never other case text.
6. **Notices** carry the case number only. platform/notification has no SDK yet, so `notifier.py` logs them and keeps the
   last ones in memory; swap its `send` for the SDK.
7. **Committee rules.** A committee may have no members, and a member may sit on a committee that handles a case they
   filed; composition rules are PRD question 7. Names are unique per organisation, ignoring case.
8. **Counts** list every active committee (and inactive ones with open cases) and, per track, all three tracks. An
   appealed case counts under the ombudsperson committee.
9. **Roles.** The complainant and committee-member roles are in the catalogue but on no profile layout; the host needs to
   grant them (PRD question 10) before the module is enabled.

## Contract notes for the owner
- `MyGrievance` has no `organisation_id`, so the shared cross-tenant helper cannot compare organisations on
  `GET /me/grievances`; the test compares rows instead.
- `PATCH /committees/{id}` documents only 409; a committee that does not exist answers 404, and a duplicate name 409
  `name_used`.
- `POST /me/grievances/{id}/updates`, `.../withdraw` and `.../appeal` on another person's case answer 404, as for reads.
- A change by a member of a committee that can see the case but no longer handles it (an SGRC member after an appeal)
  answers 403; the contract does not say.
- Error bodies are `{code, message}`, as in the other governance modules; the contract defines none.

## Layout
| Path | Purpose |
|---|---|
| `docs/` | PRD, user stories, data model, screen list |
| `contracts/` | OpenAPI, event schemas, permission catalogue |
| `backend/` | Domain, application, infrastructure, API layers + unit tests |
| `frontend/` | Pages, components, API client + tests |
| `mobile/` | Mobile screens (optional) |
| `db/` | Migrations and seed data, own schema only |
| `config/` | `env.example`, feature flags |
| `tests/e2e` | End-to-end tests runnable in isolation |

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
