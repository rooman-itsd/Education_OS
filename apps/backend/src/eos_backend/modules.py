"""What this host composes, from config/modules.enabled.yaml: platform services, feature modules and
integrations. Every entry follows the same layout, so the entry alone is enough: package eos_<name>,
router eos_<name>.api.router:router, mounted at /api/v1/<name>.

A listed entry that is not installed stops start-up with a message saying what to install: a module that
is silently skipped would only show up later as 404s."""

from __future__ import annotations

import importlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from eos_core.settings import settings
from fastapi import APIRouter

# Resolved through the repo root like the profiles, plans and permission catalogues (EOS_REPO_ROOT, or the
# checkout the process runs in), so a non-editable install finds it too. EOS_MODULES_FILE overrides it.
CONFIG = settings.repo_root / "apps" / "backend" / "config" / "modules.enabled.yaml"
_NAME = r"[a-z0-9]+(?:-[a-z0-9]+)*"
_FORMS = {
    "platform": re.compile(rf"^{_NAME}$"),
    "modules": re.compile(rf"^{_NAME}/{_NAME}$"),
    "integrations": re.compile(rf"^{_NAME}$"),
}


@dataclass(frozen=True)
class Entry:
    kind: str  # platform | modules | integrations
    entry: str  # as written in the YAML, e.g. "campus-life/hostel"

    @property
    def name(self) -> str:
        """The URL segment and the entitlement name: /api/v1/<name>."""
        return self.entry.rsplit("/", 1)[-1]

    @property
    def package(self) -> str:
        return "eos_" + self.name.replace("-", "_")

    @property
    def source(self) -> str:
        """Where the entry lives in the repo, for messages."""
        return f"{self.kind}/{self.entry}"


def enabled(path: Path | None = None) -> list[Entry]:
    """Entries in order: platform services first, then modules, then integrations.
    EOS_MODULES_FILE overrides the file (tests)."""
    path = path or Path(os.environ.get("EOS_MODULES_FILE") or CONFIG)
    if not path.is_file():
        raise RuntimeError(
            f"{path} not found: set EOS_REPO_ROOT to the repository root, or EOS_MODULES_FILE to the file to use"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries: list[Entry] = []
    for kind in ("platform", "modules", "integrations"):
        listed = data.get(kind) or []
        if not isinstance(listed, list):
            raise RuntimeError(f"{path}: `{kind}` must be a list")
        for raw in listed:
            if not isinstance(raw, str) or not _FORMS[kind].match(raw):
                form = "<domain>/<module>" if kind == "modules" else "<name>"
                raise RuntimeError(f"{path}: `{kind}` entry {raw!r} is not {form}")
            entries.append(Entry(kind, raw))
    names = [e.name for e in entries]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise RuntimeError(f"{path}: two entries would mount at the same path: {', '.join(duplicates)}")
    return entries


def router_for(entry: Entry) -> APIRouter:
    dotted = f"{entry.package}.api.router"
    try:
        module = importlib.import_module(dotted)
    except ModuleNotFoundError as e:
        # A missing package or router is a configuration problem; any other missing import is a bug inside
        # the package, shown as is.
        if e.name == entry.package:
            raise RuntimeError(
                f"{entry.source} is enabled in config/modules.enabled.yaml but {entry.package} is not installed. "
                "Run tools/scripts/py-setup.sh (or rebuild the API image), which installs every enabled entry."
            ) from e
        if e.name in (f"{entry.package}.api", dotted):
            raise RuntimeError(f"{entry.source} has no {dotted.replace('.', '/')}.py to mount") from e
        raise
    router = getattr(module, "router", None)
    if not isinstance(router, APIRouter):
        raise RuntimeError(f"{dotted} has no `router` (an APIRouter) for {entry.source}")
    return router
