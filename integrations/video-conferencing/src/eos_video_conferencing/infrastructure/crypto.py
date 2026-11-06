"""Join links and passcodes are stored encrypted: anyone holding one can enter the class (docs/prd.md, "Data model").
Fernet (AES-128-CBC with HMAC) with the key from VIDEO_CONFERENCING_DATA_KEY. Outside mock mode a missing or malformed
key is a configuration error; in mock mode a fixed development key is used so nothing real is ever protected by it."""

from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

from ..domain.errors import AdapterError
from .config import Config

_DEV_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"video-conferencing development key, not a secret").digest())


def _key(cfg: Config) -> bytes:
    if cfg.data_key:
        return cfg.data_key.encode()
    if cfg.mode == "mock":
        return _DEV_KEY
    raise AdapterError("not_configured", "VIDEO_CONFERENCING_DATA_KEY is not set")


def _fernet(cfg: Config) -> Fernet:
    try:
        return Fernet(_key(cfg))
    except (ValueError, TypeError) as e:
        raise AdapterError("not_configured", "VIDEO_CONFERENCING_DATA_KEY is not a valid Fernet key") from e


def seal(cfg: Config, value: str | None) -> str | None:
    return None if value is None else _fernet(cfg).encrypt(value.encode()).decode()


def unseal(cfg: Config, token: str | None) -> str | None:
    if token is None:
        return None
    try:
        return _fernet(cfg).decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise AdapterError("not_configured", "stored value cannot be decrypted with the current data key") from e


def client_state(cfg: Config, connection_id: str, nonce: str) -> str:
    """The clientState of a Graph subscription: HMAC of a stored nonce under the data key. Only the nonce is in the
    database (graph_subscription.client_state_ref), so reading the table never yields the secret that Graph echoes."""
    digest = hmac.new(_key(cfg), f"graph-client-state:{connection_id}:{nonce}".encode(), hashlib.sha256).hexdigest()
    return digest[:64]
