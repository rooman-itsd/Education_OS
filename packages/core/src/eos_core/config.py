"""Loaders for the repo's YAML configuration: academy profiles, plans, permission catalogues.

Permissions. A role's keys are the grants every contracts/permissions.yaml gives that role name, plus the keys of
the role its dashboard layout extends. A layout in platform/identity/config/dashboards/<role>.yaml that says
`extends: student` (or `faculty`) makes that role hold everything `student` holds as well as its own grants, so an
academy role such as research-scholar or coach is usable in every module whose catalogue only names the common
roles. Inheritance follows `extends` transitively and stops at a role already seen, so a cycle cannot loop. It only
adds keys: a module that wants to give an academy role more than the role it extends names that role in its own
catalogue. A super admin additionally holds every `platform:` key, whatever the roles.
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
def load_role_parents() -> dict[str, str]:
    """role name -> the role its dashboard layout `extends`, from platform/identity/config/dashboards/*.yaml."""
    parents: dict[str, str] = {}
    for f in sorted((_root() / "platform/identity/config/dashboards").glob("*.yaml")):
        data = yaml.safe_load(f.read_text()) or {}
        role, parent = data.get("role"), data.get("extends")
        if role and parent and role != parent:
            parents[role] = parent
    return parents


def expand_roles(roles: list[str]) -> list[str]:
    """The roles, each followed by the chain of roles its layout extends; every role once, in first-seen order."""
    parents = load_role_parents()
    out: list[str] = []
    seen: set[str] = set()
    for r in roles:
        while r is not None and r not in seen:
            seen.add(r)
            out.append(r)
            r = parents.get(r)
    return out


def permissions_for(roles: list[str], super_admin: bool = False) -> set[str]:
    """Every key the roles hold: their own grants and those of the roles their layouts extend (see module docstring)."""
    grants = load_role_grants()
    out: set[str] = set()
    for r in expand_roles(roles):
        out |= grants.get(r, set())
    if super_admin:
        out |= {k for ks in grants.values() for k in ks if k.startswith("platform:")}
    return out
