"""Feedback, views and the top-articles statistics behind the Support Staff widget, plus the profile roles that read
through their dashboard layouts."""

from datetime import timedelta

from conftest import NOW, Desk


def test_one_vote_per_person_replaced_by_a_new_one(desk):
    a = desk.published()
    path = f"/articles/{a['id']}/feedback"
    first = desk.ok(desk.post(path, {"helpful": False, "comment": "Step 3 is unclear"}, desk.reader))
    assert first == {"helpful_count": 0, "not_helpful_count": 1, "my_vote": False}
    again = desk.ok(desk.post(path, {"helpful": True}, desk.reader))
    assert again == {"helpful_count": 1, "not_helpful_count": 0, "my_vote": True}
    desk.ok(desk.post(path, {"helpful": True}, desk.viewer))
    page = desk.ok(desk.get(path, desk.viewer))
    assert page["counts"]["helpful_count"] == 2 and len(page["items"]) == 2
    assert page["items"][0]["revision_no"] == 1
    assert desk.get(path, desk.reader).status_code == 403  # comments need stats:read
    only_no = desk.ok(desk.get(f"{path}?helpful=false", desk.viewer))
    assert only_no["items"] == []


def test_feedback_only_on_published_articles(desk):
    draft = desk.draft()
    refused = desk.post(f"/articles/{draft['id']}/feedback", {"helpful": True}, desk.author)
    assert (refused.status_code, refused.json()["detail"]["code"]) == (409, "not_published")
    assert desk.post(f"/articles/{draft['id']}/feedback", {"helpful": True}, desk.reader).status_code == 404
    staff = desk.published(audience="staff", title="Internal")
    assert desk.post(f"/articles/{staff['id']}/feedback", {"helpful": True}, desk.reader).status_code == 404
    assert desk.post(f"/articles/{draft['id']}/feedback", {"helpful": "maybe"}, desk.reader).status_code == 422


def test_a_view_counts_once_per_reader_per_day(desk, clock):
    a = desk.published()
    path = f"/articles/{a['id']}"
    assert desk.ok(desk.get(path, desk.reader))["view_count"] == 1
    assert desk.ok(desk.get(path, desk.reader))["view_count"] == 1
    assert desk.ok(desk.get(path, desk.viewer))["view_count"] == 2
    clock.set(NOW + timedelta(days=1))
    assert desk.ok(desk.get(path, desk.reader))["view_count"] == 3
    archived = desk.published(title="Gone")
    desk.ok(desk.post(f"/articles/{archived['id']}/archive", {"reason": "Old"}))
    assert desk.ok(desk.get(f"/articles/{archived['id']}", desk.reader))["view_count"] == 0  # not counted


def test_top_articles_by_views_and_by_helpful_share(desk, clock, monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_BASE_HELPFUL_MIN_VOTES", "2")
    a = desk.published(title="Most read")
    b = desk.published(title="Most helpful")
    staff = desk.published(title="Staff only", audience="staff")
    for h in (desk.reader, desk.viewer, desk.author):
        desk.ok(desk.get(f"/articles/{a['id']}", h))
    desk.ok(desk.get(f"/articles/{b['id']}", desk.reader))
    desk.ok(desk.get(f"/articles/{staff['id']}", desk.viewer))
    for h in (desk.reader, desk.viewer):
        desk.ok(desk.post(f"/articles/{b['id']}/feedback", {"helpful": True}, h))
    desk.ok(desk.post(f"/articles/{a['id']}/feedback", {"helpful": False}, desk.reader))
    top = desk.ok(desk.get("/stats/top-articles", desk.viewer))
    assert (top["period"], top["metric"]) == ("30d", "views")
    assert [i["title"] for i in top["items"]] == ["Most read", "Most helpful", "Staff only"]
    assert top["items"][0]["views"] == 3 and top["items"][1]["helpful_share"] == 1.0
    helpful = desk.ok(desk.get("/stats/top-articles?metric=helpful", desk.viewer))
    assert [i["title"] for i in helpful["items"]] == ["Most helpful"]  # a has 1 vote, under the minimum
    assert len(desk.ok(desk.get("/stats/top-articles?limit=1", desk.viewer))["items"]) == 1
    clock.set(NOW + timedelta(days=8))
    assert desk.ok(desk.get("/stats/top-articles?period=7d", desk.viewer))["items"] == []
    assert desk.get("/stats/top-articles?period=1y", desk.viewer).status_code == 422
    assert desk.get("/stats/top-articles?limit=51", desk.viewer).status_code == 422
    assert desk.get("/stats/top-articles", desk.reader).status_code == 403


def test_support_staff_writes_articles_and_reads_statistics_through_their_layout(client, org, clock):
    """support-staff.yaml lists knowledge-base-author in module_roles (the module's default for the profile role), so
    the widget works and support staff write articles, but publishing and categories stay with the editor."""
    d = Desk(client, org)
    a = d.published()
    _, staff = org.user("support-staff")
    assert d.ok(d.get(f"/articles/{a['id']}", staff))["id"] == a["id"]
    assert d.get("/stats/top-articles", staff).status_code == 200
    draft = d.post("/articles", d.body(), staff)
    assert draft.status_code == 201  # author: article:write
    assert d.post(f"/articles/{draft.json()['id']}/publish", {}, staff).status_code == 403  # publishing is the editor's
    assert d.post("/categories", {"name": "Network"}, staff).status_code == 403  # so are categories
