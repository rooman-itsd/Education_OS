# Changelog — core

All notable changes to `eos-core`. Follows Keep a Changelog, semver per package.

## Unreleased

### Added
- `Settings.check_secrets()` (security review N21, October S7 follow-up): with `EOS_DEV_MODE` false it raises
  `InsecureSettingsError` when `EOS_JWT_SECRET` is unset or the built-in development key (`DEV_JWT_SECRET`), or
  shorter than 32 bytes. apps/backend calls it first thing in `create_app`, so such an API never starts.
- `eos_core.workflow` (#325 Q10): `submit(db, organisation_id, *, chain_code, entity_type, entity_id, title,
  requested_by, description=None, context=None, client_token=None) -> dict` sends a record for approval through
  platform/workflow without importing it. It delegates to `hooks.submit`, None until the host wires it
  (apps/backend does, to workflow's create-request use case); unwired it raises `WorkflowUnavailableError`, and a
  refusal is `WorkflowRefusedError` with `code` `unknown_chain`, `chain_has_no_steps` or `invalid_request`.

### Fixed
- A request body or query with `NaN`, `Infinity`, `-Infinity`, `1e999` or a lone surrogate answers 422, not 500.
  `eos_core.http_errors.install_error_handlers(app)` (called by `create_app`) quotes such an input back as text in
  the usual `detail`; every other validation error is unchanged. Modules need no workaround.

### Added
- `module_roles` on a dashboard layout: `load_role_parents()` returns them as additional parents of the layout's
  role (after `extends`), so `expand_roles` and `permissions_for` grant them. Transitive, cycle-safe, and the
  `module_roles` of an extended role are inherited. `load_role_parents()` now returns `dict[str, list[str]]`.
- `load_platform_keys()`.

### Fixed
- `permissions_for(..., super_admin=True)` holds every `platform:` key any catalogue declares in `permissions:`,
  granted to a role or not (so `platform:audit:read` is included).

### Added
- Role inheritance. `permissions_for` expands the roles through the `extends` of their dashboard layouts
  (`platform/identity/config/dashboards/*.yaml`) before looking up grants, so a role holds its own catalogue grants
  plus those of the role it extends: every academy learner role that extends `student` and every staff role that
  extends `faculty` now holds what those roles hold. Transitive, stops at a role already seen (cycle-safe), and only
  adds keys. The super-admin `platform:` rule is unchanged.
- `load_role_parents()` (cached like `load_role_grants`; tests clear it with `load_role_parents.cache_clear()`) and
  `expand_roles(roles)`.
