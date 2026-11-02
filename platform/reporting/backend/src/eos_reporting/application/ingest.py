"""MetricSnapshot ingestion through the event bus (decision on #317).

Each source event the metric definitions name (metrics.py) becomes one MetricFact per metric, then the snapshot
cell it falls in (organisation, metric, month, dimensions) is recalculated from the facts. So:
- idempotent: a fact is unique per (source event, metric); a redelivered event adds nothing and recalculates the
  same value;
- tenant-isolated: facts and snapshots carry the event's organisation_id under row-level security, and the relay
  runs this in the event's organisation;
- recalculable: recalculate() rebuilds any period range from the facts (historical recalculation, or after a
  metric definition's version changes);
- validated: a malformed payload raises InvalidPayloadError, so the relay retries and finally dead-letters it;
- aggregate-only: dimensions are each metric's whitelisted keys, never a person's id, name or email."""

from __future__ import annotations

import calendar
import json
import logging
from datetime import UTC, date, datetime
from decimal import Decimal

from eos_core.db import utcnow
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.models import MetricFact, MetricSnapshot
from . import metrics
from .metrics import BY_KEY, InvalidPayloadError, Metric

log = logging.getLogger("eos.reporting")

UNKNOWN = (
    "unknown"  # a dimension whose value the events have not told us yet (e.g. an offering created before ingestion)
)


def month_of(moment: datetime) -> tuple[date, date]:
    moment = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
    d = moment.astimezone(UTC).date()
    return date(d.year, d.month, 1), date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def dimensions_key(dimensions: dict) -> str:
    return json.dumps(dimensions, sort_keys=True, separators=(",", ":"))


def _clean(dimensions: dict) -> dict:
    out = {}
    for key, value in dimensions.items():
        if value is None:
            continue
        if not isinstance(value, str) or len(value) > 64:
            raise InvalidPayloadError(f"dimension {key} is not a short label")
        out[key] = value
    return out


def _department_of_offering(db: Session, organisation_id: str, offering_id: str) -> str:
    """academic-management's faculty-assignment events name the offering, not the department: the offering's
    department is in its own course_offerings fact (source_ref = the offering's id)."""
    dims = db.scalar(
        select(MetricFact.dimensions).where(
            MetricFact.organisation_id == organisation_id,
            MetricFact.metric_key == "academics.course_offerings",
            MetricFact.source_ref == offering_id,
        )
    )
    return (dims or {}).get("department_id") or UNKNOWN


def on_event(db: Session, event) -> None:
    ingest(db, event)


def ingest(db: Session, event) -> int:
    """Facts for every metric this event feeds; returns how many were new."""
    payload = event.payload or {}
    organisation_id = event.organisation_id or payload.get("organisation_id")
    if not organisation_id:
        return 0  # every source is a tenant event; a platform event feeds no organisation's metric
    occurred_at = event.occurred_at or utcnow()
    new = 0
    for metric, extract in metrics.for_event(event.name):
        contribution = extract(payload)
        value, dims, source_ref = contribution.value, dict(contribution.dimensions), contribution.source_ref
        if contribution.reverses:
            original = db.scalar(
                select(MetricFact).where(
                    MetricFact.organisation_id == organisation_id,
                    MetricFact.metric_key == metric.key,
                    MetricFact.source_ref == contribution.reverses,
                    MetricFact.value > 0,
                )
            )
            if original is None:
                continue  # its creation predates ingestion: nothing to release
            value, dims = -original.value, dict(original.dimensions)
        if "course_offering_id" in dims:
            dims = {
                "department_id": _department_of_offering(db, organisation_id, dims.pop("course_offering_id")),
                **dims,
            }
        dims = _clean(dims)
        fact = MetricFact(
            organisation_id=organisation_id,
            source_module=metric.source_module,
            metric_key=metric.key,
            metric_version=metric.version,
            source_event_id=event.id,
            source_ref=source_ref,
            occurred_at=occurred_at,
            dimensions=dims,
            dimensions_key=dimensions_key(dims),
            value=value,
        )
        try:
            with db.begin_nested():
                db.add(fact)
                db.flush()
        except IntegrityError:
            continue  # this event already fed this metric
        new += 1
        start, end = month_of(occurred_at)
        recalculate_cell(db, organisation_id, metric, start, end, dims)
    return new


