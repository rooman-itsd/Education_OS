"""Tokens are stored encrypted: Fernet (AES-128-CBC with HMAC) with the key from WEARABLES_DATA_KEY.
Outside mock mode a missing or malformed key is a configuration error; in mock mode a fixed development
key is used so nothing real is ever protected by it.

Rotation: WEARABLES_DATA_KEY may hold several keys, comma-separated. The first encrypts; every one decrypts. Put the new
key first, deploy, and drop the old one once nothing sealed with it is left (a token is re-sealed whenever it is
refreshed). Without this a changed key makes every stored token unreadable, and with it every inbound confirmation."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from ..domain.errors import AdapterError
from .config import Config

_DEV_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"wearables development key, not a secret").digest())


def _keys(cfg: Config) -> list[bytes]:
    if cfg.data_key:
        keys = [k.strip().encode() for k in cfg.data_key.split(",") if k.strip()]
        if keys:
            return keys
    if cfg.mode == "mock":
        return [_DEV_KEY]
    raise AdapterError("not_configured", "WEARABLES_DATA_KEY is not set")


def _fernet(cfg: Config) -> MultiFernet:
    try:
        return MultiFernet([Fernet(k) for k in _keys(cfg)])
    except (ValueError, TypeError) as e:
        raise AdapterError("not_configured", "WEARABLES_DATA_KEY is not a valid Fernet key") from e


def require_key(cfg: Config) -> None:
    """Raise now if tokens could not be sealed. Called before a one-time code or a refresh token is spent at the
    provider, so a missing key cannot leave the athlete's only copy of a new token unstored."""
    _fernet(cfg)


def seal(cfg: Config, value: str | None) -> str | None:
    return None if value is None else _fernet(cfg).encrypt(value.encode()).decode()


def unseal(cfg: Config, token: str | None) -> str | None:
    if token is None:
        return None
    try:
        return _fernet(cfg).decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise AdapterError("not_configured", "stored token cannot be decrypted with the current data key") from e
