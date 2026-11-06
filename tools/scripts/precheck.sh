#!/usr/bin/env bash
# Run exactly what CI's governance job runs, before you push. Rule: never open a PR red.
#   tools/scripts/precheck.sh            # checks only
#   tools/scripts/precheck.sh --fix      # also auto-fix lint and format
# On Windows run it in Git Bash: the venv keeps its programs in .venv/Scripts there, not .venv/bin.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
# ruff and Python both come from the venv tools/scripts/py-setup.sh makes, so `python3` (on Windows, a Microsoft
# Store shortcut that prints "Python was not found") is never needed.
BIN=""
for d in .venv/bin .venv/Scripts; do
  if [ -x "$d/ruff" ] || [ -x "$d/ruff.exe" ]; then BIN="$d"; break; fi
done
[ -n "$BIN" ] || { echo "run tools/scripts/py-setup.sh first (installs ruff)"; exit 1; }
RUFF="$BIN/ruff"; PY="$BIN/python"; CFG="--config tools/config/ruff.toml"
if [ "${1:-}" = "--fix" ]; then $RUFF check $CFG --fix -q . ; $RUFF format $CFG -q . ; fi
echo "== root layout";      "$PY" tools/scripts/check-root.py --worktree
echo "== approved stack";   "$PY" tools/scripts/check-stack.py
echo "== module boundaries"; "$PY" tools/scripts/check-boundaries.py
echo "== module manifests"; "$PY" tools/scripts/check-manifests.py
echo "== migrations";       "$PY" tools/scripts/check-migrations.py
# One command per line: under `set -e` bash ignores a failure on the left of `&&`, so `check && format` let a
# failing `ruff check` through and still printed "precheck ok".
echo "== ruff";             $RUFF check $CFG .
echo "== ruff format";      $RUFF format $CFG --check .
if git rev-parse --verify -q origin/main >/dev/null; then
  echo "== commit messages"; tools/scripts/check-commits.sh "$(git merge-base origin/main HEAD)" HEAD
fi
echo "precheck ok: safe to push"
