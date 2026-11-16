"""The error a use case raises, with the HTTP status from contracts/openapi.yaml, so the API layer only has to
render it. The contract defines no error body; `body()` gives a code, a message and, when known, the field.

Domain error kinds map as follows:
- "conflict" -> 409, the contract's answer for a duplicate period label, an inactive obligation, a refused status
  move and a change to a submitted or final filing
- "invalid" -> 422, the contract's answer for period_end before period_start, no owner and a missing comment or
  reason, and FastAPI's for a request that breaks the schema
"""

from __future__ import annotations

from ..domain.errors import DomainRuleError

STATUS_BY_KIND = {"conflict": 409, "invalid": 422}


class RegulatoryReportsError(Exception):
    def __init__(self, status: int, code: str, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.field = field

    def body(self) -> dict[str, str]:
        body = {"code": self.code, "message": self.message}
        if self.field is not None:
            body["field"] = self.field
        return body


def from_domain(err: DomainRuleError) -> RegulatoryReportsError:
    """A domain rule refused a request value or a status move."""
    return RegulatoryReportsError(STATUS_BY_KIND[err.kind], err.code, err.message, field=err.field)


def forbidden(message: str) -> RegulatoryReportsError:
    """403: the caller lacks the permission the operation names."""
    return RegulatoryReportsError(403, "forbidden", message)
