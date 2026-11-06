"""Request bodies, mirroring contracts/openapi.yaml components.schemas. Extra fields are refused, so a misspelt field is
a 422, never silently ignored. Every string has an upper bound that fits its column, every date the module's date
range and every amount the column's size, so a value too big is a 422, never a database error. Ids are lower-cased so
the same person is the same id everywhere."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator

from ..domain.dates import MAX_DATE, MIN_DATE
from ..domain.requests import APPEAL_OUTCOMES, CHANNELS, FEE_STATUSES, RESPONSE_TYPES
from ..infrastructure.models import (
    ADDRESS_MAX,
    EMAIL_LEN,
    MAX_AMOUNT_DIGITS,
    MODE_LEN,
    NAME_LEN,
    PHONE_LEN,
    RECEIPT_LEN,
    SUBJECT_LEN,
    TEXT_MAX,
)

# The contract types ids as format: uuid. Checked here so a bad id is a 422, never a stored row.
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
Uuid = Annotated[str, Field(pattern=UUID_PATTERN), AfterValidator(str.lower)]
Channel = Literal[CHANNELS]  # type: ignore[valid-type]
ResponseType = Literal[RESPONSE_TYPES]  # type: ignore[valid-type]
AppealOutcome = Literal[APPEAL_OUTCOMES]  # type: ignore[valid-type]
FeeStatus = Literal[FEE_STATUSES]  # type: ignore[valid-type]
# format: email, without the email-validator package (not on the approved stack): one @, no spaces, a dot after it.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
AMOUNT_PATTERN = rf"^[0-9]{{1,{MAX_AMOUNT_DIGITS}}}(\.[0-9]{{1,2}})?$"


def _in_range(value: date) -> date:
    if not MIN_DATE <= value <= MAX_DATE:
        raise ValueError(f"date must be between {MIN_DATE} and {MAX_DATE}")
    return value


Day = Annotated[date, AfterValidator(_in_range)]


def note(min_length: int, max_length: int):
    """Free text, stored without surrounding spaces; at least `min_length` characters once they are removed."""
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=min_length, max_length=max_length)]


def _has_nul(value) -> bool:
    if isinstance(value, str):
        return "\x00" in value
    if isinstance(value, (list, tuple)):
        return any(_has_nul(v) for v in value)
    if isinstance(value, dict):
        return any(_has_nul(k) or _has_nul(v) for k, v in value.items())
    if isinstance(value, BaseModel):
        return _has_nul(value.model_dump())
    return False


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*")
    @classmethod
    def _no_nul(cls, value):
        """Postgres text cannot hold NUL characters; refused here (422) rather than failing in the database (500)."""
        if _has_nul(value):
            raise ValueError("text must not contain NUL characters")
        return value


def as_dict(body: BaseModel, *, partial: bool = False) -> dict:
    """Request values for the use cases, nested models as plain dicts. partial (PATCH): only the fields the caller
    sent. A null on a PATCH field the contract does not allow to be null is dropped, so it never clears a value."""
    data = body.model_dump(exclude_unset=partial)
    if partial:
        data = {k: v for k, v in data.items() if v is not None}
    return data


class Applicant(Strict):
    name: note(1, NAME_LEN)
    address: note(1, ADDRESS_MAX) | None = None
    email: Annotated[str, Field(max_length=EMAIL_LEN, pattern=EMAIL_PATTERN)] | None = None
    phone: note(1, PHONE_LEN) | None = None
    person_id: Uuid | None = None


class Money(Strict):
    amount: Annotated[str, Field(pattern=AMOUNT_PATTERN)]
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] | None = None  # omitted: RTI_DEFAULT_CURRENCY


class Fee(Strict):
    status: FeeStatus
    amount: Money | None = None
    mode: note(1, MODE_LEN) | None = None
    receipt_reference: note(1, RECEIPT_LEN) | None = None


class RequestInput(Strict):
    received_via: Channel
    received_on: Day
    applicant: Applicant
    subject: note(3, SUBJECT_LEN)
    information_sought: note(3, TEXT_MAX)
    fee: Fee


class RequestUpdateInput(Strict):
    applicant: Applicant | None = None
    subject: note(3, SUBJECT_LEN) | None = None
    information_sought: note(3, TEXT_MAX) | None = None
    fee: Fee | None = None


class AssignInput(Strict):
    officer_id: Uuid


class ReferralInput(Strict):
    custodian_id: Uuid
    question: note(3, TEXT_MAX)
    due_on: Day | None = None


class ReplyInput(Strict):
    reply: note(1, TEXT_MAX)


class ResponseInput(Strict):
    type: ResponseType
    summary: note(3, TEXT_MAX)
    grounds: note(3, TEXT_MAX) | None = None
    dispatched_on: Day
    dispatch_mode: Channel


class TransferInput(Strict):
    authority_name: note(1, NAME_LEN)
    authority_address: note(1, ADDRESS_MAX) | None = None
    transferred_on: Day
    reason: note(3, TEXT_MAX)


class AppealInput(Strict):
    filed_on: Day
    grounds: note(3, TEXT_MAX)


class AppealDecisionInput(Strict):
    outcome: AppealOutcome
    decision_note: note(3, TEXT_MAX)
    decided_on: Day
