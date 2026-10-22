"""Queues and categories through the HTTP API (contract /queues, /categories)."""

from conftest import audit

# --- queues


def test_create_and_list_queues_with_open_counts(desk):
    desk.raise_ticket()
    desk.raise_ticket("Printer")
    queues = {q["name"]: q for q in desk.ok(desk.get("/queues", desk.agent))}
    assert queues["IT"]["open_count"] == 2
    assert queues["Academic office"]["open_count"] == 0
    assert queues["IT"]["organisation_id"] == desk.org.id
    assert ("queue.created", None) in audit(desk.org.id, desk.it["id"])


def test_get_queues_shows_every_queue_to_an_agent_and_an_admin(desk):
    for headers in (desk.outsider, desk.admin):
        assert {q["name"] for q in desk.ok(desk.get("/queues", headers))} == {"IT", "Academic office"}


def test_queues_filter_by_active(desk):
    desk.ok(desk.patch(f"/queues/{desk.office['id']}", {"name": "Academic office", "active": False}, desk.admin))
    assert [q["name"] for q in desk.ok(desk.get("/queues?active=true", desk.admin))] == ["IT"]
    assert [q["name"] for q in desk.ok(desk.get("/queues?active=false", desk.admin))] == ["Academic office"]


def test_a_requester_cannot_list_queues(desk):
    assert desk.get("/queues", desk.requester).status_code == 403


def test_queue_names_are_unique(desk):
    r = desk.post("/queues", {"name": "IT"}, desk.admin)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "queue_name_taken")
    r = desk.patch(f"/queues/{desk.office['id']}", {"name": "IT"}, desk.admin)
    assert r.status_code == 409


def test_only_settings_manage_creates_queues(desk):
    for headers in (desk.lead, desk.agent, desk.viewer, desk.requester):
        assert desk.post("/queues", {"name": "Accounts"}, headers).status_code == 403


def test_patch_changes_only_the_fields_sent(desk):
    updated = desk.ok(desk.patch(f"/queues/{desk.it['id']}", {"name": "IT help"}, desk.admin))
    assert updated["name"] == "IT help"
    assert set(updated["member_ids"]) == {desk.agent_id, desk.agent2_id, desk.lead_id}
    assert updated["active"] is True


def test_a_queue_with_open_tickets_cannot_be_deactivated(desk):
    desk.raise_ticket()
    r = desk.patch(f"/queues/{desk.it['id']}", {"name": "IT", "active": False}, desk.admin)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "queue_has_open_tickets")


def test_an_unknown_queue_is_not_found(desk):
    assert desk.patch("/queues/not-a-queue", {"name": "X"}, desk.admin).status_code == 404


def test_member_ids_must_be_uuids(desk):
    assert desk.post("/queues", {"name": "Accounts", "member_ids": ["bob"]}, desk.admin).status_code == 422


# --- categories


def test_two_level_categories(desk):
    child = desk.ok(
        desk.post(
            "/categories",
            {
                "parent_id": desk.category["id"],
                "name": "Password reset",
                "default_queue_id": desk.it["id"],
                "default_priority": "medium",
            },
            desk.admin,
        )
    )
    assert child["parent_id"] == desk.category["id"]
    grandchild = {
        "parent_id": child["id"],
        "name": "Too deep",
        "default_queue_id": desk.it["id"],
        "default_priority": "low",
    }
    r = desk.post("/categories", grandchild, desk.admin)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "too_deep")


def test_category_names_are_unique_under_one_parent(desk):
    body = {"name": "Account access", "default_queue_id": desk.it["id"], "default_priority": "low"}
    assert desk.post("/categories", body, desk.admin).status_code == 409
    other_parent = {**body, "parent_id": desk.category["id"]}
    assert desk.post("/categories", other_parent, desk.admin).status_code == 201


def test_a_category_with_sub_categories_cannot_become_one(desk):
    other = desk.ok(
        desk.post(
            "/categories",
            {"name": "Hardware", "default_queue_id": desk.it["id"], "default_priority": "low"},
            desk.admin,
        )
    )
    desk.ok(
        desk.post(
            "/categories",
            {
                "parent_id": desk.category["id"],
                "name": "MFA",
                "default_queue_id": desk.it["id"],
                "default_priority": "low",
            },
            desk.admin,
        )
    )
    body = {
        "parent_id": other["id"],
        "name": "Account access",
        "default_queue_id": desk.it["id"],
        "default_priority": "high",
    }
    assert desk.patch(f"/categories/{desk.category['id']}", body, desk.admin).status_code == 409


def test_category_default_queue_must_exist(desk):
    body = {"name": "Library", "default_queue_id": "00000000-0000-4000-8000-000000000000", "default_priority": "low"}
    r = desk.post("/categories", body, desk.admin)
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "unknown_queue")


def test_existing_tickets_keep_their_queue_and_priority_when_the_category_changes(desk):
    ticket = desk.raise_ticket()
    body = {"name": "Account access", "default_queue_id": desk.office["id"], "default_priority": "low"}
    desk.ok(desk.patch(f"/categories/{desk.category['id']}", body, desk.admin))
    again = desk.ok(desk.get(f"/tickets/{ticket['id']}", desk.lead))
    assert (again["queue_id"], again["priority"]) == (desk.it["id"], "high")


def test_everyone_who_raises_or_reads_tickets_can_list_categories(desk):
    for headers in (desk.requester, desk.agent, desk.admin, desk.viewer):
        assert desk.ok(desk.get("/categories", headers))[0]["name"] == "Account access"


def test_categories_filter_by_active(desk):
    body = {"name": "Account access", "default_queue_id": desk.it["id"], "default_priority": "high", "active": False}
    desk.ok(desk.patch(f"/categories/{desk.category['id']}", body, desk.admin))
    assert desk.ok(desk.get("/categories?active=true", desk.requester)) == []
