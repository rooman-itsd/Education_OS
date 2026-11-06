"""OpenSearch behind the SearchEngine port, using opensearch-py (approved stack).

Index layout (docs/prd.md, decision 6): one shared index per type per environment, `eos-<env>-<module>-<type>-v<n>`
behind the alias `eos-<env>-<module>-<type>`. Every document is written and queried with `routing=<organisation_id>`.
Writes carry external versions. Any failure of the engine, or a query that timed out, is `EngineUnavailable`: an outage
is never an empty page.

The client is injectable, so unit tests run the request building against a recording fake without a network; the
contract suite runs against a real cluster only when SEARCH_TEST_OPENSEARCH_URL is set."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from typing import Any

from ..application.ports import EngineHealth, RawHit, RawResult
from ..application.query import COUNT, MAX_TOTAL, Query, alias_name
from ..domain.declarations import TypeSpec
from ..domain.documents import document_id
from ..domain.errors import EngineUnavailable
from . import mappings
from .config import SearchConfig

log = logging.getLogger("eos.search")
_VERSION = re.compile(r"-v(\d+)$")
PURGE_TIMEOUT_SECONDS = 120


def _status(error: Exception) -> int | None:
    value = getattr(error, "status_code", None)
    return value if isinstance(value, int) else None


class OpenSearchEngine:
    name = "opensearch"

    def __init__(self, config: SearchConfig, client: Any | None = None):
        self.config = config
        self.environment = config.index_environment
        self.client = client if client is not None else self._connect(config)

    @staticmethod
    def _connect(config: SearchConfig):
        try:
            from opensearchpy import OpenSearch
        except ImportError as e:  # pragma: no cover - the package is on the approved stack
            raise RuntimeError("SEARCH_ENGINE=opensearch needs the opensearch-py package") from e
        auth = (config.opensearch_user, config.opensearch_password) if config.opensearch_user else None
        return OpenSearch(
            hosts=[config.opensearch_url],
            http_auth=auth,
            verify_certs=config.opensearch_verify_certs,
            timeout=config.opensearch_timeout_seconds,
            max_retries=0,
        )

    # --- helpers -----------------------------------------------------------------------------------------------
    def _alias(self, spec_or_key) -> str:
        return alias_name(self.environment, spec_or_key if isinstance(spec_or_key, str) else spec_or_key.key)

    def _unavailable(self, error: Exception) -> EngineUnavailable:
        # The type only: an error message can carry a query or a document.
        log.warning("search engine call failed: %s (status %s)", type(error).__name__, _status(error))
        return EngineUnavailable()

    def _live_index(self, alias: str) -> str | None:
        try:
            found = self.client.indices.get_alias(name=alias)
        except Exception as e:  # noqa: BLE001
            if _status(e) == 404:
                return None
            raise self._unavailable(e) from None
        return sorted(found, key=lambda n: int(_VERSION.search(n).group(1)) if _VERSION.search(n) else 0)[-1]

    # --- port --------------------------------------------------------------------------------------------------
    def ensure_index(self, spec: TypeSpec) -> None:
        alias = self._alias(spec)
        if self._live_index(alias) is not None:
            return
        body = {
            "settings": mappings.settings(self.config.index_shards, self.config.index_replicas),
            "mappings": mappings.mapping(spec),
            "aliases": {alias: {}},
        }
        try:
            self.client.indices.create(index=f"{alias}-v1", body=body)
        except Exception as e:  # noqa: BLE001
            if _status(e) == 400 and "already_exists" in str(getattr(e, "error", "")):
                return  # another worker created it first
            raise self._unavailable(e) from None

    def mapping_current(self, spec: TypeSpec) -> bool:
        self.ensure_index(spec)
        try:
            found = self.client.indices.get_mapping(index=self._alias(spec))
        except Exception as e:  # noqa: BLE001
            raise self._unavailable(e) from None
        meta = next(iter(found.values()), {}).get("mappings", {}).get("_meta", {})
        return meta.get("mapping_hash") == spec.mapping_hash

    def build_next_index(self, spec: TypeSpec) -> int:
        self.ensure_index(spec)
        alias = self._alias(spec)
        live = self._live_index(alias)
        n = int(_VERSION.search(live).group(1)) + 1 if live and _VERSION.search(live) else 1
        name = f"{alias}-v{n}"
        body = {
            "settings": mappings.settings(self.config.index_shards, self.config.index_replicas),
            "mappings": mappings.mapping(spec),
        }
        try:
            self.client.indices.create(index=name, body=body)
        except Exception as e:  # noqa: BLE001
            if _status(e) != 400:
                raise self._unavailable(e) from None
            # A build that failed earlier left this index half filled and not live: start it again.
            try:
                self.client.indices.delete(index=name)
                self.client.indices.create(index=name, body=body)
            except Exception as e2:  # noqa: BLE001
                raise self._unavailable(e2) from None
        return n

    def index_many(
        self,
        organisation_id: str,
        spec: TypeSpec,
        documents: Sequence[dict],
        *,
        version: int | None = None,
        target_version: int | None = None,
    ) -> tuple[int, int]:
        if not documents:
            return 0, 0
        self.ensure_index(spec)
        alias = self._alias(spec)
        target = alias if target_version is None else f"{alias}-v{target_version}"
        actions: list[dict] = []
        for doc in documents:
            if doc["organisation_id"] != organisation_id or doc["type"] != spec.key:
                raise ValueError("document does not belong to this organisation and type")
            actions.append(
                {
                    "index": {
                        "_index": target,
                        "_id": doc["doc_id"],
                        "routing": organisation_id,
                        "version": version if version is not None else doc["source_version"],
                        "version_type": "external",
                    }
                }
            )
            actions.append(doc)
        try:
            response = self.client.bulk(body=actions, request_timeout=self.config.opensearch_timeout_seconds * 15)
        except Exception as e:  # noqa: BLE001
            raise self._unavailable(e) from None
        written = stale = failed = 0
        for item in response.get("items", []):
            status = next(iter(item.values())).get("status", 500)
            if status == 409:
                stale += 1
            elif 200 <= status < 300:
                written += 1
            else:
                failed += 1
        if failed:
            log.warning("search bulk write: %d of %d documents refused by the engine", failed, len(documents))
            raise EngineUnavailable()
        return written, stale

    def delete(self, organisation_id: str, spec: TypeSpec, record_id: str, version: int) -> bool:
        self.ensure_index(spec)
        try:
            self.client.delete(
                index=self._alias(spec),
                id=document_id(organisation_id, spec.key, record_id),
                routing=organisation_id,
                version=version,
                version_type="external",
            )
            return True
        except Exception as e:  # noqa: BLE001
            if _status(e) == 409:
                return False
            if _status(e) == 404:
                return True  # already gone; the version is recorded as a tombstone
            raise self._unavailable(e) from None

    def delete_by_organisation(self, organisation_id: str) -> int:
        try:
            response = self.client.delete_by_query(
                index=f"eos-{self.environment.lower()}-*",
                body={"query": {"term": {"organisation_id": organisation_id}}},
                routing=organisation_id,
                conflicts="proceed",
                refresh=True,
                ignore_unavailable=True,
                request_timeout=PURGE_TIMEOUT_SECONDS,
            )
        except Exception as e:  # noqa: BLE001
            raise self._unavailable(e) from None
        return int(response.get("deleted", 0))

    def delete_stale(self, organisation_id: str, spec: TypeSpec, run: str, indexed_before: str) -> int:
        self.ensure_index(spec)
        body = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"organisation_id": organisation_id}},
                        {"term": {"type": spec.key}},
                        {"range": {"indexed_at": {"lt": indexed_before}}},
                    ],
                    "must_not": [{"term": {"reindex_run": run}}],
                }
            }
        }
        try:
            response = self.client.delete_by_query(
                index=self._alias(spec),
                body=body,
                routing=organisation_id,
                conflicts="proceed",
                refresh=True,
                request_timeout=PURGE_TIMEOUT_SECONDS,
            )
        except Exception as e:  # noqa: BLE001
            raise self._unavailable(e) from None
        return int(response.get("deleted", 0))

    def swap_alias(self, spec: TypeSpec, version: int) -> None:
        alias = self._alias(spec)
        old = self._live_index(alias)
        actions = [{"add": {"index": f"{alias}-v{version}", "alias": alias}}]
        if old is not None and old != f"{alias}-v{version}":
            actions.insert(0, {"remove": {"index": old, "alias": alias}})
        try:
            self.client.indices.update_aliases(body={"actions": actions})  # one request: atomic
        except Exception as e:  # noqa: BLE001
            raise self._unavailable(e) from None

    def search(self, query: Query) -> RawResult:
        if not query.type_keys:
            return RawResult()
        indices = [self._alias(k) for k in query.type_keys]
        if query.kind == COUNT:
            try:
                response = self.client.count(
                    index=indices,
                    body={"query": query.body["query"]},
                    routing=query.routing,
                    ignore_unavailable=True,
                    request_timeout=self.config.opensearch_timeout_seconds,
                )
            except Exception as e:  # noqa: BLE001
                raise self._unavailable(e) from None
            return RawResult(total=int(response.get("count", 0)))
        try:
            response = self.client.search(
                index=indices,
                body=query.body,
                routing=query.routing,
                ignore_unavailable=True,
                request_timeout=self.config.opensearch_timeout_seconds,
            )
        except Exception as e:  # noqa: BLE001
            raise self._unavailable(e) from None
        if response.get("timed_out") or response.get("_shards", {}).get("failed"):
            log.warning("search query timed out or a shard failed")
            raise EngineUnavailable()
        hits = [
            RawHit(
                type=h["_source"]["type"],
                record_id=h["_source"]["record_id"],
                title=h["_source"]["title"],
                score=float(h.get("_score") or 0.0),
                source=h["_source"],
                highlight=h.get("highlight") or {},
                sort=h.get("sort") or [],
            )
            for h in response.get("hits", {}).get("hits", [])
        ]
        total = response.get("hits", {}).get("total", {})
        value, relation = int(total.get("value", len(hits))), total.get("relation", "eq")
        facets = {
            b["key"]: int(b["doc_count"]) for b in response.get("aggregations", {}).get("types", {}).get("buckets", [])
        }
        return RawResult(
            hits=hits,
            total=min(value, MAX_TOTAL),
            total_is_lower_bound=relation == "gte" or value > MAX_TOTAL,
            facets=facets,
        )

    def count_documents(self, query: Query) -> int:
        return self.search(query).total

    def health(self) -> EngineHealth:
        try:
            cluster = self.client.cluster.health()
            listed = self.client.cat.indices(index=f"eos-{self.environment.lower()}-*", format="json")
        except Exception as e:  # noqa: BLE001
            if _status(e) == 404:
                listed = []
            else:
                raise self._unavailable(e) from None
        status = cluster.get("status", "unknown")
        return EngineHealth(
            status if status in ("green", "yellow", "red") else "unknown",
            len(listed),
            int(cluster.get("active_shards", 0)),
        )
