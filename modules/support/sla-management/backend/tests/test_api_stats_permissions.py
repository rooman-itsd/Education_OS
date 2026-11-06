"""Who may call what: the viewer reads, only the admin sets up calendars and policies, and the Support Staff profile
role reads the widget through its dashboard layout."""

from conftest import BASE, calendar_body, policy_body


def test_viewer_reads_but_does_not_set_up(desk):
    cal = desk.calendar()
    policy = desk.policy(cal["id"])
    for path in ("/calendars", f"/calendars/{cal['id']}", "/policies", f"/policies/{policy['id']}", "/clocks"):
        assert desk.get(path, desk.viewer).status_code == 200, path
    assert desk.get("/stats/breaches", desk.viewer).status_code == 200
    for path, body in [("/calendars", calendar_body()), ("/policies", policy_body(cal["id"], priority="low"))]:
        refused = desk.post(path, body, desk.viewer)
        assert (refused.status_code, refused.json()["detail"]["code"]) == (403, "forbidden"), path
    assert desk.patch(f"/calendars/{cal['id']}", {"name": "x"}, desk.viewer).status_code == 403
    assert desk.patch(f"/policies/{policy['id']}", {"active": False}, desk.viewer).status_code == 403


def test_admin_reads_everything(desk):
    assert desk.get("/clocks").status_code == 200
    assert desk.get("/stats/breaches").status_code == 200


def test_no_token_or_no_permission(client, org, clock):
    assert client.get(f"{BASE}/clocks").status_code == 401
    assert client.get(f"{BASE}/clocks", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    _, stranger = org.user("helpdesk-agent")
    for path in ("/stats/breaches", "/calendars", "/policies", "/clocks"):
        assert client.get(f"{BASE}{path}", headers=stranger).status_code == 403, path


def test_profile_role_support_staff_reads_through_its_dashboard_layout(client, org, clock):
    """support-staff.yaml gives the Support Staff profile role sla-management-viewer (module_roles)."""
    _, staff = org.user("support-staff")
    assert client.get(f"{BASE}/stats/breaches", headers=staff).status_code == 200
    assert client.get(f"{BASE}/stats/breaches?scope=mine", headers=staff).status_code == 200
    assert client.get(f"{BASE}/calendars", headers=staff).status_code == 200
    assert client.post(f"{BASE}/calendars", json=calendar_body(), headers=staff).status_code == 403
