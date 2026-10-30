"""infra/monitoring/eos-monitor.sh against a fake `docker` and `curl` on PATH (no API, no Docker).

An alert goes out when a check starts failing, not again on the next run, again as a reminder after
EOS_MONITOR_REMIND_MIN, and once when the check recovers. The webhook gets {"text": ...} with its URL kept off
the command line; without a webhook alerts go to the log only. 5xx answers and slow requests are counted from
the API's JSON `request` lines."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "infra" / "monitoring" / "eos-monitor.sh"

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or any(shutil.which(tool) is None for tool in ("bash", "awk", "df", "stat")),
    reason="needs Linux bash, awk, df and stat (as on the API host and in CI)",
)

# The fakes read what to answer from files in $FAKE_DIR, so a test can change the host between runs.
FAKE_DOCKER = """#!/bin/sh
case "$*" in
  *"ps --status running --services"*) cat "$FAKE_DIR/running" ;;
  *"logs --no-log-prefix --since"*) cat "$FAKE_DIR/logs" 2>/dev/null || true ;;
  *) echo "unexpected: docker $*" >&2; exit 2 ;;
esac
"""
FAKE_CURL = """#!/bin/sh
case "$*" in
  *"-K -"*)  # the webhook: record the URL (from stdin) and the body
    { cat; for a in "$@"; do printf 'ARG %s\\n' "$a"; done; } >>"$FAKE_DIR/posted" ;;
  *)
    [ -f "$FAKE_DIR/api-down" ] && { echo "curl: (7) Failed to connect" >&2; exit 7; }
    [ -f "$FAKE_DIR/api-blip" ] && { rm "$FAKE_DIR/api-blip"; echo "curl: (7) Failed to connect" >&2; exit 7; }
    printf '{"status":"ok","database":"postgres"}' ;;
