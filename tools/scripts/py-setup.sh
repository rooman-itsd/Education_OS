#!/usr/bin/env bash
# Create .venv and install, in editable mode, the shared packages, the API host and everything
# apps/backend/config/modules.enabled.yaml enables (platform services, modules and integrations, with
# their test extras), as tools/scripts/enabled-modules.py lists them.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q --upgrade pip
pip install -q ruff pyyaml
# shellcheck disable=SC2046  # one -e argument per enabled package
pip install -q -e packages/core -e packages/testing \
  $(python tools/scripts/enabled-modules.py install --pip --extras test) \
  -e "apps/backend[test]"
echo "ok: $(python --version), packages installed into .venv"
