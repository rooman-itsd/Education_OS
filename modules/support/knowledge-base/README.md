# knowledge-base

**Domain:** support
**Kind:** feature
**Status:** in-progress (backend and widget built and tested; not yet listed in `modules.enabled.yaml`)

Articles, FAQs and how-to guides for self-service.

## Scope
Owner: Madhumita (@madhumitha-rooman). Requirements: [docs/prd.md](docs/prd.md).

**In scope:** articles, FAQs and how-to guides for every signed-in person, with `everyone` and `staff` audiences;
a two-level category tree and tags; drafts and immutable revisions with history and rollback; review, publish,
archive and restore; browse and full-text search (`GET /articles?q=`); helpful / not-helpful feedback; the usage
statistics behind the Support Staff widget `knowledge-base.top-articles`. Article ids are stable so helpdesk tickets
can link to them.

**Not in scope:** helpdesk tickets and their links (helpdesk), incidents and problems (incident-management), public
website pages and news (web-portal-cms), course content (lms), the library catalogue (library), the search engine and
file storage themselves (platform/search, platform/documents), attachments in v1, AI answers, translation.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Dependencies
See `module.yaml`. This module must not import code from any other module under `modules/`.

## Backend
Package `eos_knowledge_base` in `backend/src/`:

| Layer | Files | What |
|---|---|---|
| domain | `domain/articles.py`, `categories.py`, `search.py`, `stats.py`, `errors.py` | Article and revision states and the moves between them, slugs, review dates and staleness; the two-level category tree; search matching, relevance and snippets; the top-articles ranking. Pure Python. |
| application | `application/service.py`, `access.py`, `errors.py` | The use case behind every contract operation; permission keys and checks, with the audience enforced in every read; errors with their HTTP status. Every state change writes an audit entry, and publish, restore and archive publish their event from `contracts/events.yaml` to the `eos_core` outbox in the same transaction. |
| infrastructure | `infrastructure/models.py`, `repository.py`, `config.py` | The tables of the PRD data model, queries scoped to the caller's organisation, view counting, `KNOWLEDGE_BASE_*` settings. |
| api | `api/router.py`, `schemas.py`, `deps.py` | All 19 operations of `contracts/openapi.yaml`, each with the permission the contract names. Error bodies are `{code, message[, field]}` in FastAPI's `detail`. |

Tables are prefixed `knowledge_base_` and created by the module's own Alembic chain in `db/` (revision
`knowledge_base_0001`, version table `knowledge_base_alembic_version`). Every table carries `organisation_id`; on
Postgres each gets the `eos_core.rls` row-level-security policy. As in helpdesk and amc-vendor-support, a temporary
`knowledge_base_audit_entry` table holds one row per state change until the audit SDK and `platform/audit` exist.

Decisions where the contract or PRD leaves a detail open (also noted in `application/service.py`):
- **Search** runs over the module's own data (PRD open question 1). Every word of `q` must appear in the title,
  summary, body or tags. Relevance weighs title 3, tags and summary 2, and body 1. The snippet is plain text with the
  matched words in `**bold**`. `GET /articles?q=` stays the contract whatever engine comes later.
- **Audience** is enforced on the server in every read, list, search and statistic. An article the caller may not
  read is "not found" (404), so its existence is not revealed.
- **Views** count at most once per reader per article per day and are stored as daily totals. To know who already
  counted today, a hash of the organisation, article, reader and day is kept for today only. Earlier days' keys are
  deleted, so no reading history is kept.
- **Notifications** for submit and return go through notification in the PRD. There is no notification SDK yet, so
  v1 records both steps in the audit table only.
- **Writes to one article lock its row first**, so revision numbers, the open revision and the vote counts never race.
  Concurrent first views of a day use `INSERT ... ON CONFLICT DO NOTHING`.
- `GET /articles` defaults `status` to `published`, or to `draft` and `published` with `owner` or `in_review`.
  Archived articles appear only when asked for with `status`.

### Needs from the host repo
- `packages/core` (`eos_core`); for tests, `packages/testing` (`eos_testing`).
- `support/knowledge-base` in `apps/backend/config/modules.enabled.yaml`, added in a later pull request of #342.
  From that list the module loader mounts `eos_knowledge_base.api.router:router` at `/api/v1/knowledge-base`, the API
  image installs the package, the auto-deploy runs the Alembic chain and CI runs `backend/tests`. Until then the
  module's tests run only as shown below.
- Permissions come from the roles in the token. The `support-staff` profile role gets the grants of
  `knowledge-base-viewer` through its dashboard layout, so it can read articles and the widget. No layout grants
  `knowledge-base-author`, `knowledge-base-editor` or `knowledge-base-reader` yet. Until a layout grants them, nobody
  on a live site can write or publish articles, and other profile roles cannot read them.

## Frontend
`frontend/src/widgets/TopArticlesWidget.tsx` is the Support Staff widget `knowledge-base.top-articles`
(`platform/identity/config/dashboards/support-staff.yaml` already lists it). It shows the published articles read
most in the last 30 days, each with its type, how readers rated it ("85% found it helpful", or "No votes yet") and its
views, from `GET /api/v1/knowledge-base/stats/top-articles` (permission `knowledge-base:stats:read`). It uses
`@eos/ui-kit` (`List`, `ListRow`, `Badge`, `SkeletonLines`, `EmptyState`, `ErrorState`). While the API is not mounted
or unreachable (404, 502, 503, network failure) it says "Knowledge base data is not available yet."; a 401 or 403
offers no retry. `frontend/src/api/client.ts` is a small typed client matching the contract's `TopArticles`, until
the repo has a generated client. Tests are in `frontend/tests/` (Vitest and Testing Library).

The dashboard shows the widget once `apps/frontend/config/modules.enabled.yaml` lists `support/knowledge-base`.

## Run the checks
```
cd modules/support/knowledge-base/backend
PYTHONPATH=src:../../../../packages/core/src:../../../../packages/testing/src python -m pytest -q tests
#   Python 3.12; dependencies plus the test extras (pytest, pyyaml, httpx, eos-testing, psycopg[binary])
cd modules/support/knowledge-base/db && alembic upgrade head                  # own tables only; EOS_DATABASE_URL
ruff check --config tools/config/ruff.toml modules/support/knowledge-base    # from the repo root
ruff format --config tools/config/ruff.toml --check modules/support/knowledge-base
pnpm --filter @eos/knowledge-base typecheck && pnpm --filter @eos/knowledge-base test   # widget
```
Instead of `PYTHONPATH`, the module can be installed with its test extras, from the repo root:
`pip install ./packages/core ./packages/testing "./modules/support/knowledge-base/backend[test]"`. It does not depend
on `packages/sdk`, which has no package yet. Tests use a throwaway SQLite file, never a real database.

Row-level security on a real PostgreSQL: `tests/test_rls_postgres.py` runs only when `KNOWLEDGE_BASE_TEST_POSTGRES_URL`
is set to a superuser URL of a **throwaway** server (for example `postgres:16-alpine`). It works like this:
- it creates its own database, and a temporary role that is neither a superuser nor allowed to bypass RLS;
- it checks the forced `tenant_isolation` policy on all 7 tables;
- on 3 of them (`knowledge_base_category`, `knowledge_base_article`, `knowledge_base_audit_entry`) it checks that each
  organisation sees and writes only its own rows;
- it checks that two first views of a day at the same time both count;
- it then drops the database and the role.

It is a test setting, not module configuration, so it is not in `config/env.example`.

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
