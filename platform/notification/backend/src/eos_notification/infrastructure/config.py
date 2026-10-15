"""Module-local configuration. Keys are NOTIFICATION_*, documented in config/env.example. Read from the
environment on every call so a test or a redeploy never sees a stale value."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..domain.models import CHANNELS


def _int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.environ.get(name, "")
    try:
        value = int(raw) if raw.strip() else default
    except ValueError:
        value = default
    return max(value, minimum)


@dataclass(frozen=True)
class NotificationConfig:
    transport: str
    adapter: str
    channels_enabled: tuple[str, ...]
    default_from_email: str
    default_from_name: str
    default_locale: str
    max_attempts: int
    retry_backoff_s: int
    sending_lease_s: int
    recovery_max_failures: int
    recovery_max_delay_s: int

    @classmethod
    def from_env(cls) -> NotificationConfig:
        channels = tuple(
            c
            for c in (s.strip() for s in os.environ.get("NOTIFICATION_CHANNELS_ENABLED", "email,in_app").split(","))
            if c in CHANNELS
        )
        return cls(
            transport=os.environ.get("NOTIFICATION_TRANSPORT", "memory").strip().lower(),
            # Which installed adapter implements the OutboundMessaging port. Resolved by entry point, so this
            # module never imports a provider package; see infrastructure/transport.py.
            adapter=os.environ.get("NOTIFICATION_ADAPTER", "messaging-providers").strip(),
            channels_enabled=channels or ("email",),
            default_from_email=os.environ.get("NOTIFICATION_DEFAULT_FROM_EMAIL", "no-reply@example.invalid"),
            default_from_name=os.environ.get("NOTIFICATION_DEFAULT_FROM_NAME", "Education OS"),
            default_locale=os.environ.get("NOTIFICATION_DEFAULT_LOCALE", "en").strip() or "en",
            max_attempts=_int("NOTIFICATION_MAX_ATTEMPTS", 5, minimum=1),
            retry_backoff_s=_int("NOTIFICATION_RETRY_BACKOFF_S", 30),
            # Must exceed the provider timeout, or a live sender is recovered and sent twice.
            sending_lease_s=_int("NOTIFICATION_SENDING_LEASE_S", 120, minimum=1),
            recovery_max_failures=_int("NOTIFICATION_RECOVERY_MAX_FAILURES", 5, minimum=1),
            recovery_max_delay_s=_int("NOTIFICATION_RECOVERY_MAX_DELAY_S", 3600, minimum=1),
        )
