"""precheck.sh must fail when any check fails. It once printed "precheck ok" while ruff reported errors: under
`set -e` bash ignores a failure on the left of `&&`, and `ruff check && ruff format --check` sat mid-script.

Runs the real script in a scratch copy of the repository layout, with stand-ins for ruff and the check scripts,
so each failure can be switched on alone."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CHECKS = ("check-root.py", "check-stack.py", "check-boundaries.py", "check-manifests.py", "check-migrations.py")


def _executable(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _layout(tmp_path: Path, *, ruff_check: int = 0, ruff_format: int = 0, failing_check: str | None = None) -> Path:
    scripts = tmp_path / "tools" / "scripts"
    scripts.mkdir(parents=True)
    (tmp_path / "tools" / "config").mkdir()
    shutil.copy(ROOT / "tools" / "scripts" / "precheck.sh", scripts / "precheck.sh")
    for name in CHECKS:
        (scripts / name).write_text(f"import sys\nsys.exit({1 if name == failing_check else 0})\n")
    venv = tmp_path / ".venv" / "bin"
    venv.mkdir(parents=True)
    _executable(
        venv / "ruff",
        f'#!/bin/sh\ncase "$1" in check) exit {ruff_check};; format) exit {ruff_format};; esac\nexit 0\n',
    )
    return scripts / "precheck.sh"


def _run(script: Path) -> subprocess.CompletedProcess:
    # Not a git repository, so the commit-message step is skipped, as the script intends outside a checkout.
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(script.parents[2].parent)}
    return subprocess.run(["bash", str(script)], capture_output=True, text=True, env=env, cwd=script.parents[2])


def test_everything_passing_says_ok(tmp_path):
    result = _run(_layout(tmp_path))
    assert result.returncode == 0 and "precheck ok" in result.stdout


@pytest.mark.parametrize(
    "failure",
    [{"ruff_check": 1}, {"ruff_format": 1}, *({"failing_check": name} for name in CHECKS)],
    ids=["ruff-check", "ruff-format", *CHECKS],
)
def test_any_failing_check_fails_the_script(tmp_path, failure):
    result = _run(_layout(tmp_path, **failure))
    assert result.returncode != 0
    assert "precheck ok" not in result.stdout
