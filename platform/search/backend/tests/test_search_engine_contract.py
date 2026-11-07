"""One contract suite for both engines (docs/prd.md, decision 8). It always runs against the in-memory engine, and
against a real OpenSearch cluster only when SEARCH_TEST_OPENSEARCH_URL points at one (skipped otherwise), so the fake
cannot drift from the real thing on tenancy, permissions, cursors and bounds.

What an analyzer or relevance would change is not tested here: the fake does not reproduce it."""

import os
import uuid

import pytest
from eos_search.application import cursor, service
from eos_search.application.query import build_count_query
from eos_search.domain.documents import HIGHLIGHT_CLOSE, HIGHLIGHT_OPEN, build_document, version_of
from eos_search.domain.errors import EngineUnavailable, SearchError
from eos_search.infrastructure.config import SearchConfig
from eos_search.infrastructure.memory_engine import InMemoryEngine
from search_support import (
    ARTICLE,
    COURSE,
    NOW,
    PERSON,
    READ_ARTICLE,
    READ_COURSE,
    READ_INTERNAL,
    READ_PERSON,
    article,
    caller,
    course,
    index,
    later,
    new_org,
    person,
    registry_of,
)

OPENSEARCH_URL = os.environ.get("SEARCH_TEST_OPENSEARCH_URL", "")
ENGINES = [
    "memory",
    pytest.param(
        "opensearch",
        marks=[
            pytest.mark.opensearch,
            pytest.mark.skipif(not OPENSEARCH_URL, reason="SEARCH_TEST_OPENSEARCH_URL not set"),
        ],
    ),
]
EVERYTHING = (READ_PERSON, READ_COURSE, READ_ARTICLE, READ_INTERNAL)


@pytest.fixture(params=ENGINES)
def engine(request):
    if request.param == "memory":
        yield InMemoryEngine("dev")
        return
    from eos_search.infrastructure.opensearch_engine import OpenSearchEngine

    environment = f"t{uuid.uuid4().hex[:10]}"
    config = SearchConfig.from_env()
    config = SearchConfig(
        **{
            **config.__dict__,
            "engine": "opensearch",
            "opensearch_url": OPENSEARCH_URL,
            "index_environment": environment,
            "index_replicas": 0,
            "opensearch_timeout_seconds": 5,
        }
    )
    real = OpenSearchEngine(config)
    yield real
    real.client.indices.delete(index=f"eos-{environment}-*", ignore=[404])


@pytest.fixture
def registry(search_providers):
    return registry_of(search_providers)


def refresh(engine) -> None:
    """A real cluster makes writes searchable on refresh; the fake is immediate."""
    if engine.name == "opensearch":
        engine.client.indices.refresh(index="_all")


def put(engine, registry, org, type_key, rid, doc, **kw):
    index(engine, registry, org, type_key, rid, doc, **kw)
    refresh(engine)


def run(engine, registry, who, q, **kw):
    return service.search(who, q=q, registry=registry, engine=engine, **kw)


def titles(result) -> list[str]:
    return sorted(i["title"] for i in result["items"])


# --- tenancy -----------------------------------------------------------------------------------------------------
def test_cross_tenant_leak_hits_facets_total_and_suggestions(engine, registry):
    a, b = new_org(), new_org()
    put(engine, registry, a, ARTICLE, "1", article("Zephyrquill handbook", "zephyrquill details"))
    put(engine, registry, a, PERSON, "p1", person("Zephyrquill Sharma"))
    mine, theirs = caller(a, *EVERYTHING), caller(b, *EVERYTHING)

    found = run(engine, registry, mine, "zephyrquill")
    assert found["total"] == 2 and {f["type"] for f in found["facets"]} == {ARTICLE, PERSON}

    leak = run(engine, registry, theirs, "zephyrquill")
    assert leak["items"] == [] and leak["facets"] == [] and leak["total"] == 0 and leak["next_cursor"] is None
    assert service.suggest(theirs, q="zephyr", registry=registry, engine=engine)["suggestions"] == []
    assert service.suggest(mine, q="zephyr", registry=registry, engine=engine)["suggestions"]
    assert engine.count_documents(build_count_query(b, registry.types[ARTICLE])) == 0
    assert engine.count_documents(build_count_query(a, registry.types[ARTICLE])) == 1


