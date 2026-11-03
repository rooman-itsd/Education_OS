"""Exam sessions (contract `ExamSession`; PRD 5.5, FR-5, FR-6) and exam duties (contract `ExamDuty`; PRD 5.8, FR-9).

Not here, on purpose: FR-5's rule that a student may not be a candidate in two overlapping sessions. It needs candidates,
which depend on the unconfirmed `student_id` mapping and on eligibility (docs/reviewer-decisions.md)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime, tzinfo

from . import cycles as cyc
from . import papers as pap
from .errors import DomainRuleError
from .values import optional_text, require_choice, require_id, require_instant, require_integer, require_text

SCHEDULED, CANCELLED, COMPLETED = "scheduled", "cancelled", "completed"
SESSION_STATUSES = (SCHEDULED, CANCELLED, COMPLETED)  # contract SessionStatus
REASON_MAX = 500


def windows_overlap(a: tuple[datetime, datetime], b: tuple[datetime, datetime]) -> bool:
    """Two [start, end) windows share time. Back-to-back windows do not overlap."""
    return a[0] < b[1] and b[0] < a[1]


@dataclass(frozen=True)
class Session:
    id: str
    exam_cycle_id: str
    starts_at: datetime
    ends_at: datetime
    invigilators_required: int = 0
    venue_label: str | None = None
    status: str = SCHEDULED
    cancel_reason: str | None = None

    def __post_init__(self) -> None:
        require_id(self.id, "id")
        require_id(self.exam_cycle_id, "exam_cycle_id")
        require_instant(self.starts_at, "starts_at")
        require_instant(self.ends_at, "ends_at")
        require_integer(self.invigilators_required, "invigilators_required", minimum=0)
        require_choice(self.status, "status", SESSION_STATUSES)
        if self.ends_at <= self.starts_at:
            raise DomainRuleError(
                "invalid_session_times", "ends_at must be after starts_at", kind="invalid", field="ends_at"
            )
        if self.venue_label is not None and optional_text(self.venue_label, "venue_label") != self.venue_label:
            raise DomainRuleError(
                "invalid_text", "venue_label must be trimmed and not blank", kind="invalid", field="venue_label"
            )

    @property
    def window(self) -> tuple[datetime, datetime]:
        return self.starts_at, self.ends_at


def new_session(
    session_id: str,
    exam_cycle_id: str,
    starts_at: object,
    ends_at: object,
    *,
    invigilators_required: object = 0,
    venue_label: object = None,
) -> Session:
    """A scheduled session from a contract `CreateExamSessionRequest`."""
    return Session(
        id=session_id,
        exam_cycle_id=exam_cycle_id,
        starts_at=require_instant(starts_at, "starts_at"),
        ends_at=require_instant(ends_at, "ends_at"),
        invigilators_required=require_integer(invigilators_required, "invigilators_required", minimum=0),
        venue_label=optional_text(venue_label, "venue_label"),
    )


def ensure_within_cycle(session: Session, cycle: cyc.Cycle, zone: tzinfo) -> None:
    """FR-5: a session falls within the cycle's dates, both days included. The days are read in `zone`, the
    organisation's time zone, which the caller supplies: there is no source for it in this module yet."""
    first, last = session.starts_at.astimezone(zone).date(), session.ends_at.astimezone(zone).date()
    if first < cycle.starts_on or last > cycle.ends_on:
        raise DomainRuleError(
            "session_outside_cycle",
            f"a session must fall within the cycle's dates, {cycle.starts_on} to {cycle.ends_on}",
            kind="unprocessable",
            field="starts_at",
        )


def ensure_papers_schedulable(
    papers: Iterable[pap.Paper], exam_cycle_id: str, *, papers_in_sessions: Iterable[str] = ()
) -> None:
    """FR-5: the papers of a session belong to its cycle, are still `draft`, and are in no other session: two sessions
    may not share a paper."""
    listed = list(papers)
    if not listed:
        raise DomainRuleError("no_papers", "a session needs at least one paper", kind="invalid", field="papers")
    ids = [p.id for p in listed]
    if len(set(ids)) != len(ids):
        raise DomainRuleError("duplicate_paper", "a paper is listed twice", kind="invalid", field="papers")
    taken = set(papers_in_sessions)
    for paper in listed:
        if paper.exam_cycle_id != exam_cycle_id:
            raise DomainRuleError(
                "paper_not_in_cycle", f"paper {paper.id} belongs to another cycle", kind="unprocessable", field="papers"
            )
        if paper.id in taken:
            raise DomainRuleError(
                "paper_already_scheduled",
                f"paper {paper.id} is already in a session",
                kind="conflict",
                field="papers",
                details={"exam_paper_id": paper.id},
            )
        if paper.status != pap.DRAFT:
            raise DomainRuleError(
                "paper_not_draft",
                f"paper {paper.id} is {paper.status}; only a draft paper can be scheduled",
                kind="conflict",
                field="papers",
                details={"exam_paper_id": paper.id},
            )


