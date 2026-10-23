"""Profile roles in contracts/permissions.yaml (contract 0.2.0). Tokens carry profile roles such as support-staff,
not the helpdesk-* roles, so each profile role named as a default gets the same grants directly."""

from conftest import BASE


def test_support_staff_works_tickets_in_their_queue(desk, org):
    staff_id, staff = org.user("support-staff")
    members = [*desk.it["member_ids"], staff_id]
    desk.ok(desk.patch(f"/queues/{desk.it['id']}", {"name": "IT", "member_ids": members}, desk.admin))
    ticket = desk.raise_ticket()
    counts = desk.ok(desk.get("/stats/open-by-priority", staff))
    assert (counts["scope"], counts["total_open"]) == ("my_queues", 1)
    assert desk.ok(desk.post(f"/tickets/{ticket['id']}/assign", {}, staff))["assignee_id"] == staff_id
    reply = {"visibility": "public", "body": "Looking into it"}
    assert desk.post(f"/tickets/{ticket['id']}/comments", reply, staff).status_code == 201


def test_support_staff_cannot_manage_or_see_every_queue(desk, org):
    _, staff = org.user("support-staff")
    assert desk.get("/stats/open-by-priority?scope=all", staff).status_code == 403
    assert desk.post("/queues", {"name": "Labs", "member_ids": []}, staff).status_code == 403


def test_org_admin_sets_up_queues(client, org):
    _, admin = org.user("org-admin")
    r = client.post(f"{BASE}/queues", json={"name": "Front desk", "member_ids": []}, headers=admin)
    assert r.status_code == 201, r.text


def test_management_reads_every_queue_but_does_not_work_tickets(desk, org):
    _, management = org.user("management")
    ticket = desk.raise_ticket()
    assert desk.ok(desk.get("/stats/open-by-priority?scope=all", management))["total_open"] >= 1
    reply = {"visibility": "public", "body": "Not allowed"}
    assert desk.post(f"/tickets/{ticket['id']}/comments", reply, management).status_code == 403


def test_other_profile_roles_get_no_helpdesk_access_yet(client, org):
    """Requesters (every other profile role) are still open question 13: student gets nothing from helpdesk."""
    _, student = org.user("student")
    assert client.get(f"{BASE}/me/tickets", headers=student).status_code == 403
