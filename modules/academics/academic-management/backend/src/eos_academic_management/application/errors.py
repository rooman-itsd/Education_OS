"""The error every use case raises: an HTTP status and the contract's ErrorResponse body ({code, message, details})."""

from __future__ import annotations

from ..domain.errors import DomainRuleError

# Domain error kinds and the contract responses that declare them (contracts/openapi.yaml, components.responses).
STATUS_BY_KIND = {"invalid": 400, "not_found": 404, "conflict": 409, "unprocessable": 422}


class AcademicManagementError(Exception):
    """A refusal with an HTTP status and a contract error body."""

    def __init__(self, status: int, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details

    def body(self) -> dict:
        body: dict = {"code": self.code, "message": self.message}
        if self.details:
            body["details"] = self.details
        return body


def from_domain(err: DomainRuleError) -> AcademicManagementError:
    """The contract response for a broken domain rule; the offending field, when known, goes in `details`."""
    details = {"field": err.field} if err.field else {}
    return AcademicManagementError(STATUS_BY_KIND[err.kind], err.code, err.message, **details)


def forbidden(message: str) -> AcademicManagementError:
    return AcademicManagementError(403, "forbidden", message)


def not_found(code: str, message: str) -> AcademicManagementError:
    return AcademicManagementError(404, code, message)
