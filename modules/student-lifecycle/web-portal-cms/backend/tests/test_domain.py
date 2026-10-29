from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from eos_web_portal_cms.domain import enums as e
from eos_web_portal_cms.domain.rules import (
    RuleViolationError,
    check_publish_change,
    check_window,
    is_visible,
    needs_manage,
)

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
HOUR = timedelta(hours=1)


def code_of(fn, *args) -> str:
    with pytest.raises(RuleViolationError) as exc:
        fn(*args)
    return exc.value.code


def test_window_must_end_after_it_starts():
    check_window(None, None)
    check_window(NOW, None)
    check_window(None, NOW)
    check_window(NOW, NOW + HOUR)
    assert code_of(check_window, NOW, NOW) == "invalid_window"
    assert code_of(check_window, NOW, NOW - HOUR) == "invalid_window"


@pytest.mark.parametrize(
    ("published", "starts", "ends", "visible"),
    [
        (True, None, None, True),
        (False, None, None, False),
        (True, NOW, None, True),  # starts_at is inclusive
        (True, NOW + HOUR, None, False),  # scheduled
        (True, None, NOW, False),  # ends_at is exclusive
        (True, None, NOW + HOUR, True),
        (True, NOW - HOUR, NOW - timedelta(seconds=1), False),  # expired
        (False, NOW - HOUR, NOW + HOUR, False),  # a draft is never visible
    ],
)
def test_visibility(published, starts, ends, visible):
    assert is_visible(published, starts, ends, NOW) is visible


def test_publish_changes():
    check_publish_change(False, True)
    check_publish_change(True, False)
    assert code_of(check_publish_change, True, True) == "already_published"
    assert code_of(check_publish_change, False, False) == "not_published"


def test_only_the_visible_filter_is_open_to_readers():
    assert needs_manage(e.VISIBLE) is False
    assert all(needs_manage(s) for s in (e.DRAFT, e.PUBLISHED, e.ALL))
    assert needs_manage(e.PUBLISHED, windowed=False) is False
    assert all(needs_manage(s, windowed=False) for s in (e.DRAFT, e.ALL))
