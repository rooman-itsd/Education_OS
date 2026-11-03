"""Selection-process domain models, enums and domain rules."""

from __future__ import annotations

from enum import StrEnum


class ProcessStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


class CandidateStatus(StrEnum):
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


class DecisionOutcome(StrEnum):
    ADVANCE = "advance"
    HOLD = "hold"
    REJECT = "reject"


class FinalizeOutcome(StrEnum):
    SELECTED = "selected"
    WAITLISTED = "waitlisted"
    REJECTED = "rejected"


class SlotStatus(StrEnum):
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


class DuplicateStageSequenceError(DomainError):
    """Two stages of one process share a sequence number (unique per process in the database)."""

    def __init__(self, sequences: list[int]) -> None:
        listed = ", ".join(str(n) for n in sequences)
        noun = "sequence" if len(sequences) == 1 else "sequences"
        super().__init__("duplicate_stage_sequence", f"Stage {noun} {listed} used more than once", status_code=422)
        self.sequences = sequences


def check_stage_sequences(stages: list[dict]) -> None:
    """Refuse a stage list in which a sequence number repeats, before anything is written."""
    seen: set[int] = set()
    repeated: set[int] = set()
    for s in stages:
        (repeated if s["sequence"] in seen else seen).add(s["sequence"])
    if repeated:
        raise DuplicateStageSequenceError(sorted(repeated))


class AlreadyDecidedError(DomainError):
    def __init__(self, message: str = "Decision already recorded by panelist for this stage") -> None:
        super().__init__("already_decided", message, status_code=409)


class NotFoundError(DomainError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__("not_found", message, status_code=404)


class ForbiddenError(DomainError):
    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__("forbidden", message, status_code=403)


class ConflictError(DomainError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, status_code=409)