def test_the_same_record_id_in_two_organisations_stays_two_documents(engine, registry):
    a, b = new_org(), new_org()
    put(engine, registry, a, ARTICLE, "same", article("Alpha only wording"))
    put(engine, registry, b, ARTICLE, "same", article("Beta only wording"))
    assert titles(run(engine, registry, caller(a, *EVERYTHING), "wording")) == ["Alpha only wording"]
    assert titles(run(engine, registry, caller(b, *EVERYTHING), "wording")) == ["Beta only wording"]


def test_a_module_the_organisation_is_not_entitled_to_disappears(engine, registry):
    org = new_org()
    put(engine, registry, org, ARTICLE, "1", article("Quixotic policy"))
    assert run(engine, registry, caller(org, *EVERYTHING, entitled={"knowledge-base"}), "quixotic")["total"] == 1
    off = caller(org, *EVERYTHING, entitled={"academic-management"})
    assert run(engine, registry, off, "quixotic")["total"] == 0
    with pytest.raises(SearchError) as e:
        run(engine, registry, off, "quixotic", module="knowledge-base")
    assert e.value.status == 404


# --- permissions -------------------------------------------------------------------------------------------------
def test_an_internal_article_is_never_matched_scored_counted_or_suggested_for_a_public_reader(engine, registry):
    org = new_org()
    put(engine, registry, org, ARTICLE, "pub", article("Marmalade public notice"))
    put(engine, registry, org, ARTICLE, "int", article("Marmalade disciplinary review", internal=True))
    public, staff = caller(org, READ_ARTICLE), caller(org, READ_ARTICLE, READ_INTERNAL)

    seen = run(engine, registry, public, "marmalade")
    assert titles(seen) == ["Marmalade public notice"]
    assert seen["total"] == 1 and [f["count"] for f in seen["facets"]] == [1]
    assert [
        s["text"] for s in service.suggest(public, q="marmal", registry=registry, engine=engine)["suggestions"]
    ] == ["Marmalade public notice"]
    assert run(engine, registry, public, "disciplinary")["total"] == 0  # not even by the secret word
    full = run(engine, registry, staff, "marmalade")
    assert full["total"] == 2 and full["facets"][0]["count"] == 2


def test_a_caller_who_may_read_nothing_of_a_type_gets_no_facet_and_no_count(engine, registry):
    org = new_org()
    put(engine, registry, org, PERSON, "p1", person("Ravenwood Iyer"))
    put(engine, registry, org, COURSE, "c1", course("Ravenwood studies"))
    result = run(engine, registry, caller(org, READ_COURSE), "ravenwood")
    assert [f["type"] for f in result["facets"]] == [COURSE] and result["total"] == 1
    assert [t["type"] for t in service.list_types(caller(org, READ_COURSE), registry)["items"]] == [COURSE]


def test_a_document_with_no_readers_matches_nobody(engine, registry):
    org = new_org()
    spec = registry.types[ARTICLE]
    doc = build_document(
        spec, organisation_id=org, record_id="x", raw=article("Orphaned nightingale"), version=1, now=NOW
    )
    doc["read_any_of"], doc["read_users"] = [], []
    engine.ensure_index(spec)
    engine.index_many(org, spec, [doc])
    refresh(engine)
    assert run(engine, registry, caller(org, *EVERYTHING), "nightingale")["total"] == 0


def test_read_users_lets_a_named_person_read_without_the_permission(engine, registry):
    org, me, other = new_org(), str(uuid.uuid4()), str(uuid.uuid4())
    put(engine, registry, org, PERSON, "mine", {**person("Thistledown Rao"), "read_users": [me]})
    assert titles(run(engine, registry, caller(org, user=me), "thistledown")) == ["Thistledown Rao"]
    assert run(engine, registry, caller(org, user=other), "thistledown")["total"] == 0
    assert run(engine, registry, caller(org, READ_PERSON, user=other), "thistledown")["total"] == 1


def test_a_role_change_takes_effect_on_the_next_query_without_a_reindex(engine, registry):
    org, user = new_org(), str(uuid.uuid4())
    put(engine, registry, org, COURSE, "c1", course("Halcyon calculus"))
    assert run(engine, registry, caller(org, READ_COURSE, user=user), "halcyon")["total"] == 1
    assert run(engine, registry, caller(org, user=user), "halcyon")["total"] == 0  # role removed
    assert run(engine, registry, caller(org, READ_COURSE, user=user), "halcyon")["total"] == 1  # and restored


