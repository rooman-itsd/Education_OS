"""Unit tests of the grading and assessment scheme rules (domain layer): FR-2, FR-3, PRD 5.2 and 5.3."""

from decimal import Decimal

import pytest
from conftest import uid
from eos_examinations.domain import assessment as asm
from eos_examinations.domain import grading as grd
from eos_examinations.domain.errors import DomainRuleError


def code(fn, *args, **kw) -> DomainRuleError:
    with pytest.raises(DomainRuleError) as e:
        fn(*args, **kw)
    return e.value


# ---------------------------------------------------------------- grading


def band(**over) -> dict:
    return {"min_percent": 40, "max_percent": 100, "grade": "P", "grade_point": 5, "is_pass": True, **over}


def test_a_grading_scheme_is_built_from_contract_bands_with_exact_numbers():
    s = grd.new_scheme(
        "Standard", [band(min_percent=0, max_percent=39.5, grade="F", grade_point=0, is_pass=False), band()]
    )
    assert [b.grade for b in s.bands] == ["F", "P"]
    assert s.bands[0].max_percent == Decimal("39.5") and s.bands[1].is_pass is True
    assert s.is_default is False and grd.new_scheme("Default", [band()], is_default=True).is_default


@pytest.mark.parametrize(
    ("change", "expected", "field"),
    [
        ({"min_percent": -1}, "below_minimum", "bands[0].min_percent"),
        ({"max_percent": 100.5}, "above_maximum", "bands[0].max_percent"),
        ({"min_percent": 60, "max_percent": 50}, "invalid_band", "bands[0].max_percent"),
        ({"grade": " "}, "invalid_text", "bands[0].grade"),
        ({"grade": "x" * 21}, "text_too_long", "bands[0].grade"),
        ({"grade_point": -0.1}, "below_minimum", "bands[0].grade_point"),
        ({"grade_point": "5"}, "invalid_number", "bands[0].grade_point"),
        ({"is_pass": 1}, "invalid_boolean", "bands[0].is_pass"),
    ],
)
def test_an_invalid_band_is_refused_naming_its_position(change, expected, field):
    err = code(grd.new_scheme, "Standard", [band(**change)])
    assert (err.code, err.kind, err.field) == (expected, "invalid", field)


def test_the_band_position_is_named_in_a_longer_list():
    err = code(grd.new_scheme, "S", [band(grade="A"), band(grade="B", max_percent=-5)])
    assert err.field == "bands[1].max_percent"


@pytest.mark.parametrize(
    ("name", "bands", "expected"),
    [
        ("Standard", [], "no_bands"),
        ("Standard", "none", "invalid_bands"),
        ("Standard", ["A"], "invalid_band"),
        ("  ", [band()], "invalid_text"),
        ("Standard", [band(grade="A"), band(grade="A")], "duplicate_grade"),
    ],
)
def test_an_invalid_grading_scheme_is_refused(name, bands, expected):
    assert code(grd.new_scheme, name, bands).code == expected


def test_band_coverage_is_not_enforced_because_its_boundary_rule_is_undecided():
    """Bands that leave a gap, or touch, are accepted: the PRD does not say whether max_percent is inclusive."""
    gap = grd.new_scheme("S", [band(min_percent=0, max_percent=30, grade="F"), band(min_percent=50, max_percent=100)])
    touching = grd.new_scheme(
        "S", [band(min_percent=0, max_percent=40, grade="F"), band(min_percent=40, max_percent=100)]
    )
    assert len(gap.bands) == len(touching.bands) == 2


def test_a_scheme_in_use_by_published_results_cannot_be_replaced():
    grd.ensure_replaceable(in_use=False)
    err = code(grd.ensure_replaceable, in_use=True)
    assert (err.code, err.kind) == ("grading_scheme_in_use", "conflict")


def test_making_a_scheme_the_default_clears_the_previous_default():
    a, b, c = uid(), uid(), uid()
    assert grd.plan_default([(a, True), (b, False), (c, False)], b) == [a, b]
    assert grd.plan_default([(a, False), (b, False)], b) == [b]
    assert grd.plan_default([(a, True), (b, False)], a) == []  # already the default
    assert code(grd.plan_default, [(a, False)], uid()).kind == "not_found"


# ---------------------------------------------------------------- assessment


def comp(**over) -> dict:
    return {
        "code": "THEORY",
        "name": "Written paper",
        "kind": "written",
        "weightage_percent": 60,
        "max_marks": 100,
        **over,
    }


def scheme(components=None, *, status="draft", version=1, offering=None, scheme_id=None):
    default = [comp(), comp(code="INT", name="Internal", kind="continuous", weightage_percent=40, max_marks=50)]
    s = asm.new_scheme(
        scheme_id or uid(), offering or uid(), 40, default if components is None else components, version=version
    )
    return asm.Scheme(**{**s.__dict__, "status": status})


