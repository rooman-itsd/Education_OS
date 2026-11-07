"""Response and resolution clocks (PRD "Clock states"):

    running --pause--> paused --resume--> running
       |                                     |
       +--stop--> stopped --reopen (resolution only)--> running
       +--cancel (also from paused)--> cancelled

`breached` is a flag set once when due_at passes; the clock keeps running until stopped. The moves here only say
whether a move is allowed; helpdesk's events drive them, and a move that does not apply is skipped, never an error.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

KINDS = ("response", "resolution")
RESPONSE, RESOLUTION = KINDS
STATES = ("running", "paused", "stopped", "cancelled")
RUNNING, PAUSED, STOPPED, CANCELLED = STATES
OUTCOMES = ("met", "breached")
MET, BREACHED = OUTCOMES
OPEN_STATES = (RUNNING, PAUSED)

# move -> (states it starts from, state it ends in)
MOVES = {
    "pause": ((RUNNING,), PAUSED),
    "resume": ((PAUSED,), RUNNING),
    "reopen": ((STOPPED,), RUNNING),
    "stop": ((RUNNING, PAUSED), STOPPED),
    "cancel": ((RUNNING, PAUSED), CANCELLED),
}


def can(move: str, state: str, kind: str) -> bool:
    """Whether `move` applies to a clock in `state`. Only a resolution clock is reopened (PRD main flow 10)."""
    sources, _ = MOVES[move]
    if move == "reopen" and kind != RESOLUTION:
        return False
    return state in sources


def target_of(move: str) -> str:
    return MOVES[move][1]


def warning_minutes(target_minutes: int, warning_percent: int) -> int:
    """Business minutes after which the warning is due: warning_percent of the target, rounded up, at least 1."""
    return max(1, math.ceil(target_minutes * warning_percent / 100))


def outcome(breached: bool) -> str:
    return BREACHED if breached else MET


def recipients(levels: Sequence[dict], level: int, assignee_id: str | None) -> list[str]:
    """Who an escalation level notifies (PRD main flow 8): the ticket's assignee if the level says so and there is
    one, plus the people named on the level, each once, in that order."""
    config = next((entry for entry in levels if entry["level"] == level), None)
    if config is None:
        return []
    people = [assignee_id] if config.get("notify_assignee", True) and assignee_id else []
    people += list(config.get("notify_person_ids") or [])
    return list(dict.fromkeys(people))


def next_level(levels: Sequence[dict], fired: int) -> dict | None:
    """The escalation level after the last one fired, if the clock's policy has one."""
    return next((entry for entry in levels if entry["level"] == fired + 1), None)
