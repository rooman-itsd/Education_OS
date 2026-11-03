"""Module-local configuration. Keys are MESSAGING_PROVIDERS_*, documented in config/env.example. Read from the
environment on every call so a test or a redeploy never sees a stale value.

Credentials live only in the environment. `password` is kept out of repr() and out of every log line, and
`describe()` is the only thing that may be logged or shown to an operator.
"""

from __future__ import annotations

import ipaddress
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
    use_ssl: bool = False  # implicit TLS from the first byte (SMTPS, usually port 465); exclusive with use_tls

    def __post_init__(self) -> None:
        if self.use_tls and self.use_ssl:
            raise ValueError(
                "MESSAGING_PROVIDERS_SMTP_USE_TLS and MESSAGING_PROVIDERS_SMTP_SSL are exclusive: pick one"
            )

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
            use_ssl=_bool("MESSAGING_PROVIDERS_SMTP_SSL", False),
        )

    @property
    def authenticated(self) -> bool:
        return bool(self.username and self.password)

    @property
    def encrypted(self) -> bool:
        return self.use_tls or self.use_ssl

    @property
    def loopback(self) -> bool:
        """A relay on this machine (a local MTA or a dev catcher): nothing crosses a network."""
        if self.host.lower() in {"localhost", "localhost.localdomain"}:
            return True
        try:
            return ipaddress.ip_address(self.host.strip("[]")).is_loopback
        except ValueError:
            return False

    @property
    def credentials_would_leak(self) -> bool:
        """Credentials configured, no TLS, and a remote host: logging in would send the password in clear."""
        return self.authenticated and not self.encrypted and not self.loopback

    def describe(self) -> str:
        """Safe to log: host and port only, and whether credentials are configured — never which."""
        tls = "ssl" if self.use_ssl else self.use_tls
        return f"smtp {self.host}:{self.port} tls={tls} auth={'yes' if self.authenticated else 'no'}"


def hourly_test_send_limit() -> int:
    """How many operator test sends the whole process allows in any hour. Zero turns test sends off."""
    return _int("MESSAGING_PROVIDERS_TEST_SEND_PER_HOUR", 10)
