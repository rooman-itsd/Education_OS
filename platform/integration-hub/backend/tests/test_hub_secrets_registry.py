"""The secret store (file backend with AES-256-GCM and key rotation, env backend) and the adapter registry's
normalisation of whatever an adapter hands back."""

import base64
import logging
import os
from dataclasses import dataclass

import pytest
from eos_integration_hub.infrastructure import registry, secrets
from eos_integration_hub.infrastructure.config import HubConfig

KEY_A = base64.b64encode(b"a" * 32).decode()
KEY_B = base64.b64encode(b"b" * 32).decode()


def _store(tmp_path, kek=KEY_A, previous=""):
    return secrets.FileSecretStore(str(tmp_path), secrets.Cipher.from_config(_config(kek, previous)))


def _config(kek, previous=""):
    os.environ["INTEGRATION_HUB_SECRET_KEK"] = kek
    os.environ["INTEGRATION_HUB_SECRET_KEK_PREVIOUS"] = previous
    return HubConfig.from_env()


def test_file_store_round_trip_encrypted_and_bound_to_its_reference(tmp_path):
    store = _store(tmp_path)
    ref = secrets.ref_for("org-1", "conn-1", "client_secret")
    store.put(ref, "s3cr3t-value")
    assert store.get(ref) == "s3cr3t-value"
    path = tmp_path / "org-1" / "conn-1" / "client_secret.enc"
    assert b"s3cr3t" not in path.read_bytes() and oct(path.stat().st_mode & 0o777) == "0o600"
    # a file copied under another name does not decrypt (the reference is the associated data)
    other = tmp_path / "org-1" / "conn-1" / "api_key.enc"
    other.write_bytes(path.read_bytes())
    with pytest.raises(secrets.SecretStoreError):
        store.get(secrets.ref_for("org-1", "conn-1", "api_key"))
    store.delete(ref)
    assert store.get(ref) is None
    assert "s3cr3t" not in repr(store) and "keys hidden" in repr(store._cipher)


def test_references_cannot_escape_the_directory(tmp_path):
    store = _store(tmp_path)
    for bad in (
        "secret://integration-hub/../etc/passwd",
        "secret://integration-hub/a/./b",
        "file:///etc/passwd",
        "secret://integration-hub/",
        "secret://integration-hub/a//b",
    ):
        with pytest.raises(secrets.SecretStoreError):
            store.get(bad)
    with pytest.raises(secrets.SecretStoreError):
        secrets.ref_for("org", "..", "x")


def test_key_rotation_without_downtime(tmp_path):
    old = _store(tmp_path, KEY_A)
    ref = secrets.ref_for("o", "c", "token")
    old.put(ref, "value-under-a")
    rotating = _store(tmp_path, KEY_B, previous=KEY_A)
    assert rotating.get(ref) == "value-under-a"  # still readable during the rotation
    assert rotating.rotate_kek() == 1 and rotating.rotate_kek() == 0
    assert _store(tmp_path, KEY_B).get(ref) == "value-under-a"  # the previous key can now be emptied
    with pytest.raises(secrets.SecretStoreError):
        _store(tmp_path, KEY_A).get(ref)


def test_a_missing_kek_is_refused_outside_dev_mode(monkeypatch):
    monkeypatch.setattr(secrets, "settings", type("S", (), {"dev_mode": False, "jwt_secret": "x"})())
    for kek in ("", "replace-me-in-the-environment", base64.b64encode(b"short").decode()):
        with pytest.raises(secrets.SecretStoreError):
            secrets.Cipher.from_config(_config(kek))
    monkeypatch.setenv("INTEGRATION_HUB_SECRET_BACKEND", "env")
    with pytest.raises(secrets.SecretStoreError):
        secrets.get_store()


