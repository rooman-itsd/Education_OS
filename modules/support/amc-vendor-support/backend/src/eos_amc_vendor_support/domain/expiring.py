"""The expiring-contracts statistics behind the Support Staff widget amc-vendor-support.contracts-expiring
(GET /stats/contracts-expiring, PRD "Dashboard widget"): active contracts ending within the window and active
contracts already past their end date, soonest first."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .contracts import ACTIVE, DRAFT


@dataclass(frozen=True)
class ContractForExpiry:
    """What the statistics need from a contract."""

    contract_id: str
    number: str
    vendor_id: str
    title: str
    status: str
    end_date: date
    successor_status: str | None  # status of the renewal draft or successor, if any


@dataclass(frozen=True)
class ExpiringItem:
    """One row of contract ExpiringContracts.items, in its field order."""

    contract_id: str
    number: str
    vendor_id: str
    title: str
    end_date: date
    days_left: int
    renewal_draft_exists: bool


@dataclass(frozen=True)
class ExpiringContracts:
    """Contract ExpiringContracts, in its field order."""

    within_days: int
    expiring_count: int
    expired_count: int
    items: list[ExpiringItem]


def contracts_expiring(contracts: list[ContractForExpiry], within_days: int, today: date) -> ExpiringContracts:
    """Active contracts with at most within_days left (days_left from 0 to within_days) and active contracts past their
    end date (negative days_left), soonest end date first, then by number."""
    items: list[ExpiringItem] = []
    for c in contracts:
        if c.status != ACTIVE:
            continue
        days_left = (c.end_date - today).days
        if days_left > within_days:
            continue
        items.append(
            ExpiringItem(
                contract_id=c.contract_id,
                number=c.number,
                vendor_id=c.vendor_id,
                title=c.title,
                end_date=c.end_date,
                days_left=days_left,
                renewal_draft_exists=c.successor_status == DRAFT,
            )
        )
    items.sort(key=lambda i: (i.end_date, i.number))
    expired = sum(1 for i in items if i.days_left < 0)
    return ExpiringContracts(
        within_days=within_days, expiring_count=len(items) - expired, expired_count=expired, items=items
    )
