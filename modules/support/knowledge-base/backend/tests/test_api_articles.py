"""Articles through the HTTP API: create, drafts and revisions, review, publish, archive and restore, with their
events and audit entries."""

from conftest import NOW, audit, days, outbox


def test_create_a_draft_with_revision_1_and_a_slug(desk):
    a = desk.draft()
    assert (a["status"], a["slug"], a["open_revision_no"], a["open_revision_state"]) == (
        "draft",
        "connect-to-campus-wi-fi",
        1,
        "draft",
    )
    assert a["owner_id"] == desk.author_id and a["published_revision_no"] is None
    assert a["revision"]["revision_no"] == 1 and a["revision"]["author_id"] == desk.author_id
    assert desk.draft()["slug"] == "connect-to-campus-wi-fi-2"
    taken = desk.post("/articles", desk.body(slug="connect-to-campus-wi-fi"), desk.author)
    assert (taken.status_code, taken.json()["detail"]["code"]) == (409, "slug_taken")
    assert desk.draft(slug="wifi-guide")["slug"] == "wifi-guide"
    assert audit(desk.org.id, a["id"]) == [("article.created", None)]


def test_create_refuses_bad_categories_and_related(desk):
    off = desk.category("Old")
    desk.ok(desk.patch(f"/categories/{off['id']}", {"active": False}))
    bad = desk.post("/articles", desk.body(category_id=off["id"]), desk.author)
    assert (bad.status_code, bad.json()["detail"]["code"]) == (422, "inactive_category")
    unknown = desk.post("/articles", desk.body(category_id="11111111-1111-4111-8111-111111111111"), desk.author)
    assert unknown.json()["detail"]["code"] == "unknown_category"
    rel = desk.post("/articles", desk.body(related_article_ids=["11111111-1111-4111-8111-111111111111"]), desk.author)
    assert (rel.status_code, rel.json()["detail"]["code"]) == (422, "unknown_related_article")
    assert desk.post("/articles", desk.body(type="video"), desk.author).status_code == 422
    assert desk.post("/articles", {"title": "Only a title"}, desk.author).status_code == 422
    assert desk.post("/articles", desk.body(), desk.reader).status_code == 403


def test_publish_sets_review_by_and_publishes_the_event(desk):
    a = desk.draft()
    published = desk.ok(desk.post(f"/articles/{a['id']}/publish", {}))
    assert (published["status"], published["published_revision_no"], published["open_revision_no"]) == (
        "published",
        1,
        None,
    )
    assert published["review_by"] == "2027-11-04"  # KNOWLEDGE_BASE_DEFAULT_REVIEW_MONTHS after today
    assert published["first_published_at"] == NOW.isoformat()
    assert published["revision"]["state"] == "published"
    event = outbox("knowledge-base.article.published", desk.org.id)[-1]
    assert (event["article_id"], event["revision_no"], event["first_publication"]) == (a["id"], 1, True)
    assert "title" not in event and "body" not in event


