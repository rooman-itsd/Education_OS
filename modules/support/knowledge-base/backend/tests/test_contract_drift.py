"""The code's enums, fields, permission keys and event names are the contract's (contracts/*.yaml)."""

from pathlib import Path

import pytest
import yaml
from eos_knowledge_base.application.access import PERMISSION_KEYS
from eos_knowledge_base.domain import articles as rules
from eos_knowledge_base.domain.stats import METRICS, PERIOD_DAYS

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


@pytest.fixture(scope="module")
def openapi():
    return yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))


def schema(openapi, name):
    return openapi["components"]["schemas"][name]


def test_enums(openapi):
    assert tuple(schema(openapi, "ArticleType")["enum"]) == rules.ARTICLE_TYPES
    assert tuple(schema(openapi, "Audience")["enum"]) == rules.AUDIENCES
    assert tuple(schema(openapi, "ArticleStatus")["enum"]) == rules.ARTICLE_STATUSES
    assert tuple(schema(openapi, "RevisionState")["enum"]) == rules.REVISION_STATES
    top = schema(openapi, "TopArticles")["properties"]
    assert tuple(top["period"]["enum"]) == tuple(PERIOD_DAYS) and tuple(top["metric"]["enum"]) == METRICS


def test_content_fields_are_the_contracts(openapi):
    assert set(schema(openapi, "RevisionFields")["properties"]) == set(rules.CONTENT_FIELDS)
    required = schema(openapi, "RevisionContent")["allOf"][1]["required"]
    assert tuple(required) == rules.REQUIRED_CONTENT_FIELDS


def test_serialised_shapes_have_every_contract_field(openapi):
    from eos_knowledge_base.application import service

    article = set(schema(openapi, "Article")["properties"])
    summary = set(schema(openapi, "RevisionSummary")["properties"])
    item = set(schema(openapi, "ArticleListItem")["properties"])
    src = Path(service.__file__).read_text(encoding="utf-8")
    for field in article | summary | item:
        assert f'"{field}"' in src, field


def test_permission_keys_are_the_catalogue():
    spec = yaml.safe_load((CONTRACTS / "permissions.yaml").read_text(encoding="utf-8"))
    assert {p["key"] for p in spec["permissions"]} == set(PERMISSION_KEYS)
    for role in spec["roles"]:
        assert set(role["grants"]) <= set(PERMISSION_KEYS), role["name"]


def test_published_event_names_are_the_catalogue():
    from eos_knowledge_base.application import service

    spec = yaml.safe_load((CONTRACTS / "events.yaml").read_text(encoding="utf-8"))
    names = {e["name"].removeprefix("knowledge-base.article.") for e in spec["events"]}
    src = Path(service.__file__).read_text(encoding="utf-8")
    assert names == {"published", "archived"}
    for name in names:
        assert f'"{name}"' in src