def test_env_backend_is_read_only(monkeypatch):
    monkeypatch.setenv("INTEGRATION_HUB_SECRET_BACKEND", "env")
    store = secrets.get_store()
    ref = secrets.ref_for("org-1", "conn-1", "api_key")
    monkeypatch.setenv(secrets.EnvSecretStore.env_name(ref), "from-env")
    assert secrets.EnvSecretStore.env_name(ref) == "INTEGRATION_HUB_SECRET__ORG_1__CONN_1__API_KEY"
    assert store.get(ref) == "from-env" and store.read_only
    with pytest.raises(secrets.SecretStoreError):
        store.put(ref, "x")


def test_cipher_refuses_tampered_or_foreign_blobs():
    cipher = secrets.Cipher.from_config(_config(KEY_A))
    blob = cipher.encrypt(b"payload", "delivery-1")
    assert cipher.decrypt(blob, "delivery-1") == b"payload"
    for bad in (blob[:-1] + bytes([blob[-1] ^ 1]), b"EH1short", b"XXX" + blob[3:]):
        with pytest.raises(secrets.SecretStoreError):
            cipher.decrypt(bad, "delivery-1")
    with pytest.raises(secrets.SecretStoreError):
        cipher.decrypt(blob, "delivery-2")
    with pytest.raises(secrets.SecretStoreError):
        secrets.Cipher.from_config(_config(KEY_B)).decrypt(blob, "delivery-1")


# ------------------------------------------------------------------ registry


@dataclass
class _Result:
    output: dict | None = None
    error: dict | None = None
    provider_reference: str | None = None


def test_normalise_accepts_mappings_objects_and_bare_outputs():
    assert registry.normalise({"output": {"a": 1}, "provider_reference": "r"}).output == {"a": 1}
    assert registry.normalise(_Result(output={"b": 2})).output == {"b": 2}
    assert registry.normalise({"status": "healthy"}).output == {"status": "healthy"}
    assert registry.normalise(None).output == {}
    out = registry.normalise({"error": {"code": "throttled", "retry_after_s": 10**9, "provider_code": 429}})
    assert (
        out.error_code == "throttled" and out.retryable and out.retry_after_s == 86_400 and out.provider_code == "429"
    )
    out = registry.normalise({"error": {"code": "auth_failed", "retryable": True}})
    assert out.retryable is False  # the contract's flag, never the adapter's
    assert registry.normalise({"error": "nonsense"}).error_code == "provider_error"
    assert registry.normalise(42).error_code == "provider_error"
    assert registry.normalise({"provider_reference": "x" * 500, "output": {}}).provider_reference == "x" * 200


def test_context_reads_as_attributes_or_mapping_and_hides_secrets():
    ctx = registry.AdapterContext(
        organisation_id="o", connection_id="c", provider="p", mode="sandbox", secrets={"client_secret": "hide-me"}
    )
    assert ctx["mode"] == ctx.mode == "sandbox" and ctx.get("nope", 1) == 1
    assert "hide-me" not in repr(ctx)
    with pytest.raises(KeyError):
        ctx["nope"]


def test_a_broken_or_duplicate_adapter_is_skipped_not_fatal(monkeypatch, caplog):
    class Broken:
        name = "broken-adapter"
        value = "x:y"

        def load(self):
            raise ImportError("no module named vendor_sdk")

    class Fine:
        def __init__(self, name):
            self.name, self.value = name, "x:y"

        def load(self):
            return lambda: type(
                "A", (), {"describe": lambda self: {"ports": [{"port": "meetings"}], "providers": [{"provider": "p1"}]}}
            )()

    points = [Broken(), Fine("dup-adapter"), Fine("dup-adapter"), Fine("good-adapter"), Fine("Bad Name")]
    monkeypatch.delenv("INTEGRATION_HUB_ADAPTERS")
    monkeypatch.setattr(registry.metadata, "entry_points", lambda group: points)
    with caplog.at_level(logging.WARNING):
        found = registry.discover()
    assert list(found.adapters) == ["good-adapter"]
    assert set(found.skipped) == {"broken-adapter", "dup-adapter", "Bad Name"}
    assert "vendor_sdk" not in caplog.text
    good = found.adapters["good-adapter"]
    assert good.provider("p1").ports == ("meetings",) and good.provider("p1").modes == ("mock",)
