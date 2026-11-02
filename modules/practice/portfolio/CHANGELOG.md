# Changelog — portfolio

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [0.1.0] - 2026-10-31
### Added
- Contracts: OpenAPI 3.1 specification, Outbox events (`portfolio.item.submitted`, `reviewed`, `withdrawn`), and permission catalog.
- Database: Alembic migration chain with `portfolio_item_type`, `portfolio_item`, `portfolio_item_media`, and `portfolio_review` tables.
- Multi-tenancy & Security: Every table enforces `organisation_id` indexing and PostgreSQL RLS policies (`eos_core.rls.POLICY`).
- Backend: Domain entities, application services, SQLAlchemy models, Pydantic schemas, and FastAPI router mounted at `/api/v1/portfolio`.
- Frontend: Typed API client and dashboard widgets `portfolio.my-portfolio` and `portfolio.reviews-pending`.
- Tests: Isolated backend test suite covering CRUD, lifecycle transitions, reviews, permissions, contract drift, and cross-tenant leak checks.
