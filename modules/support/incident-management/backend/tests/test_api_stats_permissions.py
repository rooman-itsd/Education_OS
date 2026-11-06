"""The widget endpoint GET /stats/open, and who may call what."""

from conftest import BASE, incident_body, problem_body


def test_open_counts_for_the_widget(desk):
    empty = desk.ok(desk.get("/stats/open", desk.viewer))
    assert empty == {
        "total_open": 0,
        "by_severity": [
            {"severity": "critical", "count": 0},
            {"severity": "high", "count": 0},
            {"severity": "medium", "count": 0},
            {"severity": "low", "count": 0},
        ],
        "by_status": [
            {"status": "open", "count": 0},
            {"status": "investigating", "count": 0},
            {"status": "mitigated", "count": 0},
        ],
    }
    desk.incident(severity="critical")
    investigating = desk.incident(severity="critical")
    desk.move(investigating["id"], "investigating")
    mitigated = desk.incident(severity="low")
    desk.move(mitigated["id"], "investigating")
    desk.move(mitigated["id"], "mitigated")
    resolved = desk.incident(severity="high")
    desk.move(resolved["id"], "investigating")
    desk.move(resolved["id"], "resolved", resolution_summary="Fixed")
    cancelled = desk.incident(severity="medium")
    desk.move(cancelled["id"], "cancelled", note="Duplicate report")

    body = desk.ok(desk.get("/stats/open", desk.responder))
    assert body["total_open"] == 3
    assert [(r["severity"], r["count"]) for r in body["by_severity"]] == [
        ("critical", 2),
        ("high", 0),
        ("medium", 0),
        ("low", 1),
    ]
    assert [(r["status"], r["count"]) for r in body["by_status"]] == [
        ("open", 1),
        ("investigating", 1),
        ("mitigated", 1),
    ]


def test_viewer_reads_but_does_not_change_anything(desk):
    incident = desk.incident()
    problem = desk.problem()
    for path in (f"/incidents/{incident['id']}", "/incidents", "/problems", f"/problems/{problem['id']}", "/actions"):
        assert desk.get(path, desk.viewer).status_code == 200, path
    for path, body in [
        ("/incidents", incident_body()),
        (f"/incidents/{incident['id']}/status", {"status": "investigating"}),
        (f"/incidents/{incident['id']}/updates", {"body": "No"}),
        ("/problems", problem_body()),
    ]:
        refused = desk.post(path, body, desk.viewer)
        assert (refused.status_code, refused.json()["detail"]["code"]) == (403, "forbidden"), path
    assert desk.patch(f"/incidents/{incident['id']}", {"severity": "low"}, desk.viewer).status_code == 403


def test_responder_works_incidents_but_not_problems(desk):
    problem = desk.problem()
    assert desk.patch(f"/problems/{problem['id']}", {"title": "Mine now"}, desk.responder).status_code == 403
    assert (
        desk.put(f"/problems/{problem['id']}/rca", {"summary": "abc", "root_cause": "def"}, desk.responder).status_code
        == 403
    )
    assert desk.get(f"/problems/{problem['id']}", desk.responder).status_code == 200


def test_no_token_or_no_permission(client, org, clock):
    assert client.get(f"{BASE}/incidents").status_code == 401
    assert client.get(f"{BASE}/incidents", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    _, stranger = org.user("helpdesk-agent")
    assert client.get(f"{BASE}/stats/open", headers=stranger).status_code == 403


def test_profile_role_support_staff_reads_through_its_dashboard_layout(client, org, clock):
    """support-staff.yaml gives the Support Staff profile role incident-management-responder (module_roles): it reads
    the widget, reports and works incidents, reads problems, but does not manage them."""
    _, staff = org.user("support-staff")
    assert client.get(f"{BASE}/stats/open", headers=staff).status_code == 200
    reported = client.post(f"{BASE}/incidents", json=incident_body(), headers=staff)
    assert reported.status_code == 201
    assert client.get(f"{BASE}/problems", headers=staff).status_code == 200
    assert client.post(f"{BASE}/problems", json=problem_body(), headers=staff).status_code == 403
