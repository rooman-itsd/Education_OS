"""Client for the budget-grants API, reached over HTTP like any other module's API (a module never imports another).
The caller's own token is forwarded, so budget-grants applies its own permissions (budget-grants:availability:read for
GET /availability, budget-grants:budget:read for GET /expenditures)."""

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


class BudgetGrantsRefusedError(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(f"budget-grants refused the request ({status})")
        self.status = status


PAGE = 200  # the contract's largest page


def procurement_commitments(base_url: str, token: str, line_id: str) -> set[str]:
    """The purchase orders budget-grants has recorded a commitment for on a line: GET /expenditures?kind=commitment,
    every page, keeping the references of entries whose source is procurement (an issued order's commitment carries the
    order id; releases carry other references and are simply not order ids)."""
    if not base_url:
        raise BudgetGrantsNotConfiguredError("PROCUREMENT_BUDGET_GRANTS_URL is not set")
    references: set[str] = set()
    cursor: str | None = None
    with client_factory() as client:
        while True:
            params = {"line_id": line_id, "kind": "commitment", "limit": PAGE}
            if cursor:
                params["cursor"] = cursor
            r = client.get(f"{base_url}/expenditures", params=params, headers={"Authorization": f"Bearer {token}"})
            if r.status_code != 200:
                raise BudgetGrantsRefusedError(r.status_code)
            try:
                page = r.json()
                items, cursor = page["items"], page.get("next_cursor")
                for e in items:
                    if (e.get("source") or {}).get("module") == "procurement":
                        references.add(str((e.get("source") or {}).get("reference") or ""))
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                raise BudgetGrantsRefusedError(r.status_code) from e
            if not cursor:
                return references
