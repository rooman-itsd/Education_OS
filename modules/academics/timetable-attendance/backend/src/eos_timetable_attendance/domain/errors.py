"""The single error type the domain raises. `kind` follows the meanings of the contract's error responses
(contracts/openapi.yaml, components.responses), so the API layer can map it without new decisions:

- "invalid": a value breaks a schema constraint (enum, format, required reason) -> BadRequest (400)
- "conflict": an invalid transition or a clash with current state -> Conflict (409)
- "unprocessable": a well-formed request breaks a domain rule -> Unprocessable (422)
- "not_found": the resource the rule needs is not there -> NotFound (404)
"""

from __future__ import annotations

KINDS = ("invalid", "conflict", "unprocessable", "not_found")


class DomainRuleError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        kind: str,
        field: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        if kind not in KINDS:
            raise ValueError(f"unknown error kind {kind!r}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.kind = kind
        self.field = field
        self.details = details or {}
