"""The one place a search request is built (docs/prd.md, decision 2).

`build_query(caller, ...)` is the only way to obtain a `Query`, and `Query` refuses to exist unless it carries the
organisation filter, the routing and (for anything that returns content) the permission filter. Suggestions, facet
aggregations and counts come from the same function, so there is no path that scores, counts or suggests a document
the caller may not read.

The body is the OpenSearch query DSL. The in-memory engine evaluates the same body, so the two engines cannot
disagree about who may see what."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from ..domain.declarations import TypeSpec
from ..domain.documents import HIGHLIGHT_CLOSE, HIGHLIGHT_OPEN, Caller

SEARCH, SUGGEST, COUNT = "search", "suggest", "count"
MAX_TOTAL = 10_000
TITLE_SUGGEST_FIELDS = ["title.sayt", "title.sayt._2gram", "title.sayt._3gram"]
_ALIAS_PART = re.compile(r"[^a-z0-9-]")


def org_filter(organisation_id: str) -> dict:
    return {"term": {"organisation_id": organisation_id}}


def acl_filter(user_id: str, keys: Sequence[str]) -> dict:
    """The caller may read a document if it names a permission the caller holds, or names the caller."""
    return {
        "bool": {
            "should": [{"terms": {"read_any_of": sorted(keys)}}, {"term": {"read_users": user_id}}],
            "minimum_should_match": 1,
        }
    }


@dataclass(frozen=True)
class Query:
    kind: str
    organisation_id: str
    routing: str
    type_keys: tuple[str, ...]
    body: dict
    size: int
    user_id: str | None
    acl_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        filters = self.body.get("query", {}).get("bool", {}).get("filter", [])
        if not self.organisation_id or self.routing != self.organisation_id:
            raise ValueError("a query needs an organisation and routes by it")
        if org_filter(self.organisation_id) not in filters:
            raise ValueError("a query without an organisation filter cannot be constructed")
        if self.kind in (SEARCH, SUGGEST) and (
            not self.user_id or acl_filter(self.user_id, self.acl_keys) not in filters
        ):
            raise ValueError("a query without a permission filter cannot be constructed")


def alias_name(environment: str, type_key: str) -> str:
    """eos-<environment>-<module>-<type>: the alias queries use; the index behind it is that name plus -v<n>."""
    module, _, name = type_key.partition(".")
    return f"eos-{_ALIAS_PART.sub('', environment.lower())}-{module}-{name}"


def _text_clause(spec: TypeSpec, text: str) -> dict:
    title = spec.title_field
    should: list[dict] = [
        {"match": {"title": {"query": text, "operator": "and", "boost": title.boost}}},
        {"multi_match": {"query": text, "type": "bool_prefix", "fields": TITLE_SUGGEST_FIELDS, "boost": title.boost}},
    ]
    for f in spec.text_fields:
        if f.role != "title":
            should.append({"match": {f"fields.{f.name}": {"query": text, "operator": "and", "boost": f.boost}}})
    return {
        "bool": {
            "filter": [{"term": {"type": spec.key}}],
            "must": [{"bool": {"should": should, "minimum_should_match": 1}}],
        }
    }


def build_query(
    caller: Caller,
    specs: Sequence[TypeSpec],
    *,
    text: str,
    kind: str = SEARCH,
    restrict_types: Sequence[str] | None = None,
    filters: Sequence[tuple[str, object]] = (),
    limit: int = 20,
    search_after: Sequence | None = None,
    timeout_ms: int = 2000,
) -> Query:
    """`specs` are the types in scope that the caller may use (the registry filtered them by entitlement and by
    permission); `restrict_types` narrows the hits, but not the facets, to some of them."""
    if kind not in (SEARCH, SUGGEST):
        raise ValueError("build_query builds search and suggest queries; counts use build_count_query")
    org = caller.organisation_id
    declared = {k for s in specs for k in s.read_any_of}
    keys = tuple(sorted(caller.grants & declared))
    type_keys = tuple(s.key for s in specs)
    modules = sorted({s.module for s in specs})
    filter_clauses: list[dict] = [
        org_filter(org),
        {"terms": {"type": list(type_keys)}},
        {"terms": {"module": modules}},
        acl_filter(caller.user_id, keys),
    ]
    for name, value in filters:
        filter_clauses.append({"term": {f"fields.{name}": value}})
    if kind == SEARCH:
        must = (
            [{"bool": {"should": [_text_clause(s, text) for s in specs], "minimum_should_match": 1}}] if specs else []
        )
    else:
        must = [{"multi_match": {"query": text, "type": "bool_prefix", "fields": TITLE_SUGGEST_FIELDS}}]
    body: dict = {
        "size": limit,
        "timeout": f"{timeout_ms}ms",
        "track_total_hits": MAX_TOTAL,
        "query": {"bool": {"filter": filter_clauses, "must": must}},
        "sort": [{"_score": "desc"}, {"doc_id": "asc"}],
    }
    if kind == SEARCH:
        body["_source"] = ["record_id", "type", "title", "fields"]
        body["aggs"] = {"types": {"terms": {"field": "type", "size": 100}}}
        snippet_fields = sorted({f"fields.{f.name}" for s in specs for f in s.snippet_fields})
        if snippet_fields:
            body["highlight"] = {
                "pre_tags": [HIGHLIGHT_OPEN],
                "post_tags": [HIGHLIGHT_CLOSE],
                "fragment_size": 160,
                "number_of_fragments": 1,
                "require_field_match": True,
                "fields": {name: {} for name in snippet_fields},
            }
        if restrict_types is not None:
            body["post_filter"] = {"terms": {"type": [t for t in restrict_types if t in type_keys]}}
    else:
        body["_source"] = ["record_id", "type", "title"]
    if search_after:
        body["search_after"] = list(search_after)
    return Query(kind, org, org, type_keys if specs else (), body, limit, caller.user_id, keys)


def build_count_query(organisation_id: str, spec: TypeSpec) -> Query:
    """Documents of one type in one organisation, for index health. Organisation filter only: it counts what is
    indexed, it returns no content and no title."""
    body = {
        "size": 0,
        "track_total_hits": True,
        "query": {"bool": {"filter": [org_filter(organisation_id), {"term": {"type": spec.key}}]}},
    }
    return Query(COUNT, organisation_id, organisation_id, (spec.key,), body, 0, None, ())
