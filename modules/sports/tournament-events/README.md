# tournament-events

**Domain:** sports
**Kind:** feature
**Status:** in-progress

Tournaments, fixtures, results, officials and event logistics.

## Scope
Responsible for: tournaments (draft, publish, cancel), athlete and team entries per category, fixtures (matches,
heats, rounds), results and placings, officials assigned to a tournament or a fixture, travel and event logistics, and
the calendar of published tournaments and their fixtures.

Not responsible for: athlete profiles, performance records and benchmarks (`athlete-performance`), training and video
(`training-video-analysis`), medical and nutrition records (`sports-nutrition-health`), facility booking
(`facility-booking`), ticketing and payments. Athletes, disciplines and users are referenced by their ids as plain
values, never by foreign keys; `tournament-events.result.recorded` names the athletes behind each placing so
athlete-performance can record competition results.

How it behaves (`domain/rules.py`, `application/service.py`):
- A tournament is created as a `draft`. Drafts, and everything under them, are visible only to holders of
  `tournament:write`; to anyone else they answer 404 and lists leave them out. Publishing (draft only) opens entries.
  A published tournament reads `ongoing` from its `start_date` and `completed` after its `end_date`, in the
  institution's local date (`TOURNAMENT_EVENTS_TIMEZONE`); the stored status is only draft, published or cancelled.
  Draft, published and ongoing tournaments can be cancelled with a reason; that also cancels their fixtures still to be
  played. Cancelled and completed tournaments cannot be edited.
- Entries open on publishing and close after `registration_closes_on` (inclusive, local date) or when the tournament
  ends. A new entry is pending or confirmed; pending goes to confirmed or withdrawn, confirmed to withdrawn, and a
  withdrawn entry is final. An athlete has at most one live entry per category. Confirming, or changing the athletes of
  a confirmed entry, publishes `entry.confirmed`.
- Fixtures are scheduled on a published (or ongoing) tournament, on one of its local days, with entries of that
  tournament that are not withdrawn (and of the fixture's category, if it has one); `entry_ids` may be empty while the
  participants are still to be decided. Moves: scheduled to in progress, postponed or cancelled; postponed back to
  scheduled or cancelled; in progress to postponed or cancelled. A new time or venue, or a postponed fixture scheduled
  again, publishes `fixture.scheduled`.
- A result is recorded (PUT) once the fixture's time has passed and while it is scheduled or in progress; recording
  completes the fixture. PUT again on a completed fixture corrects the result and publishes `result.recorded` again;
  the same result sent twice changes nothing.
- Logistics are one record per tournament; PUT replaces it (a field left out is cleared).
- Athletes see only their own entries. Which user is which athlete is learnt from athlete-performance's
  `athlete.registered` and `athlete.updated` events (`application/consumers.py`); an athlete not linked yet sees no
  entries. Tournaments, fixtures, results, officials and logistics of a visible tournament are the same for every
  reader.
- The calendar lists published (ongoing and completed included) tournaments with a day in the period and their
  fixtures that are not cancelled, on the institution's local days, for at most 366 days at a time.
- Every change writes an audit entry (changed fields only; descriptions, notes, cancellation reasons, accommodation
  and officials' names are not copied) and every event goes through the outbox in the same transaction.

Requirements: [docs/prd.md](docs/prd.md).

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. From the host it needs `packages/core` (database, tenant scoping, outbox, tokens) and, for its
tests, `packages/testing`. The backend is `eos_tournament_events.api.router:router`; its event consumers are on the
`eos.event_consumers` entry point; its Alembic chain is `db/`. This module must not import code from any other
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
