"""Result rules with no I/O (domain/results.py): the weighted percentage, the band, pass and fail, the grade point average
and the corrections of a revision."""

from decimal import Decimal

import pytest
from eos_examinations.domain import results as rs
from eos_examinations.domain.errors import DomainRuleError
from eos_examinations.domain.grading import Band

D = Decimal
BANDS = [
    Band(D(0), D(40), "F", D(0), False),
    Band(D(40), D(100), "P", D(6), True),
    Band(D(75), D(100), "D", D(9), True),
]


def comp(code, weight, marks, *, max_marks=100, pass_marks=None, absent=False):
    return rs.Component(
        code,
        D(weight),
        D(max_marks),
        None if pass_marks is None else D(pass_marks),
        None if absent else D(marks),
        absent,
    )


def test_the_weighted_percentage_follows_each_components_weight_and_maximum():
    parts = [comp("INT", 40, 30, max_marks=50), comp("END", 60, 70)]
    assert rs.weighted_percent(parts) == D("66.00")  # 40 * 30/50 + 60 * 70/100


def test_an_absent_component_adds_nothing_and_the_percentage_rounds_half_up_to_two_places():
    assert rs.weighted_percent([comp("INT", 40, 0, absent=True), comp("END", 60, 70)]) == D("42.00")
    assert rs.weighted_percent([comp("END", 100, D("33.335"))]) == D("33.34")


def test_where_bands_touch_the_higher_minimum_wins_and_a_gap_is_an_error():
    assert rs.band_for(BANDS, D(40)).grade == "P"
    assert rs.band_for(BANDS, D(39.99)).grade == "F"
    assert rs.band_for(BANDS, D(75)).grade == "D"
    gap = [Band(D(0), D(39), "F", D(0), False), Band(D(41), D(100), "P", D(6), True)]
    with pytest.raises(DomainRuleError) as caught:
        rs.band_for(gap, D(40))
    assert caught.value.code == "no_grading_band" and caught.value.kind == "unprocessable"


def test_a_result_passes_only_when_the_percentage_every_minimum_and_the_band_all_pass():
    assert rs.compute([comp("END", 100, 50)], D(40), BANDS).passed is True
    assert rs.compute([comp("END", 100, 39)], D(40), BANDS).passed is False  # under the overall requirement
    held = [comp("INT", 40, 5, pass_marks=10), comp("END", 60, 100)]  # 62%, but INT is under its minimum
    outcome = rs.compute(held, D(40), BANDS)
    assert outcome.passed is False and outcome.grade == "P"
    assert [c["passed"] for c in outcome.components] == [False, None]  # null: END has no minimum
    absent = rs.compute([comp("INT", 40, 0, pass_marks=10, absent=True), comp("END", 60, 100)], D(40), BANDS)
    assert absent.passed is False and absent.components[0]["absent"] is True
    only_fail_band = [Band(D(0), D(100), "F", D(0), False)]
    assert rs.compute([comp("END", 100, 90)], D(40), only_fail_band).passed is False  # a fail band is not a pass


def test_the_average_is_weighted_by_credits_and_unknown_when_a_credit_is_missing():
    assert rs.grade_point_average([(D(10), D(4)), (D(6), D(2))]) == D("8.67")
    assert rs.grade_point_average([(D(10), D(4)), (D(6), None)]) is None
    assert rs.grade_point_average([]) is None
    assert rs.grade_point_average([(D(10), D(0))]) is None


SCHEME = {"INT": comp("INT", 40, 0), "END": comp("END", 60, 0)}
PREVIOUS = [
    {"component_code": "INT", "final_marks": 50.0, "max_marks": 100.0, "absent": False, "passed": None},
    {"component_code": "END", "final_marks": None, "max_marks": 100.0, "absent": True, "passed": None},
]


def test_a_revision_replaces_the_listed_components_and_keeps_the_rest():
    parts = rs.revise(PREVIOUS, [{"component_code": "END", "final_marks": 80}], SCHEME)
    assert [(p.code, p.final_marks, p.absent) for p in parts] == [("INT", D(50), False), ("END", D(80), False)]


@pytest.mark.parametrize(
    ("corrections", "kind", "code"),
    [
        (None, "invalid", "invalid_components"),
        ([], "invalid", "invalid_components"),
        ([{"component_code": "END"}], "invalid", "invalid_components"),
        ([{"component_code": "END", "final_marks": "x"}], "invalid", "invalid_components"),
        ([{"component_code": "END", "final_marks": True}], "invalid", "invalid_components"),
        (
            [{"component_code": "END", "final_marks": 1}, {"component_code": "END", "final_marks": 2}],
            "invalid",
            "duplicate_component",
        ),
        ([{"component_code": "END", "final_marks": 1.234}], "invalid", "too_many_decimals"),
        ([{"component_code": "VIVA", "final_marks": 1}], "unprocessable", "unknown_component"),
        ([{"component_code": "END", "final_marks": 101}], "unprocessable", "marks_out_of_range"),
        ([{"component_code": "END", "final_marks": -1}], "unprocessable", "marks_out_of_range"),
    ],
)
def test_a_malformed_or_out_of_range_correction_is_refused(corrections, kind, code):
    with pytest.raises(DomainRuleError) as caught:
        rs.revise(PREVIOUS, corrections, SCHEME)
    assert (caught.value.kind, caught.value.code) == (kind, code)