# --- writes ------------------------------------------------------------------------------------------------------
def test_delete_and_purge(engine, registry):
    a, b = new_org(), new_org()
    for org in (a, b):
        put(engine, registry, org, COURSE, "c1", course("Quartzite geology"))
        put(engine, registry, org, ARTICLE, "k1", article("Quartzite care guide"))
    spec = registry.types[COURSE]
    assert engine.delete(a, spec, "c1", version_of(later(10)))
    refresh(engine)
    assert run(engine, registry, caller(a, *EVERYTHING), "quartzite")["total"] == 1
    removed = engine.delete_by_organisation(a)
    refresh(engine)
    assert removed >= 1
    assert run(engine, registry, caller(a, *EVERYTHING), "quartzite")["total"] == 0
    assert run(engine, registry, caller(b, *EVERYTHING), "quartzite")["total"] == 2  # the other tenant is untouched


def test_external_versions_stop_a_late_older_write_and_a_late_older_delete(engine, registry):
    org = new_org()
    spec = registry.types[COURSE]
    newer = build_document(
        spec, organisation_id=org, record_id="c", raw=course("Newer wording"), version=version_of(later(10)), now=NOW
    )
    older = build_document(
        spec, organisation_id=org, record_id="c", raw=course("Older wording"), version=version_of(later(5)), now=NOW
    )
    engine.ensure_index(spec)
    assert engine.index_many(org, spec, [newer]) == (1, 0)
    assert engine.index_many(org, spec, [older]) == (0, 1)  # stale, not an error
    assert not engine.delete(org, spec, "c", version_of(later(7)))
    refresh(engine)
    assert titles(run(engine, registry, caller(org, *EVERYTHING), "wording")) == ["Newer wording"]


# --- queries -----------------------------------------------------------------------------------------------------
def test_facets_count_the_whole_result_set_and_the_types_filter_narrows_hits_only(engine, registry):
    org = new_org()
    for i in range(4):
        put(engine, registry, org, COURSE, f"c{i}", course(f"Lighthouse course {i}"))
    put(engine, registry, org, ARTICLE, "a1", article("Lighthouse maintenance"))
    who = caller(org, *EVERYTHING)
    result = run(engine, registry, who, "lighthouse", limit=2)
    assert result["total"] == 5 and len(result["items"]) == 2
    assert {f["type"]: f["count"] for f in result["facets"]} == {COURSE: 4, ARTICLE: 1}
    narrowed = run(engine, registry, who, "lighthouse", types=ARTICLE)
    assert narrowed["total"] == 1 and {f["type"]: f["count"] for f in narrowed["facets"]} == {COURSE: 4, ARTICLE: 1}
    assert (
        run(engine, registry, who, "lighthouse", types="no.such-type")["items"] == []
    )  # unknown: ignored, not an error


def test_paging_with_a_signed_cursor_returns_every_hit_once(engine, registry):
    org = new_org()
    for i in range(7):
        put(engine, registry, org, COURSE, f"c{i}", course(f"Observatory studies {i}"))
    who = caller(org, *EVERYTHING)
    seen, token, pages = [], None, 0
    while True:
        page = run(engine, registry, who, "observatory", limit=3, cursor_token=token)
        seen += [i["id"] for i in page["items"]]
        pages += 1
        token = page["next_cursor"]
        if token is None:
            break
    assert pages == 3 and sorted(seen) == [f"c{i}" for i in range(7)] and len(set(seen)) == 7


def test_a_cursor_is_bound_to_the_user_the_query_and_the_clock(engine, registry):
    org = new_org()
    for i in range(4):
        put(engine, registry, org, COURSE, f"c{i}", course(f"Planetarium studies {i}"))
    me, you = caller(org, *EVERYTHING), caller(org, *EVERYTHING)
    token = run(engine, registry, me, "planetarium", limit=2)["next_cursor"]
    assert token
    assert len(run(engine, registry, me, "planetarium", limit=2, cursor_token=token)["items"]) == 2
    for who, q in ((you, "planetarium"), (me, "planetarium studies")):  # another user; another query
        with pytest.raises(SearchError) as e:
            run(engine, registry, who, q, limit=2, cursor_token=token)
        assert e.value.status == 422
    for bad in (token[:-2] + "xx", "x" * 2001, "no-dot", token.split(".")[0] + ".", ""):
        if bad == "":
            continue  # an empty cursor means no cursor
        with pytest.raises(SearchError) as e:
            run(engine, registry, me, "planetarium", limit=2, cursor_token=bad)
        assert e.value.status == 422
    expired = cursor.sign(
        SearchConfig.from_env().cursor_secret, {"u": me.user_id, "h": "x", "s": [1.0, "d"], "n": 1}, ttl_seconds=-5
    )
    with pytest.raises(SearchError):
        run(engine, registry, me, "planetarium", limit=2, cursor_token=expired)


