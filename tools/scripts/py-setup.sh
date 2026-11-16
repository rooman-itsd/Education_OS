#!/usr/bin/env bash
# Create .venv and install, in editable mode, the shared packages, the API host and everything
# apps/backend/config/modules.enabled.yaml enables (platform services, modules and integrations, with
# their test extras), as tools/scripts/enabled-modules.py lists them.
# On Windows run it in Git Bash: there `python3` is usually a Microsoft Store shortcut that only prints "Python was
# not found", and the venv keeps its programs in .venv/Scripts, not .venv/bin.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
if [ ! -d .venv ]; then
  # The first Python that actually runs, so the Store shortcut is skipped.
  made=""
  for py in python3 python "py -3"; do
    # shellcheck disable=SC2086  # "py -3" is a command and its argument
    if $py -c "" >/dev/null 2>&1; then $py -m venv .venv; made=1; break; fi
  done
  [ -n "$made" ] || { echo "no Python found: install Python 3.12 (python.org) and run this again"; exit 1; }
fi
if [ -f .venv/bin/activate ]; then . .venv/bin/activate; else . .venv/Scripts/activate; fi
python -m pip install -q --upgrade pip
pip install -q ruff pyyaml
# Assigned in its own statement so a failing script stops the setup (set -e ignores a `$(...)` used as an argument).
enabled="$(python tools/scripts/enabled-modules.py install --pip --extras test)"
# shellcheck disable=SC2086  # one -e argument per enabled package
pip install -q -e packages/core -e packages/testing $enabled -e "apps/backend[test]"
echo "ok: $(python --version), packages installed into .venv"
