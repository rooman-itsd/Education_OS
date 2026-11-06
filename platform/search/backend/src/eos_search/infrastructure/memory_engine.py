"""The in-process engine behind the SearchEngine port: the default in dev and CI, refused when EOS_DEV_MODE is
false (infrastructure/config.py).

It evaluates the very query body `application.query.build_query` produces, the same organisation, type, module and
permission filters, post_filter, facets, total, sort and `search_after`, so a leak the builder let through would show
here too. What it cannot reproduce faithfully is analysis: text is lower-cased and split on word characters, with
no stemming, no folding and no synonyms, and relevance is a simple sum. Those are tested only against the real engine
(marker `opensearch`)."""

from __future__ import annotations

import copy
import re
import threading
from collections.abc import Sequence

from ..application.ports import EngineHealth, RawHit, RawResult
from ..application.query import COUNT, Query, alias_name
from ..domain.declarations import TypeSpec
from ..domain.documents import HIGHLIGHT_CLOSE, HIGHLIGHT_OPEN, document_id
from ..domain.errors import EngineUnavailable

_WORD = re.compile(r"\w+", re.UNICODE)


def tokens(text) -> list[str]:
    return _WORD.findall(str(text).lower()) if text is not None else []


def _get(doc: dict, path: str):
    if path.startswith("title."):  # title.sayt and its shingle sub-fields
        return doc.get("title")
    node = doc
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


class InMemoryEngine:
    name = "memory"

    def __init__(self, environment: str = "dev"):
        self.environment = environment
        self._lock = threading.RLock()
        self.indices: dict[str, dict] = {}  # index name -> {"docs": {doc_id: doc}, "mapping_hash": str}
        self.aliases: dict[str, str] = {}  # alias -> index name
        self._versions: dict[tuple[str, str], int] = {}  # (index, doc_id) -> last external version, kept after delete
        self.down = False  # a test sets this to simulate an outage

    # --- helpers -----------------------------------------------------------------------------------------------
    def _check(self) -> None:
        if self.down:
            raise EngineUnavailable()

    def _alias(self, spec_or_key) -> str:
        key = spec_or_key if isinstance(spec_or_key, str) else spec_or_key.key
        return alias_name(self.environment, key)

    @staticmethod
    def _version_of(index: str) -> int:
        return int(index.rsplit("-v", 1)[1])

    # --- port --------------------------------------------------------------------------------------------------
    def ensure_index(self, spec: TypeSpec) -> None:
        with self._lock:
            self._check()
            alias = self._alias(spec)
            if alias not in self.aliases:
                name = f"{alias}-v1"
                self.indices.setdefault(name, {"docs": {}, "mapping_hash": spec.mapping_hash})
                self.aliases[alias] = name

    def mapping_current(self, spec: TypeSpec) -> bool:
        with self._lock:
            self._check()
            live = self.aliases.get(self._alias(spec))
            return live is not None and self.indices[live]["mapping_hash"] == spec.mapping_hash

    def build_next_index(self, spec: TypeSpec) -> int:
        with self._lock:
            self._check()
            self.ensure_index(spec)
            alias = self._alias(spec)
            n = max(self._version_of(i) for i in self.indices if i.startswith(alias + "-v")) + 1
            self.indices[f"{alias}-v{n}"] = {"docs": {}, "mapping_hash": spec.mapping_hash}
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
        with self._lock:
            self._check()
            self.ensure_index(spec)
            alias = self._alias(spec)
            index = self.aliases[alias] if target_version is None else f"{alias}-v{target_version}"
            written = stale = 0
            for doc in documents:
                if doc["organisation_id"] != organisation_id or doc["type"] != spec.key:
                    raise ValueError("document does not belong to this organisation and type")
                v = version if version is not None else doc["source_version"]
                if self._versions.get((index, doc["doc_id"]), -1) >= v:
                    stale += 1
                    continue
                self._versions[(index, doc["doc_id"])] = v
                self.indices[index]["docs"][doc["doc_id"]] = copy.deepcopy(doc)
                written += 1
            return written, stale

    def delete(self, organisation_id: str, spec: TypeSpec, record_id: str, version: int) -> bool:
        with self._lock:
            self._check()
            self.ensure_index(spec)
            index = self.aliases[self._alias(spec)]
            doc_id = document_id(organisation_id, spec.key, record_id)
            if self._versions.get((index, doc_id), -1) >= version:
                return False
            self._versions[(index, doc_id)] = version
            self.indices[index]["docs"].pop(doc_id, None)
            return True

    def delete_by_organisation(self, organisation_id: str) -> int:
        with self._lock:
            self._check()
            count = 0
            for name, index in self.indices.items():
                gone = [d for d, doc in index["docs"].items() if doc["organisation_id"] == organisation_id]
                for d in gone:
                    del index["docs"][d]
                    self._versions.pop((name, d), None)
                count += len(gone)
            return count

    def delete_stale(self, organisation_id: str, spec: TypeSpec, run: str, indexed_before: str) -> int:
        with self._lock:
            self._check()
            self.ensure_index(spec)
            docs = self.indices[self.aliases[self._alias(spec)]]["docs"]
            gone = [
                d
                for d, doc in docs.items()
                if doc["organisation_id"] == organisation_id
                and doc["type"] == spec.key
                and doc.get("reindex_run") != run
                and doc["indexed_at"] < indexed_before
            ]
            for d in gone:
                del docs[d]
            return len(gone)

    def swap_alias(self, spec: TypeSpec, version: int) -> None:
        with self._lock:
            self._check()
            alias = self._alias(spec)
            name = f"{alias}-v{version}"
            if name not in self.indices:
                raise ValueError("no such index version")
            self.aliases[alias] = name

    def health(self) -> EngineHealth:
        with self._lock:
            self._check()
            return EngineHealth("green", len(self.indices), len(self.indices))

    def count_documents(self, query: Query) -> int:
        return self.search(query).total

    def search(self, query: Query) -> RawResult:
        with self._lock:
            self._check()
            body = query.body
            docs: list[dict] = []
            for key in query.type_keys:
                live = self.aliases.get(self._alias(key))
                if live is not None:
                    docs.extend(self.indices[live]["docs"].values())
            matched: list[tuple[float, dict]] = []
            for doc in docs:
                score = _eval(body["query"], doc)
                if score is not None:
                    matched.append((round(score, 6), doc))
            facets: dict[str, int] = {}
            if "aggs" in body:
                for _, doc in matched:
                    facets[doc["type"]] = facets.get(doc["type"], 0) + 1
            if "post_filter" in body:
                matched = [(s, d) for s, d in matched if _eval(body["post_filter"], d) is not None]
            matched.sort(key=lambda sd: (-sd[0], sd[1]["doc_id"]))
            total = len(matched)
            limit_total = body.get("track_total_hits")
            lower = isinstance(limit_total, int) and not isinstance(limit_total, bool) and total > limit_total
            if lower:
                total = limit_total
            after = body.get("search_after")
            if after:
                matched = [(s, d) for s, d in matched if s < after[0] or (s == after[0] and d["doc_id"] > after[1])]
            page = matched[: body.get("size", 10)]
            words = _query_words(body["query"])
            source_keys = body.get("_source")
            hits = [
                RawHit(
                    type=d["type"],
                    record_id=d["record_id"],
                    title=d["title"],
                    score=s,
                    source={k: copy.deepcopy(d[k]) for k in (source_keys or d) if k in d},
                    highlight=_highlight(body.get("highlight"), d, words),
                    sort=[s, d["doc_id"]],
                )
                for s, d in page
            ]
            if query.kind == COUNT:
                hits = []
            return RawResult(hits=hits, total=total, total_is_lower_bound=lower, facets=facets)

    # --- test support ------------------------------------------------------------------------------------------
    def all_documents(self) -> list[dict]:
        with self._lock:
            return [copy.deepcopy(d) for i in self.aliases.values() for d in self.indices[i]["docs"].values()]

    def document(self, doc_id: str) -> dict | None:
        with self._lock:
            for i in self.aliases.values():
                if doc_id in self.indices[i]["docs"]:
                    return copy.deepcopy(self.indices[i]["docs"][doc_id])
        return None


