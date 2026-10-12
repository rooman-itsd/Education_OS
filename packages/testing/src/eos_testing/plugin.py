"""pytest plugin, loaded automatically wherever eos-testing is installed (entry point in pyproject.toml).

Every test can ask for a fresh fake by name; nothing leaks from one test to the next:

    def test_accept_application(client, fake_audit, fake_notification, fake_events):
        ...
        fake_events.assert_published("admissions.application.accepted", application_id=app_id)
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from .stubs import FakeAudit, FakeEvents, FakeNotification, FakeScheduler


@pytest.fixture
def fake_audit() -> FakeAudit:
    return FakeAudit()


@pytest.fixture
def fake_notification() -> FakeNotification:
    fake = FakeNotification()
    fake.start()
    return fake


@pytest.fixture
def fake_events() -> Iterator[FakeEvents]:
    fake = FakeEvents()
    fake.start()
    yield fake
    fake.stop()


@pytest.fixture
def fake_scheduler() -> FakeScheduler:
    return FakeScheduler()
