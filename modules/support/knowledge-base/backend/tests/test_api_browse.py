"""Browse and search through GET /articles: what readers and writers see, filters, sorting and paging."""

from datetime import timedelta

from conftest import NOW, days


def ids(desk, query: str, headers=None) -> list[str]:
    return [a["id"] for a in desk.ok(desk.get(f"/articles{query}", headers or desk.reader))["items"]]


def test_readers_see_only_published_articles_for_their_audience(desk):
    public = desk.published()
    staff = desk.published(audience="staff", title="Server room access")
    draft = desk.draft(title="Unfinished guide")
    assert set(ids(desk, "")) == {public["id"]}
    assert set(ids(desk, "", desk.viewer)) == {public["id"], staff["id"]}
    assert desk.get(f"/articles/{staff['id']}", desk.reader).status_code == 404
    assert desk.get(f"/articles/{draft['id']}", desk.reader).status_code == 404
    assert desk.get(f"/articles/{draft['id']}?view=open", desk.reader).status_code == 403
    assert (
        desk.ok(desk.get(f"/articles/{draft['id']}?view=open", desk.author))["revision"]["title"] == "Unfinished guide"
    )
    assert desk.get("/articles?audience=staff", desk.reader).status_code == 403
    item = desk.ok(desk.get("/articles", desk.reader))["items"][0]
    assert "open_revision_state" not in item and item["snippet"] is None


def test_writer_filters(desk):
    mine = desk.draft(title="My draft")
    other = desk.draft(desk.author2, title="Their draft")
    live = desk.published(title="Live guide")
    for q in ("?status=draft", "?owner=me", "?stale=true", "?in_review=true"):
        assert desk.get(f"/articles{q}", desk.reader).status_code == 403, q
    assert set(ids(desk, "?status=draft", desk.author)) == {mine["id"], other["id"]}
    assert set(ids(desk, "?owner=me", desk.author)) == {mine["id"], live["id"]}
    desk.ok(desk.post(f"/articles/{mine['id']}/draft/submit", None, desk.author))
    assert ids(desk, "?in_review=true", desk.author) == [mine["id"]]
    desk.ok(desk.patch(f"/articles/{live['id']}", {"review_by": days(-1)}))
    assert ids(desk, "?stale=true", desk.author) == [live["id"]]
    listed = desk.ok(desk.get("/articles?status=draft", desk.author))["items"]
    assert {i["open_revision_state"] for i in listed} == {"draft", "in_review"}
    assert desk.get("/articles?status=lost", desk.author).status_code == 422


def test_filters_by_type_category_tag_and_slug(desk):
    it = desk.category("IT")
    wifi = desk.category("Wi-Fi", parent_id=it["id"])
    a = desk.published(category_id=wifi["id"], type="faq", title="Why is Wi-Fi slow?", tags=["Speed"])
    b = desk.published(title="Exam timetable", tags=["exams"])
    assert ids(desk, f"?category_id={it['id']}") == [a["id"]]  # includes sub-categories
    assert ids(desk, "?type=faq") == [a["id"]]
    assert ids(desk, "?tag=speed") == [a["id"]]
    assert ids(desk, f"?slug={b['slug']}") == [b["id"]]
    assert desk.get("/articles?type=faq,how_to").status_code == 422  # one type, never a partial result
    assert desk.get("/articles?type=video").status_code == 422


def test_search_matches_every_word_and_returns_a_snippet(desk):
    wifi = desk.published(
        title="Connect to campus Wi-Fi",
        body="Open settings and choose the CAMPUS network.",
        tags=[],
        summary="Wi-Fi setup",
    )
    pwd = desk.published(
        title="Reset your portal password", body="Use the forgot password link.", tags=["wifi"], summary="Password help"
    )
    assert set(ids(desk, "?q=wifi")) == {pwd["id"]}  # "wi-fi" in the title is another word
    assert ids(desk, "?q=campus network") == [wifi["id"]]
    found = desk.ok(desk.get("/articles?q=password", desk.reader))["items"]
    assert found[0]["id"] == pwd["id"] and "**password**" in found[0]["snippet"]
    assert ids(desk, "?q=nothing-matches") == []
    assert desk.get("/articles?q=a").status_code == 422  # minLength 2
    assert desk.get("/articles?sort=relevance").json()["detail"]["code"] == "relevance_needs_q"


def test_sorting_and_paging(desk, clock):
    first = desk.published(title="Bravo")
    clock.set(NOW + timedelta(hours=1))
    second = desk.published(title="Alpha")
    assert ids(desk, "") == [second["id"], first["id"]]  # newest first
    assert ids(desk, "?sort=title") == [second["id"], first["id"]]
    desk.ok(desk.get(f"/articles/{first['id']}", desk.reader))  # one view
    assert ids(desk, "?sort=popular")[0] == first["id"]
    desk.ok(desk.post(f"/articles/{second['id']}/feedback", {"helpful": True}, desk.reader))
    assert ids(desk, "?sort=helpful")[0] == second["id"]
    page = desk.ok(desk.get("/articles?limit=1", desk.reader))
    assert len(page["items"]) == 1 and page["next_cursor"]
    rest = desk.ok(desk.get(f"/articles?limit=1&cursor={page['next_cursor']}", desk.reader))
    assert rest["items"][0]["id"] != page["items"][0]["id"] and rest["next_cursor"] is None


def test_related_articles_the_caller_may_read(desk):
    public = desk.published(title="Public guide")
    staff = desk.published(title="Staff guide", audience="staff")
    hidden = desk.draft(title="Hidden draft")
    a = desk.published(title="Main", related_article_ids=[public["id"], staff["id"], hidden["id"]])
    as_reader = [r["id"] for r in desk.ok(desk.get(f"/articles/{a['id']}", desk.reader))["related"]]
    as_viewer = [r["id"] for r in desk.ok(desk.get(f"/articles/{a['id']}", desk.viewer))["related"]]
    assert as_reader == [public["id"]] and as_viewer == [public["id"], staff["id"]]
