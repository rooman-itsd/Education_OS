"""ADR-0006: a Keycloak realm token signs a mapped user in; the callback route turns a code into the platform's
own token; the config route tells the sign-in page whether the organisation has a realm."""

from __future__ import annotations

import uuid

import pytest
from eos_core import oidc
from eos_core.security import create_token
from eos_core.tenant import platform_scope
from eos_identity.application import service
from eos_identity.domain.models import User
from oidc_fake import CLIENT_ID, ISSUER_BASE, ORGS, Realm
from sqlalchemy import select

PREFIX = "/api/v1/identity"


def _user(db, slug: str, email: str, *, subject: str | None = None, status: str = "active", roles=None) -> User:
    with platform_scope():
        u = service.create_user(
            db, organisation_id=ORGS[slug][0], email=email, name="P", password="Passw0rd!x", roles=roles or ["student"]
        )
        u.oidc_subject = subject
        u.status = status
        db.commit()
    return u


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@pilot.example.com"


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _reload(db, user_id: str) -> User:
    db.expire_all()
    with platform_scope():
        return db.get(User, user_id)


# ---- bearer tokens from a realm ------------------------------------------------------------------------


def test_realm_token_for_a_mapped_user_is_a_principal(client, db, realm):
    sub = "kc-" + uuid.uuid4().hex
    u = _user(db, "pilot", _email("mapped"), subject=sub, roles=["org-admin"])
    r = client.get(f"{PREFIX}/auth/me", headers=_bearer(realm.token(sub=sub)))
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["id"] == u.id and me["organisation_id"] == "org-pilot" and me["roles"] == ["org-admin"]
    assert "identity:user:read" in me["permissions"] and me["is_super_admin"] is False
    # a realm token opens routes the catalogue grants the user's roles, like our own token would
    assert client.get(f"{PREFIX}/users", headers=_bearer(realm.token(sub=sub))).status_code == 200


def test_first_sight_links_the_subject_by_verified_email(client, db, realm):
    email = _email("first")
    u = _user(db, "pilot", email)
    assert u.oidc_subject is None
    sub = "kc-" + uuid.uuid4().hex
    r = client.get(f"{PREFIX}/auth/me", headers=_bearer(realm.token(sub=sub, email=email.upper())))
    assert r.status_code == 200, r.text
    assert r.json()["id"] == u.id and r.json()["oidc_linked"] is True
    assert _reload(db, u.id).oidc_subject == sub
    # a second subject claiming the same email does not take the user over: the link is by subject now
    r = client.get(f"{PREFIX}/auth/me", headers=_bearer(realm.token(sub="kc-other", email=email)))
    assert r.status_code == 401


def test_unverified_email_never_links(client, db, realm):
    email = _email("unverified")
    u = _user(db, "pilot", email)
    r = client.get(f"{PREFIX}/auth/me", headers=_bearer(realm.token(sub="kc-x", email=email, email_verified=False)))
    assert r.status_code == 401
    assert _reload(db, u.id).oidc_subject is None


def test_unknown_person_is_refused(client, realm):
    r = client.get(f"{PREFIX}/auth/me", headers=_bearer(realm.token(sub="kc-nobody", email=_email("nobody"))))
    assert r.status_code == 401


@pytest.mark.parametrize("slug", ["dormant", "gone"])
def test_inactive_organisation_is_refused(client, db, realm, slug):
    sub = "kc-" + uuid.uuid4().hex
    _user(db, slug, _email(slug), subject=sub)
    r = client.get(f"{PREFIX}/auth/me", headers=_bearer(realm.token(slug, sub=sub)))
    assert r.status_code == 401
    assert "organisation is" in r.json()["detail"]


def test_disabled_user_is_refused(client, db, realm):
    sub = "kc-" + uuid.uuid4().hex
    _user(db, "pilot", _email("disabled"), subject=sub, status="disabled")
    assert client.get(f"{PREFIX}/auth/me", headers=_bearer(realm.token(sub=sub))).status_code == 401


