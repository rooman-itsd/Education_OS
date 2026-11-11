# rti

**Domain:** governance
**Kind:** feature
**Status:** in-progress (backend and widget built and tested; not yet listed in `modules.enabled.yaml`)

RTI request intake, assignment, tracking and responses.

## Scope
Owner: Madhumita (@madhumitha-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** recording RTI requests received by post, in person, by email or through an online portal, with the
applicant's details and fee metadata; assignment to an officer; referrals to internal custodians; responses, transfers
to other public authorities and closing; first appeals to the internal appellate authority; configurable due dates
worked out when read; the deadline list behind the Governance widget `rti.nearing-deadline`. Applicant personal data is
visible only to RTI officers and the appellate authority.

**Not in scope:** collecting fees (fees-accounts), a public online form or applicant self-service, attachments, second
appeals to outside bodies, messages to applicants, reminders and timers.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

## Backend
Package `eos_rti` in `backend/src/`:

| Layer | Files | What |
|---|---|---|
| domain | `domain/dates.py`, `deadlines.py`, `requests.py`, `errors.py` | Dates in India and day counting (calendar or working), due dates and the deadline list, request statuses and the moves between them, what each response type needs. Pure Python. |
| application | `application/service.py`, `access.py`, `errors.py` | The use case behind every contract operation; permission keys; errors with their HTTP status. Every change writes an audit entry; `rti.request.received` and `rti.request.closed` go from `contracts/events.yaml` to the `eos_core` outbox in the same transaction. |
| infrastructure | `infrastructure/models.py`, `repository.py`, `config.py` | The six tables of the PRD data model, queries scoped to the caller's organisation, `RTI_*` settings. |
| api | `api/router.py`, `schemas.py`, `deps.py` | All 14 operations of `contracts/openapi.yaml`, each with the permission the contract names. Error bodies are `{code, message[, field]}` in FastAPI's `detail`. Inputs are bounded (strings, dates 1900 to 2199, amounts, limit, cursor as plain ASCII digits), and NUL characters, NaN, Infinity, huge numbers and lone surrogates are a 4xx, never a 500. |

Tables are prefixed `rti_` and created by the module's own Alembic chain in `db/` (revision `rti_0001`, version table
`rti_alembic_version`). Every table carries `organisation_id`; on Postgres each gets the `eos_core.rls`
row-level-security policy. As in the other modules, a temporary `rti_audit_entry` table holds one row per change or read
until the audit SDK and `platform/audit` exist. See [docs/data-model.md](docs/data-model.md) and
[docs/integration-points.md](docs/integration-points.md).

### Deadlines
No statutory value is built in (PRD open question 1). Until the governance office sets them in `config/env.example`,
`RTI_RESPONSE_DAYS`, `RTI_APPEAL_WINDOW_DAYS` and `RTI_APPEAL_DECIDE_DAYS` are empty: there is no due date, nothing is
overdue, appeals are refused ("Appeal window is not configured") and a responded request stays `responded`. They are read
on every call, so a changed value applies to requests already recorded. Dates are dates in India (IST, UTC+05:30):
"today" is the date there, and a due date is met until the end of that day. `RTI_DAY_COUNTING` is `calendar` (empty
means calendar) or `working` (Monday to Friday; the day of the event is day 0). To apply the usual Right to Information
Act periods an organisation sets, for example, `RTI_RESPONSE_DAYS=30`, `RTI_APPEAL_WINDOW_DAYS=30`,
`RTI_APPEAL_DECIDE_DAYS=30` and `RTI_DAY_COUNTING=calendar`; a 48-hour period for life and liberty needs a field the
contract does not have (open question 2).

### Needs from the host repo
- `packages/core` (`eos_core`); for tests, `packages/testing` (`eos_testing`).
- `governance/rti` in `apps/backend/config/modules.enabled.yaml` and `apps/frontend/config/modules.enabled.yaml`, in a
  later pull request of #343.
- Permissions come from the roles in the token. The Governance layout already grants its profile role `rti-officer` and
  lists the widget. The other profile roles the PRD proposes (management as `rti-appellate-authority`, department-admin
  and faculty as `rti-custodian`, org-admin as `rti-viewer`) are not in any layout yet; that is a `platform/identity`
  change.