def test_bounds_are_refused_with_a_422_and_never_a_500(engine, registry):
    org = new_org()
    who = caller(org, *EVERYTHING)
    for bad in ("", "   ", "\x00\x01", "x" * 201):
        with pytest.raises(SearchError) as e:
            run(engine, registry, who, bad)
        assert e.value.status == 422
    for limit in (0, 51, -1):
        with pytest.raises(SearchError):
            run(engine, registry, who, "ok", limit=limit)
    with pytest.raises(SearchError):
        run(engine, registry, who, "ok", types=",".join(f"m.t{i}" for i in range(21)))
    for q in ("x", "x" * 51, " "):
        with pytest.raises(SearchError):
            service.suggest(who, q=q, registry=registry, engine=engine)
    with pytest.raises(SearchError):
        service.suggest(who, q="ok", limit=11, registry=registry, engine=engine)


def test_query_syntax_is_plain_text(engine, registry):
    org = new_org()
    put(engine, registry, org, ARTICLE, "1", article("Ordinary article", "plain body"))
    who = caller(org, *EVERYTHING)
    for q in (
        "title:* OR (a AND NOT b)",
        '"unterminated',
        "\\",
        "*",
        "?*",
        "{{x}}",
        "a" * 200,
        "ünïcode 日本語",
        "\ud83d"[:0] or "emoji 😀",
    ):
        assert run(engine, registry, who, q)["total"] in (0, 1)  # any answer but an error


def test_module_filters_on_declared_fields(engine, registry):
    org = new_org()
    put(engine, registry, org, COURSE, "c1", course("Cedar physics", status="open", credits=4))
    put(engine, registry, org, COURSE, "c2", course("Cedar chemistry", status="closed", credits=3))
    who = caller(org, *EVERYTHING)
    module = "academic-management"
    assert titles(run(engine, registry, who, "cedar", module=module, filters="status:open")) == ["Cedar physics"]
    assert titles(run(engine, registry, who, "cedar", module=module, filters="credits:3")) == ["Cedar chemistry"]
    assert run(engine, registry, who, "cedar", module=module, filters="status:open,credits:3")["total"] == 0
    for bad in (
        "description:x",
        "status",
        "credits:NaN",
        "credits:inf",
        "credits:abc",
        "status:open,status:closed",
        ":x",
        ",".join(f"status:v{i}" for i in range(11)),
        "status:" + "v" * 201,
        "Status:open",
    ):
        with pytest.raises(SearchError) as e:
            run(engine, registry, who, "cedar", module=module, filters=bad)
        assert e.value.status == 422, bad
    with pytest.raises(SearchError) as e:
        run(engine, registry, who, "cedar", filters="status:open")  # filters belong to a module's endpoint
    assert e.value.status == 422
    with pytest.raises(SearchError) as e:
        run(engine, registry, who, "cedar", module="nonexistent-module")
    assert e.value.status == 404


def test_hits_carry_display_fields_url_and_marked_snippets_only(engine, registry):
    org = new_org()
    put(
        engine,
        registry,
        org,
        COURSE,
        "c/1",
        course("Glacier science", code="GS-201", description="Study of glacier flow and melt", status="open"),
    )
    hit = run(engine, registry, caller(org, *EVERYTHING), "glacier")["items"][0]
    assert hit["type"] == COURSE and hit["id"] == "c/1" and hit["title"] == "Glacier science"
    assert hit["url"] == "/academics/courses/c%2F1"
    assert hit["fields"] == {"code": "GS-201", "status": "open"}  # display fields only; description is a snippet field
    assert HIGHLIGHT_OPEN in hit["snippet"] and HIGHLIGHT_CLOSE in hit["snippet"] and "<" not in hit["snippet"]
    assert len(hit["snippet"]) <= 300