def test_edit_review_and_republish(desk):
    a = desk.published()
    path = f"/articles/{a['id']}"
    started = desk.ok(desk.put(f"{path}/draft", {"title": "Connect to the campus Wi-Fi network"}, desk.author2))
    assert (started["revision_no"], started["state"], started["author_id"]) == (2, "draft", desk.author2_id)
    assert started["body"] == a["revision"]["body"]  # copied from the published revision
    # Readers still see revision 1.
    assert desk.ok(desk.get(path, desk.reader))["revision"]["title"] == "Connect to campus Wi-Fi"
    # Saving the open draft needs every content field.
    partial = desk.put(f"{path}/draft", {"title": "Only a title"}, desk.author2)
    assert (partial.status_code, partial.json()["detail"]["code"]) == (422, "content_fields_required")
    full = {k: v for k, v in desk.body(title="Campus Wi-Fi, step by step").items() if k != "tags"}
    saved = desk.ok(desk.put(f"{path}/draft", {**full, "change_note": "Clearer title"}, desk.author2))
    assert (saved["title"], saved["tags"], saved["change_note"]) == ("Campus Wi-Fi, step by step", [], "Clearer title")
    # Another author may not edit it; an editor may.
    assert desk.put(f"{path}/draft", full, desk.author).status_code == 403
    assert desk.post(f"{path}/draft/submit", None, desk.author).status_code == 403  # not their draft
    review = desk.ok(desk.post(f"{path}/draft/submit", None, desk.author2))
    assert review["state"] == "in_review" and review["submitted_at"]
    locked = desk.put(f"{path}/draft", full, desk.author2)
    assert (locked.status_code, locked.json()["detail"]["code"]) == (409, "revision_in_review")
    back = desk.ok(desk.post(f"{path}/draft/return", {"comment": "Add a screenshot description"}))
    assert (back["state"], back["review_comment"], back["reviewed_by"]) == (
        "draft",
        "Add a screenshot description",
        desk.editor_id,
    )
    assert desk.post(f"{path}/draft/return", {"comment": "Again"}).json()["detail"]["code"] == "no_revision_in_review"
    desk.ok(desk.post(f"{path}/draft/submit", None, desk.author2))
    republished = desk.ok(desk.post(f"{path}/publish", {"review_by": days(30)}))
    assert (republished["published_revision_no"], republished["review_by"]) == (2, days(30))
    history = desk.ok(desk.get(f"{path}/revisions", desk.author))
    assert [(r["revision_no"], r["state"]) for r in history] == [(2, "published"), (1, "superseded")]
    assert "body" not in history[0]
    assert outbox("knowledge-base.article.published", desk.org.id)[-1]["first_publication"] is False
    assert sorted(x[0] for x in audit(desk.org.id, a["id"])) == [
        "article.created",
        "article.published",
        "article.published",
    ]


def test_rollback_starts_a_draft_from_an_old_revision(desk):
    a = desk.published()
    path = f"/articles/{a['id']}"
    desk.ok(desk.put(f"{path}/draft", {"body": "Version two body"}, desk.author))
    desk.ok(desk.post(f"{path}/publish", {}))
    busy = desk.put(f"{path}/draft?from_revision=1", None, desk.author)
    assert busy.status_code == 200  # no open revision: a new draft from revision 1
    assert busy.json()["body"] == a["revision"]["body"] and busy.json()["revision_no"] == 3
    again = desk.put(f"{path}/draft?from_revision=1", None, desk.author)
    assert (again.status_code, again.json()["detail"]["code"]) == (409, "draft_open")
    desk.ok(desk.post(f"{path}/draft/discard", None, desk.author))
    missing = desk.put(f"{path}/draft?from_revision=99", None, desk.author)
    assert missing.status_code == 404
    assert desk.get(f"{path}/revisions/99", desk.author).status_code == 404


def test_discard_keeps_the_published_revision(desk):
    a = desk.published()
    path = f"/articles/{a['id']}"
    desk.ok(desk.put(f"{path}/draft", {"title": "Changed title"}, desk.author))
    assert desk.post(f"{path}/draft/discard", None, desk.author2).status_code == 403  # another author's draft
    discarded = desk.ok(desk.post(f"{path}/draft/discard", None, desk.author))
    assert discarded["state"] == "discarded"
    after = desk.ok(desk.get(path, desk.reader))
    assert (after["status"], after["revision"]["title"], after["open_revision_no"]) == (
        "published",
        "Connect to campus Wi-Fi",
        None,
    )
    assert desk.post(f"{path}/draft/discard", None, desk.author).json()["detail"]["code"] == "no_open_revision"
    assert desk.post(f"{path}/publish", {}).json()["detail"]["code"] == "no_open_revision"


