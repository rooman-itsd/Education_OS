"""launch-check.sh against a stand-in site: a healthy API passes every check, and the failures it exists to catch
(the /api/ proxy serving the web app, dev mode on, a missing header, an open CORS origin, no sign-in limit) fail."""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools" / "scripts" / "launch-check.sh"
BASH = shutil.which("bash") or "bash"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("curl") is None, reason="bash and curl are needed"
)

HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=()",
    "Content-Security-Policy": "default-src 'self'",
    "Cache-Control": "no-store",
}


def site(*, html=False, dev_mode=False, drop=(), cors_any=False, limit=10):
    attempts = {"n": 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep test output clean
            pass

        def _send(self, status, body: bytes, ctype: str, extra=None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            for k, v in {**HEADERS, **(extra or {})}.items():
                if k not in drop:
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if html:
                return self._send(200, b"<!doctype html><html></html>", "text/html")
            body = {"status": "ok", "database": "postgres", "dev_mode": dev_mode, "modules": []}
            self._send(200, json.dumps(body).encode(), "application/json")

        def do_OPTIONS(self):
            origin = self.headers.get("Origin", "")
            self._send(200, b"", "text/plain", {"Access-Control-Allow-Origin": origin} if cors_any else {})

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            attempts["n"] += 1
            if limit and attempts["n"] > limit:
                return self._send(429, b'{"code":"rate_limited"}', "application/json", {"Retry-After": "60"})
            self._send(401, b'{"detail":"invalid credentials"}', "application/json")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def run(**kw) -> tuple[int, str]:
    server = site(**kw)
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        p = subprocess.run([BASH, str(SCRIPT), base], capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout
    finally:
        server.shutdown()


def test_a_healthy_api_passes_every_check():
    code, out = run()
    assert code == 0, out
    assert "FAIL" not in out and out.count("PASS") >= 10


def test_the_proxy_serving_the_web_app_fails():
    code, out = run(html=True)
    assert code == 1 and "the public /api/ proxy does not reach the API" in out


def test_dev_mode_on_fails():
    code, out = run(dev_mode=True)
    assert code == 1 and "FAIL  health: dev_mode is false" in out


def test_a_missing_security_header_fails():
    code, out = run(drop=("X-Frame-Options",))
    assert code == 1 and "FAIL  X-Frame-Options: DENY" in out


def test_a_foreign_cors_origin_fails():
    code, out = run(cors_any=True)
    assert code == 1 and "FAIL  CORS allows a foreign origin" in out


def test_no_sign_in_limit_fails():
    code, out = run(limit=0)
    assert code == 1 and "FAIL  sign-in burst" in out
