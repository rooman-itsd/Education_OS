"""The SMTP email provider: the first real implementation of the OutboundMessaging port.

Defaults point at a local mail catcher (MailHog on :1025), so a developer sends real-looking mail without an
account anywhere. The same code talks to a real relay by changing MESSAGING_PROVIDERS_SMTP_* only.

Two rules run through the whole file:

* **Nothing sensitive is logged.** Not the body, not the recipient, not the subject, never a credential. A log
  line carries the message id, the channel, the outcome and a port reason code. An address in a log is a
  personal-data leak into whatever aggregates our logs.
* **Nothing a provider says is passed on verbatim.** SMTP error text frequently echoes the address back. Only
  the four port reason codes ever leave this module, so notification cannot accidentally store provider prose.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
import uuid
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from ..domain.port import (
    INVALID_RECIPIENT,
    REJECTED,
    THROTTLED,
    TRANSPORT_UNAVAILABLE,
    Capabilities,
    Health,
    SendResult,
)
from .config import SmtpConfig

log = logging.getLogger("eos.messaging_providers.smtp")

# RFC 5321: a 4xx reply is temporary and the sender should try again; 5xx is permanent. Two 4xx codes mean
# "too fast" specifically, and the port has a separate reason for that.
_THROTTLE_CODES = {421, 450, 451, 452}


class SmtpEmailProvider:
    """OutboundMessaging over SMTP, email channel only.

    `client_factory` exists so tests drive a fake server; production leaves it None and gets smtplib.
    """

    channel = "email"

    def __init__(self, config: SmtpConfig | None = None, client_factory=None) -> None:
        self._config = config or SmtpConfig.from_env()
        self._client_factory = client_factory

    # --- port: send ---------------------------------------------------------------------------------------

    def send(
        self,
        *,
        message_id: str,
        organisation_id: str,
        channel: str,
        to: str,
        sender: str,
        subject: str | None,
        body: str,
        body_html: str | None = None,
        attachments: list[dict] | None = None,
        metadata: dict | None = None,
        reply_to: str | None = None,
    ) -> SendResult:
        """Hand one rendered message to the provider.

        Every parameter is named, and there is no **kwargs: a caller that tries to pass notification's
        `dev_secrets`, or the whole OutboundMessage dataclass, gets a TypeError rather than a silent leak.
        """
        if channel != self.channel:
            # Not a port error code: asking an email provider for SMS is a programming error, not a send failure.
            raise ValueError(f"{type(self).__name__} handles 'email', not {channel!r}")
        if attachments:
            return self._refuse(message_id, REJECTED, "attachments are not supported by this provider")

        try:
            message = self._build(message_id=message_id, to=to, sender=sender, subject=subject, body=body,
                                  body_html=body_html, metadata=metadata or {}, reply_to=reply_to)  # fmt: skip
        except ValueError:
            # EmailMessage refuses a header with a line break, which is what stops header injection. Building is
            # deterministic, so a retry would fail the same way: a refusal, never retryable. Raising instead would
            # reach notification as a generic transport error and be retried until its attempts ran out.
            if "\r" in to or "\n" in to:
                return self._refuse(message_id, INVALID_RECIPIENT, "recipient is not a valid header value")
            return self._refuse(message_id, REJECTED, "a header value is not valid")
        provider_message_id = message["Message-ID"]

        try:
            with self._connect() as client:
                if self._config.authenticated:
                    client.login(self._config.username, self._config.password)
                client.send_message(message)
        except smtplib.SMTPRecipientsRefused as e:
            # One recipient, so one code. 4xx here is the mailbox being temporarily unavailable, not a bad address.
            code = _first_code(e.recipients)
            # retry_after_s stays None on every throttle: SMTP (RFC 5321) has no retry-after signal, only reply
            # prose, and prose is never trusted here. notification then falls back to its own backoff.
            if code in _THROTTLE_CODES or (code is not None and 400 <= code < 500):
                return self._refuse(message_id, THROTTLED if code in _THROTTLE_CODES else TRANSPORT_UNAVAILABLE,
                                    f"recipient temporarily refused ({code})", retryable=True)  # fmt: skip
            return self._refuse(message_id, INVALID_RECIPIENT, f"recipient refused ({code})")
        except smtplib.SMTPSenderRefused as e:
            # Our own sending identity was refused: a configuration problem, and retrying will not fix it.
            return self._refuse(message_id, REJECTED, f"sender refused ({e.smtp_code})")
        except smtplib.SMTPAuthenticationError:
            # Credentials are wrong or expired. Retryable because an operator fixing the secret makes the next
            # attempt succeed, and notification bounds attempts anyway. Never log the code or the server text.
            log.error("smtp authentication failed for %s: check the configured credentials", self._config.describe())
            return self._refuse(message_id, TRANSPORT_UNAVAILABLE, "authentication failed", retryable=True)
        except (smtplib.SMTPConnectError, smtplib.SMTPHeloError) as e:
            # Connection-level, NOT a mail reply. SMTPConnectError subclasses SMTPResponseException and its
            # "code" is a connection error, so reading it as an SMTP reply would classify a refused connection
            # as permanent and the message would never be retried. Always retryable.
            return self._refuse(message_id, TRANSPORT_UNAVAILABLE, type(e).__name__, retryable=True)
        except smtplib.SMTPResponseException as e:
            retryable = e.smtp_code in _THROTTLE_CODES or 400 <= int(e.smtp_code or 0) < 500
            reason = THROTTLED if e.smtp_code in _THROTTLE_CODES else (TRANSPORT_UNAVAILABLE if retryable else REJECTED)
            return self._refuse(message_id, reason, f"server replied {e.smtp_code}", retryable=retryable)
        except (smtplib.SMTPException, OSError) as e:
            # Connection refused, DNS failure, timeout, TLS failure, disconnect mid-session.
            return self._refuse(message_id, TRANSPORT_UNAVAILABLE, type(e).__name__, retryable=True)

        log.info("message %s accepted by %s", message_id, self._config.describe())
        return SendResult(accepted=True, provider_message_id=provider_message_id)

    # --- port: capabilities and healthcheck ---------------------------------------------------------------

    def capabilities(self) -> Capabilities:
        return Capabilities(
            channels=("email",),
            max_body_bytes=10 * 1024 * 1024,  # the usual relay limit; a larger body is refused by the server
            supports_attachments=False,  # needs platform/documents to fetch them; not in this release
            supports_html=True,
            rate_limit_per_minute=0,  # 0 = the provider imposes none that we know of; a relay may still throttle
            supports_reply_to=True,  # a plain Reply-To header, nothing the relay has to support
        )

    def healthcheck(self) -> Health:
        """Connect, authenticate if configured, NOOP, quit. Never sends a message."""
        try:
            with self._connect() as client:
                if self._config.authenticated:
                    client.login(self._config.username, self._config.password)
                client.noop()
        except smtplib.SMTPAuthenticationError:
            return Health(reachable=False, detail="authentication failed")
        except (smtplib.SMTPException, OSError) as e:
            return Health(reachable=False, detail=type(e).__name__)
        return Health(reachable=True, detail=self._config.describe())

    # --- internals ----------------------------------------------------------------------------------------

    def _connect(self):
        if self._client_factory is not None:
            return self._client_factory(self._config)
        client = smtplib.SMTP(self._config.host, self._config.port, timeout=self._config.timeout_s)
        if self._config.use_tls:
            client.starttls(context=ssl.create_default_context())
        return client

    def _build(self, *, message_id, to, sender, subject, body, body_html, metadata, reply_to=None) -> EmailMessage:
        message = EmailMessage()
        message["From"] = sender or formataddr((self._config.from_name, self._config.from_email))
        message["To"] = to
        if reply_to:
            # Same protection as To: EmailMessage's default policy raises on CR or LF, so no header can be injected.
            message["Reply-To"] = reply_to
        message["Subject"] = subject or ""
        message["Message-ID"] = make_msgid(idstring=uuid.uuid4().hex[:12])
        # The port says metadata is opaque and echoed back on receipts. It is written as headers so a webhook
        # can correlate; notification guarantees it carries no secret, and nothing else is added here.
        message["X-EOS-Message-Id"] = str(message_id)
        for key, value in sorted(metadata.items()):
            message[f"X-EOS-{key}"] = str(value)
        message.set_content(body)
        if body_html:
            message.add_alternative(body_html, subtype="html")
        return message

    def _refuse(self, message_id: str, reason: str, detail: str, *, retryable: bool = False) -> SendResult:
        """One place where a failure is logged, so the "no address, no body" rule holds for every branch."""
        log.warning("message %s not accepted by %s: %s (%s)", message_id, self._config.describe(), reason, detail)
        return SendResult(accepted=False, reason=reason, retryable=retryable)


def _first_code(recipients: dict) -> int | None:
    for code, _text in recipients.values():
        return int(code)
    return None
