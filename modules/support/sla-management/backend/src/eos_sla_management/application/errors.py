"""The error a use case raises, with the HTTP status from contracts/openapi.yaml, so the API layer only has to
render it. The contract defines no error body; `body()` gives a code, a message and, when known, the field.

Domain error kinds map as follows:
- "conflict" -> 409, the contract's answer for deactivating a calendar an active policy uses and for a second active
  policy for one priority and category
- "invalid" -> 422, the contract's answer for overlapping or reversed working intervals, an unknown time zone, a
  resolution target shorter than the response target, an inactive calendar and too many escalation levels, and
  FastAPI's for a request body that breaks the schema
"""

from __future__ import annotations

from ..domain.errors import DomainRuleError

STATUS_BY_KIND = {"conflict": 409, "invalid": 422}


class SlaManagementError(Exception):
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


def from_domain(err: DomainRuleError) -> SlaManagementError:
    """A domain rule refused a request value or a state change."""
    return SlaManagementError(STATUS_BY_KIND[err.kind], err.code, err.message, field=err.field)


def forbidden(message: str) -> SlaManagementError:
    """403: the caller lacks the permission the operation names."""
    return SlaManagementError(403, "forbidden", message)
