"""Exam papers (contract `ExamPaper`; PRD 5.4, FR-4, FR-6): one examined component of a course offering in one cycle, and
its marks-pipeline status `draft` to `scheduled` to `marks_entry` to `moderation` to `locked`."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from decimal import Decimal

from . import assessment as asm
from . import cycles as cyc
from .errors import DomainRuleError
from .values import require_choice, require_id, require_integer

DRAFT, SCHEDULED, MARKS_ENTRY, MODERATION, LOCKED = "draft", "scheduled", "marks_entry", "moderation", "locked"
PAPER_STATUSES = (DRAFT, SCHEDULED, MARKS_ENTRY, MODERATION, LOCKED)  # contract PaperStatus, in pipeline order


@dataclass(frozen=True)
class Paper:
    id: str
    exam_cycle_id: str
    course_offering_id: str
    assessment_component_id: str
    max_marks: Decimal
    duration_minutes: int | None = None
    status: str = DRAFT

    def __post_init__(self) -> None:
        for field in ("id", "exam_cycle_id", "course_offering_id", "assessment_component_id"):
            require_id(getattr(self, field), field)
        require_choice(self.status, "status", PAPER_STATUSES)
        if self.max_marks <= 0:
            raise DomainRuleError("invalid_max_marks", "max_marks must be above 0", kind="invalid", field="max_marks")
        if self.duration_minutes is not None:
            require_integer(self.duration_minutes, "duration_minutes", minimum=1)


def plan_papers(
    cycle: cyc.Cycle,
    scheme: asm.Scheme,
    component_ids: Mapping[str, str],
    requested: Iterable[Mapping],
    *,
    paper_id,
    existing_component_ids: Iterable[str] = (),
) -> list[Paper]:
    """FR-4: one paper per listed component of the course offering's *active* assessment scheme, in a cycle that can
    still be configured. `component_ids` maps the scheme's component codes to their ids; `requested` items are
    `{component_code, duration_minutes?}`; `existing_component_ids` are components that already have a paper in this
    cycle (one paper per component and cycle). `max_marks` is the component's."""
    cyc.ensure_configurable(cycle)
    if scheme.status != asm.ACTIVE:
        raise DomainRuleError(
            "scheme_not_active", "papers are created from the active assessment scheme", kind="unprocessable"
        )
    by_code = {c.code: c for c in scheme.components}
    taken = set(existing_component_ids)
    seen: set[str] = set()
    papers: list[Paper] = []
    for index, item in enumerate(requested):
        code = item.get("component_code") if isinstance(item, Mapping) else None
        where = f"papers[{index}].component_code"
        if not isinstance(code, str) or code not in by_code or code not in component_ids:
            raise DomainRuleError(
                "unknown_component",
                f"{code!r} is not a component of the active scheme",
                kind="unprocessable",
                field=where,
            )
        if code in seen:
            raise DomainRuleError(
                "duplicate_component", f"component {code} is listed twice", kind="invalid", field=where
            )
        seen.add(code)
        if component_ids[code] in taken:
            raise DomainRuleError(
                "paper_exists", f"component {code} already has a paper in this cycle", kind="conflict", field=where
            )
        papers.append(
            Paper(
                id=paper_id(),
                exam_cycle_id=cycle.id,
                course_offering_id=scheme.course_offering_id,
                assessment_component_id=component_ids[code],
                max_marks=by_code[code].max_marks,
                duration_minutes=item.get("duration_minutes"),
            )
        )
    if not papers:
        raise DomainRuleError("no_papers", "list at least one component", kind="invalid", field="papers")
    return papers


def plan_status_change(paper: Paper, to_status: object) -> Paper:
    """The marks pipeline moves forward one status at a time."""
    target = require_choice(to_status, "status", PAPER_STATUSES)
    index = PAPER_STATUSES.index(paper.status)
    expected = PAPER_STATUSES[index + 1] if index + 1 < len(PAPER_STATUSES) else None
    if target != expected:
        raise DomainRuleError(
            "invalid_status_transition",
            f"a {paper.status} paper can only move to {expected}" if expected else "locked marks do not move on",
            kind="conflict",
            details={"from": paper.status, "to": target, "allowed": expected},
        )
    return replace(paper, status=target)


def return_to_draft(paper: Paper) -> Paper:
    """FR-6: cancelling a session returns its papers to `draft` so that they can be rescheduled. Only a scheduled paper
    goes back; once marks are being entered the paper has been sat."""
    if paper.status != SCHEDULED:
        raise DomainRuleError(
            "paper_not_scheduled",
            f"only a scheduled paper returns to draft, this one is {paper.status}",
            kind="conflict",
        )
    return replace(paper, status=DRAFT)
