"""infra/backup-dr/eos-db-restore.sh replacing the live database, against a fake `docker` on PATH (no database).

Everything that uses the database and runs is stopped first (the API, the event-bus relay, the scheduler: one
writing during pg_restore would collide with the restored rows), the restored database is migrated to this
checkout (a rebuilt host runs newer code than the backup), and the stopped services start again."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "infra" / "backup-dr" / "eos-db-restore.sh"

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or any(shutil.which(tool) is None for tool in ("bash", "sha256sum")),
    reason="needs Linux bash and sha256sum (as on the API host and in CI)",
)

# Records every call; `ps --status running -q <service>` answers for the services listed in $FAKE_DIR/running.
FAKE_DOCKER = """#!/bin/sh
echo "$*" >>"$FAKE_DIR/calls"
case "$*" in
  *"ps --status running -q "*) svc="${*##* }"; grep -qx "$svc" "$FAKE_DIR/running" && echo "id-$svc" ;;
  *"pg_restore"*) cat >/dev/null ;;
  *"run --rm -T migrate"*) [ -f "$FAKE_DIR/migrate-fails" ] && exit 1 ;;
esac
exit 0
"""


@pytest.fixture
def box(tmp_path):
    bin_dir, fake = tmp_path / "bin", tmp_path / "fake"
    bin_dir.mkdir()
    fake.mkdir()
    (bin_dir / "docker").write_text(FAKE_DOCKER, newline="\n")
    (bin_dir / "eos-db-backup").write_text('#!/bin/sh\necho safety backup >>"$FAKE_DIR/calls"\n', newline="\n")
    for name in ("docker", "eos-db-backup"):
        (bin_dir / name).chmod(0o755)
    dump = tmp_path / "eos-2026-10-30T023000Z.dump"
    dump.write_text("PGDMP fake\n")
    return {"tmp": tmp_path, "bin": bin_dir, "fake": fake, "dump": dump}


def _restore(box, running: str) -> tuple[subprocess.CompletedProcess, list[str]]:
    (box["fake"] / "running").write_text(running, newline="\n")
    environ = {
        **os.environ,
        "PATH": f"{box['bin']}{os.pathsep}{os.environ['PATH']}",
        "FAKE_DIR": str(box["fake"]),
        "EOS_BACKUP_CONFIG": str(box["tmp"] / "no-config"),
    }
    r = subprocess.run(
        ["bash", str(SCRIPT), str(box["dump"])],
        env=environ,
        input="restore eos\n",
        capture_output=True,
        text=True,
        timeout=60,
    )
    calls = (box["fake"] / "calls").read_text().splitlines()
    return r, calls


def _index(calls: list[str], needle: str) -> int:
    return next(i for i, call in enumerate(calls) if needle in call)


def test_the_api_relay_and_scheduler_stop_and_the_restore_is_migrated(box):
    r, calls = _restore(box, "api\nrelay\nscheduler\n")

    assert r.returncode == 0, r.stdout + r.stderr
    stop, restore = _index(calls, " stop "), _index(calls, "pg_restore")
    migrate, start = _index(calls, "run --rm -T migrate"), _index(calls, " start ")
    assert _index(calls, "safety backup") < stop < restore < migrate < start
    assert calls[stop].endswith("stop api relay scheduler")
    assert calls[start].endswith("start api relay scheduler")


def test_only_the_running_services_are_stopped_and_started(box):
    r, calls = _restore(box, "api\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert calls[_index(calls, " stop ")].endswith("stop api")
    assert calls[_index(calls, " start ")].endswith("start api")


def test_a_failed_migration_still_starts_the_services_and_says_so(box):
    (box["fake"] / "migrate-fails").write_text("")
    r, calls = _restore(box, "api\nrelay\nscheduler\n")
    assert "the migrate step failed" in r.stderr
    assert calls[_index(calls, " start ")].endswith("start api relay scheduler")
