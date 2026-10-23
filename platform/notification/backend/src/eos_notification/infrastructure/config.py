"""Module-local configuration. Keys are NOTIFICATION_*, documented in config/env.example. Read from the
environment on every call so a test or a redeploy never sees a stale value."""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass

from ..domain.models import CHANNELS

log = logging.getLogger("eos.notification")

# The largest NOTIFICATION_RECOVERY_MAX_DELAY_S this module will honour. An OPERATIONAL CEILING on one
# configured delay, not a promise that every message is delivered within a day: NOTIFICATION_MAX_ATTEMPTS
# bounds the attempts, and a message that exhausts them becomes `failed`.
#
# Safety needs the ceiling to be finite AND far below the point where the retry arithmetic breaks: _record()
# computes `now + timedelta(seconds=delay)`, which raises OverflowError once the delay exceeds
# `datetime.max - now` (about 251,609,673,599 seconds in late 2026, and one second less every second). A
# finite ceiling is not enough on its own -- 10**12 is finite and still overflows. 86400 is roughly 2.9
# million times below that threshold, so it stays safe for the life of the software, and 24x the default, so
# no realistic configuration is constrained by it. The overflow would otherwise be raised AFTER the claim is
# committed, stranding the message in `sending` until recovery picks it up.
MAX_RECOVERY_DELAY_S = 86_400

# The ceiling for NOTIFICATION_SENDING_LEASE_S. Deliberately its own constant, even though it holds the same
# number: a lease is not a retry delay, and nothing about the recovery policy should decide it. Both are
# bounded for the same mechanical reason -- each reaches datetime arithmetic -- but if either figure ever
# changes it should change alone.
#
# A lease must be LONGER than the provider call it protects, or a send still in progress loses its claim and
# recovery dispatches it again. That lower requirement cannot be enforced here: the provider timeout belongs
# to the adapter, which this module must not import (see infrastructure/transport.py), so the relationship is
# documented in README.md and config/env.example instead of being checked. The ceiling only rules out the
# absurd: it is the overflow guard, not the correctness guarantee.
MAX_SENDING_LEASE_S = 86_400

# Fields already reported, so this can never hold more entries than NotificationConfig has fields. The lock
# makes "once per field" a guarantee: without it two threads building a config at once could both log.
_warned_fields: set[str] = set()
_warn_lock = threading.Lock()


def _warn_once(field: str, given: int, used: int) -> None:
    """Exactly one line per configuration field for the life of the process, naming the field, the value given
    and the value used. Deduplicated because from_env() runs on request and dispatch paths, where warning on
    every call would be one line per message. Keyed on the field rather than the value, which is what bounds
    it -- and means a later, different out-of-range value for the same field is not reported again. Logged
    outside the lock so no I/O happens while it is held."""
    with _warn_lock:
        if field in _warned_fields:
            return
        _warned_fields.add(field)
    log.warning("notification config %s=%s is outside the permitted range; using %s", field, given, used)


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

    def __post_init__(self) -> None:
        """from_env() parses within bounds, but send_message(), dispatch() and recover_stuck() each accept an
        injected config and the dataclass can be built directly, so a bound enforced only in from_env() is not
        a bound. The invariant belongs to the object: below its floor a delay schedules a retry in the past,
        and above the ceiling it overflows next_attempt_at."""
        self._bound("recovery_max_delay_s", floor=1, ceiling=MAX_RECOVERY_DELAY_S)
        # No ceiling: _record() and recovery_delay() already cap the doubling against recovery_max_delay_s.
        # A negative value, reachable only by direct construction, would make min() pick the left operand and
        # schedule the next attempt in the past. Zero stays legal -- it means retry on the next sweep, which
        # is what NOTIFICATION_RETRY_BACKOFF_S=0 has always meant.
        self._bound("retry_backoff_s", floor=0, ceiling=None)
        # sending_lease_s goes straight into timestamp arithmetic with nothing between it and the clock:
        # _claim() does `now + timedelta(seconds=...)` and recover_stuck() does `now - timedelta(seconds=...)`.
        # Neither is capped the way a retry delay is, and the subtraction is the tighter of the two -- from
        # 2026 it underflows above about 63,928,224,000 seconds, while the addition survives to roughly
        # 251,609,673,599. The same ceiling is reused rather than inventing a second number: a lease longer
        # than the longest recovery wait would leave a message stuck in `sending` for longer than the recovery
        # policy's own maximum, which is incoherent. The lease must exceed the provider call it protects --
        # seconds, not days -- so the ceiling is far above any sane value and only rules out the absurd.
        self._bound("sending_lease_s", floor=1, ceiling=MAX_SENDING_LEASE_S)

    def _bound(self, field: str, *, floor: int, ceiling: int | None) -> None:
        """Clamp an integer that is out of range; refuse anything that is not an integer.

        The two cases differ in kind. An operator typing a silly number is misconfiguration, and clamping with
        a warning keeps the service running -- the same tolerance _int() shows by falling back to a default on
        unparseable text. A caller passing a bool, string or float is a bug in that caller's code and must not
        be absorbed: min(True, 86400) is 1, so a bool would quietly become a one-second delay, and
        min("60", 86400) raises a TypeError about comparison that names neither the field nor the mistake.
        bool is tested before int because isinstance(True, int) is True -- the same reason _retry_after() tests
        it first."""
        given = getattr(self, field)
        if isinstance(given, bool) or not isinstance(given, int):
            raise TypeError(f"{field} must be an int, not {type(given).__name__}: {given!r}")
        used = max(floor, given if ceiling is None else min(given, ceiling))
        if used != given:
            _warn_once(field, given, used)
            object.__setattr__(self, field, used)  # frozen: the only way to normalise in __post_init__

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
