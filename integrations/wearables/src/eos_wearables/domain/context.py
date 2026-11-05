"""What the hub passes to every operation and what every operation returns (contracts/ports/adapter.yaml)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .errors import AdapterError

MODES = ("mock", "sandbox", "live")


@dataclass
class Context:
    organisation_id: str
    connection_id: str
    provider: str
    mode: str | None = None  # None: the adapter's configured mode (WEARABLES_MODE)
    settings: dict[str, Any] = field(default_factory=dict)
    # Resolved from the secret store just before the call and alive for that call only: out of repr() so a
    # traceback, a log line or an assertion message never carries one.
    secrets: dict[str, str] = field(default_factory=dict, repr=False)
    account_link: dict | None = None
    delivery_id: str | None = None
    attempt: int = 1
    idempotency_key: str | None = None
    deadline: datetime | None = None

    @classmethod
    def coerce(cls, value: Context | dict) -> Context:
        if isinstance(value, Context):
            return value
        try:
            ctx = cls(**{k: v for k, v in dict(value).items() if k in cls.__dataclass_fields__})
        except (TypeError, ValueError) as e:
            raise AdapterError("invalid_request", "the call context is malformed") from e
        if not ctx.organisation_id or not ctx.connection_id or not ctx.provider:
            raise AdapterError("invalid_request", "the call context needs organisation_id, connection_id, provider")
        if ctx.mode is not None and ctx.mode not in MODES:
            raise AdapterError("invalid_request", "mode must be mock, sandbox or live")
        if not isinstance(ctx.settings, dict) or not isinstance(ctx.secrets, dict):
            raise AdapterError("invalid_request", "settings and secrets must be objects")
        return ctx


@dataclass
class Result:
    output: dict | None = None
    error: dict | None = None
    provider_reference: str | None = None

    @classmethod
    def failure(cls, e: AdapterError) -> Result:
        return cls(error=e.to_dict())

    def to_dict(self) -> dict:
        return {"output": self.output, "error": self.error, "provider_reference": self.provider_reference}
