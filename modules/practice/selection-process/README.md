# selection-process

**Domain:** practice  
**Kind:** feature  
**Status:** in-progress  
**Tier:** common  

Generic selection process engine supporting auditions, casting calls, jury rounds, squad selection, moot court teams, and research supervisor allocations (ADR-0004).

## Scope
- Configurable process types, stages, and panels per organisation.
- Candidate registration with duplicate registration protection.
- Multi-panelist evaluation with scoring and decision uniqueness per candidate per stage.
- Automatic stage progression and direct finalization (`selected`, `waitlisted`, `rejected`).
- Outbox event publication on candidacy lifecycle changes.
- Four role-tailored dashboard widgets:
  - `selection-process.my-applications`: Candidate applications and stage tracking.
  - `selection-process.open-calls`: Available audition and selection calls.
  - `selection-process.to-judge`: Panels awaiting judge review and decisions.
  - `selection-process.upcoming`: Scheduled auditions, jury slots, and selection events.

## Public surface
- API: [contracts/openapi.yaml](contracts/openapi.yaml)
- Events: [contracts/events.yaml](contracts/events.yaml)
- Permissions: [contracts/permissions.yaml](contracts/permissions.yaml)

## Database
- Own schema with prefix `selection_process_` and dedicated version table `selection_process_alembic_version`.
- PostgreSQL RLS enabled on all tables via `eos_core.rls.POLICY`.
- Composite tenant indexes and integrity constraints.
