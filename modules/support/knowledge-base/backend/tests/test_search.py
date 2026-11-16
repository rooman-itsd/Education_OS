"""platform/search opt-in: the declaration, the document provider and the trigger events."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH")

from eos_knowledge_base.search import DECLARATION, PROVIDER  # noqa: E402

MODULE = Path(__file__).resolve().parents[2]
SEARCHABLE = yaml.safe_load((MODULE / "contracts" / "searchable.yaml").read_text(encoding="utf-8"))
EVENTS = {
    e["name"]: e for e in yaml.safe_load((MODULE / "contracts" / "events.yaml").read_text(encoding="utf-8"))["events"]
}
TYPE = SEARCHABLE["types"][0]
ENTRY_POINT = (MODULE / "backend" / "pyproject.toml").read_text(encoding="utf-8")
PERMISSIONS = (MODULE / "contracts" / "permissions.yaml").read_text(encoding="utf-8")


def test_the_provider_is_registered_under_the_module_name():
    assert '[project.entry-points."eos.search_documents"]' in ENTRY_POINT
    assert 'knowledge-base = "eos_knowledge_base.search:PROVIDER"' in ENTRY_POINT
    assert SEARCHABLE["module"] == "knowledge-base"
    assert PROVIDER.declaration == DECLARATION and DECLARATION.is_file()


def test_the_declared_triggers_exist_with_the_id_field_in_their_payload():
    assert TYPE["name"] == "article"
    assert [(t["event"], t["action"]) for t in TYPE["triggers"]] == [
        ("knowledge-base.article.published", "upsert"),
        ("knowledge-base.article.archived", "delete"),
    ]
    for trigger in TYPE["triggers"]:
        assert trigger["event"] in EVENTS
        assert trigger["id_field"] == "article_id"
        assert "article_id" in EVENTS[trigger["event"]]["payload"]


def test_the_read_permissions_are_in_the_permission_catalogue():
    for key in TYPE["read_permissions"]["any_of"]:
        assert f"key: {key}" in PERMISSIONS


def test_the_provider_returns_the_published_article(desk):
    article = desk.published(title="Reset your password", body="Use the portal reset link.")
    document = PROVIDER.get_document(desk.org.id, "article", article["id"])
    assert document == {
        "record_id": article["id"],
        "fields": {
            "title": "Reset your password",
            "body": "Use the portal reset link.",
            "slug": article["slug"],
            "category_id": desk.category_id,
            "published": True,
        },
    }


def test_the_declared_fields_are_exactly_what_the_provider_returns(desk):
    article = desk.published()
    document = PROVIDER.get_document(desk.org.id, "article", article["id"])
    assert set(document["fields"]) == set(TYPE["fields"])


def test_a_staff_article_is_readable_only_with_the_internal_permission(desk):
    everyone = desk.published(title="Public how-to")
    staff = desk.published(title="Staff runbook", audience="staff")
    assert "read_any_of" not in PROVIDER.get_document(desk.org.id, "article", everyone["id"])
    assert PROVIDER.get_document(desk.org.id, "article", staff["id"])["read_any_of"] == [
        "knowledge-base:article:read-internal"
    ]
    assert "knowledge-base:article:read-internal" in TYPE["read_permissions"]["any_of"]


def test_the_latest_published_revision_is_indexed_not_an_open_draft(desk):
    article = desk.published(title="Old title")
    desk.ok(desk.put(f"/articles/{article['id']}/draft", {"title": "Draft title"}, desk.author2))
    assert PROVIDER.get_document(desk.org.id, "article", article["id"])["fields"]["title"] == "Old title"


def test_a_draft_an_archived_article_a_missing_id_and_another_type_are_none(desk):
    draft = desk.draft()
    archived = desk.published(title="Gone")
    desk.ok(desk.post(f"/articles/{archived['id']}/archive", {"reason": "Replaced"}))
    live = desk.published(title="Live")
    org = desk.org.id
    assert PROVIDER.get_document(org, "article", draft["id"]) is None
    assert PROVIDER.get_document(org, "article", archived["id"]) is None
    assert PROVIDER.get_document(org, "article", "00000000-0000-0000-0000-000000000000") is None
    assert PROVIDER.get_document(org, "page", live["id"]) is None
    assert [d["record_id"] for d in PROVIDER.iter_documents(org, "article", None, 10)] == [live["id"]]
    assert PROVIDER.iter_documents(org, "page", None, 10) == []


def test_a_provider_call_for_one_organisation_never_returns_another_organisations_article(
    client, org, other_org, clock
):
    from conftest import Desk

    mine, theirs = Desk(client, org), Desk(client, other_org)
    a, b = mine.published(title="Mine"), theirs.published(title="Theirs")
    assert PROVIDER.get_document(org.id, "article", b["id"]) is None
    assert PROVIDER.get_document(other_org.id, "article", a["id"]) is None
    assert [d["record_id"] for d in PROVIDER.iter_documents(org.id, "article", None, 100)] == [a["id"]]
    assert [d["record_id"] for d in PROVIDER.iter_documents(other_org.id, "article", None, 100)] == [b["id"]]
    assert PROVIDER.get_document("", "article", a["id"]) is None


def test_iter_documents_pages_in_id_order(desk):
    ids = sorted(desk.published(title=f"Article {i}")["id"] for i in range(5))
    first = PROVIDER.iter_documents(desk.org.id, "article", None, 2)
    second = PROVIDER.iter_documents(desk.org.id, "article", first[-1]["record_id"], 2)
    rest = PROVIDER.iter_documents(desk.org.id, "article", second[-1]["record_id"], 2)
    assert [d["record_id"] for d in first + second + rest] == ids
