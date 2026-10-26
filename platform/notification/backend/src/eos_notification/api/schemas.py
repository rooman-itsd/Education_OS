from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..application.common import aware
from ..domain.models import SENDING, SENT, Message

Channel = Literal["email", "sms", "whatsapp", "push", "in_app"]
Category = Literal["transactional", "operational", "reminder", "announcement"]

# The merged contract (0.1.0) has no `sent` status. The database records it (provider accepted), but until the
# contract change adding it is approved the API presents it as `sending`. Flip this one flag after approval.
EXPOSE_SENT_STATUS = False
PublicStatus = Literal["queued", "sending", "delivered", "failed", "bounced", "suppressed"]


def public_status(status: str) -> str:
    return status if (EXPOSE_SENT_STATUS or status != SENT) else SENDING


def status_filter(status: str | None) -> tuple[str, ...] | None:
    if status is None:
        return None
    if status == SENDING and not EXPOSE_SENT_STATUS:
        return (SENDING, SENT)
    return (status,)


class RecipientIn(BaseModel):
    user_id: str | None = None
    address: str | None = Field(default=None, max_length=254)
    locale: str | None = Field(default=None, max_length=10)


class NewMessageIn(BaseModel):
    client_token: str | None = Field(default=None, max_length=120)
    template: str = Field(max_length=120)
    recipient: RecipientIn
    channel: Channel | None = None
    category: Category | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    send_after: datetime | None = None


class NewTemplateIn(BaseModel):
    key: str = Field(max_length=120)
    channel: Channel
    locale: str = Field(max_length=10)
    category: Category | None = None
    subject: str | None = None
    body: str
    variables: list[str] | None = None


class PreviewIn(BaseModel):
    channel: Channel | None = None
    locale: str | None = Field(default=None, max_length=10)
    variables: dict[str, Any]


class QuietHoursIn(BaseModel):
    start: str
    end: str
    timezone: str


class PreferencesIn(BaseModel):
    user_id: str | None = None
    locale: str | None = Field(default=None, max_length=10)
    channels: dict[str, list[str]]
    quiet_hours: QuietHoursIn | None = None


def _iso(value: datetime | None) -> str | None:
    value = aware(value)
    return value.isoformat() if value else None


def mask_address(address: str) -> str:
    """a***@example.com for an email, ***1234 for a phone number. Never the full address."""
    if "@" in address:
        local, _, domain = address.partition("@")
        return f"{local[:1]}***@{domain}"
    return f"***{address[-2:]}" if address else ""


def message_out(m: Message) -> dict:
    out: dict[str, Any] = {
        "id": m.id,
        "organisation_id": m.organisation_id,
        "template": m.template_key,
        "channel": m.channel,
        "category": m.category,
        "status": public_status(m.status),
        "recipient_id": m.recipient_id,
        "subject": m.subject,
        "created_at": _iso(m.created_at),
        "sent_at": _iso(m.sent_at),
        "read_at": _iso(m.read_at),
        "attempts": m.attempts,
        "last_error": m.last_error,
        "provider_message_id": m.provider_message_id,
    }
    if m.recipient_address:
        out["recipient_address"] = mask_address(m.recipient_address)
    return out
