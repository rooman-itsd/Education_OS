"""The secret store (docs/prd.md, "Credentials and the secret store"). Credentials and tokens live here, never in the
database: a connection row keeps only `secret://integration-hub/<organisation_id>/<connection_id>/<name>`, a
fingerprint and dates.

One small interface (`put`, `get`, `delete`, `rotate_kek`) and two backends, chosen by INTEGRATION_HUB_SECRET_BACKEND:

- `file` (default): one file per secret under INTEGRATION_HUB_SECRET_DIR, mode 0600 in 0700 directories, each value
  AES-256-GCM encrypted (`cryptography`) under INTEGRATION_HUB_SECRET_KEK, with the reference as associated data so a
  file copied to another name does not decrypt. INTEGRATION_HUB_SECRET_KEK_PREVIOUS still decrypts while a key is
  rotated; `rotate_kek()` re-encrypts every file under the current key.
- `env` (read only, development): values from environment variables named after the reference.

The same key encrypts the hub's other sensitive blobs (an async delivery's input kept for retries, a raw inbound body,
a PKCE verifier) through `Cipher`. Nothing here logs a value or puts one in an exception message."""

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from eos_core.settings import settings

from .config import HubConfig

log = logging.getLogger("eos.integration_hub")

REF_PREFIX = "secret://integration-hub/"
_SEGMENT = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_MAGIC = b"EH1"
_NONCE = 12
_KEY_ID = 8


class SecretStoreError(Exception):
    """The store cannot do what was asked (no key, read only, unreadable file). Never carries a value."""


def ref_for(*segments: str) -> str:
    for s in segments:
        if not _SEGMENT.match(s):
            raise SecretStoreError("invalid secret reference segment")
    return REF_PREFIX + "/".join(segments)


def _segments(ref: str) -> list[str]:
    if not isinstance(ref, str) or not ref.startswith(REF_PREFIX):
        raise SecretStoreError("not a secret reference")
    parts = ref[len(REF_PREFIX) :].split("/")
    if not parts or not all(_SEGMENT.match(p) for p in parts):
        raise SecretStoreError("invalid secret reference")
    return parts


def _parse_key(raw: str) -> bytes | None:
    if not raw:
        return None
    try:
        key = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        return None
    return key if len(key) == 32 else None


def _dev_key() -> bytes:
    """Development only: a key derived from the JWT secret, so a laptop works without setting a KEK. Outside dev mode
    a missing or malformed INTEGRATION_HUB_SECRET_KEK is refused instead (see Cipher.from_config)."""
    return hashlib.sha256(b"eos-integration-hub-dev-kek:" + settings.jwt_secret.encode()).digest()


@dataclass(frozen=True)
class Cipher:
    """AES-256-GCM under the current key, decrypting with the previous one while a rotation is in progress."""

    current: bytes
    previous: bytes | None = None

    @classmethod
    def from_config(cls, config: HubConfig) -> Cipher:
        current = _parse_key(config.secret_kek)
        if current is None:
            if not settings.dev_mode:
                raise SecretStoreError("INTEGRATION_HUB_SECRET_KEK must be 32 random bytes, base64 encoded")
            log.warning("INTEGRATION_HUB_SECRET_KEK is not set; using the development key (dev mode only)")
            current = _dev_key()
        return cls(current=current, previous=_parse_key(config.secret_kek_previous))

    def __repr__(self) -> str:  # never print a key
        return "Cipher(<keys hidden>)"

    @staticmethod
    def _key_id(key: bytes) -> bytes:
        return hashlib.sha256(key).digest()[:_KEY_ID]

    def encrypt(self, data: bytes, aad: str) -> bytes:
        nonce = os.urandom(_NONCE)
        sealed = AESGCM(self.current).encrypt(nonce, data, aad.encode())
        return _MAGIC + self._key_id(self.current) + nonce + sealed

    def decrypt(self, blob: bytes, aad: str) -> bytes:
        if not isinstance(blob, bytes | bytearray) or len(blob) < len(_MAGIC) + _KEY_ID + _NONCE + 16:
            raise SecretStoreError("encrypted value is malformed")
        if blob[: len(_MAGIC)] != _MAGIC:
            raise SecretStoreError("encrypted value is malformed")
        key_id = blob[len(_MAGIC) : len(_MAGIC) + _KEY_ID]
        nonce = blob[len(_MAGIC) + _KEY_ID : len(_MAGIC) + _KEY_ID + _NONCE]
        sealed = blob[len(_MAGIC) + _KEY_ID + _NONCE :]
        for key in (self.current, self.previous):
            if key is not None and self._key_id(key) == key_id:
                try:
                    return AESGCM(key).decrypt(nonce, bytes(sealed), aad.encode())
                except InvalidTag as e:
                    raise SecretStoreError("encrypted value does not verify") from e
        raise SecretStoreError("encrypted under a key this deployment does not hold")

    def needs_rotation(self, blob: bytes) -> bool:
        return blob[len(_MAGIC) : len(_MAGIC) + _KEY_ID] != self._key_id(self.current)


