"""OAuth with PKCE for organisation connections and for people linking their own accounts."""

from hub_support import (
    BASE,
    audit_actions,
    authorised_meet,
    code,
    create,
    link_account,
    outbox,
    put_credential,
    state_of,
    wear_connection,
)


def _start_meet(client, org):
    c = create(client, org, provider="fakemeet", port="meetings")
    put_credential(client, org, c["id"], "client_id", "id")
    put_credential(client, org, c["id"], "client_secret", "secret")
    r = client.post(
        f"{BASE}/connections/{c['id']}/authorise",
        json={"return_url": "https://app.example.test/back?x=1"},
        headers=org.admin,
    )
    assert r.status_code == 200, r.text
    return c, r.json()


def test_organisation_authorisation_with_pkce_stores_tokens_as_credentials(client, org, adapter):
    c, start = _start_meet(client, org)
    assert start["authorize_url"].startswith("https://auth.fake.example/authorize")
    assert (
        adapter.STATE["redirect_uri"] == "https://api.example.test/api/v1/integration-hub/oauth/callback/fake-adapter"
    )
    # S256: the challenge sent to the adapter is 43 base64url characters, never the verifier
    challenge = adapter.STATE["challenges"][state_of(start["authorize_url"])]
    assert len(challenge) == 43 and "=" not in challenge
    r = client.get(
        f"{BASE}/oauth/callback/fake-adapter",
        params={"state": state_of(start["authorize_url"]), "code": "good-code"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"] == "https://app.example.test/back?x=1&status=connected"
    got = client.get(f"{BASE}/connections/{c['id']}", headers=org.admin).json()
    assert got["authorised"] is True
    creds = {
        x["name"]: x for x in client.get(f"{BASE}/connections/{c['id']}/credentials", headers=org.admin).json()["items"]
    }
    assert creds["access_token"]["source"] == "oauth" and creds["refresh_token"]["set"] is True
    [ev] = outbox("integration-hub.connection.authorised", org.id)
    assert ev == {
        "organisation_id": org.id,
        "connection_id": c["id"],
        "provider": "fakemeet",
        "granted_scopes": ["activity", "sleep"],
    }
    assert "rt-secret-value" not in str(outbox("integration-hub.connection.credentials-rotated", org.id))


def test_state_is_single_use_bound_to_the_adapter_and_expires(client, org, clock):
    _c, start = _start_meet(client, org)
    state = state_of(start["authorize_url"])

    def cb(adapter="fake-adapter"):
        params = {"state": state, "code": "good-code"}
        return client.get(f"{BASE}/oauth/callback/{adapter}", params=params, follow_redirects=False)

    assert code(cb(adapter="other-adapter")) == "state_invalid"
    assert cb().status_code == 302
    r = cb()
    assert r.status_code == 401 and code(r) == "state_invalid"  # used
    _c2, start2 = _start_meet(client, org)
    clock.advance(seconds=601)
    r = client.get(
        f"{BASE}/oauth/callback/fake-adapter",
        params={"state": state_of(start2["authorize_url"]), "code": "good-code"},
        follow_redirects=False,
    )
    assert code(r) == "state_invalid"
    assert code(client.get(f"{BASE}/oauth/callback/fake-adapter", params={"state": "made-up"})) == "state_invalid"
    assert client.get(f"{BASE}/oauth/callback/fake-adapter").status_code == 422  # state is required


def test_a_refused_or_failed_exchange_redirects_with_the_code(client, org):
    _c, start = _start_meet(client, org)
    r = client.get(
        f"{BASE}/oauth/callback/fake-adapter",
        params={"state": state_of(start["authorize_url"]), "error": "access_denied"},
        follow_redirects=False,
    )
    assert r.status_code == 302 and r.headers["location"].endswith("status=failed&code=consent_required")
    _c, start = _start_meet(client, org)
    r = client.get(
        f"{BASE}/oauth/callback/fake-adapter",
        params={"state": state_of(start["authorize_url"]), "code": "bad-code"},
        follow_redirects=False,
    )
    assert r.headers["location"].endswith("status=failed&code=auth_failed")
    assert "authorisation.failed" in audit_actions(org.id)


def test_return_url_must_be_on_an_allowed_host(client, org):
    c = create(client, org, provider="fakemeet", port="meetings")
    for url in (
        "https://evil.example/x",
        "http://app.example.test/x",
        "javascript:alert(1)",
        "https://user:pw@app.example.test/",
    ):
        r = client.post(f"{BASE}/connections/{c['id']}/authorise", json={"return_url": url}, headers=org.admin)
        assert r.status_code == 422 and code(r) == "invalid_return_url", url


def test_authorise_refused_for_a_provider_without_authorization_code(client, org):
    c = create(client, org)  # fakecert: hmac_shared_secret
    r = client.post(f"{BASE}/connections/{c['id']}/authorise", json={}, headers=org.admin)
    assert r.status_code == 409 and code(r) == "provider_not_offered"


def test_a_person_links_and_disconnects_their_own_account(client, org, adapter, hub_env):
    r = client.post(
        f"{BASE}/me/account-links", json={"port": "wearable-data", "provider": "fakewear"}, headers=org.member
    )
    assert r.status_code == 409 and code(r) == "connection_disabled"
    wear_connection(client, org)
    link = link_account(client, org)
    mine = client.get(f"{BASE}/me/account-links", headers=org.member).json()["items"]
    assert [(x["id"], x["status"], x["granted_scopes"]) for x in mine] == [
        (link["id"], "active", ["activity", "sleep"])
    ]
    assert mine[0]["purpose"] == "Share daily training data with your coaches"
    assert "at-good-code" not in str(mine)
    assert client.get(f"{BASE}/me/account-links", headers=org.headers["member2"]).json()["items"] == []
    [ev] = outbox("integration-hub.account-link.connected", org.id)
    assert ev["person_id"] == org.ids["member"] and ev["account_link_id"] == link["id"]
    r = client.post(
        f"{BASE}/me/account-links", json={"port": "wearable-data", "provider": "fakewear"}, headers=org.member
    )
    assert code(r) == "link_exists"
    # nobody disconnects someone else's link
    assert client.delete(f"{BASE}/me/account-links/{link['id']}", headers=org.headers["member2"]).status_code == 404
    assert len(list(hub_env.rglob("tokens.enc"))) == 1
    r = client.delete(f"{BASE}/me/account-links/{link['id']}", headers=org.member)
    assert r.status_code == 204
    assert adapter.STATE["revoked"] == [link["id"]]
    assert not list(hub_env.rglob("tokens.enc"))  # tokens deleted from the secret store
    [rev] = outbox("integration-hub.account-link.revoked", org.id)
    assert rev["cause"] == "disconnected" and rev["person_id"] == org.ids["member"]
    assert "account-link.revoked" in audit_actions(org.id)


def test_admin_lists_and_revokes_links_with_a_reason(client, org, adapter):
    wear_connection(client, org)
    link = link_account(client, org)
    page = client.get(f"{BASE}/account-links", params={"status": "active"}, headers=org.admin).json()
    assert [x["id"] for x in page["items"]] == [link["id"]] and page["next_cursor"] is None
    assert client.get(f"{BASE}/account-links", headers=org.member).status_code == 403
    r = client.post(f"{BASE}/account-links/{link['id']}/revoke", json={"reason": "x"}, headers=org.admin)
    assert r.status_code == 422
    r = client.post(f"{BASE}/account-links/{link['id']}/revoke", json={"reason": "Left the academy"}, headers=org.admin)
    assert r.status_code == 200 and r.json()["status"] == "revoked"
    assert outbox("integration-hub.account-link.revoked", org.id)[-1]["cause"] == "revoked_by_admin"


def test_member_cannot_link_through_an_organisation_scope_provider(client, org, adapter):
    authorised_meet(client, org, adapter)
    r = client.post(f"{BASE}/me/account-links", json={"port": "meetings", "provider": "fakemeet"}, headers=org.member)
    assert r.status_code == 409 and code(r) == "provider_not_offered"


def test_token_refresh_replaces_tokens_and_expires_a_link_on_auth_failed(client, org, adapter, clock):
    from eos_core.db import SessionLocal
    from eos_integration_hub.application import authorisation

    wear_connection(client, org)
    link = link_account(client, org)
    clock.advance(hours=6, minutes=55)  # the fake's token expires at 13:00; lead time 600 s
    with SessionLocal() as db:
        assert authorisation.refresh_due(db) >= 1  # other tests' links in the shared database may be due too
    mine = client.get(f"{BASE}/me/account-links", headers=org.member).json()["items"]
    assert mine[0]["expires_at"] == "2026-11-06T13:00:00+00:00"
    adapter.STATE["refresh"] = "refused"
    clock.advance(days=1)
    with SessionLocal() as db:
        authorisation.refresh_due(db)
    mine = client.get(f"{BASE}/me/account-links", headers=org.member).json()["items"]
    assert mine[0]["status"] == "expired"
    assert outbox("integration-hub.account-link.revoked", org.id)[-1] == {
        "organisation_id": org.id,
        "account_link_id": link["id"],
        "person_id": org.ids["member"],
        "port": "wearable-data",
        "provider": "fakewear",
        "cause": "token_expired",
    }
