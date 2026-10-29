"""Which provider serves a channel. Configuration, not code: MESSAGING_PROVIDERS_EMAIL names the provider, so
changing provider is an environment change.

Fails closed. An unknown or unconfigured provider raises rather than falling back to something that silently
does not deliver — the mistake notification's memory transport exists to make impossible.
"""

from __future__ import annotations

import os

from ..domain.port import OutboundMessaging
from ..infrastructure.smtp import SmtpEmailProvider

EMAIL_PROVIDERS = {"smtp": SmtpEmailProvider}
# SMS and WhatsApp are contracted in port.yaml and config/env.example but have no implementation yet. They are
# absent here on purpose: an empty mapping gives a clear error instead of a provider that accepts and drops.
SMS_PROVIDERS: dict[str, type] = {}
WHATSAPP_PROVIDERS: dict[str, type] = {}

_BY_CHANNEL = {"email": ("MESSAGING_PROVIDERS_EMAIL", EMAIL_PROVIDERS, "smtp"),
               "sms": ("MESSAGING_PROVIDERS_SMS", SMS_PROVIDERS, ""),
               "whatsapp": ("MESSAGING_PROVIDERS_WHATSAPP", WHATSAPP_PROVIDERS, "")}  # fmt: skip


class ProviderUnavailableError(RuntimeError):
    """No usable provider for the channel. The caller decides whether that is a 503 or a failed message."""


def implemented() -> list[tuple[str, str]]:
    """(provider id, channel) for every provider this release can build, whether or not it is selected."""
    return [(name, channel) for channel, (_key, providers, _default) in _BY_CHANNEL.items() for name in providers]


def selected(channel: str) -> str:
    """The provider id the environment selects for a channel, or "" when none is."""
    env_key, _providers, default = _BY_CHANNEL[channel]
    return (os.environ.get(env_key, default) or "").strip().lower()


def get_provider_by_id(provider_id: str) -> tuple[str, OutboundMessaging]:
    """(channel, provider) for an operator naming a provider directly. Raises ProviderUnavailableError when this
    release has no provider by that id, so the API can answer 404 rather than build something else."""
    for _channel, (_key, providers, _default) in _BY_CHANNEL.items():
        if provider_id in providers:
            return _channel, providers[provider_id]()
    raise ProviderUnavailableError(f"no provider {provider_id!r} in this release")


def get_provider(channel: str) -> OutboundMessaging:
    if channel not in _BY_CHANNEL:
        raise ProviderUnavailableError(f"unknown channel {channel!r}")
    env_key, providers, _default = _BY_CHANNEL[channel]
    name = selected(channel)
    if not name:
        raise ProviderUnavailableError(f"no provider configured for {channel}: set {env_key}")
    if name not in providers:
        raise ProviderUnavailableError(f"{env_key}={name!r} is not implemented for {channel}")
    return providers[name]()
