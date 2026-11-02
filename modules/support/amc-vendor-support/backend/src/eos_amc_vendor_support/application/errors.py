"""The error a use case raises, with the HTTP status from contracts/openapi.yaml, so the API layer only has to
render it. The contract defines no error body; `body()` gives a code, a message and, when known, the field.

Domain error kinds map as follows:
- "conflict" -> 409, which the contract answers for every refused status move
- "invalid" -> 422, the contract's answer for end_date not after start_date, a missing note and a covered item of
  another contract, and FastAPI's for a request body that breaks the schema
"""

from __future__ import annotations

from ..domain.errors import DomainRuleError

STATUS_BY_KIND = {"conflict": 409, "invalid": 422}


class AmcVendorSupportError(Exception):
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


def from_domain(err: DomainRuleError) -> AmcVendorSupportError:
    """A domain rule refused a request value or a status move."""
    return AmcVendorSupportError(STATUS_BY_KIND[err.kind], err.code, err.message, field=err.field)


def forbidden(message: str) -> AmcVendorSupportError:
    """403: the caller lacks the permission the operation names."""
    return AmcVendorSupportError(403, "forbidden", message)
