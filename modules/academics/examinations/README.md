# examinations

**Domain:** academics
**Kind:** feature
**Status:** in progress (issue #325). Built: the backend domain rules and persistence foundation (exam cycles, grading
and assessment schemes, papers, sessions, duties), the permission keys and the authentication guard, and the three
Examination Staff widgets (their endpoints are not served yet) and the Faculty widget `exam-duties` (it reads
`GET /me/duties`, which the API serves). The API serves 28 of 51 operations: grading schemes,
assessment schemes, exam cycles, exam papers, exam sessions and exam duties (`api/router.py`), mounted under
`/api/v1/examinations` because the module is listed in `apps/backend/config/modules.enabled.yaml`. Not built: the other
23 operations, candidate creation and eligibility, hall tickets,
marks, results, the consumers other than the two offering ones, and the widgets `upcoming-assessments` and `results-summary`.
`application/consumers.py` fills `offering_ref` from academic-management's `offering.created` and `offering.status-changed`, and papers serve `course_code`, `course_title` and `department_id` from it when it has them (omitted otherwise; an offering created before the consumers may have no row until a backfill, and later offering changes are not applied). Open
decisions: [docs/reviewer-decisions.md](docs/reviewer-decisions.md).
The `examinations_candidate` table exists (migration `ex_0005`, schema only): nothing creates, reads or serves candidates yet.

Exam scheduling, hall tickets, evaluation, results, transcripts.

## Scope
Runs the examination lifecycle of an organisation: exam cycles, assessment and grading schemes, papers, sessions, candidates
and eligibility, hall tickets, duties, mark entry, moderation and results. What it does not own (student and staff identity,
academic catalogue, attendance, fees, files) is in [docs/prd.md](docs/prd.md) section 3.

## Backend foundation
Under `backend/src/eos_examinations/`:

| Layer | What it holds |
|---|---|
| `domain/` | Rules independent of FastAPI and SQLAlchemy: `cycles` (lifecycle, FR-1), `grading` (FR-3), `assessment` (FR-2, activation supersedes), `papers` (FR-4, marks pipeline), `sessions` (FR-5, FR-6 and duties, FR-9) |
| `infrastructure/` | `models.py` (11 `examinations_` tables, all with `organisation_id`) and `repository.py` (every query goes through `eos_core.db.scoped`) |
| `application/` | `access.py` (the 43 permission keys of `contracts/permissions.yaml`, checked by a test) and `errors.py` |
| `api/` | `deps.py`: token authentication and `require()`; `router.py`: the grading-scheme, assessment-scheme, exam-cycle, paper and session operations (24) |

Tables: `grading_scheme`, `grading_band`, `exam_cycle`, `assessment_scheme`, `assessment_component`, `exam_paper`,
`exam_session`, `session_paper`, `exam_duty`, `offering_ref` and `audit_entry`. The database itself holds one default grading
scheme per organisation, one active assessment scheme per course offering, one paper per component and cycle, a paper in at
most one session, and the rule that a duty names a session (invigilation) or a paper (evaluation, moderation), never both.

Deliberately not built, because they depend on decisions not yet taken: candidate creation, hall tickets, mark entries, results and the
registration read model (which registrations make a candidate, and the eligibility inputs), grading-band coverage (whether `max_percent` is
inclusive), department-scoped authorisation, and every event consumer except the two offering ones. See [docs/reviewer-decisions.md](docs/reviewer-decisions.md).

## Tests
Backend, from `modules/academics/examinations/backend` (a throwaway SQLite database, never a real one):
```
PYTHONPATH="src:../../../../packages/core/src:../../../../packages/testing/src" python -m pytest -q
```
(use `;` instead of `:` on Windows). The PostgreSQL row-level-security tests run only when `EXAMINATIONS_TEST_POSTGRES_URL`
points at a throwaway PostgreSQL server as a superuser.

## Migrations
```
cd modules/academics/examinations/db && alembic upgrade head
```
The database URL comes from `EOS_DATABASE_URL`, or `alembic -x url=... upgrade head`. The chain is `ex_0001`, `ex_0002` (the optional paper title) then `ex_0003` (one live duty per target), with its own
version table `examinations_alembic_version`.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

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
