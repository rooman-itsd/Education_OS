"""The single error type the domain raises. `kind` says which of the contract's failure answers a rule matches, so the
API layer can map it without new decisions:

- "invalid": a value breaks a rule of contracts/openapi.yaml (period_end not after period_start, a missing
  submitted_on, comment or value); answered with 422
- "conflict": the status or state of the record does not allow the operation; answered with 409
- "forbidden": the caller holds a permission that does not cover this change; answered with 403

The codes are this module's own; the contract defines no error body.
"""

from __future__ import annotations

KINDS = ("invalid", "conflict", "forbidden")


class DomainRuleError(Exception):
    def __init__(self, code: str, message: str, *, kind: str, field: str | None = None) -> None:
        if kind not in KINDS:
            raise ValueError(f"unknown error kind {kind!r}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.kind = kind
        self.field = field
