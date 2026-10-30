"""keycloak-realm.sh against a fake `curl` on PATH that plays a small Keycloak Admin API: a new realm gets its
realm, client and mapper; a second run updates instead of duplicating; a refused call is reported with its own
HTTP status (not the previous call's); the admin password and token never appear on curl's command line."""

import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "keycloak-realm.sh"
PASSWORD = "s3cret pass&word"
TOKEN = "admin-token-123"

FAKE_CURL = textwrap.dedent(
    r'''
    #!/usr/bin/env python3
    """A fake curl: just the options keycloak-realm.sh uses, and a Keycloak Admin API held in a JSON file."""
    import json, os, sys, urllib.parse, uuid

    state_file, log_file = os.environ["FAKE_KC_STATE"], os.environ["FAKE_KC_LOG"]
    state = json.load(open(state_file)) if os.path.exists(state_file) else {"realms": {}, "clients": {}, "mappers": {}}
    argv, args = sys.argv[1:], iter(sys.argv[1:])
    method, url, data, headers, write_out, fail = "GET", "", [], {}, None, False
    for a in args:
        if a == "-X":
            method = next(args)
        elif a in ("-d", "--data-binary", "--data-urlencode"):
            v = next(args)
            if a == "--data-urlencode" and v.endswith("@-"):
                v = v[:-2] + "=" + sys.stdin.read()
            data.append(v)
        elif a == "-H":
            k, _, v = next(args).partition(":")
            headers[k.strip().lower()] = v.strip()
        elif a == "-w":
            write_out = next(args)
        elif a == "--config":
            assert next(args) == "-"
            for line in sys.stdin.read().splitlines():
                key, _, val = line.partition("=")
                if key.strip() == "header":
                    k, _, v = val.strip().strip('"').partition(":")
                    headers[k.strip().lower()] = v.strip()
        elif a.startswith("-"):
            fail = fail or "f" in a.lstrip("-") and not a.startswith("--")
        else:
            url = a
    if data and method == "GET":
        method = "POST"
    with open(log_file, "a") as f:
        f.write(json.dumps({"argv": argv, "method": method, "url": url, "headers": headers, "data": data}) + "\n")

    u = urllib.parse.urlsplit(url)
    path, query = u.path.removeprefix("/auth"), dict(urllib.parse.parse_qsl(u.query))
    parts = [p for p in path.split("/") if p]
    forced = json.loads(os.environ.get("FAKE_KC_FORCE", "{}")).get(f"{method} {path}")

    def answer(status, body=None):
        json.dump(state, open(state_file, "w"))
        if fail and status >= 400:
            sys.stderr.write(f"curl: (22) The requested URL returned error: {status}\n")
            sys.exit(22)
        out = "" if body is None else json.dumps(body)
        sys.stdout.write(out + (write_out.replace("\\n", "\n").replace("%{http_code}", str(status)) if write_out else ""))
        sys.exit(0)

    if forced:
        answer(forced)
    if path == "/realms/master/protocol/openid-connect/token":
        form = dict(d.split("=", 1) for d in data)
        if form.get("password") == os.environ["FAKE_KC_PASSWORD"] and form.get("client_id") == "admin-cli":
            answer(200, {"access_token": os.environ["FAKE_KC_TOKEN"]})
        answer(401, {"error": "invalid_grant"})
    if headers.get("authorization") != "Bearer " + os.environ["FAKE_KC_TOKEN"]:
        answer(401, {"error": "HTTP 401 Unauthorized"})
    assert parts[:2] == ["admin", "realms"], url
    parts = parts[2:]
    body = json.loads(data[0]) if data else None
    realms, clients, mappers = state["realms"], state["clients"], state["mappers"]
    if not parts and method == "POST":
        if body["realm"] in realms:
            answer(409)
        realms[body["realm"]] = body
        answer(201)
    realm = parts[0]
    if realm not in realms:
        answer(404, {"error": "Realm not found."})
    if len(parts) == 1:
        if method == "GET":
            answer(200, realms[realm])
        if method == "PUT":
            realms[realm] = body
            answer(204)
    rc = clients.setdefault(realm, [])
    if len(parts) == 2 and parts[1] == "clients":
        if method == "GET":
            answer(200, [c for c in rc if c["clientId"] == query.get("clientId", c["clientId"])])
        if method == "POST":
            if any(c["clientId"] == body["clientId"] for c in rc):
                answer(409)
            rc.append({**body, "id": str(uuid.uuid4())})
            answer(201)
    client = next((c for c in rc if c["id"] == parts[2]), None) if len(parts) > 2 else None
    if client is None:
        answer(404)
    if len(parts) == 3 and method == "PUT":
        client.update(body)
        answer(204)
    cm = mappers.setdefault(client["id"], [])
    if parts[3:5] == ["protocol-mappers", "models"]:
        if len(parts) == 5 and method == "GET":
            answer(200, cm)
        if len(parts) == 5 and method == "POST":
            if any(m["name"] == body["name"] for m in cm):
                answer(409)
            cm.append({**body, "id": str(uuid.uuid4())})
            answer(201)
        if len(parts) == 6 and method == "PUT":
            m = next((m for m in cm if m["id"] == parts[5]), None)
            if m is None or body.get("id") != parts[5]:
                answer(400)
            m.update(body)
            answer(204)
    answer(405)
    '''
).lstrip()


