"""The error a use case raises, with the HTTP status from contracts/openapi.yaml, so the API layer only renders it.
The body is a code, a message and, when known, the field; it never repeats a submitted value."""

from __future__ import annotations

from ..domain.rules import RuleError

STATUS_BY_KIND = {"conflict": 409, "invalid": 422}


class PlacementError(Exception):
    def __init__(self, status: int, code: str, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.field = status, code, message, field

    def body(self) -> dict[str, str]:
        body = {"code": self.code, "message": self.message}
        if self.field is not None:
            body["field"] = self.field
        return body


def from_rule(err: RuleError) -> PlacementError:
    return PlacementError(STATUS_BY_KIND[err.kind], err.code, err.message, field=err.field)


def not_found(what: str) -> PlacementError:
    return PlacementError(404, "not_found", f"{what} not found in your organisation")


def conflict(code: str, message: str) -> PlacementError:
    return PlacementError(409, code, message)


def invalid(code: str, message: str, field: str | None = None) -> PlacementError:
    return PlacementError(422, code, message, field=field)