def test_super_admin_is_never_matched_by_email(client, db, realm):
    email = _email("root")
    with platform_scope():
        service.create_user(
            db,
            organisation_id=None,
            email=email,
            name="Root",
            password="RootPassw0rd!",
            roles=["super-admin"],
            is_super_admin=True,
        )
        db.commit()
    assert client.get(f"{PREFIX}/auth/me", headers=_bearer(realm.token(sub="kc-root", email=email))).status_code == 401


@pytest.mark.parametrize(
    "bad",
    [
        {"iss": "https://evil.example/auth/realms/pilot"},
        {"iss": f"{ISSUER_BASE}/realms/pilot/../other"},
        {"aud": "another-client"},
        {"exp": 1_000_000},
    ],
    ids=["wrong-issuer", "issuer-path-trick", "wrong-audience", "expired"],
)
def test_bad_realm_tokens_are_401(client, db, realm, bad):
    sub = "kc-" + uuid.uuid4().hex
    _user(db, "pilot", _email("bad"), subject=sub)
    r = client.get(f"{PREFIX}/auth/me", headers=_bearer(realm.token(sub=sub, **bad)))
    assert r.status_code == 401, r.text


def test_unknown_kid_refreshes_the_jwks_once_then_refuses(client, db, realm):
    sub = "kc-" + uuid.uuid4().hex
    _user(db, "pilot", _email("kid"), subject=sub)
    assert client.get(f"{PREFIX}/auth/me", headers=_bearer(realm.token(sub=sub))).status_code == 200
    assert realm.fetches == 1
    assert client.get(f"{PREFIX}/auth/me", headers=_bearer(realm.token(sub=sub, kid="rotated"))).status_code == 401
    assert realm.fetches == 2  # refreshed once for the unknown kid
    # the cached keys still serve the known kid without another fetch
    assert client.get(f"{PREFIX}/auth/me", headers=_bearer(realm.token(sub=sub))).status_code == 200
    assert realm.fetches == 2


def test_realm_removed_from_settings_no_longer_authenticates(client, db, realm, monkeypatch):
    """Review of #365, point 5: taking a slug out of EOS_OIDC_REALMS stops its tokens at once, cached keys or
    not, and a token naming a realm that was never configured costs no JWKS fetch."""
    from dataclasses import replace

    sub = "kc-" + uuid.uuid4().hex
    _user(db, "pilot", _email("removed"), subject=sub)
    assert client.get(f"{PREFIX}/auth/me", headers=_bearer(realm.token(sub=sub))).status_code == 200
    fetches = realm.fetches
    monkeypatch.setattr(oidc, "settings", replace(oidc.settings, oidc_realms="dormant,gone"))
    r = client.get(f"{PREFIX}/auth/me", headers=_bearer(realm.token(sub=sub)))
    assert r.status_code == 401 and "not enabled" in r.json()["detail"]
    r = client.get(f"{PREFIX}/auth/me", headers=_bearer(realm.token("norealm", sub=sub)))
    assert r.status_code == 401
    assert realm.fetches == fetches


def test_id_token_is_not_a_bearer_token(client, db, realm):
    sub = "kc-" + uuid.uuid4().hex
    _user(db, "pilot", _email("idtok"), subject=sub)
    assert client.get(f"{PREFIX}/auth/me", headers=_bearer(realm.token(sub=sub, typ="ID"))).status_code == 401
    other_client = realm.token(sub=sub, azp="security-admin-console")
    assert client.get(f"{PREFIX}/auth/me", headers=_bearer(other_client)).status_code == 401


def test_callback_refuses_an_access_token_in_place_of_the_id_token(client, db, realm, monkeypatch):
    sub = "kc-" + uuid.uuid4().hex
    _user(db, "pilot", _email("cbaccess"), subject=sub)
    _exchange_returning(realm, monkeypatch, sub=sub, typ="Bearer")
    assert _callback(client).status_code == 401


