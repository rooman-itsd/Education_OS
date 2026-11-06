"""The document the indexer stores: organisation from the envelope, bounded and clean, read permissions narrowed only
to what the type declared."""

import math
from datetime import UTC, date, datetime

import pytest
from eos_search.domain.documents import (
    HIGHLIGHT_CLOSE,
    HIGHLIGHT_OPEN,
    MAX_READ_USERS,
    DocumentRejected,
    build_document,
    canonical_record_id,
    version_of,
)
from search_support import (
    ARTICLE,
    COURSE,
    NOW,
    READ_ARTICLE,
    READ_INTERNAL,
    article,
    course,
    new_org,
    providers,
    registry_of,
)

REGISTRY = registry_of(providers())
ORG = new_org()


def build(type_key: str, raw: dict, record_id: str = "r1", org: str = ORG):
    return build_document(
        REGISTRY.types[type_key], organisation_id=org, record_id=record_id, raw=raw, version=1, now=NOW
    )


def test_the_document_takes_its_organisation_from_the_caller_and_has_a_scoped_id():
    doc = build(ARTICLE, article("Fee refunds", "How to claim"))
    assert doc["organisation_id"] == ORG
    assert doc["doc_id"] == f"{ORG}:{ARTICLE}:r1"
    assert doc["title"] == "Fee refunds" and doc["fields"]["body"] == "How to claim"
    assert doc["read_any_of"] == [READ_ARTICLE, READ_INTERNAL]
    assert doc["module"] == "knowledge-base" and doc["type"] == ARTICLE


def test_two_organisations_with_the_same_record_id_get_different_document_ids():
    a, b = build(ARTICLE, article("x"), org=new_org()), build(ARTICLE, article("x"), org=new_org())
    assert a["doc_id"] != b["doc_id"]


def test_a_provider_naming_another_organisation_is_refused():
    raw = {**article("x"), "organisation_id": new_org()}
    with pytest.raises(DocumentRejected) as e:
        build(ARTICLE, raw)
    assert e.value.reason == "organisation_mismatch"
    build(ARTICLE, {**article("x"), "organisation_id": ORG})  # naming the right one is harmless


def test_a_provider_cannot_answer_for_another_record():
    with pytest.raises(DocumentRejected):
        build(ARTICLE, {**article("x"), "record_id": "other"})


def test_undeclared_fields_are_dropped_not_indexed():
    doc = build(ARTICLE, article("x", phone="+91 98765 43210"))
    assert "phone" not in doc["fields"]


def test_the_title_is_required_and_bounded():
    with pytest.raises(DocumentRejected) as e:
        build(ARTICLE, {"fields": {"body": "no title"}})
    assert e.value.reason == "title_missing"
    assert len(build(ARTICLE, article("t" * 5000))["title"]) == 300


def test_read_permissions_may_narrow_but_only_to_declared_keys():
    assert build(ARTICLE, article("x", internal=True))["read_any_of"] == [READ_INTERNAL]
    with pytest.raises(DocumentRejected) as e:
        build(ARTICLE, {**article("x"), "read_any_of": ["admin:everything:read"]})
    assert e.value.reason == "read_permission_not_declared"


def test_a_document_nobody_may_read_is_refused():
    with pytest.raises(DocumentRejected) as e:
        build(ARTICLE, {**article("x"), "read_any_of": []})
    assert e.value.reason == "no_read_permission"
    doc = build(ARTICLE, {**article("x"), "read_any_of": [], "read_users": ["u1"]})  # a named reader is enough
    assert doc["read_users"] == ["u1"]


def test_read_users_are_bounded():
    ok = build(ARTICLE, {**article("x"), "read_users": [f"u{i}" for i in range(MAX_READ_USERS)]})
    assert len(ok["read_users"]) == MAX_READ_USERS
    with pytest.raises(DocumentRejected):
        build(ARTICLE, {**article("x"), "read_users": [f"u{i}" for i in range(MAX_READ_USERS + 1)]})
    with pytest.raises(DocumentRejected):
        build(ARTICLE, {**article("x"), "read_users": [1, 2]})


def test_the_highlight_markers_and_control_characters_never_reach_the_index():
    doc = build(ARTICLE, article(f"a{HIGHLIGHT_OPEN}b{HIGHLIGHT_CLOSE}c\x00d", body="x\x07y"))
    assert HIGHLIGHT_OPEN not in doc["title"] and HIGHLIGHT_CLOSE not in doc["title"] and "\x00" not in doc["title"]
    assert "\x07" not in doc["fields"]["body"]


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, True, "12", None])
def test_numbers_must_be_finite_numbers(bad):
    if bad is None:
        assert "credits" not in build(COURSE, course("Intro", credits=bad))["fields"]
        return
    with pytest.raises(DocumentRejected):
        build(COURSE, course("Intro", credits=bad))


def test_numbers_dates_and_booleans_are_stored_in_their_own_form():
    assert build(COURSE, course("Intro", credits=4))["fields"]["credits"] == 4
    assert build(ARTICLE, article("x", published=True))["fields"]["published"] is True
    with pytest.raises(DocumentRejected):
        build(ARTICLE, article("x", published="yes"))


def test_dates_are_normalised():
    from eos_search.domain.declarations import FieldSpec
    from eos_search.domain.documents import coerce

    f = FieldSpec("d", "date")
    assert coerce(f, date(2026, 11, 5)) == "2026-11-05"
    assert coerce(f, "2026-11-05") == "2026-11-05"
    assert coerce(f, datetime(2026, 11, 5, 1, 2, tzinfo=UTC)).startswith("2026-11-05T01:02")
    with pytest.raises(DocumentRejected):
        coerce(f, "not a date")


@pytest.mark.parametrize("bad", [None, "", "  ", True, 1.5, "x" * 129, "a\x00b", [], {}])
def test_record_ids_are_checked(bad):
    with pytest.raises(DocumentRejected):
        canonical_record_id(bad)


def test_version_is_the_event_time_in_microseconds_and_naive_means_utc():
    assert version_of(NOW) == int(NOW.timestamp() * 1_000_000)
    assert version_of(NOW.replace(tzinfo=None)) == version_of(NOW)