def test_a_scheme_is_built_from_contract_components():
    s = scheme()
    assert [(c.code, c.kind, c.weightage_percent, c.max_marks, c.pass_marks) for c in s.components] == [
        ("THEORY", "written", Decimal(60), Decimal(100), None),
        ("INT", "continuous", Decimal(40), Decimal(50), None),
    ]
    assert (s.status, s.version, s.pass_percent, s.total_weightage) == ("draft", 1, Decimal(40), Decimal(100))


@pytest.mark.parametrize("kind", ["written", "practical", "oral", "project", "continuous"])
def test_every_contract_component_kind_is_accepted(kind):
    assert asm.new_component(comp(kind=kind)).kind == kind


@pytest.mark.parametrize(
    ("change", "expected", "field"),
    [
        ({"kind": "viva"}, "invalid_choice", "components[0].kind"),
        ({"code": ""}, "invalid_text", "components[0].code"),
        ({"weightage_percent": 101}, "above_maximum", "components[0].weightage_percent"),
        ({"weightage_percent": -1}, "below_minimum", "components[0].weightage_percent"),
        ({"max_marks": 0}, "invalid_max_marks", "components[0].max_marks"),
        ({"max_marks": "100"}, "invalid_number", "components[0].max_marks"),
        ({"pass_marks": -1}, "below_minimum", "components[0].pass_marks"),
        ({"pass_marks": 101}, "invalid_pass_marks", "components[0].pass_marks"),
    ],
)
def test_an_invalid_component_is_refused_naming_its_position(change, expected, field):
    err = code(asm.new_scheme, uid(), uid(), 40, [comp(**change)])
    assert (err.code, err.kind, err.field) == (expected, "invalid", field)


def test_pass_marks_up_to_max_marks_are_valid():
    assert asm.new_component(comp(pass_marks=100)).pass_marks == Decimal(100)


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ((uid(), "x", 40, []), "invalid_id"),
        ((uid(), uid(), 101, []), "above_maximum"),
        ((uid(), uid(), 40, "none"), "invalid_components"),
        ((uid(), uid(), 40, [comp(), comp()]), "duplicate_component_code"),
    ],
)
def test_an_invalid_assessment_scheme_is_refused(args, expected):
    assert code(asm.new_scheme, *args).code == expected


def test_a_draft_may_be_incomplete_but_activation_needs_weightages_adding_up_to_100():
    partial = scheme([comp(weightage_percent=60)])  # accepted as a draft
    err = code(asm.plan_activation, partial, [])
    assert (err.code, err.kind, err.details) == ("weightage_not_100", "unprocessable", {"total": "60"})
    assert code(
        asm.plan_activation, scheme([comp(weightage_percent=60), comp(code="B", weightage_percent=60)]), []
    ).details == {"total": "120"}
    assert code(asm.plan_activation, scheme([]), []).code == "no_components"


def test_weightages_are_summed_exactly():
    thirds = [comp(code=str(i), weightage_percent=Decimal("33.33")) for i in range(3)] + [
        comp(code="r", weightage_percent=Decimal("0.01"))
    ]
    assert asm.plan_activation(scheme(thirds), []).scheme.status == "active"
    assert code(
        asm.plan_activation, scheme([comp(code=str(i), weightage_percent=0.1) for i in range(3)]), []
    ).details == {"total": "0.3"}


def test_activating_supersedes_the_previous_active_scheme_of_the_offering():
    offering = uid()
    old_active = scheme(status="active", version=1, offering=offering)
    older = scheme(status="superseded", version=0 + 1, offering=offering)
    draft = scheme(version=2, offering=offering)
    result = asm.plan_activation(draft, [old_active, older, draft])
    assert result.scheme.status == "active" and result.scheme.id == draft.id
    assert result.superseded_ids == (old_active.id,)
    assert draft.status == "draft"  # the original is untouched


def test_the_first_activation_supersedes_nothing_and_only_a_draft_can_be_activated():
    assert asm.plan_activation(scheme(), []).superseded_ids == ()
    for status in ("active", "superseded"):
        err = code(asm.plan_activation, scheme(status=status), [])
        assert (err.code, err.kind) == ("scheme_not_draft", "conflict")


def test_schemes_of_another_offering_are_a_programming_error():
    with pytest.raises(ValueError):
        asm.plan_activation(scheme(), [scheme(status="active")])


def test_versions_are_kept_and_numbered_up():
    assert asm.next_version([]) == 1
    assert asm.next_version([1, 3, 2]) == 4
    assert code(asm.new_scheme, uid(), uid(), 40, [comp()], version=0).code == "invalid_version"


def test_a_scheme_with_locked_marks_or_a_superseded_one_cannot_change():
    asm.ensure_editable(scheme(), has_locked_marks=False)
    asm.ensure_editable(scheme(status="active"), has_locked_marks=False)
    assert code(asm.ensure_editable, scheme(status="active"), has_locked_marks=True).code == "scheme_has_locked_marks"
    assert code(asm.ensure_editable, scheme(status="superseded"), has_locked_marks=False).code == "scheme_superseded"
