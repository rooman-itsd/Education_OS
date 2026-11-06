"""OpenSearch settings and mappings (docs/prd.md, decision 5).

Dynamic mapping is strict: only declared fields exist. Declared fields live under `fields.` so a module's field
name can never collide with an envelope field. Search owns the analyzer list; a module picks from it.

The `name` analyzer needs the `analysis-icu` plugin (an infra requirement). The variant list below is the small,
reviewed synonym list the PRD proposes for common Indian name spellings; extending it is a reviewed change here, not
a module's choice (open question 3)."""

from __future__ import annotations

from ..domain.declarations import FieldSpec, TypeSpec

NAME_VARIANTS = [
    "mohammed, muhammad, mohd, mohammad, mohamed",
    "vijay, vijaya",
    "shreya, sreya",
    "krishna, krishnan, kishan",
    "sanjay, sanjai",
    "deepak, dipak",
    "laxmi, lakshmi",
    "ganesh, ganesan",
]


def settings(shards: int, replicas: int) -> dict:
    return {
        "index": {"number_of_shards": shards, "number_of_replicas": replicas, "gc_deletes": "60s"},
        "analysis": {
            "filter": {
                "english_stop": {"type": "stop", "stopwords": "_english_"},
                "english_stemmer": {"type": "stemmer", "language": "english"},
                "name_edge_ngram": {"type": "edge_ngram", "min_gram": 2, "max_gram": 15},
                "name_variants": {"type": "synonym_graph", "synonyms": NAME_VARIANTS},
                "devanagari_latin": {"type": "icu_transform", "id": "Devanagari-Latin"},
                "code_split": {
                    "type": "word_delimiter_graph",
                    "split_on_numerics": True,
                    "generate_number_parts": True,
                    "generate_word_parts": True,
                    "catenate_all": True,
                    "preserve_original": False,
                },
            },
            "analyzer": {
                "english": {"tokenizer": "standard", "filter": ["lowercase", "english_stop", "english_stemmer"]},
                "name": {
                    "tokenizer": "icu_tokenizer",
                    "filter": ["devanagari_latin", "icu_folding", "name_edge_ngram"],
                },
                "name_search": {
                    "tokenizer": "icu_tokenizer",
                    "filter": ["devanagari_latin", "icu_folding", "name_variants"],
                },
                "code": {"tokenizer": "whitespace", "filter": ["code_split", "lowercase"]},
                "keyword_lower": {"tokenizer": "keyword", "filter": ["lowercase"]},
            },
        },
    }


def _text(analyzer: str) -> dict:
    out = {"type": "text", "analyzer": analyzer}
    if analyzer == "name":
        out["search_analyzer"] = "name_search"
    return out


def _field(f: FieldSpec) -> dict:
    if f.kind == "text":
        return _text(f.analyzer or "english")
    return {"type": {"keyword": "keyword", "date": "date", "number": "double", "boolean": "boolean"}[f.kind]}


def mapping(spec: TypeSpec) -> dict:
    """The mapping body for one type's index. `_meta.mapping_hash` lets search tell whether the live index is
    built from the current declaration."""
    title = spec.title_field
    return {
        "dynamic": "strict",
        "_meta": {"mapping_hash": spec.mapping_hash, "type": spec.key},
        "properties": {
            "doc_id": {"type": "keyword"},
            "organisation_id": {"type": "keyword"},
            "type": {"type": "keyword"},
            "module": {"type": "keyword"},
            "record_id": {"type": "keyword"},
            "title": {**_text(title.analyzer or "english"), "fields": {"sayt": {"type": "search_as_you_type"}}},
            "read_any_of": {"type": "keyword"},
            "read_users": {"type": "keyword"},
            "indexed_at": {"type": "date"},
            "source_version": {"type": "long"},
            "reindex_run": {"type": "keyword"},
            "fields": {
                "type": "object",
                "dynamic": "strict",
                "properties": {f.name: _field(f) for f in spec.fields.values() if f.role != "title"},
            },
        },
    }
