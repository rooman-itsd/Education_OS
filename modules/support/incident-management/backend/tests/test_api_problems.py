"""Problems and root-cause analyses through the HTTP API: open with a number, link incidents, known error, draft and
publish the RCA, resolve and close."""

from conftest import audit, outbox, rca_body


def test_open_a_problem_with_a_number(desk, monkeypatch):
    first = desk.problem(affected_services=["Wi-Fi", " wi-fi "])
    assert (first["number"], first["status"], first["owner_id"]) == ("PRB-000001", "open", desk.manager_id)
    assert (first["affected_services"], first["workaround"], first["incident_count"]) == (["Wi-Fi"], None, 0)
    monkeypatch.setenv("INCIDENT_MANAGEMENT_PROBLEM_NUMBER_PREFIX", "PB")
    second = desk.problem(owner_id=desk.responder_id)
    assert (second["number"], second["owner_id"]) == ("PB-000002", desk.responder_id)
    assert audit(desk.org.id, first["id"]) == [("problem.opened", None)]
    assert outbox("incident-management.problem.status-changed", desk.org.id) == []  # no event for a new problem


def test_problem_detail_with_incidents_rca_status_and_actions(desk):
    problem = desk.problem()
    a, b = desk.incident(), desk.incident(title="Wi-Fi down in block B")
    for incident in (a, b):
        desk.ok(desk.patch(f"/incidents/{incident['id']}", {"problem_id": problem["id"]}, desk.responder))
    detail = desk.ok(desk.get(f"/problems/{problem['id']}", desk.viewer))
    assert ([i["id"] for i in detail["incidents"]], detail["incident_count"]) == ([a["id"], b["id"]], 2)
    assert (detail["rca_status"], detail["actions"]) == (None, [])
    desk.ok(desk.put(f"/problems/{problem['id']}/rca", rca_body()))
    action = desk.action(problem["id"])
    detail = desk.ok(desk.get(f"/problems/{problem['id']}"))
    assert (detail["rca_status"], [x["id"] for x in detail["actions"]]) == ("draft", [action["id"]])
    assert [i["id"] for i in desk.ok(desk.get(f"/incidents?problem_id={problem['id']}"))["items"]] == [
        b["id"],
        a["id"],
    ]
    assert desk.ok(desk.get("/problems"))["items"][0]["incident_count"] == 2
    assert outbox("incident-management.incident.severity-changed", desk.org.id) == []  # linking publishes nothing


def test_known_error_needs_a_workaround(desk):
    problem = desk.problem()
    path = f"/problems/{problem['id']}/status"
    assert desk.post(path, {"status": "known_error", "workaround": "Reboot"}).status_code == 409  # still open
    desk.ok(desk.post(path, {"status": "investigating"}))
    missing = desk.post(path, {"status": "known_error"})
    assert (missing.status_code, missing.json()["detail"]["code"]) == (422, "workaround_required")
    known = desk.ok(desk.post(path, {"status": "known_error", "workaround": "Move users to the guest SSID"}))
    assert (known["status"], known["workaround"]) == ("known_error", "Move users to the guest SSID")
    blanked = desk.patch(f"/problems/{problem['id']}", {"workaround": "  "})
    assert (blanked.status_code, blanked.json()["detail"]["code"]) == (422, "workaround_required")
    event = outbox("incident-management.problem.status-changed", desk.org.id)[-1]
    assert event == {
        "organisation_id": desk.org.id,
        "problem_id": problem["id"],
        "number": problem["number"],
        "from_status": "investigating",
        "to_status": "known_error",
        "affected_services": [],
        "changed_at": "2026-11-04T09:00:00+00:00",
    }


def test_a_recorded_workaround_is_enough_for_known_error(desk):
    problem = desk.problem()
    desk.ok(desk.patch(f"/problems/{problem['id']}", {"workaround": "Use wired ports"}))
    desk.ok(desk.post(f"/problems/{problem['id']}/status", {"status": "investigating"}))
    known = desk.ok(desk.post(f"/problems/{problem['id']}/status", {"status": "known_error"}))
    assert known["workaround"] == "Use wired ports"


