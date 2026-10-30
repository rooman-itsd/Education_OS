"""Status vocabularies from contracts/openapi.yaml, and the statuses academic-management publishes for offerings and
sections (its contracts/events.yaml)."""

from __future__ import annotations

ACTIVE = "active"
COMPLETED = "completed"
WITHDRAWN = "withdrawn"
ENROLMENT_STATUSES = (ACTIVE, COMPLETED, WITHDRAWN)
ENROLMENT_ENDED = frozenset({COMPLETED, WITHDRAWN})

REGULAR = "regular"
SUPPLEMENTARY = "supplementary"
BACKLOG = "backlog"
REGISTRATION_TYPES = (REGULAR, SUPPLEMENTARY, BACKLOG)
# Supplementary and backlog registrations happen around exam cycles, so the term's window does not apply to them.
WINDOW_EXEMPT = frozenset({SUPPLEMENTARY, BACKLOG})

CONFIRMED = "confirmed"
REGISTRATION_STATUSES = (CONFIRMED, WITHDRAWN)

# academic-management: offerings move planned -> open -> in_progress -> completed, or to cancelled; sections are
# open or closed. Only `open` accepts registrations, the same rule its roster applies.
OPEN = "open"
OFFERING_STATUSES = ("planned", OPEN, "in_progress", "completed", "cancelled")
SECTION_STATUSES = (OPEN, "closed")
