"""The error a use case raises, with the HTTP status from contracts/openapi.yaml, so the API layer only has to render
it. The contract defines no error body; `body()` gives a code, a message and, when known, the field.

Domain error kinds map as follows:
- "conflict" -> 409: the request's status does not allow the operation, the appeal window is not configured, has
  passed or is still open, or the referral was already answered
- "invalid" -> 422: a value breaks a rule (grounds missing, a date in the future or before the step it follows)
"""

from __future__ import annotations

from ..domain.errors import DomainRuleError

STATUS_BY_KIND = {"conflict": 409, "invalid": 422}


class RtiError(Exception):
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


def from_domain(err: DomainRuleError) -> RtiError:
    """A domain rule refused a request value or a status move."""
    return RtiError(STATUS_BY_KIND[err.kind], err.code, err.message, field=err.field)