def recalculate_cell(db: Session, organisation_id: str, metric: Metric, start: date, end: date, dims: dict) -> None:
    key = dimensions_key(dims)
    total = db.scalar(
        select(func.coalesce(func.sum(MetricFact.value), 0)).where(
            MetricFact.organisation_id == organisation_id,
            MetricFact.metric_key == metric.key,
            MetricFact.metric_version == metric.version,
            MetricFact.dimensions_key == key,
            MetricFact.occurred_at >= datetime(start.year, start.month, start.day, tzinfo=UTC),
            MetricFact.occurred_at < datetime(end.year, end.month, end.day, tzinfo=UTC) + _ONE_DAY,
        )
    )
    _upsert(db, organisation_id, metric, start, end, dims, key, Decimal(total))


_ONE_DAY = datetime(2000, 1, 2) - datetime(2000, 1, 1)


def _upsert(db, organisation_id, metric: Metric, start, end, dims, key, value) -> None:
    where = (
        MetricSnapshot.organisation_id == organisation_id,
        MetricSnapshot.metric_key == metric.key,
        MetricSnapshot.period_start == start,
        MetricSnapshot.period_end == end,
        MetricSnapshot.dimensions_key == key,
        MetricSnapshot.schema_version == metric.version,
    )
    for _attempt in range(2):
        row = db.scalar(select(MetricSnapshot).where(*where))
        if row is not None:
            row.value, row.calculated_at = value, utcnow()
            db.flush()
            return
        try:
            with db.begin_nested():
                db.add(
                    MetricSnapshot(
                        organisation_id=organisation_id,
                        source_module=metric.source_module,
                        metric_key=metric.key,
                        period_start=start,
                        period_end=end,
                        dimensions=dims,
                        dimensions_key=key,
                        value=value,
                        unit=metric.unit,
                        calculated_at=utcnow(),
                        schema_version=metric.version,
                    )
                )
                db.flush()
            return
        except IntegrityError:
            continue  # another ingestion created the cell first: update it instead


def recalculate(db: Session, organisation_id: str, start: date, end: date, metric_key: str | None = None) -> int:
    """Rebuild this organisation's snapshots for every month from start to end (historical recalculation), from
    the facts of each metric's current version. Returns the cells written."""
    chosen = [BY_KEY[metric_key]] if metric_key else list(metrics.METRICS)
    first, _ = month_of(datetime(start.year, start.month, 1, tzinfo=UTC))
    _, last = month_of(datetime(end.year, end.month, 1, tzinfo=UTC))
    written = 0
    for metric in chosen:
        db.execute(
            delete(MetricSnapshot).where(
                MetricSnapshot.organisation_id == organisation_id,
                MetricSnapshot.metric_key == metric.key,
                MetricSnapshot.period_start >= first,
                MetricSnapshot.period_end <= last,
            )
        )
        facts = db.scalars(
            select(MetricFact).where(
                MetricFact.organisation_id == organisation_id,
                MetricFact.metric_key == metric.key,
                MetricFact.metric_version == metric.version,
                MetricFact.occurred_at >= datetime(first.year, first.month, 1, tzinfo=UTC),
                MetricFact.occurred_at < datetime(last.year, last.month, last.day, tzinfo=UTC) + _ONE_DAY,
            )
        )
        cells: dict[tuple, tuple[dict, Decimal]] = {}
        for fact in facts:
            s, e = month_of(fact.occurred_at)
            dims, total = cells.get((s, e, fact.dimensions_key), (fact.dimensions, Decimal(0)))
            cells[(s, e, fact.dimensions_key)] = (dims, total + fact.value)
        for (s, e, key), (dims, total) in cells.items():
            _upsert(db, organisation_id, metric, s, e, dims, key, total)
            written += 1
    db.flush()
    return written


CONSUMERS = dict.fromkeys(metrics.source_events(), on_event)
