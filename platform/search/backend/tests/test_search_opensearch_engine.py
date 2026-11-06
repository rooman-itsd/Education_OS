"""OpenSearchEngine against a recording client: what it sends (routing, filters, versions, aliases) and how it answers
a failing cluster. No network. The same engine runs against a real cluster in the contract suite when
SEARCH_TEST_OPENSEARCH_URL is set."""

import pytest
from eos_search.application.query import build_count_query, build_query, org_filter
from eos_search.domain.documents import build_document, version_of
from eos_search.domain.errors import EngineUnavailable
from eos_search.infrastructure import mappings
from eos_search.infrastructure.config import SearchConfig
from eos_search.infrastructure.opensearch_engine import OpenSearchEngine
from search_support import COURSE, NOW, READ_COURSE, caller, course, new_org, providers, registry_of

REGISTRY = registry_of(providers())
SPEC = REGISTRY.types[COURSE]


class Boom(Exception):  # noqa: N818
    def __init__(self, status_code=None, error=""):
        super().__init__("secret query text must never be logged")
        self.status_code, self.error = status_code, error


class _Namespace:
    def __init__(self, recorder, prefix):
        self._r, self._prefix = recorder, prefix

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return lambda **kw: self._r._do(f"{self._prefix}{name}", **kw)


