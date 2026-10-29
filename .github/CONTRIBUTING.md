# Contributing

The enforced rules are in [docs/team/RULES.md](../docs/team/RULES.md). This file is the how-to.

## Branches
- `main` — always deployable. Protected. PR + 1 approval from a code owner of the files (owner or backup, `.github/CODEOWNERS`); the lead is needed only for platform core, packages and architecture docs.
- `feat/<module>/<short-desc>` — feature work inside one module.
- `platform/<service>/<short-desc>` — platform work.
- `contract/<module>/<short-desc>` — contract changes. Reviewed by the owner of every consuming module.

A PR touches **one module** unless it is a contract change plus its consumers.

## Order of work for a new feature
1. `docs/prd.md` and `docs/user-stories.md` in the module.
2. `contracts/openapi.yaml`, `events.yaml`, `permissions.yaml`. Open a `contract/` PR.
3. `db/migrations` for the module's own schema.
4. Backend domain → application → infrastructure → api, with tests.
5. Frontend pages against the generated client.
6. `tests/e2e`.
7. Update `CHANGELOG.md` and `module.yaml` status.

## Where tests go
- Tests for one module live inside that module: `backend/tests`, `frontend/tests`, `tests/e2e`.
- Tests that span modules or the composed apps live in the root [`tests/`](../tests/) folder
  (`integration`, `contract`, `e2e`, `performance`, `fixtures`). See [tests/README.md](../tests/README.md).
- Never put tests under `src/`, `apps/` or `packages/<pkg>/src/`.

## Definition of done
- [ ] Contracts updated and reviewed
- [ ] Tests pass with the module alone (platform stubs)
- [ ] Cross-module behaviour covered in root `tests/` if the change touches a contract
- [ ] No imports outside the module and `packages/`
- [ ] `config/env.example` complete
- [ ] README and CHANGELOG updated
- [ ] Audit events emitted for every state change
- [ ] Permission keys registered
- [ ] Every new table has `organisation_id` and an RLS policy; cross-tenant leak test passes

## Commits
Conventional commits scoped by module: `feat(admissions): add merit list generation`.

## Adding an institution type
Start with a profile in `platform/identity/config/profiles/`, listing suites, modules, roles,
dashboards and vocabulary. Prefer configuring a generic common module over writing a specialized
one; write a specialized module only for behaviour no pattern can express (ADR-0004).

## Decisions
Anything that affects more than one module gets an ADR in `docs/architecture/adr/`.
