"""Due dates and the deadline list behind the widget rti.nearing-deadline (PRD "Main flows" 9). A due date is worked
out when read, from settings, never stored, so a changed setting applies to every open request. With no setting there
is no due date and nothing is overdue. No statutory value is built in (PRD open question 1). Pure Python."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .dates import CALENDAR, add_days, end_of_day
from .requests import APPEALED, ASSIGNED, RECEIVED

# NearingDeadline.items: the soonest ten open requests that are overdue or due soon.
LIST_SIZE = 10


@dataclass(frozen=True)
class Timelines:
    """The organisation's settings (RTI_RESPONSE_DAYS, RTI_APPEAL_WINDOW_DAYS, RTI_APPEAL_DECIDE_DAYS and
    RTI_DAY_COUNTING). A days value that is None is not configured."""

    response_days: int | None = None
    appeal_window_days: int | None = None
    appeal_decide_days: int | None = None
    counting: str = CALENDAR


def response_due_on(received_on: date, tl: Timelines) -> date | None:
    """When the response to a request received on `received_on` is due, or None when RTI_RESPONSE_DAYS is not set."""
    if tl.response_days is None:
        return None
    return add_days(received_on, tl.response_days, tl.counting)


def appeal_due_on(filed_on: date, tl: Timelines) -> date | None:
    """When the decision of an appeal filed on `filed_on` is due, or None when RTI_APPEAL_DECIDE_DAYS is not set."""
    if tl.appeal_decide_days is None:
        return None
    return add_days(filed_on, tl.appeal_decide_days, tl.counting)


def appeal_window_end(dispatched_on: date, tl: Timelines) -> date | None:
    """The last day a first appeal can be filed against a response dispatched on `dispatched_on`, or None when
    RTI_APPEAL_WINDOW_DAYS is not set."""
    if tl.appeal_window_days is None:
        return None
    return add_days(dispatched_on, tl.appeal_window_days, tl.counting)


def current_due_on(status: str, received_on: date, appeal_filed_on: date | None, tl: Timelines) -> date | None:
    """The deadline a request is waiting on: the response (received, assigned) or the appeal decision (appealed);
    None for every other status, and when the setting is not configured."""
    if status in (RECEIVED, ASSIGNED):
        return response_due_on(received_on, tl)
    if status == APPEALED and appeal_filed_on is not None:
        return appeal_due_on(appeal_filed_on, tl)
    return None


def is_overdue(due_on: date | None, today: date) -> bool:
    """Past the due date: a request due today is not yet overdue."""
    return due_on is not None and today > due_on


def is_due_soon(due_on: date | None, today: date, within_days: int) -> bool:
    """Not overdue, and due today or within `within_days` days."""
    return due_on is not None and today <= due_on <= today + timedelta(days=within_days)


@dataclass(frozen=True)
class OpenItem:
    """What the deadline list needs from an open request."""

    request_id: str
    number: str
    status: str
    seq: int
    due_on: date | None


@dataclass(frozen=True)
class DeadlineItem:
    request_id: str
    number: str
    status: str
    due_at: datetime
    overdue: bool


@dataclass(frozen=True)
class Nearing:
    within_days: int
    due_soon: int
    overdue: int
    items: list[DeadlineItem]


def nearing_deadline(items: list[OpenItem], within_days: int, today: date) -> Nearing:
    """Counts of the open requests that are overdue or due within `within_days` days, and the soonest ten of them,
    longest overdue first."""
    chosen = [i for i in items if is_overdue(i.due_on, today) or is_due_soon(i.due_on, today, within_days)]
    chosen.sort(key=lambda i: (i.due_on, i.seq))
    return Nearing(
        within_days=within_days,
        due_soon=sum(1 for i in chosen if not is_overdue(i.due_on, today)),
        overdue=sum(1 for i in chosen if is_overdue(i.due_on, today)),
        items=[
            DeadlineItem(i.request_id, i.number, i.status, end_of_day(i.due_on), is_overdue(i.due_on, today))
            for i in chosen[:LIST_SIZE]
            if i.due_on is not None
        ],
    )
