"""The open-incident counts behind the Support Staff widget incident-management.open (GET /stats/open, PRD
"Dashboard widget"): incidents in open, investigating or mitigated, by severity and by status, with the total."""

from __future__ import annotations

from dataclasses import dataclass

from .incidents import ACTIVE_STATUSES, SEVERITIES


@dataclass(frozen=True)
class SeverityCount:
    """One row of contract OpenCounts.by_severity, in its field order."""

    severity: str
    count: int


@dataclass(frozen=True)
class StatusCount:
    """One row of contract OpenCounts.by_status, in its field order."""

    status: str
    count: int


@dataclass(frozen=True)
class OpenCounts:
    """Contract OpenCounts, in its field order."""

    total_open: int
    by_severity: list[SeverityCount]
    by_status: list[StatusCount]


def open_counts(incidents: list[tuple[str, str]]) -> OpenCounts:
    """From the (status, severity) of the organisation's incidents. Only open, investigating and mitigated ones count.
    One row per severity, critical first, and one per counted status, zero counts included."""
    active = [(st, sev) for st, sev in incidents if st in ACTIVE_STATUSES]
    return OpenCounts(
        total_open=len(active),
        by_severity=[SeverityCount(s, sum(1 for _, sev in active if sev == s)) for s in SEVERITIES],
        by_status=[StatusCount(s, sum(1 for st, _ in active if st == s)) for s in ACTIVE_STATUSES],
    )
