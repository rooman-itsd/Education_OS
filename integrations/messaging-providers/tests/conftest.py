"""Fixtures only. The fake server and the request builder live in smtp_support.py, so test files import them
by a unique name rather than from `conftest`, which in a combined run can be another module's."""

from __future__ import annotations

import pytest
from smtp_support import FakeSmtp


@pytest.fixture
def smtp():
    """A fake server and a factory the provider can be constructed with."""
    server = FakeSmtp()

    def factory(_config):
        return server

    return server, factory
