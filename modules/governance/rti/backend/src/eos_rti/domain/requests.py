"""RTI requests (PRD "Main flows", "Statuses" and "Rules"): the statuses, the moves between them, what each response
type needs and the date rules of each step. Pure Python.

Statuses:
    received -> assigned -> responded -> closed
    assigned -> assigned                        (re-assign)
    received | assigned -> transferred          (final)
    responded -> appealed -> appeal_decided -> closed
"""

from __future__ import annotations

from datetime import date

from .dates import MAX_DATE, MIN_DATE
from .errors import conflict, invalid

RECEIVED, ASSIGNED, RESPONDED, APPEALED = "received", "assigned", "responded", "appealed"
APPEAL_DECIDED, TRANSFERRED, CLOSED = "appeal_decided", "transferred", "closed"
REQUEST_STATUSES = (RECEIVED, ASSIGNED, RESPONDED, APPEALED, APPEAL_DECIDED, TRANSFERRED, CLOSED)
# Waiting for the authority to act: a response is due (received, assigned) or an appeal decision is due (appealed).
# Only these can be overdue or due soon.
OPEN_STATUSES = (RECEIVED, ASSIGNED, APPEALED)

CHANNELS = ("post", "in_person", "email", "online_portal")  # contract Channel (also the dispatch mode)
RESPONSE_TYPES = ("information_provided", "partly_provided", "refused")
APPEAL_OUTCOMES = ("upheld", "partly_upheld", "dismissed")
FEE_STATUSES = ("paid", "exempt", "pending")
CLOSURES = ("responded", "appeal_decided", "transferred")
REFERRAL_STATUSES = ("open", "replied")
GROUNDS_REQUIRED = ("partly_provided", "refused")

# Allowed moves: action -> (statuses it may start from, status it leads to, contract wording of the refusal).
MOVES = {
    "correct": ((RECEIVED, ASSIGNED), None, "already responded, transferred or closed"),
    "assign": ((RECEIVED, ASSIGNED), ASSIGNED, "not received or assigned"),
    "refer": ((ASSIGNED,), None, "request is not assigned"),
    "respond": ((ASSIGNED,), RESPONDED, "not assigned"),
    "transfer": ((RECEIVED, ASSIGNED), TRANSFERRED, "not received or assigned"),
    "appeal": ((RESPONDED,), APPEALED, "not responded"),
    "decide": ((APPEALED,), APPEAL_DECIDED, "not appealed"),
    "close": ((RESPONDED, APPEAL_DECIDED), CLOSED, "not responded or appeal_decided"),
}


def move(action: str, current: str) -> str:
    """The status after `action`, or a 409 when `current` does not allow it. The status stays the same for actions
    that do not change it (correct, refer)."""
    allowed, to, why = MOVES[action]
    if current not in allowed:
        raise conflict("invalid_status", f"{why} (status is {current})")
    return to or current


def check_date(value: date, field: str) -> None:
    if not MIN_DATE <= value <= MAX_DATE:
        raise invalid("date_out_of_range", f"{field} must be between {MIN_DATE} and {MAX_DATE}", field)


def check_not_future(value: date, today: date, field: str) -> None:
    """An event that has happened is dated today or earlier (today in India)."""
    check_date(value, field)
    if value > today:
        raise invalid("date_in_future", f"{field} must not be after today ({today})", field)


def check_not_before(value: date, earliest: date, field: str, earliest_name: str) -> None:
    if value < earliest:
        raise invalid("date_before_start", f"{field} must not be before {earliest_name} ({earliest})", field)


def check_response(response_type: str, grounds: str | None) -> None:
    """Grounds (free text) are required for partly_provided and refused; no list of exemptions is built in."""
    if response_type in GROUNDS_REQUIRED and not (grounds or "").strip():
        raise invalid("grounds_required", f"grounds are required when the response is {response_type}", "grounds")


def closure_of(status_before_close: str) -> str:
    """How a request closed from `status_before_close` ended (the Closure of the contract)."""
    return RESPONDED if status_before_close == RESPONDED else APPEAL_DECIDED


def question_repeats_applicant(question: str, applicant: dict) -> str | None:
    """The applicant's name, email or phone when a referral question repeats it (custodians must not see them), else
    None. A case-insensitive search for the whole value; very short values are skipped so a one-letter name does not
    block every question."""
    text = question.lower()
    for key in ("name", "email", "phone"):
        value = (applicant.get(key) or "").strip().lower()
        if len(value) >= 4 and value in text:
            return key
    return None
