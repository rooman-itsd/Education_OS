"""enabled-modules.py disabled-tests: the suites CI runs for what the host does not enable.

Before it, CI tested only enabled modules, so workflow, documents and reporting PRs merged with green checks that
never ran their tests (#316/#317 audit)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools" / "scripts" / "enabled-modules.py"


def _module(root: Path, kind: str, entry: str, *, tests: bool, pyproject: bool = True, backend: bool = True) -> None:
    base = root / kind / entry
    package = base / "backend" if backend else base
    package.mkdir(parents=True)
    (base / "module.yaml").write_text("name: x\n")
    if pyproject:
        (package / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    (package / "tests").mkdir()
    (package / "tests" / "__init__.py").write_text("")
    if tests:
        (package / "tests" / "test_it.py").write_text("def test_it():\n    pass\n")


def _run(root: Path, config: Path) -> list[str]:
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "disabled-tests", "--root", str(root), "--config", str(config)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def test_lists_only_disabled_entries_that_have_test_files(tmp_path):
    _module(tmp_path, "platform", "enabled-svc", tests=True)
    _module(tmp_path, "platform", "workflow", tests=True)
    _module(tmp_path, "platform", "scaffold", tests=False)  # an empty tests/ is not a suite
    _module(tmp_path, "modules", "academics/lms", tests=True)
    _module(tmp_path, "integrations", "nad", tests=True, pyproject=False, backend=False)
    config = tmp_path / "modules.enabled.yaml"
    config.write_text("modules: []\nintegrations: []\nplatform: [enabled-svc]\n")
    assert _run(tmp_path, config) == [
        "platform/workflow/backend/tests",
        "modules/academics/lms/backend/tests",
        "integrations/nad/tests",
    ]


def test_the_real_repository_lists_no_enabled_entry():
    spec = importlib.util.spec_from_file_location("enabled_modules", SCRIPT)
    em = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = em  # dataclasses look their module up while the class is created
    spec.loader.exec_module(em)
    enabled = {e.package / "tests" for e in em.entries() if (e.package / "tests").is_dir()}
    disabled = {ROOT / line for line in _run(ROOT, em.CONFIG)}
    assert disabled and not enabled & disabled
    assert all(any(p.rglob("test_*.py")) for p in disabled)
