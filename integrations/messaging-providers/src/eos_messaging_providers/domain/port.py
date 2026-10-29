"""The OutboundMessaging port, version 1, exactly as contracts/port.yaml defines it.

These types are the whole vocabulary a provider sees. A caller cannot hand a provider anything that is not a
field below, which is how `dev_secrets` — notification's in-process carrier for a verification token — is kept
out of a provider payload by construction rather than by remembering to strip it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

# The only reasons a provider may give. notification stores these verbatim, so a provider's own text (which
# can echo an address) must never reach this field.
TRANSPORT_UNAVAILABLE = "transport_unavailable"  # provider unreachable; retryable
REJECTED = "rejected"  # provider refused the message; not retryable
THROTTLED = "throttled"  # rate limited; retryable after retry_after_s
INVALID_RECIPIENT = "invalid_recipient"  # malformed or refused address; not retryable
REASONS = frozenset({TRANSPORT_UNAVAILABLE, REJECTED, THROTTLED, INVALID_RECIPIENT})

CHANNELS = ("email", "sms", "whatsapp")


@dataclass(frozen=True)
class SendResult:
    """port.yaml -> operations.send.output."""

    accepted: bool
    provider_message_id: str | None = None
    reason: str | None = None
    retryable: bool = False
    retry_after_s: int | None = None

    def __post_init__(self) -> None:
        if self.reason is not None and self.reason not in REASONS:
            raise ValueError(f"reason must be one of {sorted(REASONS)}, not {self.reason!r}")
        if self.accepted and self.reason is not None:
            raise ValueError("an accepted message cannot carry a reason")


@dataclass(frozen=True)
class Capabilities:
    """port.yaml -> operations.capabilities.output."""

    channels: tuple[str, ...]
    max_body_bytes: int
    supports_attachments: bool
    supports_html: bool
    rate_limit_per_minute: int
    # notification probes for this before passing reply_to, and omits the argument entirely when it is false, so
    # a provider that predates reply_to keeps working. Defaults to false for the same reason.
    supports_reply_to: bool = False


@dataclass(frozen=True)
class Health:
    """port.yaml -> operations.healthcheck.output. Must never send a message."""

    reachable: bool
    detail: str = ""


class OutboundMessaging(Protocol):
    """Implemented by every provider adapter.

    `send` takes the port's fields as explicit keyword arguments and nothing else. That is deliberate: a caller
    that tries to pass an extra field (a secret, a whole dataclass) gets a TypeError instead of silently
    forwarding it to a provider.
    """

    def send(
        self,
        *,
        message_id: str,
        organisation_id: str,
        channel: str,
        to: str,
        sender: str,
        subject: str | None,
        body: str,
        body_html: str | None = None,
        attachments: list[dict] = ...,
        metadata: dict = ...,
        reply_to: str | None = None,
    ) -> SendResult: ...

    def capabilities(self) -> Capabilities: ...

    def healthcheck(self) -> Health: ...


@dataclass(frozen=True)
class Receipt:
    """port.yaml -> receipt. Inbound, normalised from a vendor webhook payload."""

    provider_message_id: str
    message_id: str
    status: str  # delivered | bounced | complained | failed
    detail: str = ""
    bounce_type: str | None = None  # hard | soft; None unless bounced
    occurred_at: str | None = None
    raw: dict = field(default_factory=dict, repr=False)
