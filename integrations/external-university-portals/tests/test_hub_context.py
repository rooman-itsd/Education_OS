"""The hub never passes this adapter's own Context: it passes its own object, which reads as attributes and as a
mapping (integration-hub README, "Writing an adapter"), with two fields more (port, operation). Every operation
takes that as it takes a Context."""

from dataclasses import dataclass, field

from eos_external_university_portals.domain.port import Context
from eup_support import partner


@dataclass
class HubContext:
    """The shape of the hub's AdapterContext: attributes, a mapping of the same fields, and port and operation."""

    organisation_id: str | None
    connection_id: str | None
    provider: str | None
    mode: str | None
    settings: dict = field(default_factory=dict)
    secrets: dict = field(default_factory=dict)
    account_link: dict | None = None
    delivery_id: str | None = None
    attempt: int = 1
    idempotency_key: str | None = None
    deadline: object = None
    port: str | None = "inter-institution-records"
    operation: str | None = None

    def __getitem__(self, key):
        return getattr(self, key)

    def keys(self):
        return self.__dataclass_fields__.keys()


def _hub(org, provider="file", **kw):
    return HubContext(organisation_id=org.id, connection_id="c-1", provider=provider, mode="mock", **kw)


def test_the_hubs_context_is_taken_like_the_adapters_own(adapter, org):
    hub = _hub(org, settings=partner())
    assert adapter.healthcheck(hub).ok
    assert adapter.capabilities(hub).ok
    listed = adapter.list_partners(hub)
    assert listed.ok and listed.output == adapter.list_partners(org.ctx("file", settings=partner())).output
    assert Context.of(hub) == Context(
        organisation_id=org.id, connection_id="c-1", provider="file", mode="mock", settings=partner()
    )
    assert Context.of(dict(organisation_id=org.id, provider="elmo")).provider == "elmo"


def test_a_context_without_an_organisation_is_still_refused(adapter, org):
    assert adapter.list_partners(None).error.code == "invalid_request"
    assert adapter.list_partners(object()).error.code == "invalid_request"
    assert adapter.list_partners(HubContext(None, None, None, "mock")).error.code == "invalid_request"
    assert adapter.list_partners(_hub(org, provider="nope", settings=partner())).error.code == "not_configured"
