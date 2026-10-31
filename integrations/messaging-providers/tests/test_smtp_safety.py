"""The safety properties: no secret or personal data in a log line, no credential anywhere it can escape, and
no way for notification's `dev_secrets` to reach a provider payload.

These are the tests that justify calling this a production adapter rather than a demo.
"""

from __future__ import annotations

import logging
import smtplib

import pytest
from eos_messaging_providers.infrastructure.config import SmtpConfig
from eos_messaging_providers.infrastructure.smtp import SmtpEmailProvider
from smtp_support import CONFIG, FakeSmtp, request

SECRET_BODY = "Welcome to Rooman. Verify with token SUPER-SECRET-TOKEN-9999"
ADDRESS = "person@college.example.com"


def provider(server, config=CONFIG) -> SmtpEmailProvider:
    return SmtpEmailProvider(config=config, client_factory=lambda _c: server)


# --- dev_secrets can never be forwarded ----------------------------------------------------------------


def test_send_refuses_unknown_fields_so_dev_secrets_cannot_be_forwarded(smtp):
    """notification's OutboundMessage carries `dev_secrets`, an in-process-only carrier for a verification
    token. The port has no such field. send() takes named parameters and no **kwargs, so passing it is a
    TypeError at the boundary rather than a secret quietly reaching a provider."""
    server, _ = smtp
    with pytest.raises(TypeError):
        provider(server).send(**request(), dev_secrets={"token": "SUPER-SECRET-TOKEN-9999"})
    assert server.sent == []


def test_send_refuses_a_whole_object_so_a_dataclass_cannot_be_splatted_in(smtp):
    """The other half of the same rule: an adapter must map fields one by one and never serialise
    notification's object whole (asdict would carry dev_secrets with it)."""
    server, _ = smtp
    with pytest.raises(TypeError):
        provider(server).send(request())  # positional: send() is keyword-only


# --- logging carries no personal data and no secret ----------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [None, smtplib.SMTPRecipientsRefused({ADDRESS: (550, b"no mailbox for person@college.example.com")})],
)
def test_no_log_line_contains_the_body_the_address_or_the_subject(error, caplog):
    server = FakeSmtp(raise_on_send=error)
    with caplog.at_level(logging.DEBUG, logger="eos.messaging_providers.smtp"):
        provider(server).send(**request(to=ADDRESS, body=SECRET_BODY))
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert logged, "the adapter must say something about every send"
    assert "SUPER-SECRET-TOKEN-9999" not in logged
    assert ADDRESS not in logged
    assert "Verify your Education OS organisation" not in logged
    assert "11111111-1111-1111-1111-111111111111" in logged  # the id IS logged, so it can be traced


def test_a_provider_error_text_is_never_passed_on_as_the_reason(caplog):
    """SMTP error text routinely echoes the address. Only the four port codes leave this module."""
    refused = smtplib.SMTPRecipientsRefused({ADDRESS: (550, b"no mailbox for person@college.example.com")})
    with caplog.at_level(logging.DEBUG, logger="eos.messaging_providers.smtp"):
        result = provider(FakeSmtp(raise_on_send=refused)).send(**request(to=ADDRESS))
    assert result.reason == "invalid_recipient"
    assert ADDRESS not in (result.reason or "")
    assert ADDRESS not in "\n".join(r.getMessage() for r in caplog.records)


# --- credentials ---------------------------------------------------------------------------------------


def test_the_password_is_not_in_repr_or_in_any_log_line(caplog):
    authed = SmtpConfig(**{**CONFIG.__dict__, "username": "mailer", "password": "hunter2-real-password"})
    assert "hunter2-real-password" not in repr(authed)
    assert "hunter2-real-password" not in authed.describe()
    assert authed.describe() == "smtp localhost:1025 tls=False auth=yes"

    failure = smtplib.SMTPAuthenticationError(535, b"5.7.8 authentication failed for mailer")
    with caplog.at_level(logging.DEBUG, logger="eos.messaging_providers.smtp"):
        result = provider(FakeSmtp(raise_on_login=failure), config=authed).send(**request())
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "hunter2-real-password" not in logged and "mailer" not in logged
    assert result.reason == "transport_unavailable" and result.retryable


def test_credentials_come_only_from_the_environment(monkeypatch):
    for key, value in {
        "MESSAGING_PROVIDERS_SMTP_HOST": "relay.example.net",
        "MESSAGING_PROVIDERS_SMTP_PORT": "587",
        "MESSAGING_PROVIDERS_SMTP_USERNAME": "mailer",
        "MESSAGING_PROVIDERS_SMTP_PASSWORD": "from-the-environment",
        "MESSAGING_PROVIDERS_SMTP_USE_TLS": "true",
    }.items():
        monkeypatch.setenv(key, value)
    config = SmtpConfig.from_env()
    assert config.host == "relay.example.net" and config.port == 587 and config.use_tls
    assert config.authenticated and config.password == "from-the-environment"
    assert "from-the-environment" not in repr(config)


def test_no_credential_is_committed_in_the_example_config():
    """config/env.example must stay fake: team rule 10."""
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "config" / "env.example").read_text()
    assert "MESSAGING_PROVIDERS_SMTP_PASSWORD=\n" in text or "MESSAGING_PROVIDERS_SMTP_PASSWORD=" in text
    for line in text.splitlines():
        if line.startswith("MESSAGING_PROVIDERS_SMTP_PASSWORD="):
            assert line.split("=", 1)[1].strip() == "", "a real password must never be committed"


# --- healthcheck ---------------------------------------------------------------------------------------


def test_healthcheck_does_not_send_a_message(smtp):
    server, _ = smtp
    health = provider(server).healthcheck()
    assert health.reachable and server.noops == 1 and server.sent == []


def test_healthcheck_reports_unreachable_without_leaking_detail():
    server = FakeSmtp()
    server.noop = lambda: (_ for _ in ()).throw(smtplib.SMTPServerDisconnected("closed by relay.example.net"))
    health = provider(server).healthcheck()
    assert not health.reachable and "relay.example.net" not in health.detail
