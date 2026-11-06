"""Rotating the key-encryption key (README, "Rotating the key"). One key encrypts two kinds of data: the secret
store's files (credentials and tokens) and the hub's encrypted columns (an async delivery's input kept for retries, a
raw inbound callback, a PKCE verifier). Rotation re-encrypts both under INTEGRATION_HUB_SECRET_KEK, decrypting with
INTEGRATION_HUB_SECRET_KEK_PREVIOUS, so the previous key can be removed afterwards and everything still reads.

Idempotent: only what is not yet under the current key is rewritten, so it can be run again after an interruption.
Run it once after setting the new key and keeping the old one as _PREVIOUS:

    python -m eos_integration_hub.rotate_kek

Nothing is logged but counts."""

from __future__ import annotations

import logging
from collections.abc import Callable

from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from sqlalchemy import select

from ..infrastructure.config import HubConfig
from ..infrastructure.models import Delivery, InboundReceipt, OAuthState
from ..infrastructure.secrets import Cipher, SecretStoreError, get_cipher, get_store

log = logging.getLogger("eos.integration_hub")

BATCH = 500

# (what, model, column, the associated data each blob was sealed with)
COLUMNS: list[tuple[str, type, str, Callable]] = [
    ("delivery_inputs", Delivery, "payload_encrypted", lambda r: r.id),
    ("inbound_raw", InboundReceipt, "raw_encrypted", lambda r: f"inbound:{r.id}"),
    ("oauth_verifiers", OAuthState, "code_verifier_encrypted", lambda r: r.state_hash),
]


def _rotate_column(cipher: Cipher, model, column: str, aad: Callable) -> tuple[int, int]:
    """(rewritten, unreadable) for one column, in batches, each in its own transaction."""
    rewritten = unreadable = 0
    last_id = ""
    with platform_scope(), SessionLocal() as db:
        while True:
            rows = list(
                db.scalars(
                    select(model)
                    .where(getattr(model, column).is_not(None), model.id > last_id)
                    .order_by(model.id)
                    .limit(BATCH)
                )
            )
            if not rows:
                break
            for row in rows:
                blob = getattr(row, column)
                if not cipher.needs_rotation(blob):
                    continue
                try:
                    plain = cipher.decrypt(blob, aad(row))
                except SecretStoreError:
                    unreadable += 1  # under a key this deployment no longer holds; left as is
                    continue
                setattr(row, column, cipher.encrypt(plain, aad(row)))
                rewritten += 1
            last_id = rows[-1].id
            db.commit()
    return rewritten, unreadable


def rotate_kek(config: HubConfig | None = None) -> dict[str, int]:
    """Re-encrypt the secret store and every encrypted column under the current key. Returns counts per kind, and
    `unreadable`: blobs neither key opens (they stay unreadable; remove _PREVIOUS only when it is 0)."""
    config = config or HubConfig.from_env()
    cipher = get_cipher(config)
    out = {"secrets": get_store(config).rotate_kek(), "unreadable": 0}
    for what, model, column, aad in COLUMNS:
        rewritten, unreadable = _rotate_column(cipher, model, column, aad)
        out[what] = rewritten
        out["unreadable"] += unreadable
    log.info("integration-hub key rotation: %s", out)
    return out
