"""Responses: visibility, filling in, submitting, review, evidence (PRD flows 4 and 5)."""

from datetime import timedelta

from conftest import audit, days, outbox
from eos_core.db import new_id


def code(r) -> tuple[int, str]:
    return r.status_code, r.json()["detail"]["code"]


def test_a_contributor_sees_only_their_own_responses_a_reader_sees_all(desk):
    d = desk
    c = d.collecting()
    mine = d.ok(d.get("/responses", d.alice))["items"]
    assert [r["id"] for r in mine] == [c["q"]["id"]]
    assert {r["id"] for r in d.ok(d.get("/responses", d.coordinator))["items"]} == {c["q"]["id"], c["n"]["id"]}
    assert {r["id"] for r in d.ok(d.get("/responses", d.viewer))["items"]} == {c["q"]["id"], c["n"]["id"]}
    # owner=me, an owner id, and asking for someone else's as a contributor (an empty page, not a 403).
    assert [r["id"] for r in d.ok(d.get("/responses?owner=me", d.bob))["items"]] == [c["n"]["id"]]
    assert [r["id"] for r in d.ok(d.get(f"/responses?owner={d.bob_id}", d.coordinator))["items"]] == [c["n"]["id"]]
    assert d.ok(d.get(f"/responses?owner={d.bob_id}", d.alice))["items"] == []
    # One response: another's is not found to a contributor, found for a reader.
    assert d.get(f"/responses/{c['n']['id']}", d.alice).status_code == 404
    assert d.get(f"/responses/{c['n']['id']}", d.viewer).status_code == 200
    assert d.get(f"/responses/{new_id()}").status_code == 404


def test_filters_pages_and_order(desk):
    d = desk
    c = d.collecting()
    cid = c["cycle"]["id"]
    d.ok(d.put(f"/responses/{c['q']['id']}", {"value": 1}, d.alice))
    d.ok(d.post(f"/responses/{c['q']['id']}/submit", None, d.alice))
    late = d.assign(cid, (d.metric(c["framework"]["id"])["id"], d.alice_id, days(-3)))[0]
    listed = d.ok(d.get(f"/responses?cycle_id={cid}"))["items"]
    assert [r["due_on"] for r in listed] == [days(-3), days(10), days(20)]  # soonest due first
    assert [r["id"] for r in d.ok(d.get("/responses?status=submitted"))["items"]] == [c["q"]["id"]]
    assert [r["id"] for r in d.ok(d.get("/responses?overdue=true"))["items"]] == [late["id"]]
    assert len(d.ok(d.get("/responses?overdue=false"))["items"]) == 2
    first = d.ok(d.get("/responses?limit=2"))
    assert len(first["items"]) == 2 and first["next_cursor"]
    rest = d.ok(d.get(f"/responses?limit=2&cursor={first['next_cursor']}"))
    assert len(rest["items"]) == 1 and rest["next_cursor"] is None
    ids = {r["id"] for r in first["items"] + rest["items"]}
    assert len(ids) == 3


def test_overdue_is_pending_or_returned_and_past_due(desk, clock):
    d = desk
    c = d.collecting()
    clock.set(clock.now + timedelta(days=11))  # alice's response (due in 10 days) is now a day late
    assert d.ok(d.get(f"/responses/{c['q']['id']}"))["overdue"] is True
    assert d.ok(d.get(f"/responses/{c['n']['id']}"))["overdue"] is False
    clock.set(clock.now - timedelta(days=1))  # due today is not overdue
    assert d.ok(d.get(f"/responses/{c['q']['id']}"))["overdue"] is False
    clock.set(clock.now + timedelta(days=30))
    d.ok(d.put(f"/responses/{c['q']['id']}", {"value": 1}, d.alice))
    d.ok(d.post(f"/responses/{c['q']['id']}/submit", None, d.alice))
    assert d.ok(d.get(f"/responses/{c['q']['id']}"))["overdue"] is False  # submitted: waiting on the coordinator


