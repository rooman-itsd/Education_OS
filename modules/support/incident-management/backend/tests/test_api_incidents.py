"""Incidents through the HTTP API: report with a number, move through the statuses, timeline, edits and severity,
references, and the list filters."""

from datetime import timedelta

from conftest import NOW, TICKET, audit, incident_body, outbox

STARTED = (NOW - timedelta(hours=2)).isoformat()


def test_report_an_incident_with_a_number_and_an_event(desk):
    responder = "22222222-2222-4222-8222-222222222222"
    first = desk.incident(started_at=STARTED, responder_ids=[responder, responder.upper()])
    second = desk.incident(affected_services=[" LMS ", "lms", "  ", "Email"])
    assert (first["number"], second["number"]) == ("INC-000001", "INC-000002")
    assert (first["status"], first["lead_id"], first["reported_by"]) == ("open", desk.responder_id, desk.responder_id)
    assert (first["started_at"], second["started_at"]) == ("2026-11-04T07:00:00+00:00", "2026-11-04T09:00:00+00:00")
    assert first["responder_ids"] == [responder]
    assert second["affected_services"] == ["LMS", "Email"]
    assert (first["problem_id"], first["resolution_summary"], first["mitigated_at"]) == (None, None, None)
    assert audit(desk.org.id, first["id"]) == [("incident.reported", None)]
    event = outbox("incident-management.incident.reported", desk.org.id)[0]
    assert event == {
        "organisation_id": desk.org.id,
        "incident_id": first["id"],
        "number": "INC-000001",
        "severity": "high",
        "affected_services": ["Wi-Fi"],
        "lead_id": desk.responder_id,
        "responder_ids": [responder],
        "started_at": "2026-11-04T07:00:00+00:00",
    }


def test_another_lead_and_number_prefix(desk, monkeypatch):
    monkeypatch.setenv("INCIDENT_MANAGEMENT_INCIDENT_NUMBER_PREFIX", "OUT")
    incident = desk.incident(lead_id=desk.manager_id)
    assert (incident["number"], incident["lead_id"]) == ("OUT-000001", desk.manager_id)


def test_report_refuses_bad_values(desk):
    future = (NOW + timedelta(hours=1)).isoformat()
    refused = desk.post("/incidents", incident_body(started_at=future), desk.responder)
    assert (refused.status_code, refused.json()["detail"]["code"]) == (422, "started_at_in_future")
    skewed = (NOW + timedelta(minutes=4)).isoformat()
    assert desk.post("/incidents", incident_body(started_at=skewed), desk.responder).status_code == 201
    for bad in (
        incident_body(severity="urgent"),
        incident_body(title="ab"),
        incident_body(title="   "),
        incident_body(extra=True),
        incident_body(lead_id="not-a-person"),
        {"title": "No description", "severity": "low"},
    ):
        assert desk.post("/incidents", bad, desk.responder).status_code == 422, bad


def test_full_lifecycle_with_timeline_and_events(desk, clock):
    incident = desk.incident()
    iid, path = incident["id"], f"/incidents/{incident['id']}/status"
    assert desk.post(path, {"status": "mitigated"}, desk.responder).status_code == 409  # not from open
    desk.move(iid, "investigating")
    clock.set(NOW + timedelta(minutes=30))
    mitigated = desk.move(iid, "mitigated", note="Rebooted the controller")
    assert mitigated["mitigated_at"] == "2026-11-04T09:30:00+00:00"
    missing = desk.post(path, {"status": "resolved"}, desk.responder)
    assert (missing.status_code, missing.json()["detail"]["code"]) == (422, "resolution_summary_required")
    clock.set(NOW + timedelta(hours=1))
    resolved = desk.move(iid, "resolved", resolution_summary="Controller replaced")
    assert (resolved["resolved_at"], resolved["resolution_summary"]) == (
        "2026-11-04T10:00:00+00:00",
        "Controller replaced",
    )
    no_note = desk.post(path, {"status": "investigating"}, desk.responder)
    assert (no_note.status_code, no_note.json()["detail"]["code"]) == (422, "note_required")
    reopened = desk.move(iid, "investigating", note="Dropping again")
    assert (reopened["status"], reopened["resolved_at"], reopened["resolution_summary"]) == (
        "investigating",
        None,
        None,
    )
    desk.move(iid, "resolved", resolution_summary="Firmware rolled back")
    closed = desk.move(iid, "closed")
    assert (closed["status"], closed["closed_at"]) == ("closed", "2026-11-04T10:00:00+00:00")
    assert desk.post(path, {"status": "investigating", "note": "Again"}, desk.responder).status_code == 409

    detail = desk.ok(desk.get(f"/incidents/{iid}", desk.viewer))
    assert [u["body"] for u in detail["updates"]] == ["Rebooted the controller", "Dropping again"]
    assert detail["updates"][0]["author_id"] == desk.responder_id
    moves = [
        (e["from_status"], e["to_status"]) for e in outbox("incident-management.incident.status-changed", desk.org.id)
    ]
    assert moves == [
        ("open", "investigating"),
        ("investigating", "mitigated"),
        ("mitigated", "resolved"),
        ("resolved", "investigating"),
        ("investigating", "resolved"),
        ("resolved", "closed"),
    ]
    actions = [a for a, _ in audit(desk.org.id, iid)]
    assert actions == [
        "incident.reported",
        "incident.investigating",
        "incident.mitigated",
        "incident.resolved",
        "incident.reopened",
        "incident.resolved",
        "incident.closed",
    ]