def test_rca_draft_publish_resolve_and_close(desk, clock):
    problem = desk.problem()
    pid, path = problem["id"], f"/problems/{problem['id']}"
    missing = desk.get(f"{path}/rca", desk.viewer)
    assert (missing.status_code, missing.json()["detail"]["code"]) == (404, "rca_not_found")
    assert desk.post(f"{path}/rca/publish", {}).status_code == 404
    desk.ok(desk.post(f"{path}/status", {"status": "investigating"}))
    refused = desk.post(f"{path}/status", {"status": "resolved"})
    assert (refused.status_code, refused.json()["detail"]["code"]) == (409, "rca_not_published")

    draft = desk.ok(desk.put(f"{path}/rca", rca_body(contributing_factors=["No staging"])))
    assert (draft["status"], draft["contributing_factors"], draft["published_at"]) == ("draft", ["No staging"], None)
    replaced = desk.ok(desk.put(f"{path}/rca", rca_body(summary="Firmware memory leak")))
    assert (replaced["summary"], replaced["contributing_factors"]) == ("Firmware memory leak", [])
    assert desk.post(f"{path}/status", {"status": "resolved"}).status_code == 409  # draft only

    published = desk.ok(desk.post(f"{path}/rca/publish", {}))
    assert (published["status"], published["published_by"], published["published_at"]) == (
        "published",
        desk.manager_id,
        "2026-11-04T09:00:00+00:00",
    )
    assert set(published) == {
        "summary",
        "root_cause",
        "contributing_factors",
        "attachment_document_ids",
        "problem_id",
        "organisation_id",
        "status",
        "published_at",
        "published_by",
        "updated_at",
    }
    again = desk.post(f"{path}/rca/publish", {})
    assert (again.status_code, again.json()["detail"]["code"]) == (409, "rca_published")
    edit = desk.put(f"{path}/rca", rca_body())
    assert (edit.status_code, edit.json()["detail"]["code"]) == (409, "rca_published")
    assert desk.ok(desk.get(f"{path}/rca", desk.responder))["summary"] == "Firmware memory leak"
    assert outbox("incident-management.problem.rca-published", desk.org.id) == [
        {
            "organisation_id": desk.org.id,
            "problem_id": pid,
            "number": problem["number"],
            "published_by": desk.manager_id,
            "published_at": "2026-11-04T09:00:00+00:00",
        }
    ]

    resolved = desk.ok(desk.post(f"{path}/status", {"status": "resolved"}))
    assert resolved["resolved_at"] == "2026-11-04T09:00:00+00:00"
    closed = desk.ok(desk.post(f"{path}/status", {"status": "closed"}))
    assert (closed["status"], closed["closed_at"]) == ("closed", "2026-11-04T09:00:00+00:00")
    assert desk.patch(path, {"title": "Edited title"}).status_code == 409
    incident = desk.incident()
    link = desk.patch(f"/incidents/{incident['id']}", {"problem_id": pid}, desk.responder)
    assert (link.status_code, link.json()["detail"]["code"]) == (409, "problem_closed")
    actions = [a for a, _ in audit(desk.org.id, pid)]
    assert actions == [
        "problem.opened",
        "problem.investigating",
        "rca.drafted",
        "rca.updated",
        "rca.published",
        "problem.resolved",
        "problem.closed",
    ]


def test_problem_edits_and_list_filters(desk):
    wifi = desk.problem(affected_services=["Wi-Fi"])
    lms = desk.problem(title="LMS session store fills up", owner_id=desk.responder_id, affected_services=["LMS"])
    edited = desk.ok(desk.patch(f"/problems/{wifi['id']}", {"title": "AP firmware crash", "owner_id": None}))
    assert (edited["title"], edited["owner_id"]) == ("AP firmware crash", desk.manager_id)
    assert audit(desk.org.id, wifi["id"])[-1] == ("problem.updated", "fields: title")
    desk.ok(desk.post(f"/problems/{lms['id']}/status", {"status": "investigating"}))

    def ids(query: str, headers=None) -> list[str]:
        return [p["id"] for p in desk.ok(desk.get(f"/problems{query}", headers or desk.viewer))["items"]]

    assert ids("") == [lms["id"], wifi["id"]]
    assert ids("?status=investigating") == [lms["id"]]
    assert ids("?status=open,known_error") == [wifi["id"]]
    assert ids("?owner=me", desk.responder) == [lms["id"]]
    assert ids("?service=WI-FI") == [wifi["id"]]
    assert ids("?q=session") == [lms["id"]]
    assert desk.get("/problems?status=open,stuck").status_code == 422