@pytest.fixture
def kc(tmp_path):
    if shutil.which("bash") is None:
        pytest.skip("bash not available")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl = bin_dir / "curl"
    curl.write_text(FAKE_CURL)
    curl.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_KC_STATE": str(tmp_path / "state.json"),
        "FAKE_KC_LOG": str(tmp_path / "calls.jsonl"),
        "FAKE_KC_PASSWORD": PASSWORD,
        "FAKE_KC_TOKEN": TOKEN,
        "KEYCLOAK_URL": "https://kc.example/auth",
        "KEYCLOAK_ADMIN_PASSWORD": PASSWORD,
    }

    class KC:
        def run(self, *args, **extra_env):
            return subprocess.run(
                ["bash", str(SCRIPT), *args],
                env={**env, **extra_env},
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=60,
            )

        def state(self):
            return json.loads((tmp_path / "state.json").read_text())

        def calls(self):
            return [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]

    return KC()


def test_new_realm_gets_realm_client_and_mapper(kc):
    r = kc.run("pilot", "https://edu.example/*")
    assert r.returncode == 0, r.stderr
    assert "realm pilot: created" in r.stdout
    assert "client education-os-web: created" in r.stdout
    assert "audience mapper: created" in r.stdout
    s = kc.state()
    assert s["realms"]["pilot"]["registrationAllowed"] is False
    (client,) = s["clients"]["pilot"]
    assert client["publicClient"] is True and client["redirectUris"] == ["https://edu.example/*"]
    assert client["attributes"]["pkce.code.challenge.method"] == "S256"
    (mapper,) = s["mappers"][client["id"]]
    assert mapper["config"]["included.client.audience"] == "education-os-web"


def test_rerun_updates_without_duplicating(kc):
    assert kc.run("pilot").returncode == 0
    r = kc.run("pilot", "https://other.example/cb")
    assert r.returncode == 0, r.stderr
    assert "realm pilot: exists, settings refreshed" in r.stdout
    assert "client education-os-web: exists, settings refreshed" in r.stdout
    assert "audience mapper: exists, settings refreshed" in r.stdout
    s = kc.state()
    (client,) = s["clients"]["pilot"]
    assert client["redirectUris"] == ["https://other.example/cb"]
    assert len(s["mappers"][client["id"]]) == 1


def test_a_refused_call_reports_its_own_status(kc):
    """The bug the review caught: STATUS set inside $(...) was lost, so `expect` saw the previous 201."""
    r = kc.run("pilot", FAKE_KC_FORCE=json.dumps({"GET /admin/realms/pilot/clients": 403}))
    assert r.returncode == 1
    assert "listing clients answered HTTP 403" in r.stderr
    assert "client education-os-web" not in r.stdout


def test_secrets_never_reach_the_command_line(kc):
    assert kc.run("pilot").returncode == 0
    calls = kc.calls()
    assert calls and all(PASSWORD not in " ".join(c["argv"]) for c in calls)
    assert all(TOKEN not in " ".join(c["argv"]) for c in calls)
    assert all(c["headers"].get("authorization") == f"Bearer {TOKEN}" for c in calls[1:])


def test_wrong_password_stops_before_any_admin_call(kc):
    r = kc.run("pilot", KEYCLOAK_ADMIN_PASSWORD="wrong")
    assert r.returncode == 1 and "no admin token" in r.stderr
    assert len(kc.calls()) == 1


def test_display_name_and_redirects_are_json_escaped(kc):
    r = kc.run("pilot", 'https://edu.example/"q"', REALM_DISPLAY_NAME='Pilot "School"')
    assert r.returncode == 0, r.stderr
    s = kc.state()
    assert s["realms"]["pilot"]["displayName"] == 'Pilot "School"'
    assert s["clients"]["pilot"][0]["redirectUris"] == ['https://edu.example/"q"']
