"""The single error type the domain raises. `kind` says which of the contract's failure answers a rule matches, so the
API layer can map it without new decisions:

- "invalid": a value breaks a rule of contracts/openapi.yaml (grounds missing, a date in the future, an appeal dated
  before the response); answered with 422
- "conflict": the request's status or the module's settings do not allow the operation; answered with 409

The codes are this module's own; the contract defines no error body.
"""

from __future__ import annotations

KINDS = ("invalid", "conflict")


class DomainRuleError(Exception):
    def __init__(self, code: str, message: str, *, kind: str, field: str | None = None) -> None:
        if kind not in KINDS:
            raise ValueError(f"unknown error kind {kind!r}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.kind = kind
        self.field = field


def invalid(code: str, message: str, field: str | None = None) -> DomainRuleError:
    return DomainRuleError(code, message, kind="invalid", field=field)


def conflict(code: str, message: str, field: str | None = None) -> DomainRuleError:
    return DomainRuleError(code, message, kind="conflict", field=field)
