"""The single error type the domain raises. `kind` says which of the contract's failure answers a rule matches, so the
API layer can map it without new decisions:

- "invalid": a value breaks a rule of contracts/openapi.yaml (reason missing); answered with 422
- "conflict": the case's status or the committee's state does not allow the operation; answered with 409
"""

from __future__ import annotations

KINDS = ("invalid", "conflict")


class DomainRuleError(Exception):
    def __init__(self, code: str, message: str, *, kind: str) -> None:
        if kind not in KINDS:
            raise ValueError(f"unknown error kind {kind!r}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.kind = kind
