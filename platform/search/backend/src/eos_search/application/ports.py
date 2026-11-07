"""The ports of search: the engine behind it and the provider a module implements (docs/prd.md, decisions 1 and 8).

`SearchEngine` is the only thing that touches an index. Every read goes through a `Query`, which can be built only
by `application.query.build_query` (it needs a `Caller`, and refuses to exist without the organisation and the
permission filter). Every write and delete carries an organisation id."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..domain.declarations import TypeSpec
from .query import Query


@dataclass(frozen=True)
class RawHit:
    type: str
    record_id: str
    title: str
    score: float
    source: dict
    highlight: dict[str, list[str]]
    sort: list


@dataclass(frozen=True)
class RawResult:
    hits: list[RawHit] = field(default_factory=list)
    total: int = 0
    total_is_lower_bound: bool = False
    facets: dict[str, int] = field(default_factory=dict)  # type key -> count over the whole result set


@dataclass(frozen=True)
class EngineHealth:
    cluster_status: str  # green | yellow | red | unknown
    indices: int
    shards: int


class SearchEngine(Protocol):
    name: str

    def ensure_index(self, spec: TypeSpec) -> None:
        """Create the type's index (version 1) and its alias if it has none. Idempotent."""

    def mapping_current(self, spec: TypeSpec) -> bool:
        """True when the live index was built from this spec's mapping_hash."""

    def build_next_index(self, spec: TypeSpec) -> int:
        """Create index version n+1 with the spec's current mapping and return n+1. Not live yet."""

    def index_many(
        self,
        organisation_id: str,
        spec: TypeSpec,
        documents: Sequence[dict],
        *,
        version: int | None = None,
        target_version: int | None = None,
    ) -> tuple[int, int]:
        """Write documents of one organisation. Each document's own `source_version` is its external version
        unless `version` overrides it. Returns (written, stale): a stale write lost to a newer version and is
        not an error. `target_version` writes into that (not yet live) index version instead of the alias."""

    def delete(self, organisation_id: str, spec: TypeSpec, record_id: str, version: int) -> bool:
        """Delete one document at an external version. False when a newer version exists."""

    def delete_by_organisation(self, organisation_id: str) -> int:
        """Remove every document of the organisation from every search index. Returns the count."""

    def delete_stale(self, organisation_id: str, spec: TypeSpec, run: str, indexed_before: str) -> int:
        """Remove the organisation's documents of the type that carry no `reindex_run == run` and were indexed
        before `indexed_before` (ISO time). Returns the count."""

    def search(self, query: Query) -> RawResult: ...

    def count_documents(self, query: Query) -> int: ...

    def swap_alias(self, spec: TypeSpec, version: int) -> None:
        """Atomically make index version `version` the one behind the type's alias."""

    def health(self) -> EngineHealth: ...


class DocumentProvider(Protocol):
    """Implemented by a module, registered on the `eos.search_documents` entry-point group under the module's
    name. Both methods run in the module's own code, with its own session, in the organisation's context."""

    declaration: Any  # the parsed contracts/searchable.yaml (a mapping) or a path to it

    def get_document(self, organisation_id: str, type: str, record_id: str) -> dict | None:
        """The record's searchable document, or None when it is gone or no longer searchable."""

    def iter_documents(self, organisation_id: str, type: str, after_id: str | None, limit: int) -> Sequence[dict]:
        """Up to `limit` documents of the type in record-id order after `after_id`; an empty list at the end.
        Each carries its `record_id`."""
