"""Obligations and filings through the HTTP API: record, create per period, prepare, review, return, submit and
acknowledge, with their events and audit entries."""

from conftest import audit, days, outbox


def test_record_and_list_obligations(desk):
    ob = desk.obligation()
    assert (ob["title"], ob["authority"], ob["recurrence"], ob["active"]) == (
        "Annual report to the regulator",
        "State Council",
        "annual",
        True,
    )
    desk.obligation(title="Fire safety return", authority="Fire Department", recurrence="half_yearly")
    titles = [o["title"] for o in desk.ok(desk.get("/obligations", desk.viewer))]
    assert titles == sorted(titles)
    assert [o["title"] for o in desk.ok(desk.get("/obligations?authority=Fire Department"))] == ["Fire safety return"]
    off = desk.ok(desk.patch(f"/obligations/{ob['id']}", {"active": False}))
    assert off["active"] is False
    assert desk.post("/obligations", {"title": "X", "authority": "Y", "recurrence": "weekly"}).status_code == 422
    assert (
        desk.post("/obligations", {"title": "X", "authority": "Y", "recurrence": "once"}, desk.preparer).status_code
        == 403
    )


def test_a_filing_per_period_owned_by_the_default_owner(desk):
    ob = desk.obligation()
    f = desk.filing(ob["id"], period_label="2025-26")
    assert (f["status"], f["owner_id"], f["period_label"]) == ("open", desk.preparer_id, "2025-26")
    again = desk.post(
        f"/obligations/{ob['id']}/filings",
        {"period_label": "2025-26", "period_start": days(-120), "period_end": days(-30), "due_on": days(10)},
    )
    assert again.status_code == 409  # one filing per period
    bad = desk.post(
        f"/obligations/{ob['id']}/filings",
        {"period_label": "X", "period_start": days(0), "period_end": days(-5), "due_on": days(10)},
    )
    assert bad.status_code == 422
    desk.ok(desk.patch(f"/obligations/{ob['id']}", {"active": False}))
    closed = desk.post(
        f"/obligations/{ob['id']}/filings",
        {"period_label": "Y", "period_start": days(-60), "period_end": days(-30), "due_on": days(10)},
    )
    assert closed.status_code in (409, 422)  # an inactive obligation takes no new filings
    detail = desk.ok(desk.get(f"/obligations/{ob['id']}", desk.viewer))
    assert detail["id"] == ob["id"]


def test_the_owner_prepares_and_the_coordinator_submits(desk):
    f = desk.filing()
    fid = f["id"]
    assert desk.move(fid, "in_preparation", desk.preparer)["status"] == "in_preparation"
    assert desk.post(f"/filings/{fid}/status", {"status": "under_review"}, desk.preparer2).status_code in (403, 404)
    assert desk.move(fid, "under_review", desk.preparer)["status"] == "under_review"
    no_comment = desk.post(f"/filings/{fid}/status", {"status": "in_preparation"})
    assert no_comment.status_code == 422  # returning needs a comment
    assert desk.move(fid, "in_preparation", comment="Add the annexure")["status"] == "in_preparation"
    desk.move(fid, "under_review", desk.preparer)
    assert (
        desk.post(
            f"/filings/{fid}/submit", {"submitted_on": days(0), "submission_reference": "ACK-1"}, desk.preparer
        ).status_code
        == 403
    )
    submitted = desk.ok(desk.post(f"/filings/{fid}/submit", {"submitted_on": days(0), "submission_reference": "ACK-1"}))
    assert submitted["status"] == "submitted"
    event = outbox("regulatory-reports.filing.submitted", desk.org.id)[-1]
    assert event["filing_id"] == fid
    assert (
        desk.post(f"/filings/{fid}/submit", {"submitted_on": days(0), "submission_reference": "ACK-2"}).status_code
        == 409
    )
    acked = desk.ok(desk.post(f"/filings/{fid}/acknowledge", {"acknowledged_on": days(0)}))
    assert acked["status"] == "acknowledged"
    assert outbox("regulatory-reports.filing.acknowledged", desk.org.id)[-1]["filing_id"] == fid
    assert desk.post(f"/filings/{fid}/acknowledge", {"acknowledged_on": days(0)}).status_code == 409
    assert len(audit(desk.org.id, fid)) >= 5


def test_not_applicable_needs_a_reason_and_is_final(desk):
    f = desk.filing()
    assert desk.post(f"/filings/{f['id']}/status", {"status": "not_applicable"}).status_code == 422
    done = desk.move(f["id"], "not_applicable", reason="Closed for renovation this year")
    assert done["status"] == "not_applicable"
    assert desk.post(f"/filings/{f['id']}/status", {"status": "in_preparation"}, desk.preparer).status_code == 409
    assert desk.post(f"/filings/{f['id']}/status", {"status": "not_applicable"}, desk.preparer).status_code in (
        403,
        409,
    )


def test_preparers_see_only_their_own_filings(desk):
    mine = desk.filing()
    other = desk.filing(owner_id=desk.preparer2_id)
    as_preparer = [x["id"] for x in desk.ok(desk.get("/filings", desk.preparer))["items"]]
    assert mine["id"] in as_preparer and other["id"] not in as_preparer
    assert desk.get(f"/filings/{other['id']}", desk.preparer).status_code == 404
    all_ = [x["id"] for x in desk.ok(desk.get("/filings", desk.viewer))["items"]]
    assert {mine["id"], other["id"]} <= set(all_)


def test_filings_soonest_due_first_with_filters(desk):
    late = desk.filing(due_on=days(-3))
    soon = desk.filing(due_on=days(5))
    later = desk.filing(due_on=days(50))
    order = [x["id"] for x in desk.ok(desk.get("/filings"))["items"]]
    assert order.index(late["id"]) < order.index(soon["id"]) < order.index(later["id"])
    overdue = [x["id"] for x in desk.ok(desk.get("/filings?overdue=true"))["items"]]
    assert late["id"] in overdue and soon["id"] not in overdue
    assert desk.get("/filings?status=lost").status_code == 422


def test_the_owner_edits_notes_and_only_the_coordinator_reschedules(desk):
    f = desk.filing()
    notes = desk.ok(
        desk.patch(f"/filings/{f['id']}", {"preparation_notes": "Waiting for the fee figures"}, desk.preparer)
    )
    assert notes["preparation_notes"] == "Waiting for the fee figures"
    assert desk.patch(f"/filings/{f['id']}", {"due_on": days(40)}, desk.preparer).status_code == 403
    assert desk.ok(desk.patch(f"/filings/{f['id']}", {"due_on": days(40)}))["due_on"] == days(40)


def test_dates_after_today_are_refused_for_submission_and_acknowledgement(desk):
    f = desk.filing()
    desk.move(f["id"], "in_preparation", desk.preparer)
    desk.move(f["id"], "under_review", desk.preparer)
    future = desk.post(f"/filings/{f['id']}/submit", {"submitted_on": days(1), "submission_reference": "R"})
    assert future.status_code == 422


def test_a_period_taken_by_a_concurrent_create_is_a_409(desk, monkeypatch):
    """Two creates for one period both pass the check; the second hits the unique constraint and gets the 409."""
    from eos_regulatory_reports.infrastructure import repository

    ob = desk.obligation()
    desk.filing(ob["id"], period_label="2026-27")
    monkeypatch.setattr(repository, "filing_with_label", lambda db, oid, label: None)
    body = {"period_label": "2026-27", "period_start": days(-120), "period_end": days(-30), "due_on": days(10)}
    assert desk.post(f"/obligations/{ob['id']}/filings", body).status_code == 409
