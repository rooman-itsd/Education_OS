"""infra/backup-dr/eos-db-backup.sh and its second location, against a fake `docker` on PATH (no database).

The second location keeps the same dumps as the local folders, so a pruned dump (and a purged organisation's
data, DPDP) leaves it too; but a run that would delete more than a normal night's rotation there deletes
nothing and fails, so an emptied local folder never empties the second copy. Files that are not ours are never
touched at the destination."""

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "infra" / "backup-dr" / "eos-db-backup.sh"

pytestmark = pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in ("bash", "rsync", "flock", "sha256sum")),
    reason="needs bash, rsync, flock and sha256sum (Linux, as on the API host and in CI)",
)

FAKE_DOCKER = """#!/bin/sh
# Just the calls eos-db-backup.sh makes through `docker compose`.
case "$*" in
  *"pg_dump"*) printf 'PGDMP fake dump\\n' ;;
  *"pg_restore --list"*) cat >/dev/null ;;
  *"ps -q"*) ;;
  *"config --services"*) printf 'db\\napi\\n' ;;
  *) echo "unexpected: docker $*" >&2; exit 2 ;;
esac
"""


@pytest.fixture
def box(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(FAKE_DOCKER, newline="\n")
    docker.chmod(0o755)
    local, offsite = tmp_path / "local", tmp_path / "offsite"
    for d in (local / "daily", local / "weekly", offsite):
        d.mkdir(parents=True)
    return {"tmp": tmp_path, "bin": bin_dir, "local": local, "offsite": offsite}


def _dump(folder: Path, day: int) -> str:
    """An old nightly dump, named as the script names them, with its checksum file."""
    folder.mkdir(parents=True, exist_ok=True)
    name = f"eos-2026-09-{day:02d}T020000Z.dump"
    (folder / name).write_text("PGDMP old\n")
    (folder / f"{name}.sha256").write_text(f"x  {name}\n")
    return name


def _dumps(folder: Path) -> set[str]:
    return {p.name for p in folder.glob("*.dump")} if folder.exists() else set()


def _run(box, **env) -> subprocess.CompletedProcess:
    environ = {
        **os.environ,
        "PATH": f"{box['bin']}{os.pathsep}{os.environ['PATH']}",
        "EOS_BACKUP_CONFIG": str(box["tmp"] / "no-config"),
        "EOS_BACKUP_DIR": str(box["local"]),
        "EOS_BACKUP_OFFSITE": f"{box['offsite']}/",
        "EOS_BACKUP_LOCK": str(box["tmp"] / "lock"),
        "INVOCATION_ID": "test",  # as under systemd: log to stdout only, not to logger
        **env,
    }
    return subprocess.run(["bash", str(SCRIPT)], env=environ, capture_output=True, text=True, timeout=60)


def test_the_second_location_follows_the_local_retention(box):
    """A normal night: the oldest local dump is pruned, and it leaves the second location too."""
    for day in range(1, 15):  # 14 nights, as KEEP_DAILY keeps
        name = _dump(box["local"] / "daily", day)
        _dump(box["offsite"] / "daily", day)
    (box["offsite"] / "daily" / "notes.txt").write_text("someone else's file\n")
    (box["offsite"] / "README").write_text("the destination's own file\n")

    r = _run(box, EOS_BACKUP_KEEP_DAILY="14")

    assert r.returncode == 0, r.stdout + r.stderr
    local, offsite = _dumps(box["local"] / "daily"), _dumps(box["offsite"] / "daily")
    assert len(local) == 14 and "eos-2026-09-01T020000Z.dump" not in local  # pruned locally
    assert offsite == local  # and at the second location, with tonight's dump added
    assert name in offsite
    assert (box["offsite"] / "daily" / "notes.txt").exists() and (box["offsite"] / "README").exists()
    assert not (box["offsite"] / "daily" / "eos-2026-09-01T020000Z.dump.sha256").exists()
    assert (box["offsite"] / "last-success").exists()


def test_an_emptied_local_folder_does_not_empty_the_second_location(box):
    """The local daily folder lost its dumps: deleting them offsite would destroy the only remaining copies."""
    for day in range(1, 15):
        _dump(box["offsite"] / "daily", day)

    r = _run(box)

    assert r.returncode == 1
    assert "FAILED" in r.stdout and "nothing deleted there" in r.stdout
    offsite = _dumps(box["offsite"] / "daily")
    assert len(offsite) == 15  # the 14 old dumps kept, tonight's copied beside them
    assert offsite >= _dumps(box["local"] / "daily")
    assert (box["offsite"] / "last-success").exists()


def test_a_lowered_retention_catches_up_when_forced_once(box):
    for day in range(1, 15):
        _dump(box["local"] / "daily", day)
        _dump(box["offsite"] / "daily", day)

    refused = _run(box, EOS_BACKUP_KEEP_DAILY="7")
    assert refused.returncode == 1 and len(_dumps(box["offsite"] / "daily")) == 15

    time.sleep(1.1)  # dumps are named by the second; a second run in the same second would refuse to overwrite
    forced = _run(box, EOS_BACKUP_KEEP_DAILY="7", EOS_BACKUP_OFFSITE_FORCE_PRUNE="1")
    assert forced.returncode == 0, forced.stdout + forced.stderr
    assert _dumps(box["offsite"] / "daily") == _dumps(box["local"] / "daily")
    assert len(_dumps(box["local"] / "daily")) == 7


def test_a_first_run_copies_to_an_empty_second_location(box):
    r = _run(box)
    assert r.returncode == 0, r.stdout + r.stderr
    assert len(_dumps(box["offsite"] / "daily")) == 1
    assert _dumps(box["offsite"] / "daily") == _dumps(box["local"] / "daily")
