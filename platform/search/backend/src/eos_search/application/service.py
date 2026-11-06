"""Answering searches: input checks, the call into build_query and the engine, and the shape of the response.

Every refusal here is a SearchError with one sentence that never repeats the query. An outage is an
EngineUnavailable (503), never an empty result."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date, datetime
from urllib.parse import quote

from ..domain.declarations import FIELD_RE, TypeSpec
from ..domain.documents import Caller, clean_text
from ..domain.errors import SearchError
from ..infrastructure.config import SearchConfig
from ..infrastructure.engine import get_engine
from . import cursor
from .ports import RawHit, SearchEngine
from .query import MAX_TOTAL, SUGGEST, build_query
from .registry import Registry, get_registry

MAX_PARAM_LENGTH = 1000
MAX_TYPES = 20
MAX_FILTERS = 10
MAX_FILTER_VALUE = 200
MAX_TYPE_LENGTH = 130
SUGGEST_MIN, SUGGEST_MAX, SUGGEST_LIMIT_MAX = 2, 50, 10
MAX_SNIPPET = 300


def normalise_q(raw: str, *, minimum: int, maximum: int) -> str:
    """Plain text only: control characters and the highlight markers are dropped, the rest is trimmed. The result
    is passed to match queries, never parsed as query syntax."""
    text = clean_text(raw or "", 10_000)
    if not (minimum <= len(text) <= maximum):
        raise SearchError(422, f"q must be {minimum} to {maximum} characters")
    return text


def parse_types(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    if len(raw) > MAX_PARAM_LENGTH:
        raise SearchError(422, f"types is at most {MAX_PARAM_LENGTH} characters")
    items = [t.strip() for t in raw.split(",") if t.strip()]
    if len(items) > MAX_TYPES:
        raise SearchError(422, f"types has at most {MAX_TYPES} entries")
    return [t for t in dict.fromkeys(items) if len(t) <= MAX_TYPE_LENGTH]


def _coerce_filter(spec: TypeSpec, name: str, raw: str):
    kind = spec.fields[name].kind
    try:
        if kind == "keyword":
            return raw
        if kind == "boolean":
            if raw.lower() not in ("true", "false"):
                raise ValueError
            return raw.lower() == "true"
        if kind == "number":
            number = float(raw)
            if not math.isfinite(number):
                raise ValueError
            return int(number) if number.is_integer() and abs(number) < 2**53 else number
        if kind == "date":
            return datetime.fromisoformat(raw).isoformat() if "T" in raw else date.fromisoformat(raw).isoformat()
    except ValueError:
        pass
    raise SearchError(422, f"the value for filter {name} is not a valid {kind}")


def parse_filters(raw: str | None, specs: Sequence[TypeSpec]) -> list[tuple[str, object]]:
    if not raw or not raw.strip():
        return []
    if len(raw) > MAX_PARAM_LENGTH:
        raise SearchError(422, f"filters is at most {MAX_PARAM_LENGTH} characters")
    pairs = [p for p in raw.split(",") if p.strip()]
    if len(pairs) > MAX_FILTERS:
        raise SearchError(422, f"filters has at most {MAX_FILTERS} pairs")
    out: list[tuple[str, object]] = []
    seen: set[str] = set()
    for pair in pairs:
        name, sep, value = pair.partition(":")
        name, value = name.strip(), value.strip()
        if not sep or not FIELD_RE.match(name) or not value or len(value) > MAX_FILTER_VALUE:
            raise SearchError(422, "each filter must be field:value")
        owner = next((s for s in specs if name in s.filterable_fields), None)
        if owner is None:
            raise SearchError(422, f"{name} is not a filterable field of this module")
        if name in seen:
            raise SearchError(422, f"filter {name} is given twice")
        seen.add(name)
        out.append((name, _coerce_filter(owner, name, value)))
    return out


def _snippet(spec: TypeSpec, hit: RawHit) -> str | None:
    for f in spec.snippet_fields:
        fragments = hit.highlight.get(f"fields.{f.name}") or []
        if fragments:
            return str(fragments[0])[:MAX_SNIPPET]
    return None


def hit_out(spec: TypeSpec, hit: RawHit) -> dict:
    stored = hit.source.get("fields") or {}
    fields = {}
    for f in spec.display_fields:
        value = stored.get(f.name)
        if value is not None:
            fields[f.name] = ("true" if value else "false") if isinstance(value, bool) else str(value)
    return {
        "type": spec.key,
        "id": hit.record_id,
        "title": hit.title[:300],
        "snippet": _snippet(spec, hit),
        "url": spec.url.replace("{id}", quote(hit.record_id, safe="")),
        "fields": fields,
        "score": hit.score,
    }


def search(
    caller: Caller,
    *,
    q: str,
    module: str | None = None,
    types: str | None = None,
    filters: str | None = None,
    cursor_token: str | None = None,
    limit: int = 20,
    registry: Registry | None = None,
    engine: SearchEngine | None = None,
    config: SearchConfig | None = None,
) -> dict:
    registry = registry or get_registry()
    config = config or SearchConfig.from_env().validate()
    text = normalise_q(q, minimum=1, maximum=config.max_query_length)
    if not 1 <= limit <= config.max_page_size:
        raise SearchError(422, f"limit must be 1 to {config.max_page_size}")
    if module is not None and (
        not registry.module_types(module)
        or (caller.entitled_modules is not None and module not in caller.entitled_modules)
    ):
        raise SearchError(404, "no such module with searchable types")
    specs = registry.visible_types(caller, module=module)
    restrict = parse_types(types)
    pairs = parse_filters(filters, registry.module_types(module)) if module is not None else []
    if filters and module is None:
        raise SearchError(422, "filters are only accepted on a module's endpoint")
    bound = cursor.query_hash(module, text, sorted(restrict) if restrict is not None else None, pairs)
    after, seen = None, 0
    if cursor_token:
        payload = cursor.verify(config.cursor_secret, cursor_token, user_id=caller.user_id, bound_to=bound)
        after = cursor.sort_values(payload)
        seen = int(payload["n"])
    if not specs:
        return {"items": [], "facets": [], "total": 0, "total_is_lower_bound": False, "next_cursor": None}
    query = build_query(
        caller,
        specs,
        text=text,
        restrict_types=restrict,
        filters=pairs,
        limit=limit + 1,
        search_after=after,
        timeout_ms=config.opensearch_timeout_seconds * 1000,
    )
    result = (engine or get_engine()).search(query)
    page = result.hits[:limit]
    items = [hit_out(registry.types[h.type], h) for h in page if h.type in registry.types]
    more = len(result.hits) > limit and seen + limit < MAX_TOTAL
    next_cursor = None
    if more and page:
        next_cursor = cursor.sign(
            config.cursor_secret,
            {"u": caller.user_id, "h": bound, "s": list(page[-1].sort), "n": seen + limit},
            ttl_seconds=config.cursor_ttl_seconds,
        )
    facets = [
        {"type": key, "label": registry.types[key].label, "count": count}
        for key, count in sorted(
            result.facets.items(), key=lambda kv: registry.types[kv[0]].label if kv[0] in registry.types else ""
        )
        if key in registry.types and count > 0
    ]
    return {
        "items": items,
        "facets": facets,
        "total": min(result.total, MAX_TOTAL),
        "total_is_lower_bound": result.total_is_lower_bound,
        "next_cursor": next_cursor,
    }


def suggest(
    caller: Caller,
    *,
    q: str,
    types: str | None = None,
    limit: int = 5,
    registry: Registry | None = None,
    engine: SearchEngine | None = None,
    config: SearchConfig | None = None,
) -> dict:
    registry = registry or get_registry()
    config = config or SearchConfig.from_env().validate()
    text = normalise_q(q, minimum=SUGGEST_MIN, maximum=SUGGEST_MAX)
    if not 1 <= limit <= SUGGEST_LIMIT_MAX:
        raise SearchError(422, f"limit must be 1 to {SUGGEST_LIMIT_MAX}")
    specs = registry.visible_types(caller)
    restrict = parse_types(types)
    if restrict is not None:
        specs = [s for s in specs if s.key in restrict]
    if not specs:
        return {"suggestions": []}
    query = build_query(
        caller, specs, text=text, kind=SUGGEST, limit=limit, timeout_ms=config.opensearch_timeout_seconds * 1000
    )
    result = (engine or get_engine()).search(query)
    return {
        "suggestions": [
            {"type": h.type, "id": h.record_id, "text": h.title[:300]}
            for h in result.hits[:limit]
            if h.type in registry.types
        ]
    }


def list_types(caller: Caller, registry: Registry | None = None) -> dict:
    registry = registry or get_registry()
    return {
        "items": [
            {"type": s.key, "module": s.module, "label": s.label, "filterable": list(s.filterable_fields)}
            for s in registry.visible_types(caller, holding_permission=True)
        ]
    }
