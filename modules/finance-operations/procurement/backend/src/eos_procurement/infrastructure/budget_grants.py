"""Client for the budget-grants API, reached over HTTP like any other module's API (a module never imports another).
The caller's own token is forwarded, so budget-grants applies its own permission (budget-grants:availability:read)."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

TIMEOUT_SECONDS = 15.0

# Replaced in tests with a client on httpx.MockTransport.
client_factory = lambda: httpx.Client(timeout=TIMEOUT_SECONDS)  # noqa: E731


class BudgetGrantsNotConfiguredError(Exception):
    pass


@dataclass(frozen=True)
class Response:
    status: int
    body: dict


def availability(base_url: str, token: str, line_id: str, amount: str) -> Response:
    """GET /availability. 200 carries {line_id, available, sufficient}; 404 means the line is not in an approved
    budget or active grant of the caller's organisation."""
    if not base_url:
        raise BudgetGrantsNotConfiguredError("PROCUREMENT_BUDGET_GRANTS_URL is not set")
    with client_factory() as client:
        r = client.get(
            f"{base_url}/availability",
            params={"line_id": line_id, "amount": amount},
            headers={"Authorization": f"Bearer {token}"},
        )
    try:
        data = r.json()
    except ValueError:
        data = {}
    return Response(r.status_code, data if isinstance(data, dict) else {})
