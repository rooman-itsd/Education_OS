"""build_query is the only way to a Query, and a Query cannot exist without the organisation and permission filters."""

import dataclasses

import pytest
from eos_search.application.query import (
    SEARCH,
    SUGGEST,
    Query,
    acl_filter,
    alias_name,
    build_count_query,
    build_query,
    org_filter,
)
from eos_search.domain.documents import Caller
from search_support import ARTICLE, COURSE, READ_ARTICLE, READ_COURSE, caller, new_org, providers, registry_of

REGISTRY = registry_of(providers())
SPECS = [REGISTRY.types[ARTICLE], REGISTRY.types[COURSE]]


def filters_of(query: Query) -> list:
    return query.body["query"]["bool"]["filter"]


def test_every_search_query_carries_the_organisation_filter_routing_and_permission_filter():
    org = new_org()
    who = caller(org, READ_ARTICLE, "unrelated:permission:read")
    q = build_query(who, SPECS, text="fees")
    assert q.routing == org and q.organisation_id == org
    assert org_filter(org) in filters_of(q)
    assert acl_filter(who.user_id, [READ_ARTICLE]) in filters_of(q)  # only keys the types declare are sent
    assert q.acl_keys == (READ_ARTICLE,)


def test_suggestions_go_through_the_same_filters():
    who = caller(new_org(), READ_COURSE)
    q = build_query(who, SPECS, text="fe", kind=SUGGEST)
    assert org_filter(who.organisation_id) in filters_of(q) and acl_filter(who.user_id, [READ_COURSE]) in filters_of(q)
    assert q.kind == SUGGEST and "aggs" not in q.body


def test_counts_filter_by_organisation_and_return_no_content():
    org = new_org()
    q = build_count_query(org, SPECS[0])
    assert org_filter(org) in filters_of(q) and q.body["size"] == 0 and q.routing == org


def test_a_query_without_the_organisation_filter_cannot_be_constructed():
    good = build_query(caller(new_org(), READ_ARTICLE), SPECS, text="x")
    body = dataclasses.replace(good).body
    stripped = {
        **body,
        "query": {
            "bool": {
                **body["query"]["bool"],
                "filter": [f for f in filters_of(good) if f != org_filter(good.organisation_id)],
            }
        },
    }
    with pytest.raises(ValueError, match="organisation filter"):
        dataclasses.replace(good, body=stripped)
    with pytest.raises(ValueError):
        dataclasses.replace(good, routing="another-organisation")
    with pytest.raises(ValueError):
        dataclasses.replace(good, organisation_id="")


def test_a_search_query_without_the_permission_filter_cannot_be_constructed():
    good = build_query(caller(new_org(), READ_ARTICLE), SPECS, text="x")
    body = good.body
    stripped = {
        **body,
        "query": {"bool": {**body["query"]["bool"], "filter": [f for f in filters_of(good) if "bool" not in f]}},
    }
    with pytest.raises(ValueError, match="permission filter"):
        dataclasses.replace(good, body=stripped)
    with pytest.raises(ValueError):
        dataclasses.replace(good, user_id=None)
    with pytest.raises(ValueError):
        dataclasses.replace(good, acl_keys=())  # a different key set than the one in the body


def test_a_caller_needs_an_organisation_and_a_user():
    with pytest.raises(ValueError):
        caller("", READ_ARTICLE)
    with pytest.raises(ValueError):
        Caller(user_id="", organisation_id=new_org(), grants=frozenset())


def test_the_text_is_only_ever_a_match_query_value():
    q = build_query(caller(new_org(), READ_ARTICLE), SPECS, text='title:* OR "x"')
    text = repr(q.body["query"]["bool"]["must"])
    assert "query_string" not in text and "simple_query_string" not in text and "wildcard" not in text
    assert text.count("title:* OR") >= 1


def test_the_types_restriction_is_a_post_filter_so_facets_stay_whole():
    q = build_query(caller(new_org(), READ_ARTICLE), SPECS, text="x", restrict_types=[ARTICLE, "bogus.type"])
    assert q.body["post_filter"] == {"terms": {"type": [ARTICLE]}}
    assert "post_filter" not in build_query(caller(new_org(), READ_ARTICLE), SPECS, text="x").body


def test_filters_and_search_after_and_highlight():
    q = build_query(
        caller(new_org(), READ_COURSE),
        [REGISTRY.types[COURSE]],
        text="x",
        filters=[("status", "open")],
        search_after=[1.5, "doc"],
        limit=11,
    )
    assert {"term": {"fields.status": "open"}} in filters_of(q)
    assert q.body["search_after"] == [1.5, "doc"] and q.body["size"] == 11
    assert q.body["highlight"]["fields"] == {"fields.description": {}}
    assert q.body["track_total_hits"] == 10_000 and q.body["timeout"] == "2000ms"
    assert q.body["sort"] == [{"_score": "desc"}, {"doc_id": "asc"}]


def test_only_search_and_suggest_can_be_built():
    with pytest.raises(ValueError):
        build_query(caller(new_org(), READ_ARTICLE), SPECS, text="x", kind="count")
    assert SEARCH == "search"


def test_alias_names_are_per_environment_module_and_type():
    assert alias_name("prod", ARTICLE) == "eos-prod-knowledge-base-article"
    assert alias_name("Stag ing!", COURSE) == "eos-staging-academic-management-course"
