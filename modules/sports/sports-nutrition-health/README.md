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
