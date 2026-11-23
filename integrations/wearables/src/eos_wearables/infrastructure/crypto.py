"""Tokens are stored encrypted: Fernet (AES-128-CBC with HMAC) with the key from WEARABLES_DATA_KEY.
Outside mock mode a missing or malformed key is a configuration error; in mock mode a fixed development
key is used so nothing real is ever protected by it."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from ..domain.errors import AdapterError
from .config import Config

_DEV_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"wearables development key, not a secret").digest())


def _key(cfg: Config) -> bytes:
    if cfg.data_key:
        return cfg.data_key.encode()
    if cfg.mode == "mock":
        return _DEV_KEY
    raise AdapterError("not_configured", "WEARABLES_DATA_KEY is not set")


def _fernet(cfg: Config) -> Fernet:
    try:
        return Fernet(_key(cfg))
    except (ValueError, TypeError) as e:
        raise AdapterError("not_configured", "WEARABLES_DATA_KEY is not a valid Fernet key") from e


def seal(cfg: Config, value: str | None) -> str | None:
    return None if value is None else _fernet(cfg).encrypt(value.encode()).decode()


def unseal(cfg: Config, token: str | None) -> str | None:
    if token is None:
        return None
    try:
        return _fernet(cfg).decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise AdapterError("not_configured", "stored token cannot be decrypted with the current data key") from e