def test_cancel_needs_a_note_and_ends_the_incident(desk):
    incident = desk.incident()
    path = f"/incidents/{incident['id']}/status"
    assert desk.post(path, {"status": "cancelled"}, desk.responder).status_code == 422
    cancelled = desk.move(incident["id"], "cancelled", note="Reported in error")
    assert cancelled["status"] == "cancelled"
    assert desk.patch(f"/incidents/{incident['id']}", {"title": "Edited"}, desk.responder).status_code == 409
    added = desk.post(f"/incidents/{incident['id']}/updates", {"body": "Late"}, desk.responder)
    assert (added.status_code, added.json()["detail"]["code"]) == (409, "incident_closed")
    event = outbox("incident-management.incident.status-changed", desk.org.id)[-1]
    assert (event["to_status"], event["problem_id"]) == ("cancelled", None)


def test_timeline_updates(desk):
    incident = desk.incident()
    update = desk.ok(desk.post(f"/incidents/{incident['id']}/updates", {"body": "Vendor engaged"}, desk.responder))
    assert set(update) == {"id", "incident_id", "author_id", "body", "created_at"}
    assert (update["incident_id"], update["author_id"], update["body"]) == (
        incident["id"],
        desk.responder_id,
        "Vendor engaged",
    )
    for body in ({"body": ""}, {"body": "   "}, {}):
        assert desk.post(f"/incidents/{incident['id']}/updates", body, desk.responder).status_code == 422
    assert audit(desk.org.id, incident["id"])[-1] == ("incident.update_added", f"update {update['id']}")


def test_edit_details_and_severity(desk):
    incident = desk.incident()
    iid = incident["id"]
    responder = "33333333-3333-4333-8333-333333333333"
    edited = desk.ok(
        desk.patch(
            f"/incidents/{iid}",
            {"title": "Wi-Fi down in blocks A and B", "severity": "critical", "responder_ids": [responder]},
            desk.responder,
        )
    )
    assert (edited["title"], edited["severity"], edited["responder_ids"]) == (
        "Wi-Fi down in blocks A and B",
        "critical",
        [responder],
    )
    event = outbox("incident-management.incident.severity-changed", desk.org.id)[-1]
    assert event == {
        "organisation_id": desk.org.id,
        "incident_id": iid,
        "number": incident["number"],
        "severity": "critical",
        "previous_severity": "high",
        "status": "open",
        "changed_by": desk.responder_id,
    }
    assert audit(desk.org.id, iid)[-1] == ("incident.updated", "fields: responder_ids, severity, title")
    same = desk.ok(desk.patch(f"/incidents/{iid}", {"severity": "critical", "title": None}, desk.responder))
    assert same["title"] == "Wi-Fi down in blocks A and B"  # null never clears a required value
    assert len(outbox("incident-management.incident.severity-changed", desk.org.id)) == 1  # unchanged severity


def test_started_at_cannot_follow_the_recorded_times(desk, clock):
    incident = desk.incident()
    desk.move(incident["id"], "investigating")
    desk.move(incident["id"], "mitigated")
    clock.set(NOW + timedelta(hours=2))
    later = (NOW + timedelta(hours=1)).isoformat()
    refused = desk.patch(f"/incidents/{incident['id']}", {"started_at": later}, desk.responder)
    assert (refused.status_code, refused.json()["detail"]["code"]) == (422, "started_after_mitigated")
    earlier = desk.ok(desk.patch(f"/incidents/{incident['id']}", {"started_at": STARTED}, desk.responder))
    assert earlier["started_at"] == "2026-11-04T07:00:00+00:00"