def test_archive_and_restore(desk):
    a = desk.published()
    path = f"/articles/{a['id']}"
    archived = desk.ok(desk.post(f"{path}/archive", {"reason": "Network replaced"}))
    assert (archived["status"], archived["archived_at"]) == ("archived", NOW.isoformat())
    assert desk.post(f"{path}/archive", {"reason": "Again"}).json()["detail"]["code"] == "already_archived"
    # Readable by id, gone from browse.
    assert desk.ok(desk.get(path, desk.reader))["status"] == "archived"
    assert a["id"] not in [x["id"] for x in desk.ok(desk.get("/articles", desk.reader))["items"]]
    event = outbox("knowledge-base.article.archived", desk.org.id)[-1]
    assert (event["article_id"], event["was_published"]) == (a["id"], True)
    desk.ok(desk.put(f"{path}/draft", {"title": "Draft kept while archived"}, desk.author))
    assert desk.post(f"{path}/publish", {}).json()["detail"]["code"] == "article_archived"
    restored = desk.ok(desk.post(f"{path}/restore"))
    assert (restored["status"], restored["archived_at"], restored["open_revision_state"]) == (
        "published",
        None,
        "draft",
    )
    assert desk.post(f"{path}/restore").json()["detail"]["code"] == "not_archived"
    assert outbox("knowledge-base.article.published", desk.org.id)[-1]["first_publication"] is False
    assert ("article.archived", "Network replaced") in audit(desk.org.id, a["id"])
    draft = desk.draft()
    desk.ok(desk.post(f"/articles/{draft['id']}/archive", {"reason": "Not needed"}))
    assert outbox("knowledge-base.article.archived", desk.org.id)[-1]["was_published"] is False
    assert desk.ok(desk.post(f"/articles/{draft['id']}/restore"))["status"] == "draft"


def test_settings_by_owner_or_editor(desk):
    a = desk.draft()
    path = f"/articles/{a['id']}"
    mine = desk.ok(desk.patch(path, {"review_by": days(10)}, desk.author))
    assert mine["review_by"] == days(10)
    assert desk.patch(path, {"review_by": days(5)}, desk.author2).status_code == 403
    cleared = desk.ok(desk.patch(path, {"review_by": None, "owner_id": desk.author2_id}))
    assert (cleared["review_by"], cleared["owner_id"]) == (None, desk.author2_id)
    assert ("article.settings_changed", None) in audit(desk.org.id, a["id"])


def test_publishing_into_a_category_deactivated_meanwhile_is_refused(desk):
    old = desk.category("Retired")
    a = desk.draft(category_id=old["id"])
    desk.ok(desk.patch(f"/categories/{old['id']}", {"active": False}))  # nothing published in it yet
    refused = desk.post(f"/articles/{a['id']}/publish", {})
    assert (refused.status_code, refused.json()["detail"]["code"]) == (422, "inactive_category")


def test_only_editors_review_and_publish(desk):
    a = desk.draft()
    path = f"/articles/{a['id']}"
    for p, body in [("/publish", {}), ("/archive", {"reason": "No"}), ("/restore", None)]:
        assert desk.post(path + p, body, desk.author).status_code == 403, p
    desk.ok(desk.post(f"{path}/draft/submit", None, desk.author))
    assert desk.post(f"{path}/draft/return", {"comment": "Fix"}, desk.author).status_code == 403
    assert desk.get(f"{path}/revisions", desk.reader).status_code == 403


def test_long_titles_still_get_distinct_slugs(desk):
    """A 120-character slug is trimmed to make room for -2, -3: each candidate is checked itself."""
    title = "Long " + "x" * 125
    slugs = [desk.draft(title=title)["slug"] for _ in range(3)]
    assert len(set(slugs)) == 3 and all(len(s) <= 120 for s in slugs)
    assert slugs[1].endswith("-2") and slugs[2].endswith("-3")


def test_a_slug_taken_by_a_concurrent_create_is_a_409(desk, monkeypatch):
    """Two creates with the same slug at once both pass the check; the second hits the unique constraint on flush."""
    from eos_knowledge_base.infrastructure import repository

    desk.draft(slug="race-slug")
    monkeypatch.setattr(repository, "slug_taken", lambda db, slug: False)  # the check ran before the first commit
    second = desk.post("/articles", desk.body(slug="race-slug"), desk.author)
    assert (second.status_code, second.json()["detail"]["code"]) == (409, "slug_taken")