def test_the_owner_saves_a_value_or_a_narrative_and_it_is_audited(desk):
    d = desk
    c = d.collecting()
    saved = d.ok(d.put(f"/responses/{c['q']['id']}", {"value": 61.5, "narrative": "Up from 58"}, d.alice))
    assert (saved["value"], saved["narrative"], saved["status"]) == (61.5, "Up from 58", "pending")
    # A left-out field keeps its value; null clears it.
    kept = d.ok(d.put(f"/responses/{c['q']['id']}", {"value": 70}, d.alice))
    assert (kept["value"], kept["narrative"]) == (70, "Up from 58")
    cleared = d.ok(d.put(f"/responses/{c['q']['id']}", {"narrative": None}, d.alice))
    assert (cleared["value"], cleared["narrative"]) == (70, None)
    assert audit(d.org.id, c["q"]["id"]) == [("response.assigned", None)] + [("response.saved", None)] * 3
    text = d.ok(d.put(f"/responses/{c['n']['id']}", {"narrative": "Curriculum reviewed yearly."}, d.bob))
    assert text["narrative"] == "Curriculum reviewed yearly." and text["value"] is None


def test_only_the_owner_can_save_and_a_qualitative_metric_takes_no_value(desk):
    d = desk
    c = d.collecting()
    assert d.put(f"/responses/{c['q']['id']}", {"value": 1}, d.bob).status_code == 404  # not bob's
    assert d.put(f"/responses/{c['q']['id']}", {"value": 1}, d.coordinator).status_code == 403  # no submit key
    assert d.put(f"/responses/{new_id()}", {"value": 1}, d.alice).status_code == 404
    assert code(d.put(f"/responses/{c['n']['id']}", {"value": 3}, d.bob)) == (422, "value_not_allowed")
    assert d.ok(d.get(f"/responses/{c['q']['id']}"))["value"] is None  # untouched by the refused calls


def test_saving_is_closed_outside_collecting_and_under_review(desk):
    d = desk
    c = d.collecting()
    cid = c["cycle"]["id"]
    d.move(cid, "under_review")  # still open to the owner
    assert d.put(f"/responses/{c['q']['id']}", {"value": 5}, d.alice).status_code == 200
    d.ok(d.post(f"/responses/{c['q']['id']}/submit", None, d.alice))
    d.ok(d.post(f"/responses/{c['q']['id']}/review", {"decision": "accept"}))
    d.ok(d.put(f"/responses/{c['n']['id']}", {"narrative": "x"}, d.bob))
    d.ok(d.post(f"/responses/{c['n']['id']}/submit", None, d.bob))
    d.ok(d.post(f"/responses/{c['n']['id']}/review", {"decision": "accept"}))
    d.move(cid, "submitted", submitted_on="2026-06-01")
    # A pending response cannot exist in a submitted cycle, so use a fresh cycle that is still planning.
    planning = d.cycle(c["framework"]["id"])
    extra = d.metric(c["framework"]["id"])
    r = d.assign(planning["id"], (extra["id"], d.alice_id, days(5)))[0]
    assert code(d.put(f"/responses/{r['id']}", {"value": 1}, d.alice)) == (409, "cycle_not_collecting")
    assert code(d.post(f"/responses/{r['id']}/submit", None, d.alice)) == (409, "cycle_not_collecting")
    d.move(planning["id"], "collecting")
    assert d.put(f"/responses/{r['id']}", {"value": 1}, d.alice).status_code == 200