## Frontend
- `frontend/src/widgets/NearingDeadlineWidget.tsx` is `rti.nearing-deadline` (Governance): overdue and due-soon counts and
  the soonest ten open requests by request number, each with what it is waiting for (a response or an appeal decision)
  and "Overdue by N days", "Due today" or "Due in N days" in India's dates, from `GET /stats/nearing-deadline`
  (permission `rti:stats:read`). It shows no applicant data.

It uses `@eos/ui-kit` and the widget error convention: 404, 502, 503 or a network failure is "RTI data is not available
yet." with retry; a 401 or 403 offers no retry. `frontend/src/api/client.ts` is a small typed client matching the contract
until the repo has a generated one. Tests are in `frontend/tests/` (Vitest and Testing Library).

## Run the checks
```
cd modules/governance/rti/backend
PYTHONPATH=src:../../../../packages/core/src:../../../../packages/testing/src python -m pytest -q tests
ruff check --config tools/config/ruff.toml modules/governance/rti    # from the repo root
pnpm --filter @eos/rti typecheck && pnpm --filter @eos/rti test
```
Row-level security on a real PostgreSQL: `tests/test_rls_postgres.py` runs only when `RTI_TEST_POSTGRES_URL` is set to a
superuser URL of a **throwaway** server. It creates its own database and a temporary role that is neither a superuser
nor allowed to bypass RLS, checks the forced `tenant_isolation` policy on every table and each organisation's isolation,
then drops both.

## Assumptions to revisit
Where the PRD or the contract leaves a question open, the simplest reading was built. Each is a small change.

1. **Timelines** are settings with no default (above). No 30-day, 48-hour or appeal period is built in; the PRD and the
   contract name none (open questions 1 and 2).
2. **India's dates.** "Today" is the date in IST, not UTC. Working days are Monday to Friday; there is no holiday
   calendar in the repository, so public holidays count as working days.
3. **Due until the end of the day.** `due_at` is 23:59:59 IST of the due date (written in UTC). A request due today is
   not yet overdue.
4. **The appeal window runs from the dispatch date** of the response (`dispatched_on`), not from when it was recorded.
   An appeal is in time if its `filed_on` is within the window, even when it is recorded later. A responded request
   closes once today (India) is after the last day of the window.
5. **`due_at` and `overdue` on a request.** `due_at` is always the response deadline from `received_on`. `overdue` is
   whether the deadline the request is waiting on has passed: the response for `received` and `assigned`, the appeal
   decision for `appealed` (the `appeal.due_at`); other statuses are never overdue. The widget's `due_at` is that current
   deadline, and its list holds the soonest ten, with the counts covering all.
6. **Closure** is set when a request becomes final (`closed` or `transferred`), not when the appeal is decided.
7. **PATCH changes only what it sends.** Inside `applicant` and `fee` too: the keys left out keep their stored value, and a
   key sent as null clears it (a null `amount` also clears the currency). The contract still makes `name` and `status`
   required, so they are sent with any `applicant` or `fee` object. A body that changes nothing is a 422.
8. **Fee** is metadata only. A fee amount without a currency is in `RTI_DEFAULT_CURRENCY`; no rule links the status to the
   amount, and an amount has at most ten digits before the decimal point.
9. **Dates cannot be in the future** (received, dispatched, transferred, appeal filed and decided), cannot precede the step
   they follow (dispatch before receipt, an appeal before the response, a decision before the appeal), and are accepted
   from 1900 to 2199.
10. **Referrals.** The question may not repeat the applicant's name, email or phone (422). `GET /referrals` returns
    full referrals to holders of `rti:request:read` and a custodian's own, without applicant data, to holders of only
    `rti:referral:respond`; with both, the first. Referrals can be answered after the request moved on.
11. **Nobody is notified.** `platform/notification` has no SDK in `packages/sdk`, so assignments, referrals and replies are
    audited and name their person, and the notices can be added there.
12. **Reads are audited:** the detail, and every row of a list. A list that filters on `overdue` is filtered in memory
    (overdue depends on the settings and on how days are counted), then paged.
13. **Request numbers** are `<RTI_REQUEST_NUMBER_PREFIX>-<six digits>` per organisation, fixed when the request is recorded.
14. The responses of manage operations (assign, respond, transfer, correct) include the applicant, as the contract's
    `Request` requires; `rti-officer` holds both manage and read.

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
