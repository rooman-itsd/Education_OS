"""Connections, write-only credentials, modes, going live, enabling and health."""

from hub_support import (
    BASE,
    all_outbox,
    audit_actions,
    code,
    create,
    enabled_cert,
    outbox,
    put_credential,
)


def test_ports_and_adapters_come_from_the_contract_and_the_entry_point(client, org):
    ports = client.get(f"{BASE}/ports", headers=org.admin).json()["items"]
    by_id = {p["id"]: p for p in ports}
    assert set(by_id) == {
        "certificate-issuance",
        "academic-records",
        "regulatory-submission",
        "meetings",
        "wearable-data",
        "inter-institution-records",
    }
    assert {"name": "create_meeting", "mode": "sync"} in by_id["meetings"]["operations"]
    assert {"name": "issue", "mode": "async"} in by_id["certificate-issuance"]["operations"]
    assert by_id["meetings"]["implemented_by"] == ["fake-adapter"]
    assert by_id["academic-records"]["implemented_by"] == []
    adapters = client.get(f"{BASE}/adapters", params={"port": "meetings"}, headers=org.admin).json()["items"]
    assert [a["adapter"] for a in adapters] == ["fake-adapter"]
    assert [p["provider"] for p in adapters[0]["providers"]] == ["fakemeet"]
    assert adapters[0]["providers"][0]["platform_credentials_present"] is True
    assert client.get(f"{BASE}/ports", headers=org.member).status_code == 403


def test_create_starts_disabled_with_an_inbound_url_and_publishes(client, org):
    c = create(client, org, display_name="DigiLocker sandbox")
    assert c["enabled"] is False and c["mode"] == "sandbox" and c["credentials_complete"] is False
    assert c["health"]["status"] == "not_checked" and c["authorised"] is False
    urls = c["inbound_urls"]
    assert urls[0].startswith("https://api.example.test/api/v1/integration-hub/inbound/fake-adapter/")
    assert urls[1].endswith("/{channel}")
    assert len(urls[0].rsplit("/", 1)[1]) == 43  # a random 32-byte key, not the connection id
    assert c["id"] not in urls[0]
    [ev] = outbox("integration-hub.connection.created", org.id)
    assert ev == {
        "organisation_id": org.id,
        "connection_id": c["id"],
        "adapter": "fake-adapter",
        "provider": "fakecert",
        "port": "certificate-issuance",
        "mode": "sandbox",
    }
    assert "connection.created" in audit_actions(org.id)


