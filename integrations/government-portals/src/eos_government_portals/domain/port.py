"""The Adapter contract's context, result and error vocabulary (contracts/ports/adapter.yaml), as types.

A consuming module handles a failure the same way whoever the provider is, so `code` is always one of ERROR_CODES and
`detail` never carries personal data, a secret or a provider's own prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MODES = ("mock", "sandbox", "live")

# code -> retryable, exactly as adapter.yaml error_codes.
ERROR_CODES: dict[str, bool] = {
    "not_configured": False,
    "auth_failed": False,
    "consent_required": False,
    "invalid_request": False,
    "not_found": False,
    "conflict": False,
    "rejected": False,
    "unsupported": False,
    "manual_action_required": False,
    "throttled": True,
    "transport_unavailable": True,
    "provider_error": True,
}


@dataclass(frozen=True)
class Context:
    """What the hub passes to every operation (adapter.yaml, context). Secrets are never read: this adapter has none."""

    organisation_id: str
    connection_id: str | None = None
    provider: str = "aishe"
    mode: str = "mock"
    settings: dict[str, Any] = field(default_factory=dict)
    secrets: dict[str, str] = field(default_factory=dict, repr=False)
    account_link: dict | None = None
    delivery_id: str | None = None
    attempt: int = 1
    idempotency_key: str | None = None
    deadline: Any = None


@dataclass(frozen=True)
class PortError:
    code: str
    detail: str
    retryable: bool = False
    retry_after_s: int | None = None
    provider_code: str | None = None

    def __post_init__(self) -> None:
        if self.code not in ERROR_CODES:
            raise ValueError(f"unknown error code {self.code!r}")


@dataclass(frozen=True)
class Result:
    """Exactly one of output or error is set."""

    output: dict | None = None
    error: PortError | None = None
    provider_reference: str | None = None

    def __post_init__(self) -> None:
        if (self.output is None) == (self.error is None):
            raise ValueError("a result carries exactly one of output or error")

    @property
    def ok(self) -> bool:
        return self.error is None


def ok(output: dict, provider_reference: str | None = None) -> Result:
    return Result(output=output, provider_reference=provider_reference)


def fail(code: str, detail: str, **kw: Any) -> Result:
    return Result(error=PortError(code=code, detail=detail, retryable=ERROR_CODES[code], **kw))
