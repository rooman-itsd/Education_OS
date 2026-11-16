"""The entitlement gate reads the organisation's entitlement off the event loop. Done on the loop, a pool checkout
blocks every request while the connections are taken, and the requests holding them need the loop to give them
back: a burst of dashboard widgets (two journeys at once in the e2e suite) hung the API until the pool timed out."""

import asyncio

from eos_backend import gateway
from eos_testing import register_and_login
from eos_testing.tenancy import auth


def test_the_entitlement_lookup_runs_in_a_worker_thread_not_on_the_event_loop(client, monkeypatch):
    a = register_and_login(client, slug="gate-loop", academy_type="dance-academy")
    seen: list[bool] = []
    lookup = gateway._entitlement

    def spy(org: str) -> dict:
        try:
            asyncio.get_running_loop()
            seen.append(True)
        except RuntimeError:
            seen.append(False)
        return lookup(org)

    monkeypatch.setattr(gateway, "_entitlement", spy)
    assert client.get("/api/v1/lms/ping", headers=auth(a["token"])).status_code == 200
    assert seen == [False], "the entitlement lookup ran on the event loop"
