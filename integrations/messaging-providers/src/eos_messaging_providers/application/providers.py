"""The operator view behind contracts/openapi.yaml: which providers exist, whether they are reachable, and a
rate-limited test send. Ordinary sending is not done here; callers use the OutboundMessaging port.

The state here is process-local, on purpose and with its limits stated. This module has no tables, so the last
health result and the test-send counter live in memory: they reset on restart and belong to one process, not the
deployment. For the counter that means N workers allow N times the hourly limit. That is acceptable for a
super-admin-only endpoint whose only job is "this cannot be used to send mail"; a limit shared across workers
needs a store this module does not have yet.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from datetime import UTC, datetime

from ..infrastructure.config import hourly_test_send_limit
from . import registry
from .registry import ProviderUnavailableError

# The record of every test send until platform/audit exists: who, which provider, the message id and the
# outcome. Never the address: an operator's test address is still personal data.
audit_log = logging.getLogger("eos.messaging_providers.audit")

# Provider credentials are platform-level, so a test send belongs to no organisation. The port types
# organisation_id as a uuid; the nil uuid stands for the platform itself.
PLATFORM = "00000000-0000-0000-0000-000000000000"
TEST_SUBJECT = "Education OS test message"
TEST_BODY = "This is a test message from Education OS, sent by a platform operator to check that email is delivered."
WINDOW_S = 3600


class OperatorError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class _Window:
    """A sliding one-hour window of send times, shared by every caller in the process."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._sent: deque[float] = deque()
        self._lock = threading.Lock()

    def take(self, limit: int) -> bool:
        """Claim one send if fewer than `limit` happened in the last hour. A limit of zero refuses everything."""
        with self._lock:
            now = self._clock()
            while self._sent and now - self._sent[0] >= WINDOW_S:
                self._sent.popleft()
            if len(self._sent) >= limit:
                return False
            self._sent.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._sent.clear()


test_sends = _Window()
_last_health: dict[str, dict] = {}
_health_lock = threading.Lock()


def _provider(provider_id: str):
    try:
        return registry.get_provider_by_id(provider_id)
    except ProviderUnavailableError:
        raise OperatorError(404, "no such provider") from None


def list_providers() -> dict:
    """Every provider this release can build, with what it supports. Never a host, a username or a credential:
    capabilities() carries none, and nothing else about the provider is read."""
    items = []
    for provider_id, channel in registry.implemented():
        _channel, provider = registry.get_provider_by_id(provider_id)
        caps = provider.capabilities()
        with _health_lock:
            last = _last_health.get(provider_id)
        items.append(
            {
                "id": provider_id,
                "channel": channel,
                "enabled": registry.selected(channel) == provider_id,
                "capabilities": {
                    "max_body_bytes": caps.max_body_bytes,
                    "supports_attachments": caps.supports_attachments,
                    "supports_html": caps.supports_html,
                    "rate_limit_per_minute": caps.rate_limit_per_minute,
                    "supports_reply_to": caps.supports_reply_to,
                },
                "last_health": dict(last) if last else None,
            }
        )
    return {"items": items}


def check_health(provider_id: str) -> dict:
    """The port's healthcheck, which never sends a message. The result is kept so the list can show it."""
    _channel, provider = _provider(provider_id)
    health = provider.healthcheck()
    checked_at = datetime.now(UTC).isoformat()
    with _health_lock:
        _last_health[provider_id] = {"reachable": health.reachable, "checked_at": checked_at}
    return {"reachable": health.reachable, "detail": health.detail, "checked_at": checked_at}


def send_test(provider_id: str, *, to: str, actor: str) -> dict:
    """One real message to an address the operator names. The provider is checked before the limit, so asking
    for one that does not exist does not use up a send. Every attempt counts, refused or not, so the endpoint
    cannot be used to probe addresses faster than the limit either."""
    channel, provider = _provider(provider_id)
    limit = hourly_test_send_limit()
    if not test_sends.take(limit):
        audit_log.warning("test send refused by the hourly limit: actor=%s provider=%s", actor, provider_id)
        raise OperatorError(429, f"test send limit reached: at most {limit} an hour")
    message_id = str(uuid.uuid4())
    result = provider.send(
        message_id=message_id,
        organisation_id=PLATFORM,
        channel=channel,
        to=to,
        sender="",  # the provider's configured sending identity, which is what the test is meant to prove
        subject=TEST_SUBJECT,
        body=TEST_BODY,
    )
    audit_log.info(
        "test send: actor=%s provider=%s message=%s accepted=%s reason=%s",
        actor,
        provider_id,
        message_id,
        result.accepted,
        result.reason,
    )
    return {"accepted": result.accepted, "provider_message_id": result.provider_message_id, "reason": result.reason}