def test_suggestions_complete_a_title_prefix(engine, registry):
    org = new_org()
    put(engine, registry, org, PERSON, "p1", person("Priyanka Sharma"))
    put(engine, registry, org, PERSON, "p2", person("Prakash Rao"))
    got = service.suggest(caller(org, READ_PERSON), q="pri", registry=registry, engine=engine)["suggestions"]
    assert [s["text"] for s in got] == ["Priyanka Sharma"] and got[0]["id"] == "p1" and got[0]["type"] == PERSON
    assert (
        len(service.suggest(caller(org, READ_PERSON), q="pr", limit=1, registry=registry, engine=engine)["suggestions"])
        == 1
    )


# --- mapping versions --------------------------------------------------------------------------------------------
def test_a_new_index_version_goes_live_only_at_the_alias_swap(engine, registry):
    org = new_org()
    put(engine, registry, org, COURSE, "c1", course("Meridian maps"))
    spec = registry.types[COURSE]
    who = caller(org, *EVERYTHING)
    n = engine.build_next_index(spec)
    assert n == 2
    fresh = build_document(
        spec, organisation_id=org, record_id="c2", raw=course("Meridian charts"), version=version_of(later(1)), now=NOW
    )
    assert engine.index_many(org, spec, [fresh], target_version=n) == (1, 0)
    refresh(engine)
    assert titles(run(engine, registry, who, "meridian")) == ["Meridian maps"]  # not live yet
    engine.swap_alias(spec, n)
    refresh(engine)
    assert titles(run(engine, registry, who, "meridian")) == ["Meridian charts"]  # one atomic move


def test_stale_cleanup_keeps_stamped_and_newer_documents(engine, registry):
    org = new_org()
    spec = registry.types[COURSE]
    old = build_document(
        spec, organisation_id=org, record_id="old", raw=course("Dormant relic"), version=1, now=later(-100)
    )
    kept = build_document(
        spec,
        organisation_id=org,
        record_id="kept",
        raw=course("Dormant keeper"),
        version=2,
        now=later(-100),
        reindex_run="run-1",
    )
    fresh = build_document(
        spec, organisation_id=org, record_id="fresh", raw=course("Dormant newcomer"), version=3, now=later(50)
    )
    engine.ensure_index(spec)
    engine.index_many(org, spec, [old, kept, fresh])
    refresh(engine)
    assert engine.delete_stale(org, spec, "run-1", later(0).isoformat()) == 1
    refresh(engine)
    assert titles(run(engine, registry, caller(org, *EVERYTHING), "dormant")) == ["Dormant keeper", "Dormant newcomer"]


# --- memory only -------------------------------------------------------------------------------------------------
def test_an_outage_is_a_503_and_not_an_empty_page(registry):
    engine = InMemoryEngine("dev")
    who = caller(new_org(), *EVERYTHING)
    engine.down = True
    with pytest.raises(EngineUnavailable) as e:
        run(engine, registry, who, "anything")
    assert e.value.status == 503 and "anything" not in e.value.detail
    with pytest.raises(EngineUnavailable):
        service.suggest(who, q="any", registry=registry, engine=engine)


def test_counts_above_ten_thousand_report_the_bound_and_offer_no_deeper_page(registry):
    engine = InMemoryEngine("dev")
    org = new_org()
    spec = registry.types[COURSE]
    docs = [
        build_document(spec, organisation_id=org, record_id=f"c{i:05d}", raw=course("Bulk entry"), version=1, now=NOW)
        for i in range(10_005)
    ]
    engine.ensure_index(spec)
    engine.index_many(org, spec, docs)
    who = caller(org, *EVERYTHING)
    first = run(engine, registry, who, "bulk", limit=50)
    assert first["total"] == 10_000 and first["total_is_lower_bound"] is True and first["next_cursor"]
    # A cursor already 9 960 hits deep: the page it opens reaches the bound, so it offers no further cursor even
    # though more documents exist.
    deep = cursor.sign(
        SearchConfig.from_env().cursor_secret,
        {
            "u": who.user_id,
            "h": cursor.query_hash(None, "bulk", None, []),
            "s": [first["items"][0]["score"], ""],
            "n": 9_960,
        },
        ttl_seconds=60,
    )
    last = run(engine, registry, who, "bulk", limit=50, cursor_token=deep)
    assert len(last["items"]) == 50 and last["next_cursor"] is None
