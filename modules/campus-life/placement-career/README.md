# placement-career

**Domain:** campus-life
**Kind:** feature
**Status:** in-progress (contract)

Campus placement for jobs: company records, drives, job openings, applications and offers.

## Scope
**Is:** company records, placement drives (dated campus events of one company), job openings in a drive or on their
own, student applications along a fixed status sequence, offers, and the reports behind the dashboard widgets
`placement-career.drives` (placement-officer), `placement-career.openings` (learner layouts, `GET /me/openings`) and
`placement-career.openings-summary` (placement staff and industry-liaison, `GET /reports/openings-summary`).

**Is not:** internships (field-training), recruiter logins (companies are records), automatic eligibility checks
(students self-declare; the officer shortlists), a one-offer policy. See [docs/prd.md](docs/prd.md) for the owner
decisions on #337 and [docs/user-stories.md](docs/user-stories.md).

**Roles:** `placement-career-officer` (placement-officer, industry-coordinator and practicum-coordinator layouts),
`placement-career-viewer` (industry-liaison), and `student` grants inherited by every learner layout.

**Needs from the host:** `packages/sdk` for identity and audit. No configuration keys yet.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Frontend
`@eos/placement-career` (`frontend/`) exports three dashboard widgets from `frontend/src/widgets/index.ts`. Each declares
one permission and calls one endpoint through the hand-written typed client `frontend/src/api/client.ts` (paths under
`/api/v1/placement-career`, the shell's session token as `Authorization: Bearer`), and cancels its request when it
unmounts.

| Id | Title | Dashboards | Endpoint | Permission | Shows | Empty state |
|---|---|---|---|---|---|---|
| `placement-career.openings` | Job openings | learner layouts (engineering-student, hospitality-trainee, law-student, management-student) | `GET /me/openings?limit=5` | `placement-career:self:read` | Openings still taking applications, soonest closing first: company and place, CTC, campus drive date, "Apply by" date, the student's own application status; "Showing the N closing soonest; more are open." when the page has a next cursor | "No openings right now" / "Job openings you can apply to appear here." |
| `placement-career.openings-summary` | Placement openings | placement-officer, industry-coordinator, practicum-coordinator, industry-liaison | `GET /reports/openings-summary?limit=5` | `placement-career:report:read` | Open openings, applications (all statuses), students placed; offers awaiting an answer and unpublished drafts; the openings closing soonest with company, closing date and applications; "N more open openings" | "No openings yet" / "Job openings and applications appear here once openings are posted." |
| `placement-career.drives` | Upcoming drives | placement-officer | `GET /reports/drives-upcoming?limit=5` | `placement-career:report:read` | Drives in the next 30 days; the soonest drives with company, venue, date, registration closing date, openings and applications; "N more drives in the next 30 days" | "No drives scheduled" / "Scheduled campus drives appear here." |

States, the same in every widget: a loading skeleton; the empty state above; on failure an alert with
"Placement data is not available yet." (service unreachable, 404, 502, 503) or "Could not load placement data."
(anything else; the server's wording is never shown), both with **Try again**; "Sign in again to see this." (401) and
"You do not have access to this." (403) without a retry. Dates are contract dates shown as Indian calendar dates
("5 Nov 2026", `Asia/Kolkata`) whatever the viewer's time zone; amounts are rupees with Indian digit grouping
("₹6,50,000").

For the dashboard journeys (`tests/e2e/dashboards`): the probes are `/placement-career/me/openings`,
`/placement-career/reports/openings-summary` and `/placement-career/reports/drives-upcoming`; a new organisation gets
the empty titles above. No `emptyCode`: every endpoint answers 200 with an empty list or zero counts.

Tests: `corepack pnpm --filter @eos/placement-career test` (vitest and Testing Library, run in a time zone far from
India so a date read outside `Asia/Kolkata` fails) and `corepack pnpm --filter @eos/placement-career typecheck`.

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

## Layout
| Path | Purpose |
|---|---|
| `docs/` | PRD and user stories now; `data-model.md`, `screens.md` and `integration-points.md` come with the backend PR |
| `contracts/` | OpenAPI, event schemas, permission catalogue |
| `backend/` | Domain, application, infrastructure, API layers + unit tests |
| `frontend/` | Pages, components, API client + tests |
| `mobile/` | Mobile screens (optional) |
| `db/` | Migrations and seed data, own schema only |
| `config/` | `env.example`, feature flags |
| `tests/e2e` | End-to-end tests runnable in isolation |

## Porting this module to another repo
Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