def test_submit_needs_the_value_or_narrative_the_metric_kind_asks_for(desk):
    d = desk
    c = d.collecting()
    assert code(d.post(f"/responses/{c['q']['id']}/submit", None, d.alice)) == (422, "value_required")
    d.ok(d.put(f"/responses/{c['q']['id']}", {"narrative": "only a note"}, d.alice))
    assert code(d.post(f"/responses/{c['q']['id']}/submit", None, d.alice)) == (422, "value_required")
    assert code(d.post(f"/responses/{c['n']['id']}/submit", None, d.bob)) == (422, "narrative_required")
    d.ok(d.put(f"/responses/{c['n']['id']}", {"narrative": "   "}, d.bob))
    assert code(d.post(f"/responses/{c['n']['id']}/submit", None, d.bob)) == (422, "narrative_required")
    d.ok(d.put(f"/responses/{c['q']['id']}", {"value": 0}, d.alice))  # zero is a value
    done = d.ok(d.post(f"/responses/{c['q']['id']}/submit", None, d.alice))
    assert (done["status"], done["value"], done["submitted_at"]) == ("submitted", 0, "2026-11-05T09:00:00+00:00")
    assert d.post(f"/responses/{c['q']['id']}/submit", None, d.bob).status_code == 404
    assert d.post(f"/responses/{c['q']['id']}/submit", None, d.coordinator).status_code == 403
    assert code(d.post(f"/responses/{c['q']['id']}/submit", None, d.alice)) == (409, "response_not_editable")
    assert code(d.put(f"/responses/{c['q']['id']}", {"value": 9}, d.alice)) == (409, "response_not_editable")


def test_accept_publishes_the_event_and_makes_the_response_read_only(desk, clock):
    d = desk
    c = d.submitted_q()
    rid = c["q"]["id"]
    clock.set(clock.now + timedelta(hours=1))
    accepted = d.ok(d.post(f"/responses/{rid}/review", {"decision": "accept"}))
    assert (accepted["status"], accepted["reviewed_by"], accepted["reviewed_at"]) == (
        "accepted",
        d.coordinator_id,
        "2026-11-05T10:00:00+00:00",
    )
    assert outbox("iqac-accreditation.response.accepted", d.org.id) == [
        {
            "organisation_id": d.org.id,
            "response_id": rid,
            "cycle_id": c["cycle"]["id"],
            "metric_id": c["q"]["metric_id"],
            "metric_code": "Q1",
            "accepted_at": "2026-11-05T10:00:00+00:00",
        }
    ]
    assert audit(d.org.id, rid)[-1] == ("response.accepted", None)
    assert code(d.put(f"/responses/{rid}", {"value": 1}, d.alice)) == (409, "response_not_editable")
    assert code(d.post(f"/responses/{rid}/review", {"decision": "accept"})) == (409, "response_not_submitted")
    assert len(outbox("iqac-accreditation.response.accepted", d.org.id)) == 1


def test_return_needs_a_comment_and_the_owner_corrects_and_resubmits(desk):
    d = desk
    c = d.submitted_q()
    rid = c["q"]["id"]
    for body in (
        {"decision": "return"},
        {"decision": "return", "comment": "no"},
        {"decision": "return", "comment": "   "},
    ):
        assert d.post(f"/responses/{rid}/review", body).status_code == 422, body
    returned = d.ok(d.post(f"/responses/{rid}/review", {"decision": "return", "comment": "Cite the source"}))
    assert (returned["status"], returned["review_comment"], returned["reviewed_by"]) == (
        "returned",
        "Cite the source",
        d.coordinator_id,
    )
    assert audit(d.org.id, rid)[-1] == ("response.returned", "Cite the source")
    assert outbox("iqac-accreditation.response.accepted", d.org.id) == []
    seen_by_owner = d.ok(d.get(f"/responses/{rid}", d.alice))
    assert seen_by_owner["review_comment"] == "Cite the source"
    d.ok(d.put(f"/responses/{rid}", {"value": 43}, d.alice))
    again = d.ok(d.post(f"/responses/{rid}/submit", None, d.alice))
    assert again["status"] == "submitted" and again["value"] == 43
    ok = d.ok(d.post(f"/responses/{rid}/review", {"decision": "accept", "comment": "Thanks"}))
    assert (ok["status"], ok["review_comment"]) == ("accepted", "Thanks")


def test_review_refuses_a_response_that_is_not_submitted_and_unknown_ones(desk):
    d = desk
    c = d.collecting()
    assert code(d.post(f"/responses/{c['q']['id']}/review", {"decision": "accept"})) == (409, "response_not_submitted")
    assert code(d.post(f"/responses/{c['q']['id']}/review", {"decision": "return"})) == (409, "response_not_submitted")
    assert d.post(f"/responses/{new_id()}/review", {"decision": "accept"}).status_code == 404
    assert d.post(f"/responses/{c['q']['id']}/review", {"decision": "accept"}, d.alice).status_code == 403