def ensure_open(session: Session) -> None:
    """FR-6: only a `scheduled` session can be rescheduled or cancelled."""
    if session.status != SCHEDULED:
        raise DomainRuleError(
            "session_not_scheduled",
            f"only a scheduled session can change, this one is {session.status}",
            kind="conflict",
            details={"status": session.status},
        )


def plan_reschedule(
    session: Session, *, starts_at: object | None = None, ends_at: object | None = None, venue_label: object = ...
) -> tuple[Session, list[str]]:
    """FR-6: the session after a new time or venue, and the names of the fields that changed (a change that alters
    nothing returns none). The new time must still fall within the cycle (`ensure_within_cycle`, by the caller)."""
    ensure_open(session)
    start = require_instant(starts_at, "starts_at") if starts_at is not None else session.starts_at
    end = require_instant(ends_at, "ends_at") if ends_at is not None else session.ends_at
    changes: dict[str, object] = {}
    if start != session.starts_at:
        changes["starts_at"] = start
    if end != session.ends_at:
        changes["ends_at"] = end
    if venue_label is not ...:
        venue = optional_text(venue_label, "venue_label")
        if venue != session.venue_label:
            changes["venue_label"] = venue
    if not changes:
        return session, []
    return replace(session, **changes), list(changes)  # the constructor re-checks that it still ends after it starts


def plan_cancel(session: Session, reason: object) -> Session:
    """FR-6: cancel a scheduled session, with a reason. Its papers return to draft (`papers.return_to_draft`, by the
    caller)."""
    ensure_open(session)
    return replace(session, status=CANCELLED, cancel_reason=require_text(reason, "reason", max_length=REASON_MAX))


# ---------------------------------------------------------------- duties

INVIGILATION, EVALUATION, MODERATION = "invigilation", "evaluation", "moderation"
DUTY_TYPES = (INVIGILATION, EVALUATION, MODERATION)  # contract DutyType
ASSIGNED, DUTY_CANCELLED, DUTY_COMPLETED = "assigned", "cancelled", "completed"
DUTY_STATUSES = (ASSIGNED, DUTY_CANCELLED, DUTY_COMPLETED)  # contract DutyStatus


@dataclass(frozen=True)
class Duty:
    id: str
    exam_cycle_id: str
    staff_id: str  # an identity user id (PRD 5.8); the platform-wide staff identifier is unconfirmed (Q11)
    duty_type: str
    exam_session_id: str | None = None
    exam_paper_id: str | None = None
    status: str = ASSIGNED
    cancel_reason: str | None = None

    def __post_init__(self) -> None:
        for field in ("id", "exam_cycle_id", "staff_id"):
            require_id(getattr(self, field), field)
        require_choice(self.duty_type, "duty_type", DUTY_TYPES)
        require_choice(self.status, "status", DUTY_STATUSES)
        # FR-9: invigilation needs a session; evaluation and moderation need a paper; never both.
        if self.duty_type == INVIGILATION:
            if self.exam_session_id is None or self.exam_paper_id is not None:
                raise DomainRuleError(
                    "invigilation_needs_session",
                    "invigilation needs exam_session_id and no exam_paper_id",
                    kind="invalid",
                    field="exam_session_id",
                )
            require_id(self.exam_session_id, "exam_session_id")
        else:
            if self.exam_paper_id is None or self.exam_session_id is not None:
                raise DomainRuleError(
                    "paper_duty_needs_paper",
                    f"{self.duty_type} needs exam_paper_id and no exam_session_id",
                    kind="invalid",
                    field="exam_paper_id",
                )
            require_id(self.exam_paper_id, "exam_paper_id")


def ensure_no_invigilation_clash(session: Session, staff_sessions: Iterable[Session]) -> None:
    """FR-9: a staff member cannot hold two invigilation duties in overlapping sessions. `staff_sessions` are the
    sessions of the staff member's other assigned invigilation duties; the session itself is ignored."""
    for other in staff_sessions:
        if other.id != session.id and windows_overlap(session.window, other.window):
            raise DomainRuleError(
                "invigilation_overlap",
                "the staff member already invigilates a session at that time",
                kind="conflict",
                details={"exam_session_id": other.id},
            )


def plan_duty_cancel(duty: Duty, reason: object) -> Duty:
    """FR-9: cancel an assigned duty, with a reason."""
    if duty.status != ASSIGNED:
        raise DomainRuleError(
            "duty_not_assigned", f"only an assigned duty can be cancelled, this one is {duty.status}", kind="conflict"
        )
    return replace(duty, status=DUTY_CANCELLED, cancel_reason=require_text(reason, "reason", max_length=REASON_MAX))