def test_token_signed_by_another_key_is_refused(client, db, realm):
    """Same kid, different private key: the signature check, not only the kid lookup, decides."""
    sub = "kc-" + uuid.uuid4().hex
    _user(db, "pilot", _email("forged"), subject=sub)
    forged = Realm(kid=realm.kid).token(sub=sub)
    assert client.get(f"{PREFIX}/auth/me", headers=_bearer(forged)).status_code == 401


def test_realm_tokens_are_refused_when_oidc_is_off(client, db, realm, monkeypatch):
    from dataclasses import replace

    sub = "kc-" + uuid.uuid4().hex
    _user(db, "pilot", _email("off"), subject=sub)
    token = realm.token(sub=sub)
    monkeypatch.setattr(oidc, "settings", replace(oidc.settings, oidc_issuer_base=""))
    assert client.get(f"{PREFIX}/auth/me", headers=_bearer(token)).status_code == 401


def test_own_hs256_token_path_is_unchanged(client, db, oidc_settings):
    u = _user(db, "pilot", _email("hs"), roles=["student"])
    token = create_token(user_id=u.id, organisation_id="org-pilot", roles=["student"])
    r = client.get(f"{PREFIX}/auth/me", headers=_bearer(token))
    assert r.status_code == 200 and r.json()["id"] == u.id and r.json()["roles"] == ["student"]
    assert client.get(f"{PREFIX}/auth/me", headers=_bearer(token + "x")).status_code == 401


# ---- GET /auth/oidc/config -----------------------------------------------------------------------------


def test_config_for_a_slug_with_a_realm(client, oidc_settings):
    r = client.get(f"{PREFIX}/auth/oidc/config", params={"slug": "pilot"})
    assert r.status_code == 200, r.text
    cfg = r.json()
    assert cfg["realm"] == "pilot" and cfg["issuer"] == f"{ISSUER_BASE}/realms/pilot"
    assert cfg["authorization_endpoint"] == f"{ISSUER_BASE}/realms/pilot/protocol/openid-connect/auth"
    assert cfg["token_endpoint"] == f"{ISSUER_BASE}/realms/pilot/protocol/openid-connect/token"
    assert cfg["client_id"] == CLIENT_ID and cfg["code_challenge_method"] == "S256"
    assert cfg["response_type"] == "code" and "openid" in cfg["scope"].split()
    assert "secret" not in r.text


@pytest.mark.parametrize("slug", ["norealm", "dormant", "nosuchorg", "Bad Slug!"])
def test_config_is_404_without_a_usable_realm(client, oidc_settings, slug):
    assert client.get(f"{PREFIX}/auth/oidc/config", params={"slug": slug}).status_code == 404


def test_config_is_404_when_oidc_is_off(client, monkeypatch):
    from dataclasses import replace

    monkeypatch.setattr(oidc, "settings", replace(oidc.settings, oidc_issuer_base="", oidc_realms="*"))
    assert client.get(f"{PREFIX}/auth/oidc/config", params={"slug": "pilot"}).status_code == 404


# ---- POST /auth/oidc/callback --------------------------------------------------------------------------

VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"


def _callback(client, **body):
    payload = {"code": "abc", "code_verifier": VERIFIER, "redirect_uri": "https://edu.example/", "slug": "pilot"}
    return client.post(f"{PREFIX}/auth/oidc/callback", json={**payload, **body})


def _exchange_returning(realm, monkeypatch, **token_overrides):
    calls = []

    def exchange(realm_name, *, code, code_verifier, redirect_uri):
        calls.append({"realm": realm_name, "code": code, "code_verifier": code_verifier, "redirect_uri": redirect_uri})
        return {"access_token": "opaque", "id_token": realm.token(realm_name, **{"typ": "ID", **token_overrides})}

    monkeypatch.setattr(oidc, "exchange_code", exchange)
    return calls


