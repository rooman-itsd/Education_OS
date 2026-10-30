"""Success and every provider-error branch of the SMTP adapter."""

from __future__ import annotations

import smtplib

import pytest
from eos_messaging_providers.domain.port import (
    INVALID_RECIPIENT,
    REJECTED,
    THROTTLED,
    TRANSPORT_UNAVAILABLE,
)
from eos_messaging_providers.infrastructure.smtp import SmtpEmailProvider
from smtp_support import CONFIG, FakeSmtp, request


def provider(server: FakeSmtp) -> SmtpEmailProvider:
    return SmtpEmailProvider(config=CONFIG, client_factory=lambda _c: server)


# --- success -------------------------------------------------------------------------------------------


def test_a_message_is_accepted_and_carries_a_provider_message_id(smtp):
    server, _ = smtp
    result = provider(server).send(**request())
    assert result.accepted and result.reason is None and not result.retryable
    assert result.provider_message_id and result.provider_message_id.startswith("<")
    assert len(server.sent) == 1


def test_the_built_message_has_the_addresses_subject_and_body_it_was_given(smtp):
    server, _ = smtp
    provider(server).send(**request())
    sent = server.sent[0]
    assert sent["To"] == "person@college.example.com"
    assert sent["Subject"] == "Verify your Education OS organisation"
    assert sent["X-EOS-Message-Id"] == "11111111-1111-1111-1111-111111111111"
    assert "Verify with token abc123" in sent.get_content()


def test_metadata_is_echoed_as_headers_so_a_receipt_can_be_correlated(smtp):
    server, _ = smtp
    provider(server).send(**request(metadata={"template": "tenancy.organisation.verify"}))
    assert server.sent[0]["X-EOS-template"] == "tenancy.organisation.verify"


def test_an_html_alternative_is_added_when_given(smtp):
    server, _ = smtp
    provider(server).send(**request(body_html="<p>hello</p>"))
    assert server.sent[0].is_multipart()


def test_reply_to_is_written_as_a_header_when_given(smtp):
    server, _ = smtp
    provider(server).send(**request(reply_to="office@college.example.com"))
    assert server.sent[0]["Reply-To"] == "office@college.example.com"


def test_no_reply_to_header_when_none_is_given(smtp):
    server, _ = smtp
    provider(server).send(**request())
    assert server.sent[0]["Reply-To"] is None


def test_capabilities_advertise_reply_to_because_notification_probes_for_it():
    """notification's AdapterTransport reads this with getattr(..., "supports_reply_to", False) and omits reply_to
    entirely when it is false, so without the field reply_to would silently never reach a provider."""
    assert provider(FakeSmtp()).capabilities().supports_reply_to is True


@pytest.mark.parametrize(
    "field, value, reason",
    [
        ("to", "person@college.example.com\r\nBcc: someone@else.example", INVALID_RECIPIENT),
        ("reply_to", "office@college.example.com\r\nBcc: someone@else.example", REJECTED),
        ("subject", "Verify\nBcc: someone@else.example", REJECTED),
    ],
)
def test_a_line_break_in_a_header_is_refused_for_good_and_injects_nothing(smtp, field, value, reason):
    """Not raised: notification would read an exception as a transport error and retry a message that can never
    be built. A broken recipient is that recipient's fault; any other broken header is ours."""
    server, _ = smtp
    result = provider(server).send(**request(**{field: value}))
    assert not result.accepted and result.reason == reason and not result.retryable
    assert server.sent == []


def test_credentials_are_used_only_when_both_are_configured(smtp):
    server, _ = smtp
    authed = CONFIG.__class__(**{**CONFIG.__dict__, "username": "u", "password": "p"})
    SmtpEmailProvider(config=authed, client_factory=lambda _c: server).send(**request())
    assert server.logins == [("u", "p")]

    server2 = FakeSmtp()
    provider(server2).send(**request())  # CONFIG has no username/password
    assert server2.logins == []


# --- provider errors -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error, reason, retryable",
    [
        (smtplib.SMTPRecipientsRefused({"p@x.com": (550, b"no such user")}), INVALID_RECIPIENT, False),
        (smtplib.SMTPRecipientsRefused({"p@x.com": (451, b"try later")}), THROTTLED, True),
        (smtplib.SMTPRecipientsRefused({"p@x.com": (421, b"too busy")}), THROTTLED, True),
        (smtplib.SMTPSenderRefused(553, b"bad sender", "no-reply@example.invalid"), REJECTED, False),
        (smtplib.SMTPAuthenticationError(535, b"bad credentials"), TRANSPORT_UNAVAILABLE, True),
        (smtplib.SMTPResponseException(452, b"insufficient storage"), THROTTLED, True),
        (smtplib.SMTPResponseException(554, b"transaction failed"), REJECTED, False),
        (smtplib.SMTPServerDisconnected("closed"), TRANSPORT_UNAVAILABLE, True),
        (smtplib.SMTPConnectError(111, b"refused"), TRANSPORT_UNAVAILABLE, True),
        (TimeoutError("timed out"), TRANSPORT_UNAVAILABLE, True),
        (ConnectionRefusedError("no listener"), TRANSPORT_UNAVAILABLE, True),
    ],
)
def test_every_provider_failure_maps_to_a_port_reason_code(error, reason, retryable):
    server = FakeSmtp(raise_on_send=error)
    if isinstance(error, smtplib.SMTPAuthenticationError):
        server = FakeSmtp(raise_on_login=error)
        authed = CONFIG.__class__(**{**CONFIG.__dict__, "username": "u", "password": "p"})
        result = SmtpEmailProvider(config=authed, client_factory=lambda _c: server).send(**request())
    else:
        result = provider(server).send(**request())
    assert not result.accepted
    assert result.reason == reason
    assert result.retryable is retryable
    assert result.provider_message_id is None


def test_attachments_are_refused_rather_than_silently_dropped(smtp):
    server, _ = smtp
    result = provider(server).send(**request(attachments=[{"document_id": "d1", "filename": "f.pdf"}]))
    assert not result.accepted and result.reason == REJECTED
    assert server.sent == []


def test_a_non_email_channel_is_a_programming_error_not_a_send_failure(smtp):
    server, _ = smtp
    with pytest.raises(ValueError):
        provider(server).send(**request(channel="sms"))
