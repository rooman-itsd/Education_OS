"""Module-local configuration. Keys are MESSAGING_PROVIDERS_*, documented in config/env.example. Read from the
environment on every call so a test or a redeploy never sees a stale value.

Credentials live only in the environment. `password` is kept out of repr() and out of every log line, and
`describe()` is the only thing that may be logged or shown to an operator.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.environ.get(name, "")
    try:
        value = int(raw) if raw.strip() else default
    except ValueError:
        value = default
    return max(value, minimum)


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    return default if not raw else raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    username: str
    password: str = field(repr=False)  # never in a traceback, a log line or an error message
    use_tls: bool
    timeout_s: int
    from_email: str
    from_name: str

    @classmethod
    def from_env(cls) -> SmtpConfig:
        return cls(
            host=os.environ.get("MESSAGING_PROVIDERS_SMTP_HOST", "localhost").strip(),
            port=_int("MESSAGING_PROVIDERS_SMTP_PORT", 1025, minimum=1),
            username=os.environ.get("MESSAGING_PROVIDERS_SMTP_USERNAME", "").strip(),
            password=os.environ.get("MESSAGING_PROVIDERS_SMTP_PASSWORD", ""),
            use_tls=_bool("MESSAGING_PROVIDERS_SMTP_USE_TLS", False),
            timeout_s=_int("MESSAGING_PROVIDERS_SMTP_TIMEOUT_S", 10, minimum=1),
            from_email=os.environ.get("MESSAGING_PROVIDERS_FROM_EMAIL", "no-reply@example.invalid").strip(),
            from_name=os.environ.get("MESSAGING_PROVIDERS_FROM_NAME", "Education OS").strip(),
        )

    @property
    def authenticated(self) -> bool:
        return bool(self.username and self.password)

    def describe(self) -> str:
        """Safe to log: host and port only, and whether credentials are configured — never which."""
        return f"smtp {self.host}:{self.port} tls={self.use_tls} auth={'yes' if self.authenticated else 'no'}"


def hourly_test_send_limit() -> int:
    """How many operator test sends the whole process allows in any hour. Zero turns test sends off."""
    return _int("MESSAGING_PROVIDERS_TEST_SEND_PER_HOUR", 10)
