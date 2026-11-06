"""Categories through the HTTP API: the two-level tree, names, moves, deactivation and counts."""

from conftest import audit


def test_tree_in_display_order_with_positions(desk):
    it = desk.category("IT")
    adm = desk.category("Admissions", position=0)
    wifi = desk.category("Wi-Fi", parent_id=it["id"])
    lms = desk.category("LMS", parent_id=it["id"], position=0)
    assert it["position"] == 0 and desk.category("Hostel")["position"] == 1  # after the last sibling
    names = [c["name"] for c in desk.ok(desk.get("/categories", desk.reader))]
    assert names.index("IT") < names.index("LMS") < names.index("Wi-Fi")
    assert names.index("Admissions") < names.index("IT")
    assert (wifi["parent_id"], lms["position"], adm["published_article_count"]) == (it["id"], 0, 0)
    assert audit(desk.org.id, it["id"]) == [("category.created", None)]


def test_two_levels_and_unique_names(desk):
    it = desk.category("IT")
    wifi = desk.category("Wi-Fi", parent_id=it["id"])
    third = desk.post("/categories", {"name": "Guest", "parent_id": wifi["id"]})
    assert (third.status_code, third.json()["detail"]["code"]) == (409, "third_level")
    taken = desk.post("/categories", {"name": " wi-fi ", "parent_id": it["id"]})
    assert (taken.status_code, taken.json()["detail"]["code"]) == (409, "name_taken")
    desk.category("Wi-Fi")  # the same name at the top level is another sibling set
    unknown = desk.post("/categories", {"name": "X", "parent_id": "11111111-1111-4111-8111-111111111111"})
    assert (unknown.status_code, unknown.json()["detail"]["code"]) == (422, "unknown_parent")


def test_rename_move_and_refused_moves(desk):
    it = desk.category("IT")
    hostel = desk.category("Hostel")
    wifi = desk.category("Wi-Fi", parent_id=it["id"])
    moved = desk.ok(desk.patch(f"/categories/{wifi['id']}", {"parent_id": hostel["id"], "name": "Hostel Wi-Fi"}))
    assert (moved["parent_id"], moved["name"]) == (hostel["id"], "Hostel Wi-Fi")
    top = desk.ok(desk.patch(f"/categories/{wifi['id']}", {"parent_id": None}))
    assert top["parent_id"] is None
    desk.category("Laptops", parent_id=it["id"])
    under = desk.patch(f"/categories/{it['id']}", {"parent_id": hostel["id"]})  # IT has a sub-category
    assert (under.status_code, under.json()["detail"]["code"]) == (409, "third_level")
    itself = desk.patch(f"/categories/{it['id']}", {"parent_id": it["id"]})
    assert itself.status_code == 409
    assert desk.patch("/categories/11111111-1111-4111-8111-111111111111", {"name": "X"}).status_code == 404


def test_a_category_holding_published_articles_cannot_be_deactivated(desk):
    it = desk.category("IT")
    wifi = desk.category("Wi-Fi", parent_id=it["id"])
    empty = desk.category("Empty")
    desk.published(category_id=wifi["id"])
    for cid in (wifi["id"], it["id"]):  # the parent counts its sub-category's articles
        refused = desk.patch(f"/categories/{cid}", {"active": False})
        assert (refused.status_code, refused.json()["detail"]["code"]) == (409, "category_in_use")
    assert desk.ok(desk.patch(f"/categories/{empty['id']}", {"active": False}))["active"] is False
    reader_view = [c["id"] for c in desk.ok(desk.get("/categories", desk.reader))]
    assert empty["id"] not in reader_view
    assert empty["id"] in [c["id"] for c in desk.ok(desk.get("/categories?active=false"))]
    assert desk.ok(desk.get("/categories?active=false", desk.reader)) == []
    counts = {c["id"]: c["published_article_count"] for c in desk.ok(desk.get("/categories", desk.reader))}
    assert (counts[it["id"]], counts[wifi["id"]]) == (1, 1)


def test_counts_respect_the_audience(desk):
    it = desk.category("IT")
    desk.published(category_id=it["id"])
    desk.published(category_id=it["id"], audience="staff", title="Server room procedure")
    counts = lambda h: {c["id"]: c["published_article_count"] for c in desk.ok(desk.get("/categories", h))}  # noqa: E731
    assert counts(desk.reader)[it["id"]] == 1
    assert counts(desk.viewer)[it["id"]] == 2


def test_only_category_managers_change_categories(desk):
    assert desk.post("/categories", {"name": "X"}, desk.author).status_code == 403
    it = desk.category("IT")
    assert desk.patch(f"/categories/{it['id']}", {"name": "Y"}, desk.author).status_code == 403
