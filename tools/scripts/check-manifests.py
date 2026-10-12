#!/usr/bin/env python3
"""Manifest check (module standard rules 8 and 9). Every module.yaml under modules/, platform/ and
integrations/ must be complete and consistent with where it lives:

- every key of modules/_template/module.yaml is present, with the right type and an allowed value;
- name is the folder name; kind and domain match the location (modules/<domain>/<name> is a feature);
- tier is core for platform services, common or specialized otherwise; specialized declares a field;
- depends_on names platform services and integrations that exist;
- owners are GitHub handles from docs/team/members.yaml;
- once a module is past `planned`, the files it exposes (contracts, config) exist.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

KINDS = {"modules": "feature", "platform": "platform", "integrations": "integration"}
TIERS = {"core", "common", "specialized"}
STATUSES = {"planned", "in-progress", "stable", "deprecated"}
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
TYPES: dict[str, type | tuple[type, ...]] = {
    "name": str,
    "kind": str,
    "domain": str,
    "tier": str,
    "version": str,
    "status": str,
    "description": str,
    "owners": list,
    "depends_on": dict,
    "exposes": dict,
    "consumes_events": list,
    "config": str,
    "portable": bool,
}


def manifests(root: Path) -> list[Path]:
    found = list((root / "modules").glob("*/*/module.yaml"))
    found += list((root / "platform").glob("*/module.yaml"))
    found += list((root / "integrations").glob("*/module.yaml"))
    return sorted(p for p in found if p.parent.name != "_template" and p.parent.parent.name != "_template")


def team_handles(root: Path) -> set[str] | None:
    path = root / "docs/team/members.yaml"
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {m["handle"] for m in data.get("members") or [] if m.get("handle")}


def check_manifest(path: Path, root: Path, platform: set[str], integrations: set[str], handles) -> list[str]:
    mod = path.parent
    where = mod.relative_to(root).as_posix()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        return [f"{where}/module.yaml: not valid YAML: {e}"]
    if not isinstance(data, dict):
        return [f"{where}/module.yaml: must be a mapping of keys"]

    problems = []

    def bad(msg: str) -> None:
        problems.append(f"{where}/module.yaml: {msg}")

    for key, typ in TYPES.items():
        if key not in data:
            bad(f"missing `{key}`")
        elif not isinstance(data[key], typ) or (typ is str and not data[key].strip()):
            bad(f"`{key}` must be a non-empty {typ.__name__}" if typ is str else f"`{key}` must be a {typ.__name__}")
    if problems:
        return problems

    top = mod.relative_to(root).parts[0]
    kind = KINDS[top]
    if data["name"] != mod.name:
        bad(f"name `{data['name']}` must be the folder name `{mod.name}`")
    if data["kind"] != kind:
        bad(f"kind `{data['kind']}` must be `{kind}` for a module under {top}/")
    domain = mod.parent.name if kind == "feature" else top
    if data["domain"] != domain:
        bad(f"domain `{data['domain']}` must be `{domain}`")
    if data["status"] not in STATUSES:
        bad(f"status `{data['status']}` must be one of {', '.join(sorted(STATUSES))}")
    if not SEMVER.match(data["version"]):
        bad(f"version `{data['version']}` must look like 1.2.3")

    tier = data["tier"]
    if tier not in TIERS:
        bad(f"tier `{tier}` must be one of {', '.join(sorted(TIERS))}")
    elif kind == "platform" and tier != "core":
        bad("a platform service has tier `core`")
    elif kind != "platform" and tier == "core":
        bad("tier `core` is for platform services; use `common` or `specialized`")
    if tier == "specialized" and not (isinstance(data.get("field"), str) and data["field"].strip()):
        bad("a specialized module declares its `field` (rule 9)")
    if "field" in data and tier != "specialized":
        bad("`field` is only for tier `specialized`")

    if handles is not None:
        for owner in data["owners"]:
            if not isinstance(owner, str) or owner.lstrip("@") not in handles:
                bad(f"owner `{owner}` is not a handle in docs/team/members.yaml")

    deps = data["depends_on"]
    for key, known, folder in (("platform", platform, "platform"), ("integrations", integrations, "integrations")):
        listed = deps.get(key)
        if listed is None:
            bad(f"depends_on.{key} must be a list (use [] for none)")
            continue
        if not isinstance(listed, list):
            bad(f"depends_on.{key} must be a list")
            continue
        for dep in listed:
            if dep not in known:
                bad(f"depends_on.{key} names `{dep}`, which is not a module in {folder}/")
            elif kind == "platform" and key == "platform" and dep == mod.name:
                bad("a platform service does not depend on itself")

    for key in ("api", "events", "permissions"):
        if not isinstance(data["exposes"].get(key), str):
            bad(f"exposes.{key} must be a path")
    if data["status"] != "planned":
        files = {f"exposes.{k}": v for k, v in data["exposes"].items() if isinstance(v, str)}
        files["config"] = data["config"]
        for key, rel in files.items():
            if not (mod / rel).is_file():
                bad(f"{key} points to {rel}, which does not exist (required once status is past planned)")
    return problems


def check(root: Path) -> list[str]:
    platform = {p.parent.name for p in (root / "platform").glob("*/module.yaml")}
    integrations = {p.parent.name for p in (root / "integrations").glob("*/module.yaml")}
    handles = team_handles(root)
    problems = []
    for path in manifests(root):
        problems += check_manifest(path, root, platform, integrations, handles)
    return problems


def main() -> int:
    problems = check(ROOT)
    if problems:
        print("Manifest check failed (module standard rules 8 and 9):")
        print("\n".join(problems))
        return 1
    print(f"manifest check ok ({len(manifests(ROOT))} modules)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
