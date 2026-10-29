"""CMS rules (docs/prd.md §6). Pure functions: each returns a value or raises RuleViolationError with a code from the
contract's ConflictError or RuleError list."""

from __future__ import annotations

from datetime import datetime

from .enums import VISIBLE


class RuleViolationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def check_window(starts_at: datetime | None, ends_at: datetime | None) -> None:
    """Rule 5: when both are set, the announcement stops showing after it starts."""
    if starts_at is not None and ends_at is not None and ends_at <= starts_at:
        raise RuleViolationError("invalid_window", "ends_at must be after starts_at")


def is_visible(published: bool, starts_at: datetime | None, ends_at: datetime | None, now: datetime) -> bool:
    """Rule 6: published, from starts_at (inclusive) until ends_at (exclusive); a missing bound is open."""
    if not published:
        return False
    if starts_at is not None and now < starts_at:
        return False
    return ends_at is None or now < ends_at


def check_publish_change(published_now: bool, target: bool) -> None:
    """Rule 8: publishing a published item, or unpublishing a draft, is refused."""
    if published_now and target:
        raise RuleViolationError("already_published", "It is already published")
    if not published_now and not target:
        raise RuleViolationError("not_published", "It is not published")


def needs_manage(status: str) -> bool:
    """Every status filter except `visible` shows unpublished or out-of-window items."""
    return status != VISIBLE
