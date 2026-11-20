"""The marks rules with no I/O (docs/prd.md FR-10 to FR-12): entries within 0 and the maximum, moderation deltas, and the
final marks, which are the original plus the adjustment."""

import uuid
from decimal import Decimal

import pytest
from eos_examinations.domain import marks as mk
from eos_examinations.domain.errors import DomainRuleError

MAX = Decimal(100)


def cid() -> str:
    return str(uuid.uuid4())


def refused(fn, *args) -> DomainRuleError:
    with pytest.raises(DomainRuleError) as raised:
        fn(*args)
    return raised.value


def test_entries_are_marks_within_range_or_absences():
    a, b, c = cid(), cid(), cid()
    entries = mk.parse_entries(
        [
            {"candidate_id": a, "marks_obtained": 0},
            {"candidate_id": b, "marks_obtained": 100},
            {"candidate_id": c, "absent": True},
        ],
        MAX,
    )
    assert entries == [mk.Entry(a, Decimal(0), False), mk.Entry(b, Decimal(100), False), mk.Entry(c, None, True)]
    assert mk.parse_entries([{"candidate_id": a, "marks_obtained": 12.5, "absent": False}], MAX)[
        0
    ].marks_obtained == Decimal("12.5")


@pytest.mark.parametrize(
    ("item", "kind", "code"),
    [
        ({"marks_obtained": 100.01}, "unprocessable", "marks_out_of_range"),
        ({"marks_obtained": -0.01}, "unprocessable", "marks_out_of_range"),
        ({"marks_obtained": 1.005}, "invalid", "too_many_decimals"),
        ({"marks_obtained": True}, "invalid", "invalid_number"),
        ({"marks_obtained": 5, "absent": True}, "invalid", "marks_with_absent"),
        ({}, "invalid", "marks_required"),
        ({"absent": 1}, "invalid", "invalid_boolean"),
        ({"marks_obtained": 5, "note": "x"}, "invalid", "unknown_field"),
    ],
)
def test_a_broken_entry_is_refused_with_the_contracts_kind(item, kind, code):
    error = refused(mk.parse_entries, [{"candidate_id": cid(), **item}], MAX)
    assert (error.kind, error.code) == (kind, code)


def test_the_list_of_entries_is_checked():
    a = cid()
    for bad in (None, [], "x", [5], [{"marks_obtained": 1}], [{"candidate_id": "nope", "marks_obtained": 1}]):
        assert refused(mk.parse_entries, bad, MAX).kind == "invalid"
    twice = [{"candidate_id": a, "marks_obtained": 1}, {"candidate_id": a, "absent": True}]
    assert refused(mk.parse_entries, twice, MAX).code == "duplicate_candidate"


def test_moderation_is_one_uniform_delta_or_adjustments_with_a_reason():
    a = cid()
    uniform = mk.parse_moderation({"reason": " scaling ", "uniform_delta": -2.5})
    assert uniform == mk.Moderation("scaling", Decimal("-2.5"), {})
    each = mk.parse_moderation({"reason": "r", "adjustments": [{"candidate_id": a, "delta": 3}]})
    assert each == mk.Moderation("r", None, {a: Decimal(3)})
    assert mk.parse_moderation({"reason": "r", "uniform_delta": 0}).uniform_delta == Decimal(0)  # zero is an adjustment
    for bad in (
        {},
        {"reason": "r"},
        {"reason": "r", "uniform_delta": 1, "adjustments": [{"candidate_id": a, "delta": 1}]},
        {"reason": "", "uniform_delta": 1},
        {"reason": "r" * 501, "uniform_delta": 1},
        {"reason": "r", "uniform_delta": 1.001},
        {"reason": "r", "adjustments": []},
        {"reason": "r", "adjustments": [{"candidate_id": a}]},
        {"reason": "r", "adjustments": [{"candidate_id": a, "delta": 1, "x": 2}]},
    ):
        assert refused(mk.parse_moderation, bad).kind == "invalid", bad


def test_moderated_marks_stay_within_zero_and_the_maximum():
    a = cid()
    assert mk.moderated(Decimal(70), Decimal(30), MAX, a) == Decimal(30)
    assert mk.moderated(Decimal(5), Decimal(-5), MAX, a) == Decimal(-5)
    for marks, delta in ((Decimal(70), Decimal("30.01")), (Decimal(5), Decimal("-5.01"))):
        error = refused(mk.moderated, marks, delta, MAX, a)
        assert (error.kind, error.code, error.details["candidate_id"]) == (
            "unprocessable",
            "moderated_marks_out_of_range",
            a,
        )


def test_final_marks_are_the_original_plus_the_adjustment_and_none_when_absent():
    assert mk.final_marks(Decimal(40), None) == Decimal(40)
    assert mk.final_marks(Decimal(40), Decimal("-2.5")) == Decimal("37.5")
    assert mk.final_marks(None, Decimal(5)) is None