def test_evidence_links_and_references_are_added_listed_and_removed(desk, clock):
    d = desk
    c = d.collecting()
    rid = c["q"]["id"]
    link = d.ok(
        d.post(
            f"/responses/{rid}/evidence",
            {"title": "Annual report", "kind": "link", "url": "https://example.edu/report.pdf", "note": "p. 4"},
            d.alice,
        )
    )
    assert (link["kind"], link["url"], link["note"], link["added_by"], link["response_id"]) == (
        "link",
        "https://example.edu/report.pdf",
        "p. 4",
        d.alice_id,
        rid,
    )
    assert "reference" not in link and link["added_at"] == "2026-11-05T09:00:00+00:00"
    clock.set(clock.now + timedelta(minutes=1))
    ref = d.ok(
        d.post(
            f"/responses/{rid}/evidence",
            {
                "title": "Placement report",
                "kind": "reference",
                "reference": {"module": "placement", "entity": "report", "id": "r-9"},
            },
            d.alice,
        )
    )
    assert ref["reference"] == {"module": "placement", "entity": "report", "id": "r-9"} and "url" not in ref
    detail = d.ok(d.get(f"/responses/{rid}", d.coordinator))
    assert [e["id"] for e in detail["evidence"]] == [link["id"], ref["id"]]  # oldest first
    assert d.ok(d.delete(f"/responses/{rid}/evidence/{link['id']}", d.alice)) is None
    assert [e["id"] for e in d.ok(d.get(f"/responses/{rid}"))["evidence"]] == [ref["id"]]
    assert audit(d.org.id, link["id"]) == [
        ("evidence.added", f"response {rid}"),
        ("evidence.removed", f"response {rid}"),
    ]
    assert d.delete(f"/responses/{rid}/evidence/{link['id']}", d.alice).status_code == 404  # already gone
    assert d.delete(f"/responses/{rid}/evidence/{new_id()}", d.alice).status_code == 404


def test_evidence_must_match_its_kind(desk):
    d = desk
    c = d.collecting()
    path = f"/responses/{c['q']['id']}/evidence"
    ref = {"module": "m", "entity": "e", "id": "1"}
    for body in (
        {"title": "x", "kind": "link"},
        {"title": "x", "kind": "link", "url": "https://example.edu", "reference": ref},
        {"title": "x", "kind": "reference"},
        {"title": "x", "kind": "reference", "reference": ref, "url": "https://example.edu"},
    ):
        assert d.post(path, body, d.alice).status_code == 422, body
    for url in ("javascript:alert(1)", "ftp://example.edu/x", "example.edu", "https://", "https://a b"):
        assert d.post(path, {"title": "x", "kind": "link", "url": url}, d.alice).status_code == 422, url


def test_only_the_owner_changes_evidence_and_an_accepted_response_is_closed(desk):
    d = desk
    c = d.submitted_q()
    rid = c["q"]["id"]
    body = {"title": "Report", "kind": "link", "url": "https://example.edu/r"}
    assert d.post(f"/responses/{rid}/evidence", body, d.bob).status_code == 404
    assert d.post(f"/responses/{rid}/evidence", body, d.coordinator).status_code == 403
    evidence = d.ok(d.post(f"/responses/{rid}/evidence", body, d.alice))  # allowed while submitted
    assert d.delete(f"/responses/{rid}/evidence/{evidence['id']}", d.bob).status_code == 404
    assert d.delete(f"/responses/{rid}/evidence/{evidence['id']}", d.coordinator).status_code == 403
    d.ok(d.post(f"/responses/{rid}/review", {"decision": "accept"}))
    assert code(d.post(f"/responses/{rid}/evidence", body, d.alice)) == (409, "response_accepted")
    assert code(d.delete(f"/responses/{rid}/evidence/{evidence['id']}", d.alice)) == (409, "response_accepted")
    assert len(d.ok(d.get(f"/responses/{rid}"))["evidence"]) == 1
    assert d.post(f"/responses/{new_id()}/evidence", body, d.alice).status_code == 404
