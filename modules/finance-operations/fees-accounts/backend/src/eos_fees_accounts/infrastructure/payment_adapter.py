"""Client for the payment adapter (integrations/payment-sbiepay), reached over HTTP like any other module's API. The
caller's own token is forwarded, so the adapter applies its own permissions (payer initiates, finance staff refund)."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

TIMEOUT_SECONDS = 15.0

# Replaced in tests with a client on httpx.MockTransport.
client_factory = lambda: httpx.Client(timeout=TIMEOUT_SECONDS)  # noqa: E731


class AdapterNotConfiguredError(Exception):
    pass


@dataclass(frozen=True)
class AdapterResponse:
    status: int
    body: dict


def _post(base_url: str, path: str, token: str, body: dict) -> AdapterResponse:
    if not base_url:
        raise AdapterNotConfiguredError("FEES_ACCOUNTS_PAYMENT_ADAPTER_URL is not set")
    with client_factory() as client:
        r = client.post(f"{base_url}{path}", json=body, headers={"Authorization": f"Bearer {token}"})
    try:
        data = r.json()
    except ValueError:
        data = {}
    return AdapterResponse(r.status_code, data if isinstance(data, dict) else {})


def start_payment(base_url: str, token: str, body: dict) -> AdapterResponse:
    """POST /payments. 201 is a new session; 409 carries the session of the payment already open for the invoice."""
    return _post(base_url, "/payments", token, body)


def refund(base_url: str, token: str, reference: str, amount: str, reason: str) -> AdapterResponse:
    """POST /payments/{reference}/refunds. 202 carries the adapter's refund with its status."""
    return _post(base_url, f"/payments/{reference}/refunds", token, {"amount": amount, "reason": reason})
