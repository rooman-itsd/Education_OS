# training-video-analysis

**Domain:** sports
**Kind:** feature
**Status:** in-progress

Training plans, sessions, video upload, tagging and annotation.

## Scope
Responsible for: training plans, the sessions inside them (schedule, location, attendees, status and completion), the
drill repository, the metadata of training and performance videos, drill tags on a video's timeline and time-coded
coaching annotations.

Not responsible for: the video files themselves (`platform/documents`; a video here keeps its `video_url` and
metadata only), athlete profiles and performance (`athlete-performance`), tournaments (`tournament-events`), medical
and nutrition records (`sports-nutrition-health`), facilities and their booking (`sports-facilities`,
`facility-booking`) and sign-in (`platform/identity`). Athletes, coaches, squads and facilities are referenced by
their ids, never by foreign keys.

Who sees what (`application/service.py`). Coaches and administrators see their organisation's plans, sessions and
videos. An athlete sees, read-only:
- the sessions that list them as an attendee, without the coach's notes and without the other attendees' ids;
- the plans those sessions belong to;
- the videos of those sessions and any video with an annotation that tags them;
- on those videos, every drill tag and the annotations that tag them or tag no one, with only their own tagged id.

Anything else answers 404. Which user is which athlete is learnt from athlete-performance's `athlete.registered` and
`athlete.updated` events (`application/consumers.py`); an athlete not linked yet sees nothing.

Behaviour:
- A plan moves draft → active → completed → archived (draft and active may also be archived). An archived plan is
  read-only and a completed or archived one takes no new sessions. Its dates may not move past its sessions.
- A session moves scheduled → in_progress → completed, or to cancelled; completed and cancelled are final. A closed
  session keeps its schedule, but its attendees, drills, notes and actual duration may still be recorded. It cannot
  be completed before it starts, and `session.completed` carries the actual duration or, without one, the scheduled
  length.
- A session in a plan starts on one of the plan's days, by the institution's local date
  (`TRAINING_VIDEO_ANALYSIS_TIMEZONE`); the session list's `from_date`/`to_date` are local dates too. Times are
  stored and returned in UTC.
- Drill tags lie inside the video (0 ≤ start < end ≤ duration) and name a drill of the repository. Annotations point
  inside the video; they are written in the caller's name (`author_id` must be the caller), changed only by their
  author and removed by their author or anyone else holding `annotation:write`.
- Every change writes an audit entry without titles, notes, annotation text, markup or file links.

Requirements: [docs/prd.md](docs/prd.md). Tables: [docs/data-model.md](docs/data-model.md).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. From the host it needs `packages/core` (database, tenant scoping, outbox, tokens) and, for its
tests, `packages/testing`. The backend is `eos_training_video_analysis.api.router:router`; its Alembic chain is `db/`;
its event handlers are on the `eos.event_consumers` entry point. This module must not import code from any other
module under `modules/`.

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
