"""contracts/searchable.yaml is validated when search loads it; a type that does not pass is refused (fail closed)."""

import copy

import pytest
from eos_search.application.registry import Registry, load_registry
from eos_search.domain.declarations import parse_declaration
from eos_search.domain.errors import DeclarationError
from search_support import FIXTURES, ExampleProvider, declaration


def article_decl() -> dict:
    return copy.deepcopy(declaration("knowledge-base"))


def refused(mutate) -> list[str]:
    data = article_decl()
    mutate(data["types"][0])
    _, accepted, refusals = parse_declaration(data)
    assert not accepted
    return refusals


def test_the_three_first_types_are_valid():
    for module in ("student-information", "academic-management", "knowledge-base"):
        name, specs, refusals = parse_declaration(declaration(module))
        assert name == module and specs and not refusals


def test_spec_properties():
    _, (spec,), _ = parse_declaration(article_decl())
    assert spec.key == "knowledge-base.article"
    assert spec.title_field.name == "title"
    assert [f.name for f in spec.snippet_fields] == ["body"]
    assert set(spec.filterable_fields) == {"category_id", "published"}
    assert spec.read_any_of == ("knowledge-base:article:read", "knowledge-base:article:read-internal")


@pytest.mark.parametrize(
    "mutate, expect",
    [
        (lambda t: t["fields"]["body"].update(analyzer="shingle_everything"), "analyzer"),
        (lambda t: t["fields"]["title"].pop("role"), "role: title"),
        (lambda t: t["fields"]["body"].update(role="title"), "role: title"),
        (lambda t: t.pop("read_permissions"), "read_permissions"),
        (lambda t: t.update(read_permissions={"any_of": []}), "read_permissions"),
        (lambda t: t.update(read_permissions={"any_of": ["not a key"]}), "read_permissions"),
        (lambda t: t["fields"]["slug"].update(kind="blob"), "kind"),
        (lambda t: t["fields"]["body"].update(filterable=True), "filterable"),
        (lambda t: t["fields"]["slug"].update(snippet=True), "snippet"),
        (lambda t: t["fields"]["slug"].update(analyzer="english"), "analyzer"),
        (lambda t: t["fields"]["title"].update(boost=0), "boost"),
        (lambda t: t["fields"]["title"].update(boost=float("nan")), "boost"),
        (lambda t: t["fields"].update({"Bad Name": {"kind": "keyword"}}), "field name"),
        (lambda t: t.update(url="https://evil.example/{id}"), "url"),
        (lambda t: t.update(url="//evil.example/{id}"), "url"),
        (lambda t: t.update(url="/no-placeholder"), "url"),
        (
            lambda t: t["triggers"].append({"event": "billing.invoice.issued", "action": "upsert", "id_field": "x"}),
            "belong",
        ),
        (
            lambda t: t["triggers"].append({"event": "knowledge-base.article.x", "action": "reindex", "id_field": "x"}),
            "action",
        ),
        (lambda t: t["triggers"].append(dict(t["triggers"][0])), "twice"),
        (lambda t: t["fields"].update({f"f{i}": {"kind": "keyword"} for i in range(40)}), "fields"),
    ],
)
def test_a_type_that_breaks_the_rules_is_refused(mutate, expect):
    messages = refused(mutate)
    assert any(expect in m for m in messages), messages


def test_a_bad_type_does_not_take_the_good_ones_down():
    data = article_decl()
    good = copy.deepcopy(data["types"][0])
    good["name"] = "faq"
    bad = copy.deepcopy(data["types"][0])
    bad["name"] = "broken"
    bad.pop("read_permissions")
    data["types"] = [good, bad]
    _, accepted, refusals = parse_declaration(data)
    assert [s.name for s in accepted] == ["faq"] and len(refusals) == 1


def test_a_malformed_header_is_an_error():
    for data in (None, [], {"module": "Bad Module", "types": []}, {"module": "knowledge-base", "types": []}):
        with pytest.raises(DeclarationError):
            parse_declaration(data)


def test_the_registry_refuses_a_module_registered_under_another_name():
    registry = Registry()
    registry.add("student-information", ExampleProvider("x", declaration("knowledge-base")))
    assert not registry.types and "registered as student-information" in registry.errors[0]


def test_the_registry_refuses_a_provider_without_methods():
    class Bare:
        declaration = declaration("knowledge-base")

    registry = Registry()
    registry.add("knowledge-base", Bare())
    assert not registry.types and "get_document" in registry.errors[0]


def test_the_registry_reads_a_declaration_from_a_path_and_refuses_a_missing_one():
    registry = load_registry(
        [("knowledge-base", ExampleProvider("knowledge-base", FIXTURES / "knowledge-base.yaml"))]  # type: ignore[arg-type]
    )
    assert "knowledge-base.article" in registry.types
    registry = load_registry([("knowledge-base", ExampleProvider("knowledge-base", FIXTURES / "nope.yaml"))])  # type: ignore[arg-type]
    assert not registry.types and registry.errors


def test_trigger_lookup():
    registry = load_registry([("knowledge-base", ExampleProvider("knowledge-base", article_decl()))])
    assert registry.trigger_events() == {"knowledge-base.article.published", "knowledge-base.article.archived"}
    ((spec, action, id_field),) = registry.triggered_by("knowledge-base.article.archived")
    assert (spec.key, action, id_field) == ("knowledge-base.article", "delete", "article_id")
    assert list(registry.triggered_by("other.event.name")) == []


def test_mapping_hash_changes_only_with_the_mapping():
    _, (a,), _ = parse_declaration(article_decl())
    data = article_decl()
    data["types"][0]["label"] = "Help articles"
    data["types"][0]["url"] = "/help/{id}"
    _, (b,), _ = parse_declaration(data)
    assert a.mapping_hash == b.mapping_hash
    data["types"][0]["fields"]["extra"] = {"kind": "keyword"}
    _, (c,), _ = parse_declaration(data)
    assert a.mapping_hash != c.mapping_hash