# --- the query DSL subset build_query uses -----------------------------------------------------------------------
def _eval(clause: dict, doc: dict) -> float | None:
    """Score of `doc` for the clause, or None when it does not match. Filter clauses score 0."""
    ((name, spec),) = clause.items()
    if name == "term":
        ((field, value),) = spec.items()
        got = _get(doc, field)
        got = got if isinstance(got, list) else [got]
        return 0.0 if any(g == value and isinstance(g, bool) == isinstance(value, bool) for g in got) else None
    if name == "terms":
        ((field, values),) = spec.items()
        got = _get(doc, field)
        got = got if isinstance(got, list) else [got]
        return 0.0 if any(g in values for g in got if g is not None) else None
    if name == "match":
        ((field, opts),) = spec.items()
        wanted = tokens(opts["query"])
        have = set(tokens(_get(doc, field)))
        ok = bool(wanted) and (
            all(t in have for t in wanted) if opts.get("operator") == "and" else any(t in have for t in wanted)
        )
        return float(opts.get("boost", 1)) * len(wanted) if ok else None
    if name == "multi_match":
        wanted = tokens(spec["query"])
        if not wanted:
            return None
        title = tokens(doc.get("title"))
        ok = all(t in title for t in wanted[:-1]) and any(w.startswith(wanted[-1]) for w in title)
        return float(spec.get("boost", 1)) * len(wanted) if ok else None
    if name == "bool":
        total = 0.0
        for sub in spec.get("filter", []):
            if _eval(sub, doc) is None:
                return None
        for sub in spec.get("must", []):
            s = _eval(sub, doc)
            if s is None:
                return None
            total += s
        for sub in spec.get("must_not", []):
            if _eval(sub, doc) is not None:
                return None
        should = [s for s in (_eval(sub, doc) for sub in spec.get("should", [])) if s is not None]
        needed = spec.get("minimum_should_match", 0 if spec.get("filter") or spec.get("must") else 1)
        if spec.get("should") and len(should) < needed:
            return None
        return total + sum(should)
    raise ValueError(f"the in-memory engine does not implement the {name} clause")


def _query_words(clause) -> list[str]:
    found: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "match":
                    for opts in value.values():
                        found.extend(tokens(opts["query"]))
                elif key == "multi_match":
                    found.extend(tokens(value["query"]))
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(clause)
    return list(dict.fromkeys(found))


def _highlight(spec: dict | None, doc: dict, words: list[str]) -> dict[str, list[str]]:
    if not spec or not words:
        return {}
    out: dict[str, list[str]] = {}
    for path in spec["fields"]:
        text = _get(doc, path)
        if not isinstance(text, str):
            continue
        spans = [m for m in _WORD.finditer(text) if any(m.group().lower().startswith(w) for w in words)]
        if not spans:
            continue
        start = max(0, spans[0].start() - 40)
        piece = text[start : start + spec.get("fragment_size", 160)]
        marked = _WORD.sub(
            lambda m: (
                f"{HIGHLIGHT_OPEN}{m.group()}{HIGHLIGHT_CLOSE}"
                if any(m.group().lower().startswith(w) for w in words)
                else m.group()
            ),
            piece,
        )
        out[path] = [marked]
    return out
