"""The error a use case raises, with the HTTP status from contracts/openapi.yaml, so the API layer only renders it.
The contract defines no error body; `body()` gives a code, a message and, when known, the field."""

from __future__ import annotations

from ..domain.rules import RuleError

STATUS_BY_KIND = {"conflict": 409, "invalid": 422}


class ProcurementError(Exception):
    def __init__(self, status: int, code: str, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.field = status, code, message, field

    def body(self) -> dict[str, str]:
        body = {"code": self.code, "message": self.message}
        if self.field is not None:
            body["field"] = self.field
        return body


def from_rule(err: RuleError) -> ProcurementError:
    return ProcurementError(STATUS_BY_KIND[err.kind], err.code, err.message, field=err.field)


def not_found(what: str) -> ProcurementError:
    return ProcurementError(404, "not_found", f"{what} not found in your organisation")


def forbidden(message: str) -> ProcurementError:
    return ProcurementError(403, "forbidden", message)


def conflict(code: str, message: str) -> ProcurementError:
    return ProcurementError(409, code, message)


def invalid(code: str, message: str, field: str | None = None) -> ProcurementError:
    return ProcurementError(422, code, message, field=field)
