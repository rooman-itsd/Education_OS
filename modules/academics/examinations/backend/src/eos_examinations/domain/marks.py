"""Mark entry, moderation and locking rules (docs/prd.md FR-10 to FR-12, contracts/openapi.yaml), with no I/O.

- Marks are between 0 and the paper's `max_marks`, or the candidate is `absent` (FR-10). Marks and `absent` are exclusive.
- A moderation adjustment is a delta to the *original* marks, either one uniform delta for the paper or one delta per
  candidate, always with a reason; the original marks are kept and the result stays within 0 and `max_marks` (FR-11).
  A later moderation replaces the delta, it does not add to it. An absent candidate has no marks to adjust.
- Values have at most two decimal places, the precision the marks are stored with: nothing is rounded silently.

Not decided here, and not invented: how a moderation is "completed" (there is no such flag in the schema or the contract;
the paper's status `moderation` is the whole state), and any rule of the department head's own scope (PRD Q13)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .errors import DomainRuleError
from .values import require_bool, require_id, require_number, require_text

ENTERED, MODERATED, LOCKED = "entered", "moderated", "locked"  # contract MarkStatus
REASON_MAX = 500
PLACES = Decimal("0.01")


@dataclass(frozen=True)
class Entry:
    candidate_id: str
    marks_obtained: Decimal | None
    absent: bool


def _two_places(value: Decimal, field: str) -> Decimal:
    if value != value.quantize(PLACES):
        raise DomainRuleError(
            "too_many_decimals", f"{field} has at most two decimal places", kind="invalid", field=field
        )
    return value


def final_marks(marks_obtained: Decimal | None, moderation_delta: Decimal | None) -> Decimal | None:
    """The marks that count: the original plus the moderation adjustment. None for an absent candidate."""
    if marks_obtained is None:
        return None
    return marks_obtained + (moderation_delta or Decimal(0))


def parse_entries(raw: object, max_marks: Decimal) -> list[Entry]:
    """The `entries` of EnterMarksRequest: each names a candidate once and has marks within 0 and `max_marks`, or is
    absent. Out-of-range marks are the contract's 422; a malformed entry is the contract's 400."""
    if not isinstance(raw, list) or not raw:
        raise DomainRuleError("invalid_entries", "entries must be a non-empty list", kind="invalid", field="entries")
    entries: list[Entry] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        where = f"entries[{i}]"
        if not isinstance(item, dict):
            raise DomainRuleError("invalid_entries", f"{where} must be an object", kind="invalid", field=where)
        unknown = set(item) - {"candidate_id", "marks_obtained", "absent"}
        if unknown:
            raise DomainRuleError(
                "unknown_field", f"{where} has no field {sorted(unknown)[0]}", kind="invalid", field=where
            )
        if "candidate_id" not in item:
            raise DomainRuleError(
                "required_field", f"{where}.candidate_id is required", kind="invalid", field=f"{where}.candidate_id"
            )
        candidate_id = require_id(item["candidate_id"], f"{where}.candidate_id")
        if candidate_id in seen:
            raise DomainRuleError(
                "duplicate_candidate", f"{candidate_id} appears twice", kind="invalid", field=f"{where}.candidate_id"
            )
        seen.add(candidate_id)
        absent = require_bool(item["absent"], f"{where}.absent") if "absent" in item else False
        if absent and "marks_obtained" in item:
            raise DomainRuleError(
                "marks_with_absent",
                f"{where}: marks_obtained is omitted when absent is true",
                kind="invalid",
                field=f"{where}.marks_obtained",
            )
        if absent:
            entries.append(Entry(candidate_id, None, True))
            continue
        if "marks_obtained" not in item:
            raise DomainRuleError(
                "marks_required",
                f"{where}: give marks_obtained, or absent true",
                kind="invalid",
                field=f"{where}.marks_obtained",
            )
        marks = _two_places(
            require_number(item["marks_obtained"], f"{where}.marks_obtained"), f"{where}.marks_obtained"
        )
        if marks < 0 or marks > max_marks:
            raise DomainRuleError(
                "marks_out_of_range",
                f"{where}.marks_obtained must be between 0 and {max_marks.normalize():f}",
                kind="unprocessable",
                field=f"{where}.marks_obtained",
                details={"max_marks": float(max_marks)},
            )
        entries.append(Entry(candidate_id, marks, False))
    return entries


@dataclass(frozen=True)
class Moderation:
    reason: str
    uniform_delta: Decimal | None
    adjustments: dict[str, Decimal]  # candidate id -> delta


def parse_moderation(data: dict) -> Moderation:
    """ModerationRequest: a reason and either `uniform_delta` or `adjustments`, not both and not neither."""
    reason = require_text(data.get("reason"), "reason", max_length=REASON_MAX)
    has_uniform, has_each = "uniform_delta" in data, "adjustments" in data
    if has_uniform == has_each:
        raise DomainRuleError(
            "moderation_kind",
            "give either uniform_delta or adjustments",
            kind="invalid",
            field="uniform_delta" if has_each else "adjustments",
        )
    if has_uniform:
        delta = _two_places(require_number(data["uniform_delta"], "uniform_delta"), "uniform_delta")
        return Moderation(reason, delta, {})
    raw = data["adjustments"]
    if not isinstance(raw, list) or not raw:
        raise DomainRuleError(
            "invalid_adjustments", "adjustments must be a non-empty list", kind="invalid", field="adjustments"
        )
    each: dict[str, Decimal] = {}
    for i, item in enumerate(raw):
        where = f"adjustments[{i}]"
        if not isinstance(item, dict) or set(item) != {"candidate_id", "delta"}:
            raise DomainRuleError(
                "invalid_adjustments", f"{where} needs candidate_id and delta only", kind="invalid", field=where
            )
        candidate_id = require_id(item["candidate_id"], f"{where}.candidate_id")
        if candidate_id in each:
            raise DomainRuleError(
                "duplicate_candidate", f"{candidate_id} appears twice", kind="invalid", field=f"{where}.candidate_id"
            )
        each[candidate_id] = _two_places(require_number(item["delta"], f"{where}.delta"), f"{where}.delta")
    return Moderation(reason, None, each)


def moderated(marks_obtained: Decimal, delta: Decimal, max_marks: Decimal, candidate_id: str) -> Decimal:
    """The delta, if the original plus it stays within 0 and `max_marks` (422 otherwise)."""
    final = marks_obtained + delta
    if final < 0 or final > max_marks:
        raise DomainRuleError(
            "moderated_marks_out_of_range",
            f"moderated marks must stay between 0 and {max_marks.normalize():f}",
            kind="unprocessable",
            details={"candidate_id": candidate_id, "marks_obtained": float(marks_obtained), "delta": float(delta)},
        )
    return delta
