# alumni

**Domain:** campus-life
**Kind:** feature
**Status:** in-progress (contracts)

Alumni directory and mentoring.

## Scope
- **In (v1.0):** a directory of alumni kept by staff (alumni have no login), a mentor flag, assignment of a mentor
  to a student, optional mentoring sessions, and the student's own view of their mentor (widget `alumni.mentoring`).
- **Not in v1.0:** alumni logins or self-registration, students browsing the directory, automatic matching, alumni
  events, donations and engagement campaigns (v1.1).

Product requirements and the owner's decisions: [docs/prd.md](docs/prd.md). Stories: [docs/user-stories.md](docs/user-stories.md).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml), base `/api/v1/alumni`
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml). Module roles `alumni-coordinator` and
  `alumni-mentee`; management-institute maps `placement-officer` and `management-student` onto them in their layouts.

## Dependencies
See `module.yaml`: platform identity and audit, through `packages/sdk`. This module must not import code from any
other module under `modules/`.

## Frontend

`frontend/src/widgets/index.ts` exports the dashboard widget. The management-student layout in
`platform/identity/config/dashboards/` places it and holds the module role `alumni-mentee`, which grants
`alumni:self:read`; the module's entry in `apps/frontend/config/modules.enabled.yaml` registers it (not enabled yet).

| Widget | Title | Dashboard | Endpoint | Permission |
|---|---|---|---|---|
| `alumni.mentoring` | My mentor | Management student | `GET /me/mentoring` | `alumni:self:read` |

- **Shows:** the student's active mentor: name, current designation and company, class year with programme,
  industry and city, the mentoring focus, "Mentoring since" with the start date, and the contact details the
  contract gives the assigned student (email as a `mailto:` link, phone as a `tel:` link, LinkedIn as a link that
  says it opens in a new tab; only http(s) addresses become links). Then up to five upcoming sessions, soonest first,
  each with its date and time in India (Asia/Kolkata, e.g. "Thu, 5 Nov 2026, 4:30 pm", whatever the viewer's zone),
  topic, mode, place (a meeting link becomes a link) and length. Upcoming means scheduled and at or after now; the
  contract already filters, and the widget filters again so a session that passes while the page is open drops off.
  Without sessions: "No sessions scheduled.". Staff notes are not in `MyMentoring` and are never shown.
- **Empty:** `assignment` is null (no active mentor): "No mentor assigned yet", with "Your alumni mentor and upcoming
  sessions appear here once one is assigned.".
- **States:** loading, empty, and error with a retry when trying again can help. Until the backend is mounted (404,
  502, 503 or no answer), "Alumni data is not available yet."; without the permission, "You do not have access to
  this." (no retry); with an expired session, "Sign in again to see this." (no retry); any other failure, "Could not
  load alumni data.". The request is cancelled when the widget unmounts, a retry's request included.
- **Dashboard journey:** the panel is found by the title "My mentor"; the probe is `GET /api/v1/alumni/me/mentoring`,
  which answers 200 with `assignment: null` for a new organisation, so the empty text is "No mentor assigned yet". No
  `emptyCode` is needed (the endpoint never answers 404 for "nothing yet").
- **Data:** the widget reads through `src/api/client.ts`, a hand-written typed client that the generated client will
  replace.
- **Tests:** `corepack pnpm --filter @eos/alumni test` (vitest and Testing Library; the tests run in the
  America/New_York zone to prove times are shown in India).

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
