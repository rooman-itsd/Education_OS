# Changelog — core

All notable changes to `eos-core`. Follows Keep a Changelog, semver per package.

## Unreleased

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
