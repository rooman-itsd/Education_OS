"""deploy-api-lxc.sh writes the reverse proxy's address into .env.api for the two settings that need it.

`EOS_TRUSTED_PROXIES` is platform/api-gateway's (rate limits per visitor) and `EOS_FORWARDED_ALLOW_IPS` is uvicorn's
(the visitor's address and https as the rest of the API sees them). Both must name the nginx container, or every
visitor counts as the proxy. The script builds the command it runs inside the container with `proxy_key_cmd`; this
extracts that function from the script and runs the command it builds against real files, so what the server does
is what is tested. Nothing here needs Proxmox or a container."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools" / "scripts" / "deploy-api-lxc.sh"
COMPOSE = ROOT / "infra" / "docker" / "docker-compose.api.yml"
# The bash on PATH, by its full path: on Windows a bare "bash" is System32's WSL launcher, not Git Bash.
BASH = shutil.which("bash") or "bash"
KEYS = ("EOS_TRUSTED_PROXIES", "EOS_FORWARDED_ALLOW_IPS")
PROXY = "10.1.2.3"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not available")


def _function() -> str:
    found = re.search(r"^proxy_key_cmd\(\) \{.*?^\}", SCRIPT.read_text(encoding="utf-8"), re.S | re.M)
    assert found, "proxy_key_cmd is not defined in deploy-api-lxc.sh"
    return found.group(0)


def _apply(env: Path, key: str, address: str = PROXY) -> None:
    """Build the command as the script does, then run it as the container would, against `env`."""
    # The file is named relative to its folder: the server's path (/opt/education-os/...) has no spaces, and a
    # temporary folder on a developer's machine may, which the unquoted command would split.
    built = subprocess.run(
        [BASH, "-c", f'{_function()}\nproxy_key_cmd "$1" "$2" "$3"', "bash", key, address, env.name],
        capture_output=True,
        text=True,
        check=True,
        cwd=env.parent,
    ).stdout.strip()
    done = subprocess.run([BASH, "-c", built], capture_output=True, text=True, cwd=env.parent)
    assert done.returncode == 0, done.stderr


def _lines(env: Path) -> list[str]:
    return [line for line in env.read_text(encoding="utf-8").splitlines() if line]


@pytest.mark.parametrize("key", KEYS)
def test_a_missing_key_is_added(tmp_path, key):
    env = tmp_path / ".env.api"
    env.write_text("EOS_API_PORT=8000\n")
    _apply(env, key)
    assert _lines(env) == ["EOS_API_PORT=8000", f"{key}={PROXY}"]


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("value", ["", "127.0.0.1", "127.0.0.1,::1", "::1", "localhost", " 127.0.0.1"])
def test_an_empty_or_loopback_value_is_replaced(tmp_path, key, value):
    env = tmp_path / ".env.api"
    env.write_text(f"EOS_API_PORT=8000\n{key}={value}\nEOS_DEV_MODE=false\n")
    _apply(env, key)
    assert sorted(_lines(env)) == sorted(["EOS_API_PORT=8000", "EOS_DEV_MODE=false", f"{key}={PROXY}"])


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("value", ["10.9.9.9", "10.9.9.9,10.9.9.8", PROXY])
def test_a_value_naming_an_address_is_kept(tmp_path, key, value):
    """An operator's own value, or one already written by an earlier run, is never overwritten or duplicated."""
    env = tmp_path / ".env.api"
    env.write_text(f"{key}={value}\nEOS_API_PORT=8000\n")
    _apply(env, key)
    assert _lines(env) == [f"{key}={value}", "EOS_API_PORT=8000"]


@pytest.mark.parametrize("key", KEYS)
def test_a_file_without_a_final_newline_gets_the_key_on_its_own_line(tmp_path, key):
    env = tmp_path / ".env.api"
    env.write_text("EOS_API_PORT=8000")
    _apply(env, key)
    assert _lines(env) == ["EOS_API_PORT=8000", f"{key}={PROXY}"]


def test_the_two_keys_are_independent_and_a_rerun_changes_nothing(tmp_path):
    env = tmp_path / ".env.api"
    env.write_text("EOS_TRUSTED_PROXIES=10.9.9.9\nEOS_FORWARDED_ALLOW_IPS=127.0.0.1,::1\n")
    for _ in range(2):
        for key in KEYS:
            _apply(env, key)
    assert sorted(_lines(env)) == sorted(["EOS_TRUSTED_PROXIES=10.9.9.9", f"EOS_FORWARDED_ALLOW_IPS={PROXY}"])


def test_a_key_that_only_starts_with_the_name_is_left_alone(tmp_path):
    env = tmp_path / ".env.api"
    env.write_text("EOS_TRUSTED_PROXIES_EXTRA=127.0.0.1\n")
    _apply(env, "EOS_TRUSTED_PROXIES")
    assert _lines(env) == ["EOS_TRUSTED_PROXIES_EXTRA=127.0.0.1", f"EOS_TRUSTED_PROXIES={PROXY}"]


def test_the_script_sets_both_keys_and_compose_passes_both_to_the_container():
    script = SCRIPT.read_text(encoding="utf-8")
    assert re.search(r"for key in EOS_TRUSTED_PROXIES EOS_FORWARDED_ALLOW_IPS;", script)
    assert 'in_ct "$(proxy_key_cmd "$key" "$proxy_ip"' in script
    compose = COMPOSE.read_text(encoding="utf-8")
    for key in KEYS:
        assert key in compose, f"{key} is written to .env.api but docker-compose.api.yml does not pass it on"
