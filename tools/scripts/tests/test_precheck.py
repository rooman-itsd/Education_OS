"""precheck.sh must fail when any check fails. It once printed "precheck ok" while ruff reported errors: under
`set -e` bash ignores a failure on the left of `&&`, and `ruff check && ruff format --check` sat mid-script.

Runs the real script in a scratch copy of the repository layout, with stand-ins for ruff and the check scripts,
so each failure can be switched on alone. The venv is laid out both ways: `.venv/bin` (Linux, macOS) and
`.venv/Scripts` (Windows, where `python3` is a Microsoft Store shortcut, so the script must not rely on it)."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CHECKS = ("check-root.py", "check-stack.py", "check-boundaries.py", "check-manifests.py", "check-migrations.py")


def _executable(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _layout(
    tmp_path: Path,
    *,
    ruff_check: int = 0,
    ruff_format: int = 0,
    failing_check: str | None = None,
    venv_dir: str | None = "bin",
) -> Path:
    scripts = tmp_path / "tools" / "scripts"
    scripts.mkdir(parents=True)
    (tmp_path / "tools" / "config").mkdir()
    shutil.copy(ROOT / "tools" / "scripts" / "precheck.sh", scripts / "precheck.sh")
    for name in CHECKS:
        (scripts / name).write_text(f"import sys\nsys.exit({1 if name == failing_check else 0})\n")
    if venv_dir is not None:
        venv = tmp_path / ".venv" / venv_dir
        venv.mkdir(parents=True)
        _executable(
            venv / "ruff",
            f'#!/bin/sh\ncase "$1" in check) exit {ruff_check};; format) exit {ruff_format};; esac\nexit 0\n',
        )
        # The venv's Python, standing in for the real one: the Python running these tests.
        _executable(venv / "python", f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" "$@"\n')
    return scripts / "precheck.sh"


def _run(script: Path) -> subprocess.CompletedProcess:
    # Not a git repository, so the commit-message step is skipped, as the script intends outside a checkout.
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(script.parents[2].parent)}
    return subprocess.run(["bash", str(script)], capture_output=True, text=True, env=env, cwd=script.parents[2])


@pytest.mark.parametrize("venv_dir", ["bin", "Scripts"])
def test_everything_passing_says_ok(tmp_path, venv_dir):
    result = _run(_layout(tmp_path, venv_dir=venv_dir))
    assert result.returncode == 0 and "precheck ok" in result.stdout


def test_without_a_venv_it_says_to_run_the_setup(tmp_path):
    result = _run(_layout(tmp_path, venv_dir=None))
    assert result.returncode != 0
    assert "run tools/scripts/py-setup.sh first" in result.stdout


@pytest.mark.parametrize(
    "failure",
    [
        {"ruff_check": 1},
        {"ruff_format": 1},
        *({"failing_check": name} for name in CHECKS),
    ],
    ids=["ruff-check", "ruff-format", *CHECKS],
)
@pytest.mark.parametrize("venv_dir", ["bin", "Scripts"])
def test_any_failing_check_fails_the_script(tmp_path, failure, venv_dir):
    result = _run(_layout(tmp_path, venv_dir=venv_dir, **failure))
    assert result.returncode != 0
    assert "precheck ok" not in result.stdout


def test_a_skipped_commit_message_check_is_said_not_hidden(tmp_path):
    """Outside a checkout, or without origin/main, the commit-message step cannot run. The script used to skip it
    in silence and still print an unqualified "precheck ok: safe to push"."""
    result = _run(_layout(tmp_path))
    assert result.returncode == 0
    assert "commit messages NOT checked" in result.stdout
    assert "precheck ok: safe to push" not in result.stdout


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


def test_check_commits_fails_when_git_log_fails(tmp_path):
    """The loop read `git log` through a process substitution, whose exit status bash ignores: an unknown base
    printed no commits, and the script said "commit messages ok" having checked nothing."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "-c", "user.email=a@b.c", "-c", "user.name=a", "commit", "-q", "--allow-empty", "-m", "oops")
    script = ROOT / "tools" / "scripts" / "check-commits.sh"
    unknown = "0" * 40
    result = subprocess.run(["bash", str(script), unknown, "HEAD"], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode != 0
    assert "commit messages ok" not in result.stdout


def test_check_commits_still_flags_a_bad_message_and_passes_a_good_one(tmp_path):
    script = ROOT / "tools" / "scripts" / "check-commits.sh"
    _git(tmp_path, "init", "-q")
    ident = ("-c", "user.email=a@b.c", "-c", "user.name=a")
    _git(tmp_path, *ident, "commit", "-q", "--allow-empty", "-m", "feat(repo): the first commit")
    base = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    _git(tmp_path, *ident, "commit", "-q", "--allow-empty", "-m", "fix(repo): a properly scoped message")
    ok = subprocess.run(["bash", str(script), base, "HEAD"], cwd=tmp_path, capture_output=True, text=True)
    assert ok.returncode == 0 and "commit messages ok" in ok.stdout
    _git(tmp_path, *ident, "commit", "-q", "--allow-empty", "-m", "fixed stuff")
    bad = subprocess.run(["bash", str(script), base, "HEAD"], cwd=tmp_path, capture_output=True, text=True)
    assert bad.returncode != 0 and "bad commit message: fixed stuff" in bad.stdout
