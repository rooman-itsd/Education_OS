"""A fake SMTP server good enough to prove the adapter's behaviour, and a valid port-shaped request.

Kept out of conftest.py so test files can import them by a name no other module uses. `from conftest import`
resolves to whichever conftest pytest loaded last, which in CI's single combined run is another module's.

The fake records what was handed to it so a test can assert on the exact message, and can be told to raise any
smtplib exception so every error branch is exercised without a server that misbehaves on demand.
"""

from __future__ import annotations

from eos_messaging_providers.infrastructure.config import SmtpConfig

CONFIG = SmtpConfig(
    host="localhost",
    port=1025,
    username="",
    password="",
    use_tls=False,
    timeout_s=5,
    from_email="no-reply@example.invalid",
    from_name="Education OS",
)


class FakeSmtp:
    """Stands in for smtplib.SMTP. Used as a context manager, exactly as the adapter uses the real one."""

    def __init__(self, raise_on_send=None, raise_on_login=None):
        self.raise_on_send = raise_on_send
        self.raise_on_login = raise_on_login
        self.sent: list = []
        self.logins: list[tuple[str, str]] = []
        self.noops = 0
        self.quit_called = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.quit_called = True
        return False

    def login(self, username, password):
        self.logins.append((username, password))
        if self.raise_on_login:
            raise self.raise_on_login

    def send_message(self, message):
        if self.raise_on_send:
            raise self.raise_on_send
        self.sent.append(message)

    def noop(self):
        self.noops += 1


def request(**overrides) -> dict:
    """A complete, valid port-shaped send(). Tests override one field at a time."""
    body = dict(
        message_id="11111111-1111-1111-1111-111111111111",
        organisation_id="22222222-2222-2222-2222-222222222222",
        channel="email",
        to="person@college.example.com",
        sender="Education OS <no-reply@example.invalid>",
        subject="Verify your Education OS organisation",
        body="Welcome to Rooman. Verify with token abc123",
    )
    body.update(overrides)
    return body
