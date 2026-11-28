"""infra/autodeploy/eos-api-autodeploy.sh rolls back when the new API never answers its health check.

Before this, only a failed migration kept the previous version: an API that crashed at start-up (a setting it refuses,
an import error) stayed down until someone noticed. The script runs here against stand-in `git` and `docker`
commands that record every call, so each path is checked without a server."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "infra" / "autodeploy" / "eos-api-autodeploy.sh"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None or os.name == "nt", reason="needs a POSIX bash")

GIT = """#!/usr/bin/env bash
echo "git $*" >> "$CALLS"
case "$1" in
  rev-parse) case "$*" in *HEAD*) echo "$FAKE_HAVE" ;; *) echo "$FAKE_WANT" ;; esac ;;
esac
exit 0
"""

DOCKER = """#!/usr/bin/env bash
echo "docker $*" >> "$CALLS"
case "$*" in
  *" ps -q api"*) [ -n "$FAKE_CID" ] && echo "$FAKE_CID" ;;
  *" run --rm -T migrate"*)
    [ -f "$EOS_AUTODEPLOY_MARK" ] && echo "mark present during migrate" >> "$CALLS"
    exit "${FAKE_MIGRATE_EXIT:-0}" ;;
  *" config --services"*) printf 'db\\nmigrate\\napi\\nrelay\\nscheduler\\n' ;;
  "inspect -f {{.Config.Image}} "*) echo "eos-api:latest" ;;
  "inspect -f {{.Image}} "*) echo "sha256:old" ;;
  "exec "*)
    [ -f "$EOS_AUTODEPLOY_MARK" ] && echo "mark present during the health wait" >> "$CALLS"
    [ "$FAKE_HEALTH" = ok ] ;;
esac
"""

PASS = """#!/usr/bin/env bash
[ "$(basename "$0")" = logger ] && echo "logger $*" >> "$CALLS"
exit 0
"""


def _run(tmp_path: Path, **fake: str) -> tuple[int, list[str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name, body in {"git": GIT, "docker": DOCKER, "flock": PASS, "logger": PASS}.items():
        path = bin_dir / name
        path.write_text(body, encoding="utf-8", newline="\n")
        path.chmod(0o755)
    app = tmp_path / "app"
    (app / "infra" / "docker").mkdir(parents=True, exist_ok=True)
    (app / "infra" / "docker" / ".env.api").write_text("EOS_APP_DB_PASSWORD=x\n", encoding="utf-8")
    calls = tmp_path / "calls.txt"
    calls.write_text("", encoding="utf-8")
    failed = tmp_path / "state" / "failed"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "CALLS": str(calls),
        "EOS_AUTODEPLOY_CONFIG": str(tmp_path / "none.env"),
        "EOS_APP_DIR": str(app),
        "EOS_AUTODEPLOY_LOCK": str(tmp_path / "lock"),
        "EOS_AUTODEPLOY_FAILED_FILE": str(failed),
        "EOS_AUTODEPLOY_MARK": str(tmp_path / "run" / "api-deploying"),
        "EOS_AUTODEPLOY_HEALTH_SECONDS": "0",
        "FAKE_HAVE": "aaa1111",
        "FAKE_WANT": "bbb2222",
        "FAKE_CID": "cid-old",
        "FAKE_HEALTH": "ok",
        **fake,
    }
    result = subprocess.run([BASH, str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60)
    return result.returncode, calls.read_text(encoding="utf-8").splitlines(), failed


def test_a_healthy_deploy_keeps_the_new_version_and_drops_the_rollback_image(tmp_path):
    code, calls, failed = _run(tmp_path)
    assert code == 0, calls
    assert "docker image tag sha256:old eos-api:rollback" in calls  # kept before the rebuild takes the name
    assert not any(c.startswith("git reset -q --hard aaa1111") for c in calls)
    assert "docker image rm eos-api:rollback" in calls
    assert any("deployed main bbb2222 (was aaa1111)" in c for c in calls)
    assert not failed.exists()


def test_an_api_that_never_answers_is_rolled_back_to_the_previous_image_and_commit(tmp_path):
    code, calls, failed = _run(tmp_path, FAKE_HEALTH="down")
    assert code == 1
    assert "git reset -q --hard aaa1111" in calls
    assert "docker image tag eos-api:rollback eos-api:latest" in calls
    restart = [c for c in calls if c.endswith("up -d --no-deps api relay scheduler")]
    assert restart, "the rollback restarts api, relay and scheduler without re-running migrate"
    assert calls.index(restart[0]) > calls.index("docker image tag eos-api:rollback eos-api:latest")
    assert any("rolled back to aaa1111" in c for c in calls)
    assert failed.read_text().strip() == "bbb2222"
    assert not any("image prune" in c for c in calls)  # the old image must survive


def test_the_failed_commit_is_not_redeployed_every_run_but_force_or_a_new_commit_is(tmp_path):
    _run(tmp_path, FAKE_HEALTH="down")
    code, calls, _ = _run(tmp_path, FAKE_HEALTH="down")
    assert code == 0 and not any(" build " in c for c in calls), "same failed commit: skipped"
    _, calls, _ = _run(tmp_path, FORCE="1")
    assert any(" build " in c for c in calls), "FORCE=1 tries it again"
    _, calls, failed = _run(tmp_path, FAKE_WANT="ccc3333")
    assert any(" build " in c for c in calls) and not failed.exists(), "a new commit deploys and clears the mark"


def test_a_first_deploy_without_a_running_api_does_not_try_to_roll_back(tmp_path):
    code, calls, failed = _run(tmp_path, FAKE_CID="", FAKE_HEALTH="down")
    assert code == 1
    assert not any("eos-api:rollback" in c for c in calls)
    assert any("no previous image to roll back to" in c for c in calls)
    assert failed.read_text().strip() == "bbb2222"


def test_a_failed_migration_still_leaves_the_running_api_alone(tmp_path):
    code, calls, _ = _run(tmp_path, FAKE_MIGRATE_EXIT="1")
    assert code == 1
    assert not any(" up -d" in c for c in calls)
    assert any("migrations failed at bbb2222" in c for c in calls)
    assert not (tmp_path / "run" / "api-deploying").exists()


def test_the_restart_skips_migrate_so_the_api_is_not_stopped_while_it_runs_again(tmp_path):
    """25 Nov: a plain `up -d` ran migrate a second time while api, relay and scheduler waited for it, stopped:
    1.5 to 3.5 minutes of outage on every merge."""
    code, calls, _ = _run(tmp_path)
    assert code == 0, calls
    ups = [c for c in calls if " up -d" in c]
    assert len(ups) == 1 and ups[0].endswith(" up -d --quiet-pull --no-deps db api relay scheduler"), ups
    assert calls.index(ups[0]) > max(i for i, c in enumerate(calls) if "run --rm -T migrate" in c)


def test_the_deploy_mark_covers_the_deploy_and_is_gone_after_it(tmp_path):
    mark = tmp_path / "run" / "api-deploying"
    _, calls, _ = _run(tmp_path)
    assert "mark present during migrate" in calls and "mark present during the health wait" in calls
    assert not mark.exists()

    _run(tmp_path, FAKE_HEALTH="down", FAKE_WANT="ccc3333")  # a rollback removes it too
    assert not mark.exists()

    mark.write_text("")  # left by a run that was killed
    _, calls, _ = _run(tmp_path, FAKE_WANT="aaa1111")  # nothing new to deploy
    assert not any(" build " in c for c in calls) and not mark.exists()
