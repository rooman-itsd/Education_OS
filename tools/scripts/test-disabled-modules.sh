#!/usr/bin/env bash
# Run the test suite of every module, integration and platform service that apps/backend/config/modules.enabled.yaml
# does NOT enable. CI's other steps test only what the host mounts, so a disabled module's suite (workflow, documents
# and reporting among them) otherwise never runs before merge.
#
# Its own virtualenv: installing a disabled module's package also installs its entry points (event consumers,
# scheduler jobs), which would change what the host's tests see. Each suite runs on its own, on SQLite.
#   tools/scripts/test-disabled-modules.sh          # all of them; exits non-zero if any suite fails
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
VENV="${DISABLED_VENV:-.venv/disabled-modules}"  # inside .venv/, which is git-ignored
PY="$VENV/bin/python"

# The repo's venv first (as precheck.sh): enabled-modules.py needs PyYAML, which a bare runner's python3 may lack, and
# this script's own venv lives inside .venv/, so creating it first would leave .venv without the main venv.
[ -x .venv/bin/python ] || { echo "run tools/scripts/py-setup.sh first"; exit 1; }
HOST_PY=".venv/bin/python"
suites="$("$HOST_PY" tools/scripts/enabled-modules.py disabled-tests)"
if [ -z "$suites" ]; then echo "no disabled module has a test suite"; exit 0; fi

[ -x "$PY" ] || "$HOST_PY" -m venv "$VENV"
"$PY" -m pip install -q --upgrade pip
# shellcheck disable=SC2046  # the -e arguments are meant to split
"$PY" -m pip install -q -e packages/core -e packages/testing $("$HOST_PY" tools/scripts/enabled-modules.py install --pip --extras test)

failed=()
for tests in $suites; do
  package="$(dirname "$tests")"
  pythonpath=""
  if [ -f "$package/pyproject.toml" ]; then
    # Several module manifests depend on eos-sdk, which packages/sdk does not ship yet, so a full install can be
    # impossible; the module's own code is what is under test, so fall back to installing it without dependencies.
    "$PY" -m pip install -q -e "${package}[test]" 2>/dev/null || "$PY" -m pip install -q --no-deps -e "$package"
  else
    pythonpath="$ROOT/$package/src"  # an integration with no pyproject.toml yet
  fi
  echo "::group::$tests"
  if ! PYTHONPATH="$pythonpath" "$PY" -m pytest "$tests" -q -p no:cacheprovider; then
    failed+=("$tests")
  fi
  echo "::endgroup::"
done

if [ "${#failed[@]}" -gt 0 ]; then
  printf 'disabled-module suites failed:\n'; printf '  %s\n' "${failed[@]}"
  exit 1
fi
echo "every disabled module's suite passed"
