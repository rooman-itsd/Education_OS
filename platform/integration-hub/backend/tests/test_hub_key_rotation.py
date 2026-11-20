"""Rotating the key-encryption key covers everything it encrypts: the secret store's files and the database's
encrypted columns. After a rotation the previous key can be removed and everything still reads."""

import base64

from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_integration_hub.application import deliveries
from eos_integration_hub.application.invoke import invoke
from eos_integration_hub.application.keys import rotate_kek
from eos_integration_hub.infrastructure.models import Delivery, InboundReceipt, OAuthState
from eos_integration_hub.infrastructure.secrets import SecretStoreError, get_cipher
from hub_support import BASE, authorised_meet, binding_of, create, enabled_cert, key_of, put_credential, state_of
from sqlalchemy import select

OLD = base64.b64encode(b"k" * 32).decode()  # conftest's key
NEW = base64.b64encode(b"n" * 32).decode()


def _blobs(org_id: str) -> dict[str, list[tuple[bytes, str]]]:
    with SessionLocal() as db, platform_scope():
        return {
            "delivery": [
                (d.payload_encrypted, d.id)
                for d in db.scalars(select(Delivery).where(Delivery.organisation_id == org_id))
                if d.payload_encrypted
            ],
            "inbound": [
                (r.raw_encrypted, f"inbound:{r.id}")
                for r in db.scalars(select(InboundReceipt).where(InboundReceipt.organisation_id == org_id))
                if r.raw_encrypted
            ],
            "verifier": [
                (s.code_verifier_encrypted, s.state_hash)
                for s in db.scalars(select(OAuthState).where(OAuthState.organisation_id == org_id))
            ],
        }


def test_after_rotation_the_previous_key_can_go_and_everything_still_reads(client, org, adapter, monkeypatch, hub_env):
    # under the old key: credentials (files), a queued async input, a kept raw callback, a pending PKCE verifier
    enabled_cert(client, org)
    queued = invoke(
        port="certificate-issuance",
        operation="issue",
        input={"issuance_key": "rot-1", "doc_kind": "marksheet", "holder": {"person_id": "p-1"}},
        idempotency_key="exam:rot-1",
        caller_module="examinations",
        organisation_id=org.id,
    )
    assert queued["status"] == "queued"
    meet = authorised_meet(client, org, adapter)
    raw = b'{"event": "meeting.started", "event_id": "rot-evt", "payload": {"meeting_key": "k"}}'
    r = client.post(
        f"{BASE}/inbound/fake-adapter/{key_of(meet)}",
        content=raw,
        headers={"content-type": "application/json", "x-fake-signature": adapter.sign("meet-client-secret", raw)},
    )
    assert r.status_code == 200
    pending = create(client, org, provider="fakemeet", port="meetings", settings={"account_id": "acc-2"})
    put_credential(client, org, pending["id"], "client_id", "id")
    put_credential(client, org, pending["id"], "client_secret", "secret")
    r = client.post(
        f"{BASE}/connections/{pending['id']}/authorise",
        json={"return_url": "https://app.example.test/"},
        headers=org.admin,
    )
    start, cookie = r.json(), binding_of(r)
    before = _blobs(org.id)
    assert all(before.values()), before

    # the new key, the old one kept as previous: rotate
    monkeypatch.setenv("INTEGRATION_HUB_SECRET_KEK", NEW)
    monkeypatch.setenv("INTEGRATION_HUB_SECRET_KEK_PREVIOUS", OLD)
    counts = rotate_kek()
    assert counts["secrets"] >= 4 and counts["unreadable"] == 0
    assert counts["delivery_inputs"] >= 1 and counts["inbound_raw"] >= 1 and counts["oauth_verifiers"] >= 1
    assert rotate_kek() == {"secrets": 0, "unreadable": 0, "delivery_inputs": 0, "inbound_raw": 0, "oauth_verifiers": 0}

    # the previous key removed: every kind still decrypts under the new key alone
    monkeypatch.delenv("INTEGRATION_HUB_SECRET_KEK_PREVIOUS")
    cipher = get_cipher()
    assert cipher.previous is None
    for kind, items in _blobs(org.id).items():
        for blob, aad in items:
            assert cipher.decrypt(blob, aad), kind
    # and it works end to end: the queued delivery runs with its input and the credentials,
    deliveries.process_due()
    with SessionLocal() as db, platform_scope():
        assert db.get(Delivery, queued["delivery_id"]).status == "succeeded"
    # the pending authorisation completes with its verifier and stores tokens
    r = client.get(
        f"{BASE}/oauth/callback/fake-adapter",
        params={"state": state_of(start["authorize_url"]), "code": "good-code"},
        headers=cookie,
        follow_redirects=False,
    )
    assert r.status_code == 302 and r.headers["location"].endswith("status=connected"), r.headers


def test_without_rotation_removing_the_previous_key_loses_the_database_blobs(client, org, monkeypatch):
    """The failure the rotation prevents: blobs sealed under the old key do not open under the new one alone."""
    enabled_cert(client, org)
    invoke(
        port="certificate-issuance",
        operation="issue",
        input={"issuance_key": "rot-2", "doc_kind": "marksheet", "holder": {"person_id": "p-1"}},
        idempotency_key="exam:rot-2",
        caller_module="examinations",
        organisation_id=org.id,
    )
    [(blob, aad)] = _blobs(org.id)["delivery"]
    monkeypatch.setenv("INTEGRATION_HUB_SECRET_KEK", NEW)
    try:
        get_cipher().decrypt(blob, aad)
    except SecretStoreError:
        pass
    else:
        raise AssertionError("an old blob opened under the new key alone")
