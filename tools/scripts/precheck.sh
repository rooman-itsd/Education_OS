#!/usr/bin/env bash
# Run exactly what CI's governance job runs, before you push. Rule: never open a PR red.
#   tools/scripts/precheck.sh            # checks only
#   tools/scripts/precheck.sh --fix      # also auto-fix lint and format
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
[ -x .venv/bin/ruff ] || { echo "run tools/scripts/py-setup.sh first (installs ruff)"; exit 1; }
RUFF=".venv/bin/ruff"; CFG="--config tools/config/ruff.toml"
if [ "${1:-}" = "--fix" ]; then $RUFF check $CFG --fix -q . ; $RUFF format $CFG -q . ; fi
echo "== root layout";      python3 tools/scripts/check-root.py --worktree
echo "== approved stack";   python3 tools/scripts/check-stack.py
echo "== module boundaries"; python3 tools/scripts/check-boundaries.py
echo "== module manifests"; python3 tools/scripts/check-manifests.py
echo "== migrations";       python3 tools/scripts/check-migrations.py
echo "== ruff";             $RUFF check $CFG . && $RUFF format $CFG --check .
if git rev-parse --verify -q origin/main >/dev/null; then
  echo "== commit messages"; tools/scripts/check-commits.sh "$(git merge-base origin/main HEAD)" HEAD
fi
echo "precheck ok: safe to push"
