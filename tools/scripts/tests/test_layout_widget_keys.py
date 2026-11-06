"""A dashboard layout must give its role the permission key of every widget it lists.

platform/identity/config/dashboards/<role>.yaml lists a role's widgets and the module roles it holds (`module_roles`,
plus the role it `extends`). Each widget declares the one key it needs (`permission:` in its module's
frontend/src/widgets/index.ts), and that declared key is the one the dashboard shell checks. When the layout does not
give the role that key, the widget is listed on a dashboard that cannot show it: the shell leaves it out, and where
the API takes only that key it refuses the role (403, a "no access" panel while apps/frontend shows every widget).
Nothing caught that before the dashboard's e2e journey ran (#537: research-lead lists projects.to-review but holds no
projects:guidance:read).

The role's keys are worked out as eos_core.config.permissions_for does (grants of the role and of every role its
layout extends or lists, transitively), repeated here with yaml alone because the governance job installs no packages;
test_the_rule_here_is_eos_cores checks the two agree wherever eos_core is installed."""

from __future__ import annotations

import re
import sys
from functools import cache
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
LAYOUTS = ROOT / "platform" / "identity" / "config" / "dashboards"

# Wrong on main when this test was added (6 Nov 2026); each needs its layout or its widget changed by the owner.
# Fixing one never fails this test; adding one does. Remove a line once it is fixed (the list only shrinks).
KNOWN = {
    # GET /projects?status=active also takes projects:project:read, which projects-coordinator holds, so the API
    # answers these roles; but the widget declares projects:guidance:read, so the shell will not show it to them.
    # Either the layouts give projects-guide (as research-lead's did, #596), or projects offers coordinators a widget
    # that declares project:read.
    ("research-office", "projects.active"): "declared key is guidance:read, coordinators hold project:read",
    ("industry-liaison", "projects.active"): "declared key is guidance:read, coordinators hold project:read",
    ("applicant", "web-portal-cms.announcements"): "applicant holds no web-portal-cms:announcement:read",
}

WIDGET = re.compile(r"\{[^{}]*?\bid:\s*\"([a-z0-9-]+\.[a-z0-9-]+)\"[^{}]*?\bpermission:\s*\"([^\"]+)\"[^{}]*?\}", re.S)


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@cache
def widget_keys() -> dict[str, str]:
    """widget id -> the key it declares, from every module's widgets entry point."""
    out: dict[str, str] = {}
    for pattern in ("modules/*/*/frontend/src/widgets/index.ts", "platform/*/frontend/src/widgets/index.ts",
                    "integrations/*/frontend/src/widgets/index.ts"):  # fmt: skip
        for f in ROOT.glob(pattern):
            out.update(WIDGET.findall(f.read_text(encoding="utf-8")))
    return out


@cache
def grants() -> dict[str, frozenset[str]]:
    """role -> its own grants, from every contracts/permissions.yaml (eos_core.config.load_role_grants)."""
    out: dict[str, set[str]] = {}
    for pattern in ("*/*/contracts/permissions.yaml", "modules/*/*/contracts/permissions.yaml"):
        for f in ROOT.glob(pattern):
            for role in _yaml(f).get("roles") or []:
                out.setdefault(role["name"], set()).update(role.get("grants") or [])
    return {r: frozenset(k) for r, k in out.items()}


@cache
def parents() -> dict[str, tuple[str, ...]]:
    """role -> the role its layout extends, then its module_roles (eos_core.config.load_role_parents)."""
    out: dict[str, tuple[str, ...]] = {}
    for f in sorted(LAYOUTS.glob("*.yaml")):
        data = _yaml(f)
        role = data.get("role")
        if role:
            names = [
                p for p in dict.fromkeys([data.get("extends"), *(data.get("module_roles") or [])]) if p and p != role
            ]
            out[role] = tuple(names)
    return out


def keys_of(role: str) -> set[str]:
    """Every key the role holds: its grants and those of every parent, transitively (a cycle stops at a repeat)."""
    held: set[str] = set()
    seen: set[str] = set()
    stack = [role]
    while stack:
        r = stack.pop()
        if r in seen:
            continue
        seen.add(r)
        held |= grants().get(r, frozenset())
        stack.extend(parents().get(r, ()))
    return held


def layouts() -> list[tuple[str, list[str]]]:
    out = []
    for f in sorted(LAYOUTS.glob("*.yaml")):
        data = _yaml(f)
        if data.get("role"):
            ids = [w if isinstance(w, str) else (w or {}).get("id") for w in data.get("widgets") or []]
            out.append((data["role"], [i for i in ids if i]))
    return out


LAYOUT_LIST = layouts()


def test_the_layouts_and_widgets_are_found():
    """Guards the parsing: if a folder or the widget shape changes, this fails instead of checking nothing."""
    assert len(LAYOUT_LIST) >= 50
    assert len(widget_keys()) >= 80
    assert widget_keys().get("projects.to-review") == "projects:guidance:read"


@pytest.mark.parametrize(("role", "widgets"), LAYOUT_LIST, ids=[r for r, _ in LAYOUT_LIST])
def test_the_layout_gives_its_role_every_listed_widgets_key(role, widgets):
    held = keys_of(role)
    missing = [
        f"{w} needs {widget_keys()[w]}"
        for w in widgets
        if w in widget_keys() and widget_keys()[w] not in held and (role, w) not in KNOWN
    ]
    assert not missing, (
        f"{role}.yaml lists widgets whose declared key its role does not hold, so its dashboard cannot show them: "
        f"{missing}. Add a module role that "
        "grants the key to module_roles (see the module's contracts/permissions.yaml), or drop the widget."
    )


def test_the_rule_here_is_eos_cores():
    config = pytest.importorskip("eos_core.config", reason="eos_core is not installed (the governance job)")
    for role, _ in LAYOUT_LIST:
        assert keys_of(role) == config.permissions_for([role]), role


# ------------------------------------------------------------------ the rule itself, on a made-up role tree


def test_keys_come_through_extends_and_module_roles_transitively(monkeypatch):
    monkeypatch.setattr(
        sys.modules[__name__], "grants", lambda: {"base": frozenset({"a:x:read"}), "mod": frozenset({"b:y:read"})}
    )
    monkeypatch.setattr(sys.modules[__name__], "parents", lambda: {"child": ("middle",), "middle": ("base", "mod")})
    assert keys_of("child") == {"a:x:read", "b:y:read"}
    assert keys_of("base") == {"a:x:read"}
