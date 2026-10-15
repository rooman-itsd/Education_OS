"""GET /faculty-load (operationId getFacultyLoad; PRD FR-13): the FacultyLoadReport for one term.

The query that reads the term and its assignment rows belongs to infrastructure, which waits for the schema
decision on issue #100; the caller passes them in. Defaulting `department_id` to the caller's department waits
for the HoD-department decision, so the department is used exactly as given."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from decimal import Decimal

from ..domain.errors import DomainRuleError
from ..domain.load import LoadEntry, faculty_load, summarise
from ..domain.terms import Term
from .access import FACULTY_LOAD_READ, Actor, require
from .errors import from_domain, not_found


def _number(value: Decimal) -> int | float:
    """A contract `type: number` for JSON: whole numbers stay integers."""
    return int(value) if value == value.to_integral_value() else float(value)


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
        loads = faculty_load(entries, max_weekly_contact_hours=max_weekly_contact_hours)
    except DomainRuleError as err:
        raise from_domain(err) from err
    summary = summarise(loads, over_load_only=over_load_only)
    return {
        "academic_period_id": period.id,
        "academic_period_code": period.code,
        "academic_period_name": period.name,
        "department_id": department_id,
        "max_weekly_contact_hours": _number(Decimal(str(max_weekly_contact_hours))),
        "faculty_count": summary.faculty_count,
        "over_load_count": summary.over_load_count,
        "items": [
            {
                "faculty_id": load.faculty_id,
                "faculty_name": faculty_name(load.faculty_id),
                "offerings_count": load.offerings_count,
                "contact_hours": _number(load.contact_hours),
                "over_load": load.over_load,
            }
            for load in summary.items
        ],
    }
