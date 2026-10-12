"""Signed server-to-server notifications to a caller's notify_url (PaymentNotification in contracts/openapi.yaml)."""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx

SIGNATURE_HEADER = "X-Payment-Signature"
TIMEOUT_SECONDS = 10.0

# Replaced in tests with a client on httpx.MockTransport.
client_factory = lambda: httpx.Client(timeout=TIMEOUT_SECONDS)  # noqa: E731


def encode(body: dict) -> bytes:
    """The exact bytes that are signed and sent."""
    return json.dumps(body, separators=(",", ":"), sort_keys=True).encode()


def sign(raw: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def verify_signature(raw: bytes, signature: str, secret: str) -> bool:
    """For receivers (billing, tests): constant-time comparison of the header against the raw body."""
    return bool(secret) and hmac.compare_digest(sign(raw, secret), signature or "")


def post(url: str, body: dict, secret: str) -> None:
    """Raises on any failure, including a non-2xx answer, so the caller can schedule a retry."""
    if not secret:
        raise RuntimeError("PAYMENT_SBIEPAY_NOTIFY_SECRET is not set; notifications cannot be signed")
    raw = encode(body)
    headers = {"Content-Type": "application/json", SIGNATURE_HEADER: sign(raw, secret)}
    with client_factory() as client:
        response = client.post(url, content=raw, headers=headers)
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"notify_url answered {response.status_code}")
