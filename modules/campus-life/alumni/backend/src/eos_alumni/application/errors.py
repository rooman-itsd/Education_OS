"""The error a use case raises, with the HTTP status from contracts/openapi.yaml, so the API layer only renders it.
`body()` gives a code, a message and, when known, the field."""

from __future__ import annotations

from ..domain.rules import RuleError

STATUS_BY_KIND = {"conflict": 409, "invalid": 422}


class AlumniError(Exception):
    def __init__(self, status: int, code: str, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.field = status, code, message, field

    def body(self) -> dict[str, str]:
        body = {"code": self.code, "message": self.message}
        if self.field is not None:
            body["field"] = self.field
        return body


def from_rule(err: RuleError) -> AlumniError:
    return AlumniError(STATUS_BY_KIND[err.kind], err.code, err.message, field=err.field)


def not_found(what: str) -> AlumniError:
    return AlumniError(404, "not_found", f"{what} not found in your organisation")


def conflict(code: str, message: str) -> AlumniError:
    return AlumniError(409, code, message)
