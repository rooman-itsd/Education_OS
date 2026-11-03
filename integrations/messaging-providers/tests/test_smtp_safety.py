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


# --- TLS: credentials never cross a network in clear (#316 audit M2, L1, L2) ------------------------------------


def _with(**changes) -> SmtpConfig:
    return SmtpConfig(**{**CONFIG.__dict__, **changes})


def test_credentials_to_a_remote_relay_without_tls_are_never_sent():
    remote = _with(host="smtp.relay.example.net", port=587, username="mailer", password="secret")
    connected = []
    p = SmtpEmailProvider(config=remote, client_factory=lambda c: connected.append(c) or FakeSmtp())
    result = p.send(**request())
    assert not result.accepted and result.reason == "transport_unavailable" and result.retryable
    assert connected == []  # refused before connecting, so the password never left the process
    health = p.healthcheck()
    assert not health.reachable and "without TLS" in health.detail


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1", "[::1]"])
def test_a_loopback_relay_may_take_credentials_without_tls(host):
    server = FakeSmtp()
    local = _with(host=host, username="mailer", password="secret")
    assert SmtpEmailProvider(config=local, client_factory=lambda _c: server).send(**request()).accepted
    assert server.logins == [("mailer", "secret")]


@pytest.mark.parametrize("tls", [{"use_tls": True}, {"use_ssl": True}])
def test_a_remote_relay_with_tls_takes_credentials(tls):
    server = FakeSmtp()
    remote = _with(host="smtp.relay.example.net", username="mailer", password="secret", **tls)
    assert SmtpEmailProvider(config=remote, client_factory=lambda _c: server).send(**request()).accepted
    assert server.logins == [("mailer", "secret")]


def test_starttls_and_implicit_tls_are_exclusive(monkeypatch):
    with pytest.raises(ValueError, match="exclusive"):
        _with(use_tls=True, use_ssl=True)
    monkeypatch.setenv("MESSAGING_PROVIDERS_SMTP_SSL", "true")
    monkeypatch.setenv("MESSAGING_PROVIDERS_SMTP_PORT", "465")
    config = SmtpConfig.from_env()
    assert config.use_ssl and not config.use_tls and config.port == 465 and "tls=ssl" in config.describe()


def test_implicit_tls_connects_with_smtp_ssl_and_a_verifying_context(monkeypatch):
    made = {}

    class FakeSsl(FakeSmtp):
        def __init__(self, host, port, timeout, context):
            super().__init__()
            made.update(host=host, port=port, context=context)

        def starttls(self, **kwargs):
            raise AssertionError("SMTP_SSL is already encrypted; no STARTTLS")

    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSsl)
    config = _with(host="smtp.relay.example.net", port=465, use_ssl=True, username="u", password="p")
    assert SmtpEmailProvider(config=config).send(**request()).accepted
    assert made["port"] == 465 and made["context"].verify_mode.name == "CERT_REQUIRED"


def test_a_failed_starttls_closes_the_connection(monkeypatch):
    closed = []

    class NoTls(FakeSmtp):
        def __init__(self, host, port, timeout):
            super().__init__()

        def starttls(self, **kwargs):
            raise smtplib.SMTPNotSupportedError("STARTTLS extension not supported by server.")

        def close(self):
            closed.append(True)

    monkeypatch.setattr(smtplib, "SMTP", NoTls)
    result = SmtpEmailProvider(config=_with(use_tls=True)).send(**request())
    assert not result.accepted and result.retryable and closed == [True]


def test_metadata_keys_must_be_header_names():
    server = FakeSmtp()
    bad = provider(server).send(**request(metadata={"x: injected\r\nBcc": "a@b.example"}))
    assert not bad.accepted and bad.reason == "rejected" and not bad.retryable and server.sent == []
    good = provider(server).send(**request(metadata={"Template": "verify"}))
    assert good.accepted and server.sent[-1]["X-EOS-Template"] == "verify"
