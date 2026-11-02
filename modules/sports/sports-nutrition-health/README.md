# sports-nutrition-health

**Domain:** sports
**Kind:** feature
**Status:** in-progress

Diet plans, medical records, injury tracking, physio sessions.

## Scope
Responsible for: nutrition (diet) plans and their reviews, confidential health records (history, allergies,
medication, screenings, vaccinations), injuries from report to recovery, and physiotherapy, medical and nutrition
appointments.

Not responsible for: athlete profiles, results and fitness clearance (`athlete-performance`), training plans and video
(`training-video-analysis`), tournaments (`tournament-events`). Athletes are referenced by athlete-performance's
athlete id, never by a foreign key.

Confidentiality: health records need `health-record:read`, held only by medical roles (`org-admin` does not get it).
An injury's `clinical_notes` are returned only to holders of `health-record:read` and written or cleared only with
`health-record:write` (403 otherwise); coaches, athletes and org-admin see the injury, its status and expected return.
Appointment `notes` are clinical too: returned to and written by medical roles, and by a nutritionist (`plan:write`)
only for `nutrition` appointments. Since the type decides who sees the notes, changing the type of an appointment that has
notes needs the right to write notes of both the old and the new type. Events carry ids, statuses and dates only, and audit entries never copy clinical or
free-text fields.

Athletes see only their own plans, injuries and appointments. This module learns which user is which athlete from
`athlete-performance.athlete.registered` (consumed through the event bus, `application/consumers.py`); until that event
arrives, an athlete user sees nothing. A newer registration of the same athlete moves the link; an older one delivered
late does not.

Behaviour worth knowing: only an active plan is reviewed; a review that ends a plan completes it; a completed or
archived plan can only move between those two states and is never due for review; a resolved injury records
`resolved_on`; a scheduled appointment is in the future (a past session is logged as completed); an appointment is
completed or marked no-show only once its time has passed; a cancelled, no-show or completed appointment takes only
notes; `?on=` on appointments is a UTC day.

Requirements: [docs/prd.md](docs/prd.md). Tables: [docs/data-model.md](docs/data-model.md).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dashboard widgets
`frontend/src/widgets/index.ts` exports the widgets the role layouts in `platform/identity/config/dashboards/` name:

| Widget | Layout | Permission | Endpoints |
|---|---|---|---|
| `sports-nutrition-health.nutrition-plan` | athlete | `plan:read` | `GET /nutrition-plans?status=active` (the athlete's own plans) |
| `sports-nutrition-health.injured-athletes` | medical-staff | `injury:read` | `GET /injuries?status=active`, `GET /injuries?status=recovering` |
| `sports-nutrition-health.appointments-today` | medical-staff | `appointment:read` | `GET /appointments?on=<UTC day>`, once or twice |
| `sports-nutrition-health.athletes-on-plans` | nutritionist | `plan:read` | `GET /nutrition-plans?status=active` |
| `sports-nutrition-health.plan-reviews-due` | nutritionist | `plan:read` | `GET /nutrition-plans?status=active&review_due_before=<today + 7 days>` |

Athletes are referenced by id only and this module has no endpoint that names them, so rows show a short id
("Athlete 3f2a9c7e"); a widget does not call athlete-performance for names. No widget shows an injury's clinical
notes or an appointment's notes: the client drops them before a widget sees the row.

`?on=` is a UTC calendar day, while "today" is the viewer's local day. A local day overlaps two UTC days unless the
viewer is on UTC (in India, 00:00 to 05:30 local is the previous UTC day), so appointments-today asks for each UTC
day the local day overlaps and keeps the appointments between local midnight and midnight. It lists the whole
organisation's appointments, not only the viewer's own (the widget does not know the viewer's user id).
List widgets load one page of 200 per request (the contract maximum); athletes-on-plans says so when more active
plans exist than it loaded.

## Dependencies
See `module.yaml`. From the host it needs `packages/core` (database, tenant scoping, outbox, tokens), for its tests
`packages/testing`, and `platform/event-bus` to deliver the consumed event. The backend is
`eos_sports_nutrition_health.api.router:router`; its Alembic chain is `db/`. This module must not import code from any other module under `modules/`.

**Known risk, fixed upstream:** athlete-performance lets an athlete's `user_id` change but publishes no event for it
(`TRACKED_ATHLETE_FIELDS` has no `user_id`, and only `athlete.registered` carries it). Until it does, an athlete
reassigned from user X to user Y stays linked to X here: X keeps seeing that athlete's plans, injuries and appointments,
and Y sees nothing. The fix is to add `user_id` to athlete-performance's `athlete.updated` event, then consume that
event here and move the link.

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
