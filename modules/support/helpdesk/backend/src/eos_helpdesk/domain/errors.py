"""The single error type the domain raises. `kind` says which of the contract's failure answers a rule matches,
so the API layer can map it without new decisions:

- "invalid": a value breaks a schema constraint of contracts/openapi.yaml (an enum, a field that is required in
  some cases)
- "conflict": the ticket's status does not allow the operation; contracts/openapi.yaml answers these with 409

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