def test_create_refusals(client, org, monkeypatch):
    base = {"adapter": "fake-adapter", "provider": "fakecert", "port": "certificate-issuance", "mode": "sandbox"}

    def post(**f):
        return client.post(f"{BASE}/connections", json={**base, **f}, headers=org.admin)

    assert code(post(adapter="no-such-adapter")) == "adapter_not_installed"
    assert code(post(adapter="Bad Name!")) == "adapter_not_installed"
    assert code(post(provider="zoom")) == "provider_not_offered"
    assert code(post(port="meetings")) == "provider_not_offered"  # fakecert does not serve meetings
    assert code(post(mode="live")) == "invalid_mode"  # live is reached through /mode
    assert code(post(mode="banana")) == "invalid_mode"
    assert post(port="not-a-port").status_code == 422
    r = post(provider="fakemeet", port="meetings", settings={"region": "eu"})
    assert r.status_code == 422 and code(r) == "invalid_settings"
    assert code(post(provider="fakemeet", port="meetings", settings={"unknown": 1})) == "invalid_settings"
    assert code(post(provider="fakemeet", port="meetings", settings={"account_id": "x" * 41})) == "invalid_settings"
    deep = {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": 1}}}}}}}}
    assert code(post(settings=deep)) == "invalid_settings"
    assert post(display_name="x" * 121).status_code == 422
    monkeypatch.setenv("INTEGRATION_HUB_ALLOW_MOCK", "false")
    assert code(post(mode="mock")) == "mock_not_allowed"
    create(client, org, display_name="Main")
    assert code(post(display_name="main")) == "connection_exists"
    assert post().status_code == 201  # a second, unnamed connection (a sandbox and a live one) is allowed
    assert client.post(f"{BASE}/connections", json={"adapter": "fake-adapter"}, headers=org.member).status_code == 403


def test_nan_and_infinity_in_settings_are_refused(client, org):
    raw = b'{"adapter":"fake-adapter","provider":"fakecert","port":"certificate-issuance","mode":"sandbox","settings":{"x":NaN}}'
    r = client.post(f"{BASE}/connections", content=raw, headers={**org.admin, "content-type": "application/json"})
    assert r.status_code == 422


def test_update_validates_settings_and_names_changed_settings_only(client, org):
    c = create(client, org, provider="fakemeet", port="meetings", settings={"account_id": "a1"})
    r = client.patch(
        f"{BASE}/connections/{c['id']}", json={"settings": {"account_id": "a2", "region": "in"}}, headers=org.admin
    )
    assert r.status_code == 200 and r.json()["settings"] == {"account_id": "a2", "region": "in"}
    [ev] = outbox("integration-hub.connection.updated", org.id)
    assert ev["changed_settings"] == ["account_id", "region"]
    r = client.patch(f"{BASE}/connections/{c['id']}", json={"settings": {"region": 5}}, headers=org.admin)
    assert code(r) == "invalid_settings"
    r = client.patch(f"{BASE}/connections/{c['id']}", json={"display_name": "Zoom main"}, headers=org.admin)
    assert r.json()["display_name"] == "Zoom main"


def test_credentials_are_write_only_and_live_outside_the_database(client, org, hub_env):
    c = create(client, org)
    st = put_credential(client, org, c["id"], "api_key", "very-secret-api-key")
    assert st["set"] is True and len(st["fingerprint"]) == 8 and st["source"] == "admin"
    assert "very-secret" not in str(st)
    listed = client.get(f"{BASE}/connections/{c['id']}/credentials", headers=org.admin).json()["items"]
    assert [(x["name"], x["set"]) for x in listed] == [("api_key", True), ("webhook_secret", False)]
    # nowhere: not in any response, event, audit record, or the database file; the secret file is encrypted, 0600
    got = client.get(f"{BASE}/connections/{c['id']}", headers=org.admin).text
    assert "very-secret-api-key" not in got
    events = all_outbox(org.id)
    assert "very-secret-api-key" not in str([e.payload for e in events])
    [rot] = outbox("integration-hub.connection.credentials-rotated", org.id)
    assert rot == {
        "organisation_id": org.id,
        "connection_id": c["id"],
        "name": "api_key",
        "fingerprint": st["fingerprint"],
        "removed": False,
    }
    from eos_core.settings import settings

    db_file = settings.database_url.split("sqlite:///", 1)[1]
    assert b"very-secret-api-key" not in open(db_file, "rb").read()
    files = list(hub_env.rglob("api_key.enc"))
    assert len(files) == 1 and b"very-secret-api-key" not in files[0].read_bytes()
    assert oct(files[0].stat().st_mode & 0o777) == "0o600"

    # unknown names, bad names, oversize values
    def put(name, v):
        return client.put(f"{BASE}/connections/{c['id']}/credentials/{name}", json={"value": v}, headers=org.admin)

    assert code(put("password", "x")) == "unknown_credential"
    assert code(put("Bad-Name", "x")) == "unknown_credential"
    assert put("api_key", "").status_code == 422
    assert put("api_key", "x" * 16385).status_code == 422
    # removal
    r = client.delete(f"{BASE}/connections/{c['id']}/credentials/api_key", headers=org.admin)
    assert r.status_code == 204 and not list(hub_env.rglob("api_key.enc"))
    assert client.delete(f"{BASE}/connections/{c['id']}/credentials/api_key", headers=org.admin).status_code == 404
    assert outbox("integration-hub.connection.credentials-rotated", org.id)[-1]["removed"] is True


def test_enable_needs_credentials_and_a_check_that_is_not_auth_failed(client, org, adapter):
    c = create(client, org)
    r = client.post(f"{BASE}/connections/{c['id']}/enable", headers=org.admin)
    assert r.status_code == 409 and code(r) == "credentials_missing"
    put_credential(client, org, c["id"], "api_key", "k")
    put_credential(client, org, c["id"], "webhook_secret", "w")
    adapter.SCRIPT["healthcheck"] = [{"error": {"code": "auth_failed"}}]
    r = client.post(f"{BASE}/connections/{c['id']}/enable", headers=org.admin)
    assert code(r) == "health_check_failed"
    assert client.get(f"{BASE}/connections/{c['id']}/health", headers=org.admin).json()["status"] == "auth_failed"
    r = client.post(f"{BASE}/connections/{c['id']}/enable", headers=org.admin)
    assert r.status_code == 200 and r.json()["enabled"] is True and r.json()["health"]["status"] == "healthy"
    assert r.json()["credentials_complete"] is True
    [ev] = outbox("integration-hub.connection.enabled", org.id)
    assert ev["mode"] == "sandbox"
    changes = outbox("integration-hub.connection.health-changed", org.id)
    assert [(e["from_status"], e["to_status"]) for e in changes] == [
        ("not_checked", "auth_failed"),
        ("auth_failed", "healthy"),
    ]
    # the secrets reached the adapter by name, for the call only
    assert ("healthcheck", "sandbox", ("api_key", "webhook_secret"), "certificate-issuance") in adapter.CALLS


def test_one_enabled_connection_per_port_and_provider(client, org):
    first = enabled_cert(client, org)
    second = enabled_cert(client, org)
    assert client.get(f"{BASE}/connections/{first['id']}", headers=org.admin).json()["enabled"] is False
    assert second["enabled"] is True
    [ev] = outbox("integration-hub.connection.disabled", org.id)
    assert ev["connection_id"] == first["id"] and second["id"] in ev["reason"]
    enabled = client.get(f"{BASE}/connections", params={"enabled": "true"}, headers=org.admin).json()["items"]
    assert [x["id"] for x in enabled] == [second["id"]]


def test_removing_a_required_credential_disables(client, org):
    c = enabled_cert(client, org)
    client.delete(f"{BASE}/connections/{c['id']}/credentials/api_key", headers=org.admin)
    got = client.get(f"{BASE}/connections/{c['id']}", headers=org.admin).json()
    assert got["enabled"] is False
    assert outbox("integration-hub.connection.disabled", org.id)[-1]["reason"] == "credential_removed"


def test_mock_mode_needs_the_switch_and_no_credentials(client, org, monkeypatch):
    c = create(client, org, mode="mock")
    r = client.post(f"{BASE}/connections/{c['id']}/enable", headers=org.admin)
    assert r.status_code == 200 and r.json()["mode"] == "mock"
    monkeypatch.setenv("INTEGRATION_HUB_ALLOW_MOCK", "false")
    other = create(client, org)
    r = client.post(f"{BASE}/connections/{other['id']}/mode", json={"mode": "mock"}, headers=org.admin)
    assert r.status_code == 422 and code(r) == "mock_not_allowed"


def test_going_live_needs_the_separate_key_every_credential_a_healthy_check_and_confirmation(client, org, adapter):
    c = create(client, org)
    url = f"{BASE}/connections/{c['id']}/mode"
    # faculty holds no hub key; a member neither
    assert (
        client.post(url, json={"mode": "live", "confirm_live": True}, headers=org.headers["faculty"]).status_code == 403
    )
    r = client.post(url, json={"mode": "live", "confirm_live": True}, headers=org.admin)
    assert code(r) == "credentials_missing"
    put_credential(client, org, c["id"], "api_key", "k")
    put_credential(client, org, c["id"], "webhook_secret", "w")
    assert code(client.post(url, json={"mode": "live"}, headers=org.admin)) == "invalid_mode"
    adapter.SCRIPT["healthcheck"] = [{"output": {"status": "degraded"}}]
    assert (
        code(client.post(url, json={"mode": "live", "confirm_live": True}, headers=org.admin)) == "health_check_failed"
    )
    r = client.post(url, json={"mode": "live", "confirm_live": True}, headers=org.admin)
    assert r.status_code == 200 and r.json()["mode"] == "live"
    assert ("healthcheck", "live", ("api_key", "webhook_secret"), "certificate-issuance") in adapter.CALLS
    [ev] = outbox("integration-hub.connection.mode-changed", org.id)
    assert (ev["from_mode"], ev["to_mode"]) == ("sandbox", "live")
    assert "connection.mode-changed" in audit_actions(org.id)


def test_live_not_allowed_when_the_provider_has_no_live_mode(client, org):
    c = create(client, org, provider="fakewear", port="wearable-data")
    r = client.post(
        f"{BASE}/connections/{c['id']}/mode", json={"mode": "live", "confirm_live": True}, headers=org.admin
    )
    assert r.status_code == 409 and code(r) == "live_not_allowed"


def test_health_on_demand_is_rate_limited(client, org, monkeypatch, clock):
    monkeypatch.setenv("INTEGRATION_HUB_HEALTH_RUNS_PER_HOUR", "2")
    c = enabled_cert(client, org)
    url = f"{BASE}/connections/{c['id']}/health"
    assert client.post(url, headers=org.admin).json()["status"] == "healthy"
    assert client.post(url, headers=org.admin).status_code == 200
    r = client.post(url, headers=org.admin)
    assert r.status_code == 429 and code(r) == "too_many_requests"
    clock.advance(hours=1, seconds=1)
    assert client.post(url, headers=org.admin).status_code == 200


def test_bad_ids_and_cursors_are_4xx(client, org):
    assert client.get(f"{BASE}/connections/not-a-uuid", headers=org.admin).status_code == 404
    assert client.get(f"{BASE}/connections/{'x' * 500}", headers=org.admin).status_code == 404
    assert client.get(f"{BASE}/deliveries", params={"cursor": "abc"}, headers=org.admin).status_code == 400
    assert client.get(f"{BASE}/deliveries", params={"cursor": "9" * 30}, headers=org.admin).status_code == 422
    assert client.get(f"{BASE}/deliveries", params={"limit": 0}, headers=org.admin).status_code == 422
    assert client.get(f"{BASE}/deliveries", params={"status": "nope"}, headers=org.admin).status_code == 422
    assert client.get(f"{BASE}/deliveries", params={"since": "yesterday"}, headers=org.admin).status_code == 422
    assert client.get(f"{BASE}/account-links", params={"cursor": "-1"}, headers=org.admin).status_code == 400
