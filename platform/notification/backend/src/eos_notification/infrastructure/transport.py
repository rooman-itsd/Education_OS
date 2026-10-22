"""How a rendered message leaves the process.

Two transports. `memory` sends nothing and is the test and dev transport (it appends to eos_core.notify.sent,
which eos_testing reads); it is refused outside dev mode. `adapter` hands the message to an implementation of
the OutboundMessaging port (integrations/messaging-providers/contracts/port.yaml).

This module NEVER imports an adapter package. The port is the contract, and which implementation serves it is
configuration: an adapter advertises itself on the `eos.outbound_messaging` entry-point group and notification
loads the one named by NOTIFICATION_ADAPTER. That keeps "changing provider is configuration, not code" true,
and keeps notification inside its module boundary. Everything fails closed: anything unresolved is a 503
raised before a message row is written, never a silent fallback to something that does not deliver."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from importlib import metadata
from typing import Protocol

from eos_core import notify
from eos_core.settings import settings

from ..domain.errors import NotificationError
from .config import NotificationConfig

log = logging.getLogger("eos.notification")

# The only error codes ever stored in Message.last_error: never provider text, which may echo an address.
ERROR_CODES = frozenset(
    {
        "transport_unavailable",
        "transport_error",
        "rejected",
        "throttled",
        "invalid_recipient",
        "abandoned",
        "outcome_unknown",
        "secret_unavailable",
        "render_error",
        "template_unavailable",
        "recovery_exhausted",
    }
)


@dataclass
class OutboundMessage:
    """The OutboundMessaging port's `send` input. `metadata` is echoed back on provider receipts, so it must never
    carry a secret. `dev_secrets` is NOT part of the port: only the in-process memory transport reads it (so
    eos_testing can read a verification token); an adapter must never forward it. The body, address and
    dev_secrets are kept out of repr() so a stray log line cannot leak them.

    AdapterTransport below maps these fields one by one and never serialises this object whole (asdict would
    carry dev_secrets with it). The port has no dev_secrets field, so a provider cannot receive one."""

    message_id: str
    organisation_id: str
    channel: str
    to: str = field(repr=False)
    sender: str
    subject: str | None
    body: str = field(repr=False)
    metadata: dict = field(default_factory=dict)
    # Where replies go. Sent only when the organisation has a VERIFIED address and the provider advertises
    # support; otherwise the argument is omitted entirely (never passed as None), so an adapter that predates
    # reply_to keeps working. Stays None until the organisation-sender work lands.
    reply_to: str | None = None
    dev_secrets: dict = field(default_factory=dict, repr=False)


@dataclass
class SendResult:
    accepted: bool
    provider_message_id: str | None = None
    reason: str | None = None  # one of ERROR_CODES when not accepted
    retryable: bool = False
    retry_after_s: int | None = None


class Transport(Protocol):
    def send(self, message: OutboundMessage) -> SendResult: ...


class MemoryTransport:
    """Keeps the message in process memory and sends nothing. The rendered body, including any secret, sits in
    eos_core.notify.sent so eos_testing can read a verification token: acceptable only because this transport
    is refused outside dev mode (see get_transport)."""

    def send(self, message: OutboundMessage) -> SendResult:
        notify.sent.append(
            {
                "to": message.to,
                "subject": message.subject,
                "body": message.body,
                "organisation_id": message.organisation_id,
                "message_id": message.message_id,
                **message.metadata,
                **message.dev_secrets,
            }
        )
        if len(notify.sent) > 200:
            del notify.sent[:100]
        log.info("memory transport: message %s kept in process, not delivered", message.message_id)
        return SendResult(accepted=True, provider_message_id=f"memory:{message.message_id}")


ADAPTER_GROUP = "eos.outbound_messaging"
MAX_PROVIDER_MESSAGE_ID = 200  # Message.provider_message_id is String(200)


def _provider_message_id(value) -> str | None:
    """Only a string, cut to the column: an over-long id would fail the SENT update after the provider already
    accepted the message, and recovery would then send it again."""
    return value[:MAX_PROVIDER_MESSAGE_ID] if isinstance(value, str) and value else None


def _retry_after_s(value, max_delay_s: int) -> int | None:
    """A positive integer clamped to the recovery cap; anything else is None, so notification uses its own
    backoff instead of a retry in the past or a timestamp that overflows."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return min(value, max_delay_s)


def _supports_reply_to(provider) -> bool:
    """A provider that predates reply_to, or whose capabilities() fails, is treated as not supporting it."""
    try:
        return bool(getattr(provider.capabilities(), "supports_reply_to", False))
    except Exception as e:  # noqa: BLE001 - a broken capabilities() must not stop a send
        log.warning("adapter capabilities() raised %s; assuming no reply_to support", type(e).__name__)
        return False