def test_callback_exchanges_the_code_and_issues_the_platform_token(client, db, realm, monkeypatch):
    sub = "kc-" + uuid.uuid4().hex
    u = _user(db, "pilot", _email("cb"), subject=sub, roles=["org-admin"])
    calls = _exchange_returning(realm, monkeypatch, sub=sub)
    r = _callback(client, code="the-code")
    assert r.status_code == 200, r.text
    assert calls == [
        {"realm": "pilot", "code": "the-code", "code_verifier": VERIFIER, "redirect_uri": "https://edu.example/"}
    ]
    body = r.json()
    assert body["user"]["id"] == u.id and body["user"]["email"] == u.email
    # the token is the platform's own (HS256), so every other route reads it as before
    import jwt

    assert jwt.get_unverified_header(body["token"])["alg"] == "HS256"
    me = client.get(f"{PREFIX}/auth/me", headers=_bearer(body["token"]))
    assert me.status_code == 200 and me.json()["id"] == u.id and me.json()["roles"] == ["org-admin"]


def test_callback_links_on_first_sight(client, db, realm, monkeypatch):
    email = _email("cbfirst")
    u = _user(db, "pilot", email)
    _exchange_returning(realm, monkeypatch, sub="kc-cb-first", email=email)
    assert _callback(client).status_code == 200
    assert _reload(db, u.id).oidc_subject == "kc-cb-first"


def test_callback_refuses_unknown_users_with_no_account(client, realm, monkeypatch):
    _exchange_returning(realm, monkeypatch, sub="kc-stranger", email=_email("stranger"))
    r = _callback(client)
    assert r.status_code == 403 and r.json()["detail"] == "no_account"


def test_callback_is_404_for_a_slug_without_oidc(client, realm, monkeypatch):
    _exchange_returning(realm, monkeypatch)
    assert _callback(client, slug="norealm").status_code == 404


def test_callback_refuses_a_failed_exchange(client, db, realm, monkeypatch):
    def refused(realm_name, **kw):  # noqa: ARG001
        raise oidc.OIDCError("code exchange refused by realm pilot: invalid_grant")

    monkeypatch.setattr(oidc, "exchange_code", refused)
    r = _callback(client)
    assert r.status_code == 401 and "invalid_grant" in r.json()["detail"]


def test_callback_refuses_an_id_token_from_another_realm(client, db, realm, monkeypatch):
    sub = "kc-" + uuid.uuid4().hex
    _user(db, "pilot", _email("cross"), subject=sub)
    _user(db, "dormant", _email("cross"), subject=sub)

    def exchange(realm_name, **kw):  # noqa: ARG001
        return {"id_token": realm.token("dormant", sub=sub, typ="ID")}

    monkeypatch.setattr(oidc, "exchange_code", exchange)
    assert _callback(client, slug="pilot").status_code == 401


def test_callback_refuses_a_bad_id_token(client, db, realm, monkeypatch):
    sub = "kc-" + uuid.uuid4().hex
    _user(db, "pilot", _email("badid"), subject=sub)
    _exchange_returning(realm, monkeypatch, sub=sub, aud="someone-else")
    assert _callback(client).status_code == 401


def test_callback_validates_its_body(client, oidc_settings):
    assert _callback(client, code_verifier="short").status_code == 422
    assert client.post(f"{PREFIX}/auth/oidc/callback", json={}).status_code == 422


def test_link_is_unique_per_organisation(db, oidc_settings):
    """The same realm subject cannot point at two users of one organisation (migration index)."""
    from sqlalchemy.exc import IntegrityError

    sub = "kc-" + uuid.uuid4().hex
    _user(db, "pilot", _email("u1"), subject=sub)
    with platform_scope(), pytest.raises(IntegrityError):
        u2 = service.create_user(
            db, organisation_id="org-pilot", email=_email("u2"), name="P", password="Passw0rd!x", roles=["student"]
        )
        u2.oidc_subject = sub
        db.commit()
    db.rollback()
    with platform_scope():
        assert db.scalar(select(User).where(User.oidc_subject == sub, User.organisation_id == "org-pilot")) is not None
