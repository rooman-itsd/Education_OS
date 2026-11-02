# Portfolio Module

**Domain:** `practice`  
**Kind:** feature  
**Status:** active  
**Part of:** Issue #322 (Merges #116, #117, #106)

Learner portfolios: artworks, repertoire, showreels, designs, case studies, teaching and research portfolios. Follows the generic portfolio pattern (ADR-0004), remaining vocabulary-neutral with organisation-defined item types.

---

## 1. Scope

- **Item Types:** Organisation-defined types (`ItemType`) configuring required reviews and designated reviewers.
- **Items:** Draft, submitted, under review, changes requested, approved, and withdrawn states.
- **Media:** Attached files referencing document IDs stored by `platform/documents`.
- **Reviews:** Evaluations, rubric scoring, and critique from designated instructors/mentors.
- **Dashboard Widgets:**
  - `portfolio.my-portfolio`: Creative learner dashboard widget showing recent works and statuses.
  - `portfolio.reviews-pending`: Reviewer dashboard widget listing submissions awaiting review.

---

## 2. Public Surface

- **OpenAPI Contract:** [`contracts/openapi.yaml`](contracts/openapi.yaml) mounted at `/api/v1/portfolio`.
- **Event Outbox:** [`contracts/events.yaml`](contracts/events.yaml):
  - `portfolio.item.submitted`
  - `portfolio.item.reviewed`
  - `portfolio.item.withdrawn`
- **Permissions:** [`contracts/permissions.yaml`](contracts/permissions.yaml):
  - `portfolio:item-type:read`
  - `portfolio:item-type:manage`
  - `portfolio:item:read`
  - `portfolio:item:read-all`
  - `portfolio:item:write`
  - `portfolio:item:manage`
  - `portfolio:review:write`
  - `portfolio:review:manage`
  - Module roles: `portfolio-learner`, `portfolio-reviewer`, `portfolio-manager`.
  - Profile roles: `actor`, `artist`, `designer`, `filmmaker`, `musician`, `research-scholar`, `teacher-trainee` (Learners); `design-mentor`, `mentor-teacher`, `music-teacher`, `research-supervisor`, `studio-instructor` (Reviewers).

---

## 3. Database Schema & Alembic

- Migration chain in `db/migrations/versions/20261031_0001_initial.py` (revision `portfolio_0001`).
- Tables:
  - `portfolio_item_type`
  - `portfolio_item`
  - `portfolio_item_media`
  - `portfolio_review`
- Every table carries `organisation_id` with composite indexes and PostgreSQL Row Level Security (RLS) policies via `eos_core.rls.POLICY`.

---

## 4. Testing

```powershell
# Run isolated module test suite
pytest modules/practice/portfolio/backend/tests -v

# Run migration check
python tools/scripts/check-migrations.py

# Verify role inheritance
pytest apps/backend/tests/test_role_inheritance.py

# Verify frontend types
pnpm --filter @eos/portfolio typecheck
```
