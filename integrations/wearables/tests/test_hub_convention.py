"""The hub's calling convention (platform/integration-hub README, "Writing an adapter"), pinned from this side.

The hub passes `context` as an object that reads as attributes or as a mapping, never as this adapter's own Context, and
for an app-level callback (/inbound/{adapter}) every connection field of it is None. This file does not import the hub
(module boundary); HubContext below has the same shape as the hub's AdapterContext."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from wear_support import STRAVA_VERIFY, request


@dataclass
class HubContext:
    organisation_id: str | None
    connection_id: str | None
    provider: str | None
    mode: str | None
    settings: dict = field(default_factory=dict)
    secrets: dict = field(default_factory=dict, repr=False)
    account_link: dict | None = None
    delivery_id: str | None = None
    attempt: int = 1
    idempotency_key: str | None = None
    deadline: Any = None
    port: str | None = None
    operation: str | None = None

    def __getitem__(self, key):
        if key not in self.__dataclass_fields__:
            raise KeyError(key)
        return getattr(self, key)

    def keys(self):
        return self.__dataclass_fields__.keys()


def hub_ctx(org, provider="strava", **over) -> HubContext:
    return HubContext(**{**org.ctx(provider, mode="mock"), "port": "wearable-data", **over})


def test_a_hub_context_object_works_for_adapter_and_port_operations(adapter, org):
    ctx = hub_ctx(org)
    assert adapter.healthcheck(ctx).output["status"] == "healthy"
    caps = adapter.capabilities(ctx, {})
    assert caps.error is None and caps.output["port"] == "wearable-data"
    r = adapter.begin_authorisation(
        ctx,
        {
            "state": "s",
            "code_challenge": "C" * 43,
            "code_challenge_method": "S256",
            "redirect_uri": "https://hub.example/oauth/callback/wearables",
            "scope_hint": [],
        },
    )
    assert r.error is None and r.output["authorize_url"].startswith("https://")


def test_a_result_is_an_object_the_hub_can_read_as_output_or_error(adapter, org):
    bad = adapter.link_account(hub_ctx(org), {})
    assert bad.output is None and bad.error["code"] == "invalid_request"
    assert set(bad.error) >= {"code", "detail"}


def test_an_app_level_callback_has_no_connection_and_is_verified_with_platform_credentials(adapter):
    """The hub's context for /inbound/{adapter} has organisation_id, connection_id, provider and mode all None."""
    app = HubContext(None, None, None, None, operation="verify_inbound")
    handshake = request(
        b"",
        method="GET",
        query={
            "provider": "strava",
            "hub.mode": "subscribe",
            "hub.challenge": "15f7d1a91c1f40f8a748fd134752feb3",
            "hub.verify_token": STRAVA_VERIFY,
        },
    )
    v = adapter.verify_inbound(app, handshake).output
    assert v["verdict"] == "handshake"
    assert json.loads(v["handshake_response"]["body"]) == {"hub.challenge": "15f7d1a91c1f40f8a748fd134752feb3"}