class SecretStore:
    """The interface every backend implements."""

    read_only = False

    def put(self, ref: str, value: str) -> None:
        raise NotImplementedError

    def get(self, ref: str) -> str | None:
        raise NotImplementedError

    def delete(self, ref: str) -> None:
        raise NotImplementedError

    def rotate_kek(self) -> int:
        return 0


class FileSecretStore(SecretStore):
    def __init__(self, directory: str, cipher: Cipher):
        if not directory:
            raise SecretStoreError("INTEGRATION_HUB_SECRET_DIR is not set")
        self._root = Path(directory)
        self._cipher = cipher

    def __repr__(self) -> str:
        return f"FileSecretStore({self._root})"

    def _path(self, ref: str) -> Path:
        parts = _segments(ref)
        return self._root.joinpath(*parts[:-1], parts[-1] + ".enc")

    def put(self, ref: str, value: str) -> None:
        if not isinstance(value, str):
            raise SecretStoreError("a secret value must be text")
        path = self._path(ref)
        try:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            tmp = path.with_name(f".{path.name}.{os.urandom(6).hex()}.tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                os.write(fd, self._cipher.encrypt(value.encode(), ref))
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(tmp, path)
        except OSError as e:
            raise SecretStoreError(f"secret store not writable ({type(e).__name__})") from e

    def get(self, ref: str) -> str | None:
        path = self._path(ref)
        try:
            blob = path.read_bytes()
        except FileNotFoundError:
            return None
        except OSError as e:
            raise SecretStoreError(f"secret store not readable ({type(e).__name__})") from e
        return self._cipher.decrypt(blob, ref).decode()

    def delete(self, ref: str) -> None:
        try:
            self._path(ref).unlink(missing_ok=True)
        except OSError as e:
            raise SecretStoreError(f"secret store not writable ({type(e).__name__})") from e

    def rotate_kek(self) -> int:
        """Re-encrypt every secret not yet under the current key. Idempotent; returns how many were rewritten."""
        rewritten = 0
        if not self._root.is_dir():
            return 0
        for path in sorted(self._root.rglob("*.enc")):
            rel = path.relative_to(self._root).with_suffix("")
            ref = REF_PREFIX + "/".join(rel.parts)
            blob = path.read_bytes()
            if self._cipher.needs_rotation(blob):
                self.put(ref, self._cipher.decrypt(blob, ref).decode())
                rewritten += 1
        return rewritten


class EnvSecretStore(SecretStore):
    """Read only, development: `secret://integration-hub/<org>/<conn>/<name>` is read from
    INTEGRATION_HUB_SECRET__<ORG>__<CONN>__<NAME>, with `-` turned into `_` and upper-cased."""

    read_only = True

    @staticmethod
    def env_name(ref: str) -> str:
        return "INTEGRATION_HUB_SECRET__" + "__".join(p.replace("-", "_").upper() for p in _segments(ref))

    def put(self, ref: str, value: str) -> None:
        raise SecretStoreError("the env secret backend is read only")

    def get(self, ref: str) -> str | None:
        return os.environ.get(self.env_name(ref))

    def delete(self, ref: str) -> None:
        raise SecretStoreError("the env secret backend is read only")


def get_store(config: HubConfig | None = None) -> SecretStore:
    config = config or HubConfig.from_env()
    if config.secret_backend == "file":
        return FileSecretStore(config.secret_dir, Cipher.from_config(config))
    if config.secret_backend == "env":
        if not settings.dev_mode:
            raise SecretStoreError("the env secret backend is for development only")
        return EnvSecretStore()
    raise SecretStoreError("unknown INTEGRATION_HUB_SECRET_BACKEND")


def get_cipher(config: HubConfig | None = None) -> Cipher:
    return Cipher.from_config(config or HubConfig.from_env())