class Recorder:
    """Stands in for opensearchpy.OpenSearch and its namespaces; calls are named like `indices.create`."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.responses: dict[str, object] = {}
        self.indices, self.cluster, self.cat = (
            _Namespace(self, "indices."),
            _Namespace(self, "cluster."),
            _Namespace(self, "cat."),
        )

    def _do(self, _call, /, **kw):
        self.calls.append((_call, kw))
        out = self.responses.get(_call)
        if isinstance(out, Exception):
            raise out
        return out(kw) if callable(out) else (out if out is not None else {})

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return lambda **kw: self._do(name, **kw)

    def of(self, name):
        return [kw for n, kw in self.calls if n == name]


def make(recorder=None):
    r = recorder or Recorder()
    r.responses.setdefault("indices.get_alias", {"eos-dev-academic-management-course-v1": {}})
    config = SearchConfig(**{**SearchConfig.from_env().__dict__, "engine": "opensearch"})
    return OpenSearchEngine(config, client=r), r


def doc(org, rid="c1", version=5):
    return build_document(SPEC, organisation_id=org, record_id=rid, raw=course("Intro"), version=version, now=NOW)


def test_search_is_sent_with_routing_the_organisation_filter_and_the_permission_filter():
    engine, r = make()
    org = new_org()
    r.responses["search"] = {"hits": {"hits": [], "total": {"value": 0, "relation": "eq"}}}
    q = build_query(caller(org, READ_COURSE), [SPEC], text="x")
    engine.search(q)
    (call,) = r.of("search")
    assert call["routing"] == org and call["index"] == ["eos-dev-academic-management-course"]
    assert org_filter(org) in call["body"]["query"]["bool"]["filter"]
    assert {"terms": {"read_any_of": [READ_COURSE]}} in call["body"]["query"]["bool"]["filter"][3]["bool"]["should"]


def test_search_parses_hits_highlights_total_and_facets():
    engine, r = make()
    org = new_org()
    r.responses["search"] = {
        "timed_out": False,
        "hits": {
            "total": {"value": 10000, "relation": "gte"},
            "hits": [
                {
                    "_score": 2.5,
                    "sort": [2.5, "d1"],
                    "highlight": {"fields.description": ["a b"]},
                    "_source": {"type": COURSE, "record_id": "c1", "title": "T", "fields": {"code": "X"}},
                }
            ],
        },
        "aggregations": {"types": {"buckets": [{"key": COURSE, "doc_count": 7}]}},
    }
    result = engine.search(build_query(caller(org, READ_COURSE), [SPEC], text="x"))
    assert result.total == 10000 and result.total_is_lower_bound and result.facets == {COURSE: 7}
    hit = result.hits[0]
    assert (hit.record_id, hit.title, hit.score, hit.sort) == ("c1", "T", 2.5, [2.5, "d1"])
    assert hit.highlight["fields.description"] == ["a b"]


@pytest.mark.parametrize("failure", [Boom(), Boom(503), Boom(429), Boom(400), TimeoutError(), ConnectionError()])
def test_any_failure_is_an_outage_and_never_leaks_what_was_asked(failure, caplog):
    engine, r = make()
    r.responses["search"] = failure
    with pytest.raises(EngineUnavailable) as e:
        engine.search(build_query(caller(new_org(), READ_COURSE), [SPEC], text="top secret words"))
    assert e.value.status == 503 and "secret" not in e.value.detail
    assert "secret" not in caplog.text and "top secret" not in caplog.text


@pytest.mark.parametrize(
    "body", [{"timed_out": True, "hits": {"hits": []}}, {"_shards": {"failed": 1}, "hits": {"hits": []}}]
)
def test_a_timed_out_or_partial_answer_is_an_outage_not_a_short_page(body):
    engine, r = make()
    r.responses["search"] = body
    with pytest.raises(EngineUnavailable):
        engine.search(build_query(caller(new_org(), READ_COURSE), [SPEC], text="x"))


def test_nothing_visible_means_no_request():
    engine, r = make()
    assert engine.search(build_query(caller(new_org(), READ_COURSE), [], text="x")).hits == []
    assert not r.of("search")


def test_counts_use_the_organisation_filter_and_routing():
    engine, r = make()
    org = new_org()
    r.responses["count"] = {"count": 4}
    assert engine.count_documents(build_count_query(org, SPEC)) == 4
    (call,) = r.of("count")
    assert call["routing"] == org and org_filter(org) in call["body"]["query"]["bool"]["filter"]


def test_writes_carry_routing_and_external_versions_and_a_conflict_is_stale():
    engine, r = make()
    org = new_org()
    r.responses["bulk"] = {"items": [{"index": {"status": 201}}, {"index": {"status": 409}}]}
    assert engine.index_many(org, SPEC, [doc(org, "a", 7), doc(org, "b", 8)]) == (1, 1)
    (call,) = r.of("bulk")
    meta = call["body"][0]["index"]
    assert meta == {
        "_index": "eos-dev-academic-management-course",
        "_id": f"{org}:{COURSE}:a",
        "routing": org,
        "version": 7,
        "version_type": "external",
    }
    assert call["body"][2]["index"]["version"] == 8
    assert engine.index_many(org, SPEC, []) == (0, 0)


def test_a_refused_document_in_a_bulk_is_an_error_not_a_silent_skip():
    engine, r = make()
    org = new_org()
    r.responses["bulk"] = {"items": [{"index": {"status": 400}}]}
    with pytest.raises(EngineUnavailable):
        engine.index_many(org, SPEC, [doc(org)])


def test_a_document_of_another_organisation_is_never_sent():
    engine, r = make()
    with pytest.raises(ValueError):
        engine.index_many(new_org(), SPEC, [doc(new_org())])
    assert not r.of("bulk")


def test_delete_uses_the_scoped_id_routing_and_version_and_maps_statuses():
    engine, r = make()
    org = new_org()
    assert engine.delete(org, SPEC, "c1", 9)
    (call,) = r.of("delete")
    assert call == {
        "index": "eos-dev-academic-management-course",
        "id": f"{org}:{COURSE}:c1",
        "routing": org,
        "version": 9,
        "version_type": "external",
    }
    r.responses["delete"] = Boom(409)
    assert engine.delete(org, SPEC, "c1", 1) is False
    r.responses["delete"] = Boom(404)
    assert engine.delete(org, SPEC, "c1", 1) is True
    r.responses["delete"] = Boom(500)
    with pytest.raises(EngineUnavailable):
        engine.delete(org, SPEC, "c1", 1)


def test_purge_is_a_delete_by_query_on_the_organisation_with_routing_across_this_environments_indexes():
    engine, r = make()
    org = new_org()
    r.responses["delete_by_query"] = {"deleted": 12}
    assert engine.delete_by_organisation(org) == 12
    (call,) = r.of("delete_by_query")
    assert call["index"] == "eos-dev-*" and call["routing"] == org
    assert call["body"] == {"query": {"term": {"organisation_id": org}}}


def test_stale_cleanup_filters_on_organisation_type_age_and_the_run_stamp():
    engine, r = make()
    org = new_org()
    r.responses["delete_by_query"] = {"deleted": 2}
    assert engine.delete_stale(org, SPEC, "run-9", "2026-11-05T12:00:00+00:00") == 2
    (call,) = r.of("delete_by_query")
    bool_ = call["body"]["query"]["bool"]
    assert {"term": {"organisation_id": org}} in bool_["filter"] and call["routing"] == org
    assert {"range": {"indexed_at": {"lt": "2026-11-05T12:00:00+00:00"}}} in bool_["filter"]
    assert bool_["must_not"] == [{"term": {"reindex_run": "run-9"}}]


def test_the_alias_swap_is_one_request_that_removes_and_adds():
    engine, r = make()
    engine.swap_alias(SPEC, 2)
    (call,) = r.of("indices.update_aliases")
    assert call["body"]["actions"] == [
        {"remove": {"index": "eos-dev-academic-management-course-v1", "alias": "eos-dev-academic-management-course"}},
        {"add": {"index": "eos-dev-academic-management-course-v2", "alias": "eos-dev-academic-management-course"}},
    ]


def test_a_new_index_version_is_created_next_to_the_live_one():
    engine, r = make()
    assert engine.build_next_index(SPEC) == 2
    create = r.of("indices.create")[-1]
    assert create["index"] == "eos-dev-academic-management-course-v2" and "aliases" not in create["body"]


def test_ensure_index_creates_version_one_with_the_alias_only_when_missing():
    engine, r = make()
    engine.ensure_index(SPEC)
    assert not r.of("indices.create")
    r.responses["indices.get_alias"] = Boom(404)
    engine.ensure_index(SPEC)
    (create,) = r.of("indices.create")
    assert create["index"].endswith("-v1") and create["body"]["aliases"] == {"eos-dev-academic-management-course": {}}


def test_mapping_current_compares_the_stored_hash():
    engine, r = make()
    r.responses["indices.get_mapping"] = {"x-v1": {"mappings": {"_meta": {"mapping_hash": SPEC.mapping_hash}}}}
    assert engine.mapping_current(SPEC)
    r.responses["indices.get_mapping"] = {"x-v1": {"mappings": {"_meta": {"mapping_hash": "old"}}}}
    assert not engine.mapping_current(SPEC)


def test_health_maps_the_cluster_status():
    engine, r = make()
    r.responses["cluster.health"] = {"status": "yellow", "active_shards": 6}
    r.responses["cat.indices"] = [{"index": "a"}, {"index": "b"}]
    h = engine.health()
    assert (h.cluster_status, h.indices, h.shards) == ("yellow", 2, 6)
    r.responses["cluster.health"] = Boom(503)
    with pytest.raises(EngineUnavailable):
        engine.health()


def test_the_mapping_is_strict_and_uses_the_closed_analyzer_list():
    body = mappings.mapping(SPEC)
    assert body["dynamic"] == "strict" and body["fields"]["dynamic"] == "strict" if "fields" in body else True
    props = body["properties"]
    assert props["fields"]["dynamic"] == "strict"
    assert props["title"]["fields"]["sayt"] == {"type": "search_as_you_type"}
    assert props["organisation_id"] == {"type": "keyword"} and props["read_any_of"] == {"type": "keyword"}
    assert props["fields"]["properties"]["credits"] == {"type": "double"}
    assert props["fields"]["properties"]["code"]["analyzer"] == "code"
    assert body["_meta"]["mapping_hash"] == SPEC.mapping_hash
    analyzers = mappings.settings(1, 1)["analysis"]["analyzer"]
    assert {"english", "name", "name_search", "code", "keyword_lower"} <= set(analyzers)
    person = REGISTRY.types["student-information.person"]
    assert mappings.mapping(person)["properties"]["title"]["search_analyzer"] == "name_search"


def test_the_engine_needs_the_package_when_no_client_is_given(monkeypatch):
    import builtins

    real = builtins.__import__

    def refuse(name, *a, **k):
        if name == "opensearchpy":
            raise ImportError(name)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", refuse)
    with pytest.raises(RuntimeError, match="opensearch-py"):
        OpenSearchEngine(SearchConfig.from_env())
    assert version_of(NOW)
