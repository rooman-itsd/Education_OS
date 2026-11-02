"""The metric definitions: which source event feeds which metric, how a payload becomes a value and dimensions, and
what the metric is (unit, category). Versioned: a definition whose extraction changes gets a new `version`; facts
and snapshots carry it, readers use the current one, and POST /metrics/recalculate rebuilds a range.

Sources (decision on #317): admissions, academics, examinations and finance. Only modules that publish today are
wired. examinations and timetable-attendance are scaffolds with no code (their contracts declare result.published
and attendance-session.closed, but nothing publishes them), so pass-rate and attendance metrics have no source yet:
UNAVAILABLE lists them, and reports and widgets say so rather than show zeros.

Every extractor validates its payload and raises InvalidPayloadError on anything malformed, so the relay retries and
finally dead-letters the event, where an operator sees it. Dimensions are whitelisted per metric: no person ids,
names or emails ever reach a fact."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

ACADEMIC, ADMINISTRATIVE, FINANCIAL = "academic", "administrative", "financial"


class InvalidPayloadError(ValueError):
    """The event cannot be turned into a fact. Raised, never skipped: a silent skip would undercount."""


@dataclass(frozen=True)
class Contribution:
    value: Decimal
    dimensions: dict
    source_ref: str | None = None  # the source entity's own id (never a person), when a later event must find it
    reverses: str | None = None  # this event undoes the fact with this source_ref (a faculty assignment that ended)


@dataclass(frozen=True)
class Metric:
    key: str
    version: int
    source_module: str
    unit: str
    category: str
    description: str
    events: dict[str, Callable[[dict], Contribution]]


def _id(payload: dict, field: str, *, required: bool = True) -> str | None:
    value = payload.get(field)
    if value is None or value == "":
        if required:
            raise InvalidPayloadError(f"{field} is missing")
        return None
    if not isinstance(value, str) or len(value) > 64:
        raise InvalidPayloadError(f"{field} is not an id")
    return value


def _amount(payload: dict, field: str) -> Decimal:
    try:
        value = Decimal(str(payload[field]))
    except (KeyError, InvalidOperation) as e:
        raise InvalidPayloadError(f"{field} is not an amount") from e
    if not value.is_finite() or value < 0:
        raise InvalidPayloadError(f"{field} must be a non-negative amount")
    return value


def _year(payload: dict) -> str | None:
    year = payload.get("academic_year")
    if year is not None and (not isinstance(year, str) or len(year) > 16):
        raise InvalidPayloadError("academic_year is not a year label")
    return year


def _count(dimensions: dict) -> Contribution:
    return Contribution(Decimal(1), {k: v for k, v in dimensions.items() if v is not None})


def _programme_year(p: dict) -> Contribution:
    return _count({"programme_id": _id(p, "programme_id"), "academic_year": _year(p)})


ONE = Decimal(1)

METRICS: tuple[Metric, ...] = (
    # --- admissions (modules/student-lifecycle/admissions) -----------------------------------------------------
    Metric("admissions.applications_submitted", 1, "admissions", "count", ADMINISTRATIVE,
           "Applications submitted, by programme and academic year",
           {"admissions.application.submitted": _programme_year}),
    Metric("admissions.offers_made", 1, "admissions", "count", ADMINISTRATIVE,
           "Admission offers made", {"admissions.offer.made": lambda p: (_id(p, "offer_id"), _count({}))[1]}),
    Metric("admissions.applications_accepted", 1, "admissions", "count", ADMINISTRATIVE,
           "Offers accepted (enrolments), by programme and academic year",
           {"admissions.application.accepted": _programme_year}),
    Metric("admissions.applications_declined", 1, "admissions", "count", ADMINISTRATIVE,
           "Applications declined", {"admissions.application.declined": lambda p: (_id(p, "application_id"), _count({}))[1]}),
    # --- academics (modules/academics/academic-management) -----------------------------------------------------
    Metric("academics.course_offerings", 1, "academic-management", "count", ACADEMIC,
           "Course offerings created, by department and academic period",
           {"academic-management.offering.created": lambda p: Contribution(
               ONE,
               {"department_id": _id(p, "department_id"), "academic_period_id": _id(p, "academic_period_id")},
               source_ref=_id(p, "course_offering_id"),
           )}),
    Metric("academics.faculty_contact_hours", 1, "academic-management", "hours", ACADEMIC,
           "Weekly contact hours assigned to faculty, by department (an ended assignment releases its hours)",
           {"academic-management.faculty-assignment.created": lambda p: Contribution(
               _amount(p, "contact_hours"), {"course_offering_id": _id(p, "course_offering_id")},
               source_ref=_id(p, "instructor_assignment_id"),
           ),
            "academic-management.faculty-assignment.ended": lambda p: Contribution(
               Decimal(0), {}, reverses=_id(p, "instructor_assignment_id"),
           )}),
    # --- finance (modules/finance-operations/fees-accounts): financial, needs reporting:report:execute ----------
    Metric("finance.fees_invoiced", 1, "fees-accounts", "amount", FINANCIAL, "Fee invoices issued (total)",
           {"fees-accounts.invoice.issued": lambda p: Contribution(_amount(p, "total"), {})}),
    Metric("finance.fees_collected", 1, "fees-accounts", "amount", FINANCIAL,
           "Payments received, net of voided payments",
           {"fees-accounts.payment.received": lambda p: Contribution(
               _amount(p, "amount"), {"mode": p.get("mode")}, source_ref=_id(p, "payment_id"),
           ),
            # A void takes back the payment it names, in that payment's own mode: the reversal copies the original
            # fact's dimensions, so the per-mode figure goes down and no cell without a mode is ever created. The
            # amount is still validated, so a malformed event is dead-lettered like any other; the value booked is
            # the original's (ingest.py), not the payload's.
            "fees-accounts.payment.voided": lambda p: Contribution(
               -_amount(p, "amount"), {}, reverses=_id(p, "payment_id"),
           )}),
    Metric("finance.refunds_issued", 1, "fees-accounts", "amount", FINANCIAL, "Refunds issued",
           {"fees-accounts.refund.issued": lambda p: Contribution(_amount(p, "amount"), {})}),
    Metric("finance.concessions_approved", 1, "fees-accounts", "amount", FINANCIAL, "Concessions approved, by kind",
           {"fees-accounts.concession.approved": lambda p: Contribution(_amount(p, "approved_amount"), {"kind": p.get("kind")})}),
    Metric("finance.invoices_cancelled", 1, "fees-accounts", "count", FINANCIAL, "Fee invoices cancelled",
           {"fees-accounts.invoice.cancelled": lambda p: (_id(p, "invoice_id"), _count({}))[1]}),
)  # fmt: skip

BY_KEY: dict[str, Metric] = {m.key: m for m in METRICS}

# What the standard reports and widgets would need but no module publishes yet
UNAVAILABLE: dict[str, str] = {
    "attendance": "modules/academics/timetable-attendance publishes no events yet (no code)",
    "exam_results": "modules/academics/examinations publishes no events yet (no code)",
}


def for_event(name: str) -> list[tuple[Metric, Callable[[dict], Contribution]]]:
    return [(m, m.events[name]) for m in METRICS if name in m.events]


def source_events() -> list[str]:
    return sorted({name for m in METRICS for name in m.events})
