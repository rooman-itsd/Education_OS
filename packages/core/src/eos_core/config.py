"""Loaders for the repo's YAML configuration: academy profiles, plans, permission catalogues.

Permissions. A role's keys are the grants every contracts/permissions.yaml gives that role name, plus the keys of
the roles its dashboard layout names as parents. A layout in platform/identity/config/dashboards/<role>.yaml has
two ways to name them:

- `extends: student` (or `faculty`): the role holds everything `student` holds, so an academy role such as
  research-scholar or coach is usable in every module whose catalogue only names the common roles.
- `module_roles: [projects-member, portfolio-learner, ...]`: the role also holds each listed role. A module grants
  its own roles (`projects-member`, `lms-instructor`, ...) and knows nothing of any academy's profile roles; the
  layout of each profile role says which module roles that role holds. `module_roles` of a role the layout
  extends are inherited too, so the base `student` and `faculty` layouts list the module roles every learner or
  teacher holds and an extending layout lists only its own.

Inheritance follows both transitively and stops at a role already seen, so a cycle cannot loop. It only adds keys.
A module that wants to give an academy role more than its parents hold names that role in its own catalogue.
A super admin additionally holds every `platform:` key any catalogue declares in its `permissions:` list, whether
or not a role is granted it.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from .settings import settings


def _root() -> Path:
    return settings.repo_root


@lru_cache(maxsize=1)
def load_profiles() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in sorted((_root() / "platform/identity/config/profiles").glob("*.yaml")):
        data = yaml.safe_load(f.read_text())
        out[data["profile"]] = data
    return out


@lru_cache(maxsize=1)
def load_plans() -> dict[str, dict]:
    data = yaml.safe_load((_root() / "platform/billing/config/plans.yaml").read_text())
    return {p["id"]: p for p in data["plans"]}


@lru_cache(maxsize=1)
def load_role_grants() -> dict[str, set[str]]:
    """role name -> permission keys, from every contracts/permissions.yaml in the repo."""
    grants: dict[str, set[str]] = {}
    for f in _root().glob("*/*/contracts/permissions.yaml"):
        data = yaml.safe_load(f.read_text()) or {}
        for role in data.get("roles") or []:
            grants.setdefault(role["name"], set()).update(role.get("grants") or [])
    for f in _root().glob("modules/*/*/contracts/permissions.yaml"):
        data = yaml.safe_load(f.read_text()) or {}
        for role in data.get("roles") or []:
            grants.setdefault(role["name"], set()).update(role.get("grants") or [])
    return grants


@lru_cache(maxsize=1)
def load_role_parents() -> dict[str, list[str]]:
    """role name -> its parent roles, from platform/identity/config/dashboards/*.yaml.

    The parents are the role the layout `extends` (first) and the roles in its `module_roles`, without duplicates
    and without the role itself.
    """
    parents: dict[str, list[str]] = {}
    for f in sorted((_root() / "platform/identity/config/dashboards").glob("*.yaml")):
        data = yaml.safe_load(f.read_text()) or {}
        role = data.get("role")
        if not role:
            continue
        found = [data.get("extends"), *(data.get("module_roles") or [])]
        names = [p for p in dict.fromkeys(found) if p and p != role]
        if names:
            parents[role] = names
    return parents


@lru_cache(maxsize=1)
def load_platform_keys() -> set[str]:
    """Every `platform:` key any contracts/permissions.yaml declares in its `permissions:` list."""
    keys: set[str] = set()
    for pattern in ("*/*/contracts/permissions.yaml", "modules/*/*/contracts/permissions.yaml"):
        for f in _root().glob(pattern):
            data = yaml.safe_load(f.read_text()) or {}
            keys |= {p["key"] for p in data.get("permissions") or [] if str(p.get("key", "")).startswith("platform:")}
    return keys


def expand_roles(roles: list[str]) -> list[str]:
    """The roles, each followed by every role its layout extends or lists in `module_roles`, transitively.

    Every role appears once, in first-seen (depth-first) order; a cycle stops at the role already seen.
    """
    parents = load_role_parents()
    out: list[str] = []
    seen: set[str] = set()
    stack = list(reversed(roles))
    while stack:
        r = stack.pop()
        if r in seen:
            continue
        seen.add(r)
        out.append(r)
        stack.extend(reversed(parents.get(r, [])))
    return out


def permissions_for(roles: list[str], super_admin: bool = False) -> set[str]:
    """Every key the roles hold: their own grants and those of their parent roles (see module docstring)."""
    grants = load_role_grants()
    out: set[str] = set()
    for r in expand_roles(roles):
        out |= grants.get(r, set())
    if super_admin:
        out |= load_platform_keys()
    return out
