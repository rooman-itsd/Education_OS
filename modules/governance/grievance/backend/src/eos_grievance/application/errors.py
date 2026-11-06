"""The error a use case raises, with the HTTP status from contracts/openapi.yaml, so the API layer only has to render it.
The contract defines no error body; `body()` gives a code and a message.

Domain error kinds map as follows:
- "conflict" -> 409, the contract's answer for a refused status move, a case in a final state, a committee with open
  cases, a name already used and an appeal that cannot be made
- "invalid" -> 422, the contract's answer for a missing reason and for a committee that cannot take the case, and
  FastAPI's for a request that breaks the schema
"""

from __future__ import annotations

from ..domain.errors import DomainRuleError

STATUS_BY_KIND = {"conflict": 409, "invalid": 422}


class GrievanceError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def body(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def from_domain(err: DomainRuleError) -> GrievanceError:
    return GrievanceError(STATUS_BY_KIND[err.kind], err.code, err.message)


def forbidden(message: str) -> GrievanceError:
    """403: the caller lacks the permission the operation names, or is not on the committee that handles the case."""
    return GrievanceError(403, "forbidden", message)


def not_found(what: str) -> GrievanceError:
    return GrievanceError(404, "not_found", f"{what} not found")


def conflict(code: str, message: str) -> GrievanceError:
    return GrievanceError(409, code, message)


def invalid(code: str, message: str) -> GrievanceError:
    return GrievanceError(422, code, message)
