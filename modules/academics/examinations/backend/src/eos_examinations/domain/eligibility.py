"""Candidate eligibility (docs/prd.md FR-7), as rules independent of FastAPI and SQLAlchemy.

A candidate's status is decided from four inputs, in this order, each failing with its own reason: registration in the
offering, student status, attendance and dues. An input whose source is not available leaves the candidate `pending`: it
never counts as eligible silently, and it adds no reason. The cycle's own examination rules (the PRD's fifth input) have
no definition yet and are not an input.

Registration types (decision D2, issue #325): enrolment-registration registers `regular`, `supplementary` and `backlog`
students. A `regular` registration makes a student a candidate in the papers of a cycle that is not `supplementary`;
`supplementary` and `backlog` registrations make a student a candidate in the papers of a `supplementary` cycle, and only
there. A registration of another type for the cycle's kind makes no candidate. This pairing is this module's rule, not
enrolment-registration's: how supplementary and backlog students are registered is still open with Praveen (Q1)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

PENDING, ELIGIBLE, INELIGIBLE = "pending", "eligible", "ineligible"
ELIGIBILITY_STATUSES = (PENDING, ELIGIBLE, INELIGIBLE)  # contract EligibilityStatus

REGISTRATION, STUDENT_STATUS, ATTENDANCE, DUES = "registration", "student_status", "attendance", "dues"
INPUTS = (REGISTRATION, STUDENT_STATUS, ATTENDANCE, DUES)  # contract pending_inputs, in the order FR-7 applies them

PASSED, FAILED, UNAVAILABLE, NOT_REQUIRED = "passed", "failed", "unavailable", "not_required"

# The reason an input adds when it fails (contract EligibilityReasonCode).
REASON_CODE = {
    REGISTRATION: "not_registered",
    STUDENT_STATUS: "student_status",
    ATTENDANCE: "attendance_shortage",
    DUES: "dues_outstanding",
}

REGULAR, SUPPLEMENTARY, BACKLOG = "regular", "supplementary", "backlog"
REGISTRATION_TYPES = (REGULAR, SUPPLEMENTARY, BACKLOG)  # enrolment-registration's RegistrationType
SUPPLEMENTARY_CYCLE = "supplementary"  # contract CycleType


def registration_makes_candidate(cycle_type: str, registration_type: str) -> bool:
    """Decision D2: whether a registration of this type puts the student in the papers of a cycle of this type."""
    if cycle_type == SUPPLEMENTARY_CYCLE:
        return registration_type in (SUPPLEMENTARY, BACKLOG)
    return registration_type == REGULAR


def attendance_input(percent: Decimal | None, minimum: Decimal | None) -> str:
    """The attendance input against the cycle's own minimum (decision D7: `min_attendance_percent` of the exam cycle, never a
    constant). Not required when the cycle sets no minimum; unavailable when it sets one and no reading is available; the
    minimum itself passes (`at least`)."""
    if minimum is None:
        return NOT_REQUIRED
    if percent is None:
        return UNAVAILABLE
    return PASSED if percent >= minimum else FAILED


@dataclass(frozen=True)
class Decision:
    status: str
    reasons: tuple[dict, ...]  # contract EligibilityReason: {code, detail}
    pending_inputs: tuple[str, ...]


DETAIL = {
    REGISTRATION: "the student holds no confirmed registration in the offering",
    STUDENT_STATUS: "the student's status does not allow sitting the exam",
    ATTENDANCE: "attendance is below the cycle's minimum",
    DUES: "dues are outstanding",
}


def decide(outcomes: dict[str, str]) -> Decision:
    """Ineligible when any input failed (a reason per failed input, in FR-7's order); otherwise pending while any input is
    unavailable; otherwise eligible. `pending_inputs` lists what is unavailable, whichever way the decision went."""
    failed = [name for name in INPUTS if outcomes.get(name) == FAILED]
    pending = tuple(name for name in INPUTS if outcomes.get(name) == UNAVAILABLE)
    reasons = tuple({"code": REASON_CODE[name], "detail": DETAIL[name]} for name in failed)
    if failed:
        return Decision(INELIGIBLE, reasons, pending)
    return Decision(PENDING if pending else ELIGIBLE, (), pending)
