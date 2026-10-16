"""Unit tests of the curriculum rules (domain layer): FR-4 versions and immutability, FR-5 credit total, and
publication re-checking every item against the programme as it is now."""

from decimal import Decimal

import pytest
from eos_academic_management.domain.curricula import (
    DRAFT,
    PUBLISHED,
    CurriculumItem,
    ensure_editable,
    ensure_publishable,
    next_version,
    total_credits,
    validate_item,
)
from eos_academic_management.domain.errors import DomainRuleError


def item(credits, category="core", term=1, duration_terms=2):
    return validate_item(
        course_id="c", programme_term=term, category=category, credits=credits, duration_terms=duration_terms
    )


def publish(items, credits_required, duration_terms=2, status=DRAFT):
    ensure_publishable(status, items, credits_required=credits_required, duration_terms=duration_terms)


# --- items


def test_valid_item_at_both_ends_of_the_programme():
    assert item(4, term=1).programme_term == 1
    assert item(4, term=2) == CurriculumItem("c", 2, "core", Decimal(4))


@pytest.mark.parametrize(
    ("kwargs", "code", "field"),
    [
        ({"programme_term": 0}, "below_minimum", "programme_term"),
        ({"programme_term": 3}, "programme_term_out_of_range", "programme_term"),
        ({"category": "optional"}, "invalid_choice", "category"),
        ({"credits": -1}, "below_minimum", "credits"),
        ({"duration_terms": 0}, "below_minimum", "duration_terms"),
        ({"duration_terms": "2"}, "invalid_integer", "duration_terms"),
    ],
)
def test_invalid_items(kwargs, code, field):
    values = {"course_id": "c", "programme_term": 1, "category": "core", "credits": 3, "duration_terms": 2, **kwargs}
    with pytest.raises(DomainRuleError) as err:
        validate_item(**values)
    assert (err.value.code, err.value.field, err.value.kind) == (code, field, "invalid")


def test_item_accepts_decimal_credits_exactly():
    assert item(Decimal("2.5")).credits == Decimal("2.5")


def test_total_credits_is_exact_for_fractions():
    assert total_credits([item(0.1), item(0.2)]) == Decimal("0.3")
    assert total_credits([item(Decimal("0.1")), item(Decimal("0.2"))]) == Decimal("0.3")
    assert total_credits([]) == Decimal(0)


# --- immutability


def test_draft_is_editable_and_published_is_immutable():
    ensure_editable(DRAFT)
    with pytest.raises(DomainRuleError) as err:
        ensure_editable(PUBLISHED)
    assert (err.value.code, err.value.kind) == ("curriculum_published", "conflict")


def test_editable_rejects_an_unknown_status():
    with pytest.raises(DomainRuleError) as err:
        ensure_editable("archived")
    assert (err.value.code, err.value.field) == ("invalid_choice", "status")


# --- publication


def test_publishing_needs_credits_equal_to_the_programme():
    publish([item(60), item(60, category="elective", term=2)], Decimal(120))
    publish([item(0.1), item(0.2)], Decimal("0.3"))
    publish([item(Decimal("0.1")), item(Decimal("0.2"))], 0.3)  # float requirement, exact comparison


@pytest.mark.parametrize("credits", [[60], [60, 61]])
def test_publishing_with_wrong_credit_total_is_unprocessable(credits):
    with pytest.raises(DomainRuleError) as err:
        publish([item(c) for c in credits], Decimal(120))
    assert (err.value.code, err.value.kind) == ("credits_mismatch", "unprocessable")


def test_publishing_twice_is_a_conflict():
    with pytest.raises(DomainRuleError) as err:
        publish([item(120)], Decimal(120), status=PUBLISHED)
    assert (err.value.code, err.value.kind) == ("curriculum_published", "conflict")


def test_item_valid_when_entered_is_rejected_after_the_programme_gets_shorter():
    entered = item(120, term=4, duration_terms=4)  # valid while the programme had 4 terms
    with pytest.raises(DomainRuleError) as err:
        publish([entered], Decimal(120), duration_terms=2)  # programme now has 2 terms
    assert (err.value.code, err.value.kind, err.value.field) == (
        "programme_term_out_of_range",
        "unprocessable",
        "items[0].programme_term",
    )


@pytest.mark.parametrize(
    ("bad_item", "code", "field"),
    [
        (CurriculumItem("c", 99, "core", Decimal(60)), "programme_term_out_of_range", "items[1].programme_term"),
        (CurriculumItem("c", 1, "bogus", Decimal(60)), "invalid_choice", "items[1].category"),
        (CurriculumItem("c", 1, "core", Decimal("-1")), "below_minimum", "items[1].credits"),
        (CurriculumItem("c", 1, "core", Decimal("NaN")), "invalid_number", "items[1].credits"),
        (CurriculumItem("c", True, "core", Decimal(60)), "invalid_integer", "items[1].programme_term"),
    ],
)
def test_directly_constructed_invalid_items_are_rejected_at_publication(bad_item, code, field):
    with pytest.raises(DomainRuleError) as err:
        publish([item(60), bad_item], Decimal(120))
    assert (err.value.code, err.value.kind, err.value.field) == (code, "unprocessable", field)


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [({"duration_terms": 0}, "below_minimum"), ({"credits_required": float("inf")}, "invalid_number")],
)
def test_publication_rejects_an_invalid_programme(kwargs, code):
    values = {"credits_required": Decimal(60), "duration_terms": 2, **kwargs}
    with pytest.raises(DomainRuleError) as err:
        ensure_publishable(DRAFT, [item(60)], **values)
    assert err.value.code == code


def test_publication_rejects_an_unknown_status():
    with pytest.raises(DomainRuleError) as err:
        publish([item(60)], Decimal(60), status="archived")
    assert (err.value.code, err.value.field) == ("invalid_choice", "status")


# --- versions


def test_versions_start_at_one_and_follow_the_highest():
    assert next_version([]) == 1
    assert next_version(iter([])) == 1
    assert next_version([1, 3, 2]) == 4
    assert next_version([1, 1]) == 2


@pytest.mark.parametrize(
    ("history", "code"),
    [
        (["3"], "invalid_integer"),
        ([True], "invalid_integer"),
        ([1.0], "invalid_integer"),
        ([0], "below_minimum"),
        ([-2], "below_minimum"),
        ([1, 2, "x"], "invalid_integer"),
        ([3, None, 1], "invalid_integer"),
    ],
)
def test_invalid_version_history_is_an_error(history, code):
    with pytest.raises(DomainRuleError) as err:
        next_version(history)
    assert (err.value.code, err.value.field) == (code, "version")
