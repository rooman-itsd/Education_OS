"""The reopen window and the auto-close rule (PRD main flow 7; config/env.example HELPDESK_REOPEN_WINDOW_DAYS and
HELPDESK_AUTO_CLOSE_DAYS; MyTicketDetail.can_reopen; POST /me/tickets/{id}/reopen).

`resolved_at` is when the ticket was resolved, the start of both windows ("Days after resolution"). How the
ticket's own fields store it is a persistence matter, not decided here."""

from __future__ import annotations

from datetime import datetime, timedelta

from .errors import DomainRuleError
from .tickets import RESOLVED, reopen, require_status


def _window(days: int) -> timedelta:
    if isinstance(days, bool) or not isinstance(days, int) or days < 0:
        raise ValueError(f"a window is a whole number of days, at least 0, got {days!r}")
    return timedelta(days=days)


def can_reopen(status: object, resolved_at: datetime | None, now: datetime, window_days: int) -> bool:
    """MyTicketDetail.can_reopen: "True while resolved and inside the reopen window". The window ends
    HELPDESK_REOPEN_WINDOW_DAYS after resolution ("Days after resolution during which the requester may reopen");
    its last moment is still inside."""
    window = _window(window_days)
    if require_status(status) != RESOLVED or resolved_at is None:
        return False
    return now <= resolved_at + window


def reopen_within_window(status: object, resolved_at: datetime | None, now: datetime, window_days: int) -> str:
    """POST /me/tickets/{id}/reopen: "resolved → in_progress"; 409 when "Not resolved, or the reopen window has
    passed"."""
    after = reopen(status)
    if not can_reopen(status, resolved_at, now, window_days):
        message = "the reopen window has passed"
        raise DomainRuleError("reopen_window_passed", message, kind="conflict", field="status")
    return after


def due_for_auto_close(status: object, resolved_at: datetime | None, now: datetime, auto_close_days: int) -> bool:
    """PRD main flow 7: the daily job "closes tickets resolved more than HELPDESK_AUTO_CLOSE_DAYS ago". Only a
    resolved ticket is closed; the job then moves it with tickets.close."""
    window = _window(auto_close_days)
    if require_status(status) != RESOLVED or resolved_at is None:
        return False
    return now - resolved_at > window
