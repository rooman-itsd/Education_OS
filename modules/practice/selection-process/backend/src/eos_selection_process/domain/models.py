"""Selection-process domain models, enums and domain rules."""

from __future__ import annotations

from enum import Enum


class ProcessStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


class CandidateStatus(str, Enum):
    REGISTERED = "registered"
    IN_PROGRESS = "in_progress"
    SELECTED = "selected"
    WAITLISTED = "waitlisted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


FINAL_CANDIDATE_STATUSES = {
    CandidateStatus.SELECTED.value,
    CandidateStatus.WAITLISTED.value,
    CandidateStatus.REJECTED.value,
    CandidateStatus.WITHDRAWN.value,
}


class DecisionOutcome(str, Enum):
    ADVANCE = "advance"
    HOLD = "hold"
    REJECT = "reject"


class FinalizeOutcome(str, Enum):
    SELECTED = "selected"
    WAITLISTED = "waitlisted"
    REJECTED = "rejected"


class SlotStatus(str, Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DomainError(Exception):
    """Base selection process domain exception."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ProcessNotDraftError(DomainError):
    def __init__(self, message: str = "Process is not a draft") -> None:
        super().__init__("process_not_draft", message, status_code=409)


class ProcessNotOpenError(DomainError):
    def __init__(self, message: str = "Process is not open") -> None:
        super().__init__("process_not_open", message, status_code=409)


class NoStagesError(DomainError):
    def __init__(self, message: str = "Process has no stages") -> None:
        super().__init__("no_stages", message, status_code=409)


class DuplicateCandidateError(DomainError):
    def __init__(self, message: str = "This person is already a candidate on this process") -> None:
        super().__init__("duplicate_candidate", message, status_code=409)


class CandidateFinalizedError(DomainError):
    def __init__(self, message: str = "Candidate already has a final outcome") -> None:
        super().__init__("candidate_finalized", message, status_code=409)


class AlreadyDecidedError(DomainError):
    def __init__(self, message: str = "Decision already recorded by panelist for this stage") -> None:
        super().__init__("already_decided", message, status_code=409)


class NotFoundError(DomainError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__("not_found", message, status_code=404)


class ConflictError(DomainError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, status_code=409)

