"""Cross-tenant leak test (module standard rule 11): one organisation never sees or changes another's rows."""

from conftest import BASE, Desk
from eos_testing import assert_no_cross_tenant_leak


def token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def seed(client, org) -> tuple[Desk, dict]:
    d = Desk(client, org)
    a = d.published(title="Shared title in both organisations")
    d.ok(d.get(f"/articles/{a['id']}", d.reader))
    d.ok(d.post(f"/articles/{a['id']}/feedback", {"helpful": True, "comment": "Thanks"}, d.reader))
    return d, {"article": a["id"], "category": d.category_id}


def test_no_cross_tenant_leak(client, org, other_org, clock):
    a, _ = seed(client, org)
    b, _ = seed(client, other_org)
    assert_no_cross_tenant_leak(client, f"{BASE}/categories", token(a.viewer), token(b.viewer))
    # Article list items carry no organisation_id (contract ArticleListItem); one article each, so compare ids.
    assert_no_cross_tenant_leak(client, f"{BASE}/articles", token(a.viewer), token(b.viewer), id_field="id")
    assert len(a.ok(a.get("/articles?q=shared", a.reader))["items"]) == 1
    top_a = a.ok(a.get("/stats/top-articles", a.viewer))["items"]
    top_b = b.ok(b.get("/stats/top-articles", b.viewer))["items"]
    assert len(top_a) == len(top_b) == 1 and top_a[0]["views"] == top_b[0]["views"] == 1


def test_another_organisations_records_are_not_found(client, org, other_org, clock):
    a, ids = seed(client, org)
    b = Desk(client, other_org)
    aid, cid = ids["article"], ids["category"]
    for path in (
        f"/articles/{aid}",
        f"/articles/{aid}/revisions",
        f"/articles/{aid}/revisions/1",
        f"/articles/{aid}/feedback",
    ):
        assert b.get(path, b.editor).status_code == 404, path
    for path, body in [
        (f"/articles/{aid}/publish", {}),
        (f"/articles/{aid}/archive", {"reason": "Stolen"}),
        (f"/articles/{aid}/restore", None),
        (f"/articles/{aid}/draft/submit", None),
        (f"/articles/{aid}/draft/return", {"comment": "Stolen"}),
        (f"/articles/{aid}/draft/discard", None),
        (f"/articles/{aid}/feedback", {"helpful": False}),
    ]:
        assert b.post(path, body).status_code == 404, path
    assert b.put(f"/articles/{aid}/draft", {"title": "Stolen title"}).status_code == 404
    assert b.patch(f"/articles/{aid}", {"review_by": None}).status_code == 404
    assert b.patch(f"/categories/{cid}", {"name": "Stolen"}).status_code == 404
    into_a = b.post("/articles", b.body(category_id=cid), b.author)
    assert (into_a.status_code, into_a.json()["detail"]["code"]) == (422, "unknown_category")
    related = b.post("/articles", b.body(related_article_ids=[aid]), b.author)
    assert related.json()["detail"]["code"] == "unknown_related_article"
    # A's records are untouched.
    after = a.ok(a.get(f"/articles/{aid}", a.editor))
    assert (after["status"], after["helpful_count"], after["open_revision_no"]) == ("published", 1, None)
