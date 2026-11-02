"""AMC contracts (PRD "Main flows" 1 to 3 and 7 to 9, "Statuses" and "Rules").

Stored statuses are draft, active, terminated and renewed. expiring and expired are not stored: they are worked out
from end_date, renewal_notice_days and today whenever a contract is read (PRD main flow 7), so there is no timer."""

from __future__ import annotations

from datetime import date

from .errors import DomainRuleError

DRAFT = "draft"
ACTIVE = "active"
TERMINATED = "terminated"
RENEWED = "renewed"
CONTRACT_STATUSES = (DRAFT, ACTIVE, TERMINATED, RENEWED)  # contract ContractStatus, in its order
CLOSED_STATUSES = (TERMINATED, RENEWED)

COVERAGE_TYPES = ("comprehensive", "non_comprehensive")  # contract CoverageType

# PATCH /contracts/{id}: "An active contract can change only owner_id, vendor_contacts and renewal_notice_days; its
# terms change through a renewal."
ACTIVE_EDITABLE_FIELDS = frozenset({"owner_id", "vendor_contacts", "renewal_notice_days"})


def check_period(start: date, end: date) -> None:
    """422 "end_date not after start_date" (POST /contracts, PATCH, /renew)."""
    if end <= start:
        raise DomainRuleError("end_before_start", "end_date must be after start_date", kind="invalid", field="end_date")


def check_editable(status: str, fields: set[str]) -> None:
    """A draft can change any field; an active contract only ACTIVE_EDITABLE_FIELDS; a terminated or renewed one
    nothing (PATCH 409)."""
    if status in CLOSED_STATUSES:
        raise DomainRuleError("contract_closed", f"a {status} contract cannot be edited", kind="conflict")
    if status == ACTIVE:
        locked = sorted(fields - ACTIVE_EDITABLE_FIELDS)
        if locked:
            message = f"{', '.join(locked)} cannot change on an active contract; renew it instead"
            raise DomainRuleError("field_not_editable", message, kind="conflict", field=locked[0])


def activate(status: str) -> str:
    """draft -> active (POST /contracts/{id}/activate, 409 when not a draft)."""
    if status != DRAFT:
        raise DomainRuleError("not_draft", f"only a draft can be activated, this one is {status}", kind="conflict")
    return ACTIVE


def terminate(status: str) -> str:
    """active -> terminated (POST /contracts/{id}/terminate, 409 when not active)."""
    if status != ACTIVE:
        raise DomainRuleError(
            "not_active", f"only an active contract can be terminated, this one is {status}", kind="conflict"
        )
    return TERMINATED


def check_renewable(status: str, renewed_to_id: str | None) -> None:
    """A renewal starts from an active contract only, and a contract has at most one successor (/renew 409)."""
    if status != ACTIVE:
        raise DomainRuleError(
            "not_active", f"only an active contract can be renewed, this one is {status}", kind="conflict"
        )
    if renewed_to_id is not None:
        raise DomainRuleError("successor_exists", "this contract already has a renewal", kind="conflict")


def check_predecessor_active(status: str) -> None:
    """Activating a renewal draft marks the contract it renews as renewed, which must still be active (activate 409:
    "the contract it renews is no longer active")."""
    if status != ACTIVE:
        raise DomainRuleError(
            "predecessor_not_active", f"the contract this renews is {status}, no longer active", kind="conflict"
        )


def check_items_changeable(status: str) -> None:
    """Covered items are added and removed while the contract is a draft or active (409 otherwise)."""
    if status not in (DRAFT, ACTIVE):
        raise DomainRuleError("contract_closed", f"covered items of a {status} contract cannot change", kind="conflict")


def is_expired(status: str, end_date: date, today: date) -> bool:
    """Active and past its end date. The end date itself is still covered."""
    return status == ACTIVE and end_date < today


def is_expiring(status: str, end_date: date, renewal_notice_days: int, today: date) -> bool:
    """Active, not yet past its end date, and the end date within renewal_notice_days."""
    return status == ACTIVE and today <= end_date and (end_date - today).days <= renewal_notice_days


def check_can_raise_engagement(status: str, end_date: date, today: date) -> None:
    """ "An engagement can only be raised against an active contract that has not expired" (POST /engagements 409)."""
    if status != ACTIVE:
        raise DomainRuleError("contract_not_active", f"the contract is {status}", kind="conflict", field="contract_id")
    if is_expired(status, end_date, today):
        raise DomainRuleError(
            "contract_expired", "the contract has passed its end date", kind="conflict", field="contract_id"
        )
