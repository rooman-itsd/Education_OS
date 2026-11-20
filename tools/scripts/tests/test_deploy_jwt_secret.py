"""deploy-api-lxc.sh gives .env.api a signing key the API accepts outside dev mode (security review N21).

The API refuses to start with EOS_DEV_MODE=false and the built-in development key or one under 32 bytes
(eos_core Settings.check_secrets). The script writes a random key on the first run; on later runs `jwt_secret_cmd`
builds the command that replaces a missing, short or development key and keeps a good one. This extracts that
function from the script and runs the command it builds against real files. Nothing here needs Proxmox."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools" / "scripts" / "deploy-api-lxc.sh"
BASH = shutil.which("bash") or "bash"
DEV_KEY = "dev-only-change-me-dev-only-change-me-32b"  # eos_core.settings.DEV_JWT_SECRET

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("openssl") is None, reason="bash and openssl are needed"
)


def _function() -> str:
    found = re.search(r"^jwt_secret_cmd\(\) \{.*?^\}", SCRIPT.read_text(encoding="utf-8"), re.S | re.M)
    assert found, "jwt_secret_cmd is not defined in deploy-api-lxc.sh"
    return found.group(0)


def _apply(env: Path) -> None:
    built = subprocess.run(
        [BASH, "-c", f'{_function()}\njwt_secret_cmd "$1"', "bash", env.name],
        capture_output=True,
        text=True,
        check=True,
        cwd=env.parent,
    ).stdout.strip()
    done = subprocess.run([BASH, "-c", built], capture_output=True, text=True, cwd=env.parent)
    assert done.returncode == 0, done.stderr


def _keys(env: Path) -> list[str]:
    return [
        line.split("=", 1)[1]
        for line in env.read_text(encoding="utf-8").splitlines()
        if line.startswith("EOS_JWT_SECRET=")
    ]


@pytest.mark.parametrize(
    "before",
    [
        "",
        "EOS_JWT_SECRET=\n",
        "EOS_JWT_SECRET=short\n",
        f"EOS_JWT_SECRET={DEV_KEY}\n",
        "EOS_JWT_SECRET=" + "a" * 31 + "\n",
    ],
)
def test_a_missing_short_or_development_key_is_replaced_by_a_random_one(tmp_path, before):
    env = tmp_path / ".env.api"
    env.write_text("EOS_API_PORT=8000\n" + before)
    _apply(env)
    (key,) = _keys(env)
    assert re.fullmatch(r"[0-9a-f]{64}", key)
    assert "EOS_API_PORT=8000" in env.read_text()


def test_a_good_key_is_kept(tmp_path):
    env = tmp_path / ".env.api"
    good = "f" * 64
    env.write_text(f"EOS_JWT_SECRET={good}\nEOS_API_PORT=8000\n")
    _apply(env)
    assert _keys(env) == [good]
    _apply(env)  # and again: nothing changes
    assert _keys(env) == [good]
