"""GET /faculty-load (operationId getFacultyLoad; PRD FR-13): the FacultyLoadReport for one term.

The query that reads the term and its assignment rows belongs to infrastructure, which waits for the schema
decision on issue #100; the caller passes them in. Defaulting `department_id` to the caller's department waits
for the HoD-department decision, so the department is used exactly as given.

getFacultyLoad declares 200, 403 and 404 only. The assignment rows, the configured maximum and the faculty names
come from the module's own storage, settings and platform/identity, not from the request, so invalid values there
are server faults (ValueError), never a 400 that would blame the caller."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from decimal import Decimal

from ..domain.errors import DomainRuleError
from ..domain.load import LoadEntry, faculty_load, summarise
from ..domain.terms import Term
from ..domain.values import require_number
from .access import FACULTY_LOAD_READ, Actor, require
from .errors import not_found


def _number(value: Decimal) -> int | float:
    """A contract `type: number` for JSON: whole numbers stay integers."""
    return int(value) if value == value.to_integral_value() else float(value)


def _display_name(faculty_name: Callable[[str], str], faculty_id: str) -> str:
    """FacultyLoad.faculty_name is a required string in the contract."""
    name = faculty_name(faculty_id)
    if not isinstance(name, str):
        raise ValueError(f"no display name was resolved for faculty member {faculty_id}")
    return name


def faculty_load_report(
    actor: Actor,
    *,
    period: Term | None,
    entries: Iterable[LoadEntry],
    faculty_name: Callable[[str], str],
    max_weekly_contact_hours: object,
    department_id: str | None = None,
    over_load_only: bool = False,
) -> dict:
    """The FacultyLoadReport of contracts/openapi.yaml for `period`: the requested term, or the active term when
    none was requested. `period` is None when that term does not exist, which the contract answers with 404
    `active_term_not_found`. `faculty_name` resolves a faculty member's display name (platform/identity)."""
    require(actor, FACULTY_LOAD_READ)
    if period is None:
        raise not_found("active_term_not_found", "no academic term was given and no term is active")
    try:
        maximum = require_number(max_weekly_contact_hours, "max_weekly_contact_hours", minimum=0)
        loads = faculty_load(entries, max_weekly_contact_hours=maximum)
    except DomainRuleError as err:
        raise ValueError(f"invalid faculty-load data ({err.field}): {err.message}") from err
    summary = summarise(loads, over_load_only=over_load_only)
    return {
        "academic_period_id": period.id,
        "academic_period_code": period.code,
        "academic_period_name": period.name,
        "department_id": department_id,
        "max_weekly_contact_hours": _number(maximum),
        "faculty_count": summary.faculty_count,
        "over_load_count": summary.over_load_count,
        "items": [
            {
                "faculty_id": load.faculty_id,
                "faculty_name": _display_name(faculty_name, load.faculty_id),
                "offerings_count": load.offerings_count,
                "contact_hours": _number(load.contact_hours),
                "over_load": load.over_load,
            }
            for load in summary.items
        ],
    }
