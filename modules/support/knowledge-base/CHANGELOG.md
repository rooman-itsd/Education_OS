# Changelog — knowledge-base

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Searchable for platform/search: `contracts/searchable.yaml` (type `article`; `article.published` upserts, `article.archived` deletes) and a document provider on the `eos.search_documents` entry point. Indexes the title, body, slug and category of published articles; staff-only articles are readable only with `knowledge-base:article:read-internal`. Drafts and archived articles are never indexed.
- Module scaffolded.
- Contracts proposed: categories; articles of type article, FAQ and how-to with `everyone` and `staff` audiences;
  drafts and revisions with history and rollback; review, publish, archive and restore; browse and search
  (`GET /articles?q=`); feedback; `GET /stats/top-articles` behind the Support Staff widget
  `knowledge-base.top-articles`; two events (`article.published`, `article.archived`); permissions and roles.
- PRD (`docs/prd.md`).
- Backend (#342):
  - domain rules: article and revision states with one open revision at a time; review, return and discard; publish,
    with the previous revision superseded; archive and restore; slugs, review dates and staleness; the two-level
    category tree; search with relevance and snippets; the top-articles ranking;
  - use cases for all 19 operations, with the audience enforced in every read, an audit entry per state change and
    outbox events for publish, restore and archive;
  - views counted once per reader per day, as daily totals;
  - API router for every path in the contract.
- Alembic chain `knowledge_base_0001`: seven `knowledge_base_*` tables with `organisation_id`, RLS policy on Postgres.
- Tests: domain unit tests, API tests per area, input bounds, contract drift and event payload tests, cross-tenant
  leak test, migration test, settings test, row-level security and concurrent views on Postgres (opt-in).
- Widget `knowledge-base.top-articles` (GET /stats/top-articles) with loading, empty and error states following the
  widget error convention; typed API client in `frontend/src/api/client.ts`; vitest widget tests.
