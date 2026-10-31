"""Choosing a provider is configuration. It fails closed: no silent fallback to something that does not send."""

from __future__ import annotations

import pytest
from eos_messaging_providers.application.registry import ProviderUnavailableError, get_provider
from eos_messaging_providers.infrastructure.smtp import SmtpEmailProvider


def test_email_defaults_to_smtp(monkeypatch):
    monkeypatch.delenv("MESSAGING_PROVIDERS_EMAIL", raising=False)
    assert isinstance(get_provider("email"), SmtpEmailProvider)


def test_an_unimplemented_provider_name_is_refused_not_ignored(monkeypatch):
    monkeypatch.setenv("MESSAGING_PROVIDERS_EMAIL", "sendgrid")
    with pytest.raises(ProviderUnavailableError, match="not implemented"):
        get_provider("email")


@pytest.mark.parametrize("channel", ["sms", "whatsapp"])
def test_contracted_but_unbuilt_channels_fail_closed(channel, monkeypatch):
    """port.yaml and env.example name SMS and WhatsApp. Neither is built, and asking for one must raise
    rather than return something that accepts a message and drops it."""
    monkeypatch.delenv(f"MESSAGING_PROVIDERS_{channel.upper()}", raising=False)
    with pytest.raises(ProviderUnavailableError):
        get_provider(channel)


def test_an_unknown_channel_is_refused(monkeypatch):
    with pytest.raises(ProviderUnavailableError, match="unknown channel"):
        get_provider("carrier-pigeon")


def test_capabilities_reports_what_this_release_actually_supports():
    caps = get_provider("email").capabilities()
    assert caps.channels == ("email",)
    assert caps.supports_html is True
    assert caps.supports_attachments is False  # needs platform/documents; refused by send() today
