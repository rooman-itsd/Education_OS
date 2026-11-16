#!/usr/bin/env python3
"""What apps/backend/config/modules.enabled.yaml enables, as repo paths, for the places that install, migrate
or test it before the API is installed (py-setup.sh, the API image, the API auto-deploy, stamp-chains.py,
CI). The API itself reads the same file through eos_backend.modules.

  enabled-modules.py install [--pip] [--extras test]   package folders (platform first); --pip prints "-e <path>" args
  enabled-modules.py chains                            Alembic chain folders (<entry>/db) that exist, platform first
  enabled-modules.py tests                             test folders of enabled modules and integrations
  enabled-modules.py prefixes                          table prefixes of enabled modules and integrations
  enabled-modules.py disabled-tests                    test folders, with at least one test file, of every
                                                       module, integration and platform service NOT enabled

Paths are relative to the repo root. Needs only PyYAML.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "apps/backend/config/modules.enabled.yaml"
NAME = r"[a-z0-9]+(?:-[a-z0-9]+)*"
FORMS = {"platform": rf"^{NAME}$", "modules": rf"^{NAME}/{NAME}$", "integrations": rf"^{NAME}$"}


class _UniqueKeyLoader(yaml.SafeLoader):
    """safe_load that refuses a key given twice: PyYAML keeps the last one silently, so a merge that kept both
    sides of a `platform:` line would drop one side's services from the install, the migrations and the image."""

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise SystemExit(
                    f"`{key}` is given twice (line {key_node.start_mark.line + 1}); merge them into one list"
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


@dataclass(frozen=True)
class Entry:
    kind: str
    entry: str
    root: Path

    @property
    def name(self) -> str:
        return self.entry.rsplit("/", 1)[-1]

    @property
    def prefix(self) -> str:
        """Table prefix; the chain's version table is <prefix>alembic_version."""
        return self.name.replace("-", "_") + "_"

    @property
    def base(self) -> Path:
        return self.root / self.kind / self.entry

    @property
    def package(self) -> Path:
        """The folder with pyproject.toml: <entry>/backend, or the entry itself (integrations/payment-sbiepay)."""
        for candidate in (self.base / "backend", self.base):
            if (candidate / "pyproject.toml").is_file():
                return candidate
        raise SystemExit(f"{self.kind}/{self.entry} is enabled but has no backend/pyproject.toml or pyproject.toml")

    @property
    def chain(self) -> Path | None:
        db = self.base / "db"
        return db if (db / "alembic.ini").is_file() else None

    @property
    def tests(self) -> Path | None:
        t = self.package / "tests"
        return t if t.is_dir() else None


def entries(config: Path = CONFIG, root: Path = ROOT) -> list[Entry]:
    data = yaml.load(config.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader) or {}  # noqa: S506 (a SafeLoader)
    found: list[Entry] = []
    for kind in ("platform", "modules", "integrations"):
        for raw in data.get(kind) or []:
            if not isinstance(raw, str) or not re.match(FORMS[kind], raw):
                raise SystemExit(f"{config}: `{kind}` entry {raw!r} is malformed")
            found.append(Entry(kind, raw, root))
    return found


def all_entries(root: Path = ROOT) -> list[Entry]:
    """Every module, integration and platform service on disk, enabled or not."""
    found: list[Entry] = []
    for kind, pattern in (("platform", "*"), ("modules", "*/*"), ("integrations", "*")):
        for base in sorted((root / kind).glob(pattern)):
            entry = base.relative_to(root / kind).as_posix()
            if base.is_dir() and re.match(FORMS[kind], entry) and (base / "module.yaml").is_file():
                found.append(Entry(kind, entry, root))
    return found


def suite_of(e: Entry) -> Path | None:
    """The entry's test folder if it holds at least one test file (a scaffold's empty tests/ is not a suite).
    An entry without a pyproject.toml keeps its tests next to src/ (integrations/<name>/tests)."""
    for folder in (e.base / "backend" / "tests", e.base / "tests"):
        if folder.is_dir() and any(folder.rglob("test_*.py")):
            return folder
    return None


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("what", choices=["install", "chains", "tests", "prefixes", "disabled-tests"])
    ap.add_argument("--pip", action="store_true", help="install: print -e arguments on one line")
    ap.add_argument("--extras", help="install: append [extras] to module and integration packages")
    ap.add_argument("--config", type=Path, default=CONFIG)
    ap.add_argument("--root", type=Path, default=ROOT)
    a = ap.parse_args(argv)
    found = entries(a.config, a.root)
    features = [e for e in found if e.kind != "platform"]
    if a.what == "install":
        paths = [rel(e.package, a.root) + (f"[{a.extras}]" if a.extras and e.kind != "platform" else "") for e in found]
        print(" ".join(f"-e {p}" for p in paths) if a.pip else "\n".join(paths))
    elif a.what == "chains":
        print("\n".join(rel(e.chain, a.root) for e in found if e.chain))
    elif a.what == "disabled-tests":
        # what the host does not mount still has to pass its own suite (tools/scripts/test-disabled-modules.sh)
        enabled = {(e.kind, e.entry) for e in found}
        suites = [suite_of(e) for e in all_entries(a.root) if (e.kind, e.entry) not in enabled]
        print("\n".join(rel(t, a.root) for t in suites if t))
    elif a.what == "tests":
        # every enabled entry with a suite, platform services included, so CI runs what the host mounts
        print("\n".join(rel(e.tests, a.root) for e in found if e.tests))
    else:
        print("\n".join(e.prefix for e in features))
    return 0


if __name__ == "__main__":
    sys.exit(main())
