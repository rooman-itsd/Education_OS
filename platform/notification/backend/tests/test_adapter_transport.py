"""The `adapter` transport: discovery by entry point, explicit selection, and the field mapping.

Notification must never import an adapter package, so everything here goes through the entry-point group and
through fakes shaped like the port. Nothing in this file imports eos_messaging_providers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest
from eos_notification.domain.errors import NotificationError
from eos_notification.infrastructure import transport as t
from eos_notification.infrastructure.config import NotificationConfig

SECRET = "SUPER-SECRET-TOKEN-9999"


@dataclass
class FakeResult:
    accepted: bool
    provider_message_id: str | None = None
    reason: str | None = None
    retryable: bool = False
    retry_after_s: int | None = None


@dataclass
class FakeCaps:
    supports_reply_to: bool = False


class FakeProvider:
    """Shaped like the port: keyword-only send(), no dev_secrets parameter."""

    def __init__(self, result=None, caps=None, raises=None):
        self.result = result or FakeResult(accepted=True, provider_message_id="pm-1")
        self.caps = caps if caps is not None else FakeCaps()
        self.raises = raises
        self.calls: list[dict] = []

    def capabilities(self):
        return self.caps

    def send(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises
        return self.result


class OldProvider(FakeProvider):
    """Predates reply_to: capabilities() has no such field and send() would reject the argument."""

    def capabilities(self):
        return object()

    def send(self, *, message_id, organisation_id, channel, to, sender, subject, body, metadata):
        self.calls.append({"message_id": message_id, "to": to, "body": body, "metadata": metadata})
        return FakeResult(accepted=True, provider_message_id="old-1")


def message(**over) -> t.OutboundMessage:
    base = dict(
        message_id="m-1",
        organisation_id="org-1",
        channel="email",
        to="person@college.example.com",
        sender="Education OS <no-reply@example.invalid>",
        subject="Verify",
        body=f"Verify with token {SECRET}",
        metadata={"template": "tenancy.organisation.verify"},
        dev_secrets={"token": SECRET},
    )
    base.update(over)
    return t.OutboundMessage(**base)


def config(**over) -> NotificationConfig:
    values = {f: getattr(NotificationConfig.from_env(), f) for f in NotificationConfig.__dataclass_fields__}
    values.update(over)
    return NotificationConfig(**values)


class FakeEntryPoint:
    def __init__(self, name, loads=None, raises=None):
        self.name, self._loads, self._raises = name, loads, raises

    def load(self):
        if self._raises:
            raise self._raises
        return self._loads


def points(monkeypatch, *eps):
    monkeypatch.setattr(t.metadata, "entry_points", lambda group=None: list(eps))


# --- discovery and selection -------------------------------------------------------------------------


def test_the_real_adapter_is_discoverable_on_the_entry_point_group():
    """The installed package advertises itself, and notification finds it without importing it.

    SKIPPED when no adapter is installed. notification and integrations/messaging-providers are separate
    modules with separate pull requests, so this module's suite must pass on its own: a missing adapter is a
    deployment fact (see the README's packaging note), not a notification defect. Every other test here
    patches the entry-point registry and runs regardless."""
    names = {ep.name for ep in t.metadata.entry_points(group=t.ADAPTER_GROUP)}
    if not names:
        pytest.skip(f"no {t.ADAPTER_GROUP} adapter installed; run `pip install -e integrations/messaging-providers`")
    assert "messaging-providers" in names, f"an adapter is installed but is not the expected one: {names}"


def test_the_configured_adapter_is_selected_by_name(monkeypatch):
    wanted, other = FakeProvider(), FakeProvider()
    points(monkeypatch, FakeEntryPoint("other", lambda ch: other), FakeEntryPoint("wanted", lambda ch: wanted))
    transport = t.get_transport(config(transport="adapter", adapter="wanted"))
    transport.send(message())
    assert wanted.calls and not other.calls


def test_the_first_entry_point_is_never_chosen_for_the_caller(monkeypatch):
    """Two installed adapters, neither named by config: refuse rather than pick one."""
    points(
        monkeypatch,
        FakeEntryPoint("alpha", lambda ch: FakeProvider()),
        FakeEntryPoint("beta", lambda ch: FakeProvider()),
    )
    with pytest.raises(NotificationError) as e:
        t.get_transport(config(transport="adapter", adapter="gamma"))
    assert e.value.status == 503 and "alpha, beta" in e.value.detail


def test_no_adapter_installed_is_a_503(monkeypatch):
    points(monkeypatch)
    with pytest.raises(NotificationError) as e:
        t.get_transport(config(transport="adapter", adapter="messaging-providers"))
    assert e.value.status == 503 and "none installed" in e.value.detail


def test_two_distributions_claiming_one_name_are_refused_not_guessed(monkeypatch):
    points(
        monkeypatch, FakeEntryPoint("dup", lambda ch: FakeProvider()), FakeEntryPoint("dup", lambda ch: FakeProvider())
    )
    with pytest.raises(NotificationError) as e:
        t.get_transport(config(transport="adapter", adapter="dup"))
    assert e.value.status == 503 and "2 distributions" in e.value.detail


def test_an_adapter_that_fails_to_load_is_a_503_without_leaking_the_error(monkeypatch):
    points(monkeypatch, FakeEntryPoint("broken", raises=ImportError("no module named secret_internal_thing")))
    with pytest.raises(NotificationError) as e:
        t.get_transport(config(transport="adapter", adapter="broken"))
    assert e.value.status == 503 and "secret_internal_thing" not in e.value.detail


def test_an_empty_adapter_name_is_refused(monkeypatch):
    with pytest.raises(NotificationError) as e:
        t.get_transport(config(transport="adapter", adapter=""))
    assert e.value.status == 503


def test_an_adapter_that_is_not_callable_is_refused(monkeypatch):
    points(monkeypatch, FakeEntryPoint("thing", loads="not-callable"))
    with pytest.raises(NotificationError) as e:
        t.get_transport(config(transport="adapter", adapter="thing"))
    assert e.value.status == 503


# --- delivery and reason codes -----------------------------------------------------------------------


def test_a_successful_send_returns_the_provider_message_id(monkeypatch):
    provider = FakeProvider(FakeResult(accepted=True, provider_message_id="<abc@relay>"))
    points(monkeypatch, FakeEntryPoint("a", lambda ch: provider))
    result = t.get_transport(config(transport="adapter", adapter="a")).send(message())
    assert result.accepted and result.provider_message_id == "<abc@relay>" and result.reason is None


@pytest.mark.parametrize(
    "reason, retryable",
    [("transport_unavailable", True), ("rejected", False), ("throttled", True), ("invalid_recipient", False)],
)
def test_each_port_reason_code_is_passed_through(monkeypatch, reason, retryable):
    provider = FakeProvider(FakeResult(accepted=False, reason=reason, retryable=retryable))
    points(monkeypatch, FakeEntryPoint("a", lambda ch: provider))
    result = t.get_transport(config(transport="adapter", adapter="a")).send(message())
    assert not result.accepted and result.reason == reason and result.retryable is retryable
    assert result.provider_message_id is None


def test_an_unknown_reason_is_replaced_not_stored(monkeypatch):
    """A provider's own text may echo an address; only codes this module knows are ever recorded."""
    provider = FakeProvider(FakeResult(accepted=False, reason="550 no mailbox for person@college.example.com"))
    points(monkeypatch, FakeEntryPoint("a", lambda ch: provider))
    result = t.get_transport(config(transport="adapter", adapter="a")).send(message())
    assert result.reason == "transport_error"
    assert result.reason in t.ERROR_CODES


def test_a_provider_that_raises_does_not_escape(monkeypatch):
    provider = FakeProvider(raises=RuntimeError("boom"))
    points(monkeypatch, FakeEntryPoint("a", lambda ch: provider))
    result = t.get_transport(config(transport="adapter", adapter="a")).send(message())
    assert not result.accepted and result.reason == "transport_error" and result.retryable


def test_a_channel_with_no_provider_fails_that_message_only(monkeypatch):
    def factory(channel):
        raise LookupError(f"no provider for {channel}")

    points(monkeypatch, FakeEntryPoint("a", loads=factory))
    result = t.get_transport(config(transport="adapter", adapter="a")).send(message(channel="sms"))
    assert not result.accepted and result.reason == "rejected" and not result.retryable


# --- reply_to capability gate ------------------------------------------------------------------------


def test_reply_to_is_passed_when_supported_and_configured(monkeypatch):
    provider = FakeProvider(caps=FakeCaps(supports_reply_to=True))
    points(monkeypatch, FakeEntryPoint("a", lambda ch: provider))
    t.get_transport(config(transport="adapter", adapter="a")).send(message(reply_to="admissions@college.example.com"))
    assert provider.calls[0]["reply_to"] == "admissions@college.example.com"


def test_reply_to_is_omitted_entirely_when_unsupported(monkeypatch):
    provider = FakeProvider(caps=FakeCaps(supports_reply_to=False))
    points(monkeypatch, FakeEntryPoint("a", lambda ch: provider))
    t.get_transport(config(transport="adapter", adapter="a")).send(message(reply_to="a@b.com"))
    assert "reply_to" not in provider.calls[0], "must be omitted, not passed as None"


def test_reply_to_is_omitted_when_none_is_configured(monkeypatch):
    provider = FakeProvider(caps=FakeCaps(supports_reply_to=True))
    points(monkeypatch, FakeEntryPoint("a", lambda ch: provider))
    t.get_transport(config(transport="adapter", adapter="a")).send(message(reply_to=None))
    assert "reply_to" not in provider.calls[0]


def test_an_adapter_predating_reply_to_still_works(monkeypatch):
    """capabilities() without the field, send() without the parameter: no TypeError, message still sent."""
    provider = OldProvider()
    points(monkeypatch, FakeEntryPoint("old", lambda ch: provider))
    result = t.get_transport(config(transport="adapter", adapter="old")).send(message(reply_to="a@b.com"))
    assert result.accepted and provider.calls and "reply_to" not in provider.calls[0]


# --- secret isolation --------------------------------------------------------------------------------


def test_dev_secrets_never_reach_the_provider(monkeypatch):
    provider = FakeProvider()
    points(monkeypatch, FakeEntryPoint("a", lambda ch: provider))
    t.get_transport(config(transport="adapter", adapter="a")).send(message())
    call = provider.calls[0]
    assert "dev_secrets" not in call
    assert not any(SECRET in str(v) for k, v in call.items() if k != "body"), "a secret escaped outside the body"
    assert call["metadata"] == {"template": "tenancy.organisation.verify"}


def test_the_whole_message_object_is_never_forwarded(monkeypatch):
    """asdict(message) would carry dev_secrets; only the port's named fields may be sent."""
    provider = FakeProvider()
    points(monkeypatch, FakeEntryPoint("a", lambda ch: provider))
    t.get_transport(config(transport="adapter", adapter="a")).send(message())
    assert set(provider.calls[0]) == {
        "message_id", "organisation_id", "channel", "to", "sender", "subject", "body", "metadata",
    }  # fmt: skip


def test_no_log_line_from_a_failure_carries_the_secret_or_the_address(monkeypatch, caplog):
    provider = FakeProvider(raises=RuntimeError(f"failed sending to person@college.example.com: {SECRET}"))
    points(monkeypatch, FakeEntryPoint("a", lambda ch: provider))
    with caplog.at_level(logging.DEBUG, logger="eos.notification"):
        t.get_transport(config(transport="adapter", adapter="a")).send(message())
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert SECRET not in logged and "person@college.example.com" not in logged
    assert "m-1" in logged