class AdapterTransport:
    """An OutboundMessaging implementation, reached through the port and never imported by name.

    `factory` is the entry point's loaded callable: channel -> provider. It is called per message because one
    adapter may serve several channels, and because a channel with no provider must fail that message rather
    than the whole transport."""

    def __init__(self, factory, name: str = "", max_retry_delay_s: int = 3600) -> None:
        self._factory = factory
        self._name = name
        self._max_retry_delay_s = max_retry_delay_s

    def send(self, message: OutboundMessage) -> SendResult:
        try:
            provider = self._factory(message.channel)
        except Exception as e:  # noqa: BLE001 - the adapter's own exception types are not imported here
            # No provider for this channel: permanent for this message, not a transport outage.
            log.warning("adapter %s has no provider for channel %s (%s)", self._name, message.channel, type(e).__name__)
            return SendResult(accepted=False, reason="rejected", retryable=False)

        extra = {}
        if message.reply_to and _supports_reply_to(provider):
            extra["reply_to"] = message.reply_to  # omitted entirely when unsupported, never passed as None

        try:
            # Field by field. Never asdict(message): dev_secrets would travel with it, and the port has no
            # such field. dev_secrets is deliberately absent below.
            result = provider.send(
                message_id=message.message_id,
                organisation_id=message.organisation_id,
                channel=message.channel,
                to=message.to,
                sender=message.sender,
                subject=message.subject,
                body=message.body,
                metadata=dict(message.metadata),
                **extra,
            )
        except Exception as e:  # noqa: BLE001 - a provider must never take the process down
            log.warning("adapter %s raised %s on message %s", self._name, type(e).__name__, message.message_id)
            return SendResult(accepted=False, reason="transport_error", retryable=True)

        accepted = bool(getattr(result, "accepted", False))
        reason = getattr(result, "reason", None)
        if reason is not None and reason not in ERROR_CODES:
            # Never store something this module does not recognise: a provider's own text may echo an address.
            log.warning("adapter %s returned unknown reason %r; recording transport_error", self._name, reason)
            reason = "transport_error"
        return SendResult(
            accepted=accepted,
            provider_message_id=_provider_message_id(getattr(result, "provider_message_id", None))
            if accepted
            else None,
            reason=None if accepted else (reason or "transport_error"),
            retryable=bool(getattr(result, "retryable", False)),
            retry_after_s=_retry_after_s(getattr(result, "retry_after_s", None), self._max_retry_delay_s),
        )


def _load_adapter(config: NotificationConfig) -> Transport:
    """Resolve the configured adapter by entry point. Explicit by name: the first installed entry point is
    never chosen for the caller, because which provider sends an organisation's mail is not a detail to guess."""
    name = config.adapter
    if not name:
        raise NotificationError(503, "no messaging adapter configured: set NOTIFICATION_ADAPTER")
    try:
        points = list(metadata.entry_points(group=ADAPTER_GROUP))
    except Exception as e:  # noqa: BLE001 - a broken installation must read as unavailable, not crash
        log.warning("could not read %s entry points: %s", ADAPTER_GROUP, type(e).__name__)
        raise NotificationError(503, "messaging adapters could not be enumerated") from e

    matches = [ep for ep in points if ep.name == name]
    if not matches:
        available = sorted({ep.name for ep in points})
        detail = f"installed: {', '.join(available)}" if available else "none installed"
        raise NotificationError(503, f"messaging adapter '{name}' is not installed ({detail})")
    if len(matches) > 1:
        # Two distributions claiming one name: refuse rather than pick, or which one sends is a coin toss.
        raise NotificationError(503, f"messaging adapter '{name}' is provided by {len(matches)} distributions")

    try:
        factory = matches[0].load()
    except Exception as e:  # noqa: BLE001 - never surface an import error's text to a caller
        log.warning("messaging adapter %s failed to load: %s", name, type(e).__name__)
        raise NotificationError(503, f"messaging adapter '{name}' could not be loaded") from e
    if not callable(factory):
        raise NotificationError(503, f"messaging adapter '{name}' does not expose a callable")
    return AdapterTransport(factory, name, max_retry_delay_s=config.recovery_max_delay_s)


def get_transport(config: NotificationConfig | None = None) -> Transport:
    """Fail closed. 503 for anything that is not a transport this release can safely use."""
    config = config or NotificationConfig.from_env()
    if config.transport == "memory":
        if not settings.dev_mode:
            raise NotificationError(503, "memory transport is only allowed in dev mode")
        return MemoryTransport()
    if config.transport == "adapter":
        return _load_adapter(config)
    raise NotificationError(503, "unknown notification transport")
