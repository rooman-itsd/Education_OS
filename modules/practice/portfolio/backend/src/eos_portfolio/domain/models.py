"""Portfolio domain models, statuses and business rules."""

from __future__ import annotations

from enum import StrEnum


class ItemStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    WITHDRAWN = "withdrawn"


class ReviewDecision(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"


class PortfolioError(Exception):
    def __init__(self, status: int, code: str, message: str, **extra) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra

    def body(self) -> dict:
        return {"code": self.code, "message": self.message, **self.extra}


class ConflictError(PortfolioError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(409, code, message)


class NotFoundError(PortfolioError):
    def __init__(self, what: str) -> None:
        super().__init__(404, "not_found", f"{what} not found in your organisation")


class RuleViolationError(PortfolioError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(422, code, message)


def allowed_actions(status: str, is_owner: bool, is_reviewer: bool, is_manager: bool) -> list[str]:
    """Calculate actions caller may take now on this item."""
    can: list[str] = []
    # Edit
    if (is_owner or is_manager) and status in (ItemStatus.DRAFT, ItemStatus.CHANGES_REQUESTED):
        can.append("edit")
    # Delete
    if (is_owner or is_manager) and status == ItemStatus.DRAFT:
        can.append("delete")
    # Submit
    if (is_owner or is_manager) and status in (ItemStatus.DRAFT, ItemStatus.CHANGES_REQUESTED):
        can.append("submit")
    # Withdraw
    if (is_owner or is_manager) and status in (ItemStatus.SUBMITTED, ItemStatus.UNDER_REVIEW):
        can.append("withdraw")
    # Review
    if (is_reviewer or is_manager) and status in (ItemStatus.SUBMITTED, ItemStatus.UNDER_REVIEW):
        can.append("review")
    return can