esac
"""


@pytest.fixture
def box(tmp_path):
    bin_dir, fake = tmp_path / "bin", tmp_path / "fake"
    bin_dir.mkdir()
    fake.mkdir()
    for name, body in (("docker", FAKE_DOCKER), ("curl", FAKE_CURL)):
        (bin_dir / name).write_text(body, newline="\n")
        (bin_dir / name).chmod(0o755)
    (fake / "running").write_text("db\napi\nrelay\nscheduler\n", newline="\n")
    mark = tmp_path / "last-success"
    mark.write_text("2026-10-30T023000Z 456K eos.dump\n")
    return {"tmp": tmp_path, "bin": bin_dir, "fake": fake, "mark": mark}


def _run(box, **env) -> subprocess.CompletedProcess:
    environ = {
        **os.environ,
        "PATH": f"{box['bin']}{os.pathsep}{os.environ['PATH']}",
        "FAKE_DIR": str(box["fake"]),
        "EOS_MONITOR_CONFIG": str(box["tmp"] / "no-config"),
        "EOS_MONITOR_STATE_DIR": str(box["tmp"] / "state"),
        "EOS_MONITOR_BACKUP_MARK": str(box["mark"]),
        "EOS_MONITOR_DISK_PATH": str(box["tmp"]),
        "EOS_MONITOR_DISK_MAX_PCT": "101",
        "EOS_MONITOR_LABEL": "staging",
        "EOS_MONITOR_HEALTH_RETRY_S": "0",
        "INVOCATION_ID": "test",  # as under systemd: log to stdout only, not to logger
        **env,
    }
    return subprocess.run(["bash", str(SCRIPT)], env=environ, capture_output=True, text=True, timeout=60)


def _alerts(r) -> list[str]:
    return [line for line in r.stdout.splitlines() if line.startswith("ALERT: ")]


def _request(status: int, duration_ms: float) -> str:
    return json.dumps(
        {"method": "GET", "route": "/x", "status": status, "duration_ms": duration_ms, "event": "request"}
    )


def test_a_healthy_host_sends_nothing(box):
    r = _run(box)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _alerts(r) == [] and r.stdout.strip().endswith("ok")


def test_an_outage_alerts_once_then_recovers(box):
    (box["fake"] / "api-down").write_text("")
    first = _run(box)
    assert first.returncode == 1
    assert _alerts(first) == [
        "ALERT: [staging] FAILING health: http://127.0.0.1:8000/api/v1/health does not answer: "
        "curl: (7) Failed to connect"
    ]

    again = _run(box)
    assert again.returncode == 1 and _alerts(again) == []  # still down: no alert every minute
    assert "alerted already" in again.stdout

    (box["fake"] / "api-down").unlink()
    back = _run(box)
    assert back.returncode == 0
    assert _alerts(back) == ["ALERT: [staging] RECOVERED health"]
    assert _alerts(_run(box)) == []


def test_an_api_restart_answered_on_the_retry_is_not_an_outage(box):
    (box["fake"] / "api-blip").write_text("")  # the first request fails, as during an auto-deploy
    r = _run(box)
    assert r.returncode == 0 and _alerts(r) == []
    assert not (box["fake"] / "api-blip").exists()


def test_a_long_failure_is_repeated_as_a_reminder(box):
    (box["fake"] / "running").write_text("db\napi\nrelay\n", newline="\n")
    assert _alerts(_run(box)) == ["ALERT: [staging] FAILING containers: not running: scheduler"]
    mark = box["tmp"] / "state" / "containers"
    mark.write_text(str(int(time.time()) - 61 * 60))  # alerted an hour and a minute ago
    assert _alerts(_run(box)) == ["ALERT: [staging] STILL FAILING containers: not running: scheduler"]


def test_5xx_answers_over_the_threshold_alert(box):
    logs = box["fake"] / "logs"
    # 4xx answers are the caller's mistakes (a wrong password, a missing page), not the API failing.
    lines = ["not json: uvicorn starting", _request(200, 12.0)] + [_request(404, 5.0)] * 10 + [_request(500, 30.0)] * 3
    logs.write_text("\n".join(lines) + "\n", newline="\n")
    assert _alerts(_run(box)) == []  # 3 is within the default 5

    logs.write_text("\n".join(lines + [_request(502, 30.0)] * 3) + "\n", newline="\n")
    alerts = _alerts(_run(box))
    assert len(alerts) == 1 and alerts[0].startswith("ALERT: [staging] FAILING errors: 6 answers with status 5xx")


def test_slow_requests_over_the_threshold_alert(box):
    lines = [_request(200, 2500.5)] * 3 + [_request(200, 1999.0)] * 5
    (box["fake"] / "logs").write_text("\n".join(lines) + "\n", newline="\n")
    alerts = _alerts(_run(box, EOS_MONITOR_MAX_SLOW="2"))
    assert alerts == ["ALERT: [staging] FAILING slow: 3 requests slower than 2000 ms in the last 5m (more than 2)"]


def test_a_missing_or_old_backup_alerts(box):
    box["mark"].unlink()
    assert "FAILING backup: no successful backup recorded" in _alerts(_run(box))[0]

    box["mark"].write_text("old\n")
    old = time.time() - 30 * 3600
    os.utime(box["mark"], (old, old))
    r = _run(box, EOS_MONITOR_STATE_DIR=str(box["tmp"] / "state2"))
    assert _alerts(r) == [
        "ALERT: [staging] FAILING backup: the last successful backup is 30h old: journalctl -t eos-db-backup"
    ]


def test_the_webhook_gets_json_and_the_url_stays_off_the_command_line(box):
    url = "https://hooks.example.invalid/services/SECRET"
    (box["fake"] / "api-down").write_text("")
    r = _run(box, EOS_MONITOR_WEBHOOK_URL=url)
    assert r.returncode == 1
    posted = (box["fake"] / "posted").read_text()
    assert f'url = "{url}"' in posted  # from stdin
    assert not any(url in line for line in posted.splitlines() if line.startswith("ARG "))
    body = next(line[4:] for line in posted.splitlines() if line.startswith("ARG {"))
    assert json.loads(body)["text"].startswith("[staging] FAILING health:")


def test_without_a_webhook_alerts_stay_in_the_log(box):
    (box["fake"] / "api-down").write_text("")
    r = _run(box)
    assert len(_alerts(r)) == 1
    assert not (box["fake"] / "posted").exists()