def test_references_recorded_once_and_removed_with_audit(desk):
    incident = desk.incident()
    path = f"/incidents/{incident['id']}/references"
    ref = desk.ok(desk.post(path, {**TICKET, "note": "Raised by the library"}, desk.responder))
    assert set(ref) == {"module", "entity", "id", "relation", "note", "reference_id", "created_by", "created_at"}
    assert (ref["module"], ref["id"], ref["relation"], ref["created_by"]) == (
        "helpdesk",
        "hd-101",
        "related_ticket",
        desk.responder_id,
    )
    again = desk.post(path, {**TICKET, "relation": "work_order"}, desk.responder)
    assert (again.status_code, again.json()["detail"]["code"]) == (409, "reference_exists")
    asset = {"module": "asset-management", "entity": "asset", "id": "ap-7", "relation": "affected_asset"}
    desk.ok(desk.post(path, asset, desk.responder))
    assert desk.post(path, {**asset, "relation": "parent"}, desk.responder).status_code == 422
    detail = desk.ok(desk.get(f"/incidents/{incident['id']}"))
    assert [r["id"] for r in detail["references"]] == ["hd-101", "ap-7"]

    assert desk.delete(f"{path}/{ref['reference_id']}", desk.responder).status_code == 204
    assert desk.delete(f"{path}/{ref['reference_id']}", desk.responder).status_code == 404
    assert [r["id"] for r in desk.ok(desk.get(f"/incidents/{incident['id']}"))["references"]] == ["ap-7"]
    assert audit(desk.org.id, incident["id"])[-1] == (
        "incident.reference_removed",
        f"reference {ref['reference_id']}: helpdesk/ticket/hd-101",
    )
    # A reference on another incident is not found under this one.
    other = desk.incident()
    elsewhere = desk.ok(desk.post(f"/incidents/{other['id']}/references", TICKET, desk.responder))
    assert desk.delete(f"{path}/{elsewhere['reference_id']}", desk.responder).status_code == 404


def test_list_filters_and_pages(desk, clock):
    wifi = desk.incident()
    clock.set(NOW + timedelta(minutes=1))
    lms = desk.incident(
        title="LMS login fails", severity="critical", affected_services=["LMS"], lead_id=desk.manager_id
    )
    clock.set(NOW + timedelta(minutes=2))
    mail = desk.incident(title="Email delayed", severity="low", affected_services=["Email", "LMS"])
    desk.move(mail["id"], "investigating")

    def ids(query: str, headers=None) -> list[str]:
        return [i["id"] for i in desk.ok(desk.get(f"/incidents{query}", headers or desk.viewer))["items"]]

    assert ids("") == [mail["id"], lms["id"], wifi["id"]]  # newest first
    assert ids("?status=investigating") == [mail["id"]]
    assert ids("?status=open,investigating") == [mail["id"], lms["id"], wifi["id"]]
    assert ids("?severity=critical") == [lms["id"]]
    assert ids("?service=lms") == [mail["id"], lms["id"]]
    assert ids("?q=login") == [lms["id"]]
    assert ids("?q=inc-000001") == [wifi["id"]]
    assert ids("?q=100%25") == []  # % is matched literally
    assert ids("?lead=me", desk.manager) == [lms["id"]]
    assert ids(f"?lead={desk.responder_id}") == [mail["id"], wifi["id"]]

    first = desk.ok(desk.get("/incidents?limit=2"))
    assert [i["id"] for i in first["items"]] == [mail["id"], lms["id"]]
    second = desk.ok(desk.get(f"/incidents?limit=2&cursor={first['next_cursor']}"))
    assert ([i["id"] for i in second["items"]], second["next_cursor"]) == ([wifi["id"]], None)


def test_responders_cannot_open_problems_but_can_link_to_one(desk):
    problem = desk.problem()
    incident = desk.incident()
    assert desk.post("/problems", {"title": "Nope", "description": "Nope"}, desk.responder).status_code == 403
    linked = desk.ok(desk.patch(f"/incidents/{incident['id']}", {"problem_id": problem["id"]}, desk.responder))
    assert linked["problem_id"] == problem["id"]
    assert audit(desk.org.id, incident["id"])[-1] == ("incident.linked", f"problem {problem['id']}")
    unlinked = desk.ok(desk.patch(f"/incidents/{incident['id']}", {"problem_id": None}, desk.responder))
    assert unlinked["problem_id"] is None
    assert audit(desk.org.id, incident["id"])[-1] == ("incident.unlinked", f"problem {problem['id']}")
    unknown = desk.patch(
        f"/incidents/{incident['id']}", {"problem_id": "00000000-0000-4000-8000-000000000000"}, desk.responder
    )
    assert (unknown.status_code, unknown.json()["detail"]["code"]) == (404, "not_found")


def test_a_blank_description_is_refused_on_edit_as_on_report(desk):
    incident = desk.incident()
    path = f"/incidents/{incident['id']}"
    for blank in ("", "ab", "   "):
        assert desk.patch(path, {"description": blank}, desk.responder).status_code == 422, repr(blank)
    refused = desk.patch(path, {"description": "      "}, desk.responder)
    assert (refused.status_code, refused.json()["detail"]["code"]) == (422, "description_blank")
    assert desk.ok(desk.get(path, desk.responder))["description"] == incident["description"]
    edited = desk.ok(desk.patch(path, {"description": "Wi-Fi is down in blocks A and B"}, desk.responder))
    assert edited["description"] == "Wi-Fi is down in blocks A and B"
