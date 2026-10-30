"""Delivery through a REAL SMTP server, not a fake. Skipped unless one is configured.

    docker run -d --name eos-mail -p 1026:1025 -p 8026:8025 mailhog/mailhog
    EOS_LIVE_SMTP_HOST=localhost EOS_LIVE_SMTP_PORT=1026 \
      pytest integrations/messaging-providers/tests/test_live_smtp.py -q

Until this has run, nobody may claim the adapter delivers: every other test in this suite talks to a fake
server that cannot disagree with my assumptions about smtplib.
"""

from __future__ import annotations

import logging
import os
from email.utils import formataddr

import pytest
from eos_messaging_providers.infrastructure.config import SmtpConfig
from eos_messaging_providers.infrastructure.smtp import SmtpEmailProvider
from smtp_support import request

HOST = os.environ.get("EOS_LIVE_SMTP_HOST")
pytestmark = pytest.mark.skipif(not HOST, reason="set EOS_LIVE_SMTP_HOST to exercise a real SMTP server")


USERNAME = os.environ.get("EOS_LIVE_SMTP_USERNAME", "")
# Gmail and most authenticated relays rewrite or refuse a From that is not the authenticated account, so the
# sender defaults to the account itself. With MailHog (no auth) it falls back to the usual placeholder.
FROM_EMAIL = USERNAME or "no-reply@example.invalid"
# Send somewhere you can actually open, so "it arrived" is something you saw rather than something SMTP implied.
TO = os.environ.get("EOS_LIVE_SMTP_TO", "live@college.example.com")


def live_config() -> SmtpConfig:
    return SmtpConfig(
        host=HOST,
        port=int(os.environ.get("EOS_LIVE_SMTP_PORT", "1025")),
        username=USERNAME,
        password=os.environ.get("EOS_LIVE_SMTP_PASSWORD", ""),
        use_tls=os.environ.get("EOS_LIVE_SMTP_USE_TLS", "").lower() in {"1", "true", "yes"},
        timeout_s=int(os.environ.get("EOS_LIVE_SMTP_TIMEOUT_S", "15")),
        from_email=FROM_EMAIL,
        from_name="Education OS",
    )


def live_request(**overrides) -> dict:
    """The shared request, addressed for whichever real server is configured. An override wins."""
    fields = {"to": TO, "sender": formataddr(("Education OS", FROM_EMAIL))}
    fields.update(overrides)
    return request(**fields)


def test_healthcheck_reaches_a_real_server():
    health = SmtpEmailProvider(config=live_config()).healthcheck()
    assert health.reachable, health.detail


def test_a_real_message_is_accepted_by_a_real_server():
    result = SmtpEmailProvider(config=live_config()).send(**live_request())
    assert result.accepted, result.reason
    assert result.provider_message_id


def test_an_unroutable_recipient_never_reaches_a_log_line(caplog):
    """MailHog accepts every recipient and a real relay refuses this one, so the outcome depends on the server.

    What must hold on both is the module's rule. The result cannot carry server text by construction (reason is
    pinned to the port codes, the id is generated here), so the place a leak could happen is the log. And if the
    server does refuse, it must read as this recipient being bad, not as a transport failure worth retrying."""
    address = "not-an-address"
    with caplog.at_level(logging.DEBUG, logger="eos.messaging_providers.smtp"):
        result = SmtpEmailProvider(config=live_config()).send(**live_request(to=address))
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert logged, "the adapter must say something about every send"
    assert address not in logged
    if result.accepted:
        assert result.provider_message_id and result.reason is None
    else:
        assert result.reason in {"invalid_recipient", "rejected"} and not result.retryable
