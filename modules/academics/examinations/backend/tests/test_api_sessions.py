"""listExamSessions, scheduleExamSession, getExamSession, rescheduleExamSession, cancelExamSession."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BASE,
    DEFAULT_ENDS,
    DEFAULT_STARTS,
    FACULTY,
    HEAD,
    NOW,
    STUDENT,
    VIEWER,
    all_outbox,
    audit_entries,
    err,
    make_cycle,
    make_grading,
    make_papers,
    make_session,
    ok,
    outbox,
    session_body,
    session_for,
    set_row,
    uid,
)
from eos_examinations.infrastructure import repository as repo  # noqa: E402
from eos_examinations.infrastructure.models import (  # noqa: E402
    ExamCycleRow,
    ExamDutyRow,
    ExamPaperRow,
    ExamSessionPaperRow,
    ExamSessionRow,
)

URL = f"{BASE}/sessions"
PAPERS = f"{BASE}/papers"


@pytest.fixture
def cycle(client, h) -> dict:
    scheme = make_grading(client, h)
    ok(client.post(f"{BASE}/grading-schemes/{scheme['id']}/set-default", headers=h))
    return make_cycle(client, h)


@pytest.fixture
def papers(client, h, cycle) -> list[dict]:
    """Two draft papers of one offering (INT and END) in `cycle`."""
    return make_papers(client, h, cycle["id"])


def paper_status(client, h, paper_id) -> str:
    return ok(client.get(f"{PAPERS}/{paper_id}", headers=h))["status"]


def test_the_operations_need_their_keys(client, org, h, cycle, papers):
    _, head = org.user(HEAD)
    _, viewer = org.user(VIEWER)
    _, faculty = org.user(FACULTY)
    _, student = org.user(STUDENT)  # session:read-own only, which is not session:read
    session = make_session(client, h, cycle["id"], [papers[0]["id"]])
    assert client.get(URL).status_code == 401
    assert client.post(URL, json={}).status_code == 401
    for headers in (head, viewer, faculty):  # session:read
        assert client.get(URL, headers=headers).status_code == 200
        assert client.get(f"{URL}/{session['id']}", headers=headers).status_code == 200
    assert client.get(URL, headers=student).status_code == 403
    assert client.get(f"{URL}/{session['id']}", headers=student).status_code == 403
    for headers in (head, viewer, faculty, student):  # reading is not managing
        for r in (
            client.post(URL, json=session_body(cycle["id"], [papers[1]["id"]]), headers=headers),
            client.patch(f"{URL}/{session['id']}", json={"venue_label": "x"}, headers=headers),
            client.post(f"{URL}/{session['id']}/cancel", json={"reason": "x"}, headers=headers),
        ):
            assert r.status_code == 403
            assert r.json()["detail"]["code"] == "forbidden"
    assert ok(client.get(f"{URL}/{session['id']}", headers=h))["status"] == "scheduled"


def test_schedule_creates_a_session_and_moves_its_papers_to_scheduled(client, org, h, cycle, papers):
    ids = [p["id"] for p in papers]
    session = make_session(client, h, cycle["id"], ids, venue_label="  Hall A  ")
    assert session == {
        "id": session["id"],
        "organisation_id": org.id,
        "exam_cycle_id": cycle["id"],
        "starts_at": DEFAULT_STARTS,
        "ends_at": DEFAULT_ENDS,
        "venue_label": "Hall A",
        "status": "scheduled",
        "cancel_reason": None,
        "invigilators_required": 2,
        "invigilators_assigned": 0,
        "candidate_count": 0,
        "papers": session["papers"],
    }
    assert {p["exam_paper_id"] for p in session["papers"]} == set(ids)
    assert {p["component_code"] for p in session["papers"]} == {"INT", "END"}
    assert ok(client.get(f"{URL}/{session['id']}", headers=h)) == session
    for p in papers:
        paper = ok(client.get(f"{PAPERS}/{p['id']}", headers=h))
        assert (paper["status"], paper["exam_session_id"]) == ("scheduled", session["id"])


def test_defaults_and_instants_in_any_offset_are_kept_as_utc(client, h, cycle, papers):
    body = {
        "exam_cycle_id": cycle["id"],
        "starts_at": "2026-11-25T14:30:00+05:30",
        "ends_at": "2026-11-25T17:30:00+05:30",
        "exam_paper_ids": [papers[0]["id"]],
    }
    session = ok(client.post(URL, json=body, headers=h), 201)
    assert session["starts_at"] == "2026-11-25T09:00:00+00:00" and session["ends_at"] == "2026-11-25T12:00:00+00:00"
    assert (session["invigilators_required"], session["venue_label"]) == (1, None)  # the contract's default is 1


@pytest.mark.parametrize(
    ("change", "code", "field"),
    [
        ({"exam_cycle_id": "x"}, "invalid_id", "exam_cycle_id"),
        ({"starts_at": "2026-11-25T09:00:00"}, "invalid_datetime", "starts_at"),  # no zone
        ({"starts_at": "tomorrow"}, "invalid_datetime", "starts_at"),
        ({"ends_at": 5}, "invalid_datetime", "ends_at"),
        ({"ends_at": DEFAULT_STARTS}, "invalid_session_times", "ends_at"),  # not after the start
        ({"ends_at": "2026-11-25T08:00:00+00:00"}, "invalid_session_times", "ends_at"),
        ({"exam_paper_ids": []}, "no_papers", "papers"),
        ({"exam_paper_ids": "x"}, "invalid_body", "exam_paper_ids"),
        ({"exam_paper_ids": ["x"]}, "invalid_id", "exam_paper_ids[0]"),
        ({"invigilators_required": -1}, "below_minimum", "invigilators_required"),
        ({"invigilators_required": "2"}, "invalid_integer", "invigilators_required"),
        ({"venue_label": 5}, "invalid_text", "venue_label"),
        ({"venue_label": "v" * 201}, "text_too_long", "venue_label"),
        ({"status": "completed"}, "unknown_field", "status"),
    ],
)
def test_invalid_input_is_400_and_schedules_nothing(client, org, h, cycle, papers, change, code, field):
    body = session_body(cycle["id"], [papers[0]["id"]], **change)
    detail = err(client.post(URL, json=body, headers=h), 400, code)
    assert detail["details"]["field"] == field
    assert ok(client.get(URL, headers=h))["total"] == 0
    assert paper_status(client, h, papers[0]["id"]) == "draft"
    assert outbox("examinations.exam-session.scheduled", org.id) == []


@pytest.mark.parametrize("missing", ["exam_cycle_id", "starts_at", "ends_at", "exam_paper_ids"])
def test_a_missing_field_is_400(client, h, cycle, papers, missing):
    body = session_body(cycle["id"], [papers[0]["id"]])
    del body[missing]
    assert err(client.post(URL, json=body, headers=h), 400, "missing_field")["details"]["field"] == missing


def test_unprocessable_requests_are_422(client, org, other_org, h, cycle, papers):
    err(client.post(URL, json=session_body(uid(), [papers[0]["id"]]), headers=h), 422, "unknown_exam_cycle")
    detail = err(
        client.post(URL, json=session_body(cycle["id"], [papers[0]["id"], uid()]), headers=h), 422, "unknown_paper"
    )
    assert detail["details"]["field"] == "exam_paper_ids[1]"
    other_cycle = make_cycle(client, h)
    foreign = make_papers(client, h, other_cycle["id"], uid())[0]
    err(client.post(URL, json=session_body(cycle["id"], [foreign["id"]]), headers=h), 422, "paper_not_in_cycle")
    err(
        client.post(URL, json=session_body(cycle["id"], [papers[0]["id"], papers[0]["id"]]), headers=h),
        400,
        "duplicate_paper",
    )
    # another organisation's papers do not exist for this caller, and its cycle neither
    other_h = other_org.controller()
    theirs_g = make_grading(client, other_h)
    ok(client.post(f"{BASE}/grading-schemes/{theirs_g['id']}/set-default", headers=other_h))
    their_cycle = make_cycle(client, other_h)
    their_paper = make_papers(client, other_h, their_cycle["id"], uid())[0]
    err(client.post(URL, json=session_body(cycle["id"], [their_paper["id"]]), headers=h), 422, "unknown_paper")
    err(client.post(URL, json=session_body(their_cycle["id"], [papers[0]["id"]]), headers=h), 422, "unknown_exam_cycle")
    assert ok(client.get(URL, headers=h))["total"] == 0 and paper_status(client, h, papers[0]["id"]) == "draft"


def test_two_sessions_may_not_share_a_paper_and_a_refused_request_keeps_the_others_draft(client, org, h, cycle, papers):
    first, second = papers
    make_session(client, h, cycle["id"], [first["id"]])
    detail = err(
        client.post(URL, json=session_body(cycle["id"], [second["id"], first["id"]]), headers=h),
        409,
        "paper_already_scheduled",
    )
    assert detail["details"]["exam_paper_id"] == first["id"]
    assert paper_status(client, h, second["id"]) == "draft"  # all or nothing
    assert ok(client.get(URL, headers=h))["total"] == 1
    assert len(outbox("examinations.exam-session.scheduled", org.id)) == 1


def test_only_a_draft_paper_can_be_scheduled_and_only_in_a_configurable_cycle(client, org, h, cycle, papers):
    set_row(org.id, ExamPaperRow, papers[0]["id"], status="marks_entry")
    err(client.post(URL, json=session_body(cycle["id"], [papers[0]["id"]]), headers=h), 409, "paper_not_draft")
    set_row(org.id, ExamCycleRow, cycle["id"], status="in_progress")
    detail = err(
        client.post(URL, json=session_body(cycle["id"], [papers[1]["id"]]), headers=h), 409, "cycle_not_configurable"
    )
    assert detail["details"]["status"] == "in_progress"


def test_the_session_is_not_checked_against_the_cycle_dates_yet(client, h, cycle, papers):
    """FR-5's within-the-cycle rule needs an organisation time zone that does not exist (docs/reviewer-decisions.md): it
    is deferred, not guessed. This test records that, and fails when the rule is enforced."""
    far = {"starts_at": "2030-01-01T09:00:00+00:00", "ends_at": "2030-01-01T12:00:00+00:00"}
    assert cycle["ends_on"] == "2026-12-10"
    assert make_session(client, h, cycle["id"], [papers[0]["id"]], **far)["starts_at"].startswith("2030-01-01")


def test_overlapping_sessions_are_allowed_without_candidates(client, h, cycle, papers):
    """The student-clash rule of FR-5 needs candidates (not built); two sessions at one time have no other rule."""
    make_session(client, h, cycle["id"], [papers[0]["id"]])
    assert make_session(client, h, cycle["id"], [papers[1]["id"]])["status"] == "scheduled"


def test_a_missing_session_is_404(client, h):
    err(client.get(f"{URL}/{uid()}", headers=h), 404, "exam_session_not_found")
    err(client.patch(f"{URL}/{uid()}", json={"venue_label": "x"}, headers=h), 404, "exam_session_not_found")
    err(client.post(f"{URL}/{uid()}/cancel", json={"reason": "x"}, headers=h), 404, "exam_session_not_found")
    err(client.get(f"{URL}/not-a-uuid", headers=h), 404, "exam_session_not_found")


def test_reschedule_changes_time_and_venue_and_keeps_the_papers(client, org, h, cycle, papers):
    session = make_session(client, h, cycle["id"], [p["id"] for p in papers])
    patch = {
        "starts_at": "2026-11-26T09:00:00+00:00",
        "ends_at": "2026-11-26T11:00:00+00:00",
        "venue_label": " Hall B ",
        "reason": "clash",
    }
    moved = ok(client.patch(f"{URL}/{session['id']}", json=patch, headers=h))
    assert moved == {
        **session,
        "starts_at": "2026-11-26T09:00:00+00:00",
        "ends_at": "2026-11-26T11:00:00+00:00",
        "venue_label": "Hall B",
    }
    assert ok(client.get(f"{URL}/{session['id']}", headers=h)) == moved
    assert {paper_status(client, h, p["id"]) for p in papers} == {"scheduled"}
    cleared = ok(client.patch(f"{URL}/{session['id']}", json={"venue_label": None}, headers=h))
    assert cleared["venue_label"] is None and cleared["starts_at"] == moved["starts_at"]
    only_end = ok(client.patch(f"{URL}/{session['id']}", json={"ends_at": "2026-11-26T12:00:00+00:00"}, headers=h))
    assert only_end["ends_at"] == "2026-11-26T12:00:00+00:00"


def test_reschedule_publishes_the_event_for_time_or_venue_only(client, org, h, cycle, papers):
    session = make_session(client, h, cycle["id"], [papers[0]["id"]])
    ok(
        client.patch(
            f"{URL}/{session['id']}",
            json={"starts_at": "2026-11-26T09:00:00+00:00", "ends_at": "2026-11-26T12:00:00+00:00", "reason": "clash"},
            headers=h,
        )
    )
    ok(client.patch(f"{URL}/{session['id']}", json={"venue_label": "Hall C"}, headers=h))
    ok(client.patch(f"{URL}/{session['id']}", json={"invigilators_required": 5}, headers=h))  # not time or venue
    ok(client.patch(f"{URL}/{session['id']}", json={}, headers=h))  # nothing changes
    ok(client.patch(f"{URL}/{session['id']}", json={"venue_label": "Hall C", "invigilators_required": 5}, headers=h))
    events = outbox("examinations.exam-session.rescheduled", org.id)
    assert len(events) == 2
    first = next(e for e in events if e["reason"] == "clash")
    assert first == {
        "organisation_id": org.id,
        "exam_session_id": session["id"],
        "exam_cycle_id": cycle["id"],
        "previous_starts_at": DEFAULT_STARTS,
        "previous_ends_at": DEFAULT_ENDS,
        "starts_at": "2026-11-26T09:00:00+00:00",
        "ends_at": "2026-11-26T12:00:00+00:00",
        "venue_label": "Hall A",
        "reason": "clash",
    }
    second = next(e for e in events if e["reason"] is None)
    assert second["venue_label"] == "Hall C" and second["previous_starts_at"] == "2026-11-26T09:00:00+00:00"
    assert len(audit_entries(org.id, session["id"])) == 4  # scheduled, two moves and the invigilators change


@pytest.mark.parametrize(
    ("patch", "code"),
    [
        ({"ends_at": DEFAULT_STARTS}, "invalid_session_times"),
        ({"starts_at": "2026-11-25T13:00:00+00:00"}, "invalid_session_times"),  # after the stored end
        ({"starts_at": "2026-11-25T09:00:00"}, "invalid_datetime"),
        ({"invigilators_required": -1}, "below_minimum"),
        ({"venue_label": 5}, "invalid_text"),
        ({"reason": 5}, "invalid_text"),
        ({"reason": "r" * 501}, "text_too_long"),
        ({"exam_cycle_id": uid()}, "unknown_field"),
        ({"papers": []}, "unknown_field"),
        ({"status": "cancelled"}, "unknown_field"),
    ],
)
def test_an_invalid_reschedule_is_400_and_changes_nothing(client, org, h, cycle, papers, patch, code):
    session = make_session(client, h, cycle["id"], [papers[0]["id"]])
    err(client.patch(f"{URL}/{session['id']}", json=patch, headers=h), 400, code)
    assert ok(client.get(f"{URL}/{session['id']}", headers=h)) == session
    assert outbox("examinations.exam-session.rescheduled", org.id) == []
    assert len(audit_entries(org.id, session["id"])) == 1


def test_only_a_scheduled_session_can_be_rescheduled_or_cancelled(client, org, h, cycle, papers):
    done, _ = (make_session(client, h, cycle["id"], [p["id"]]) for p in papers)
    set_row(org.id, ExamSessionRow, done["id"], status="completed")
    for r in (
        client.patch(f"{URL}/{done['id']}", json={"venue_label": "x"}, headers=h),
        client.post(f"{URL}/{done['id']}/cancel", json={"reason": "x"}, headers=h),
    ):
        assert err(r, 409, "session_not_scheduled")["details"]["status"] == "completed"


def test_rescheduling_needs_a_draft_or_scheduled_cycle(client, org, h, cycle, papers):
    session = make_session(client, h, cycle["id"], [papers[0]["id"]])
    set_row(org.id, ExamCycleRow, cycle["id"], status="in_progress")
    detail = err(
        client.patch(f"{URL}/{session['id']}", json={"venue_label": "x"}, headers=h), 409, "cycle_not_configurable"
    )
    assert detail["details"]["status"] == "in_progress"
    assert ok(client.get(f"{URL}/{session['id']}", headers=h)) == session


@pytest.mark.parametrize("status", ["draft", "scheduled", "in_progress"])
def test_a_scheduled_session_can_be_cancelled_while_its_cycle_is_draft_scheduled_or_in_progress(
    client, org, h, cycle, papers, status
):
    ids = [p["id"] for p in papers]
    session = make_session(client, h, cycle["id"], ids)
    set_row(org.id, ExamCycleRow, cycle["id"], status=status)
    cancelled = ok(client.post(f"{URL}/{session['id']}/cancel", json={"reason": "invigilators unwell"}, headers=h))
    assert (cancelled["status"], cancelled["cancel_reason"]) == ("cancelled", "invigilators unwell")
    assert {paper_status(client, h, i) for i in ids} == {"draft"}
    (event,) = outbox("examinations.exam-session.cancelled", org.id)
    assert event["exam_session_id"] == session["id"] and event["reason"] == "invigilators unwell"
    entries = {e.action: e for e in audit_entries(org.id, session["id"])}
    assert entries["exam_session.cancelled"].reason == "invigilators unwell"


@pytest.mark.parametrize("status", ["evaluation", "results_published", "closed"])
def test_a_session_cannot_be_cancelled_once_its_cycle_is_past_in_progress(client, org, h, cycle, papers, status):
    session = make_session(client, h, cycle["id"], [papers[0]["id"]])
    set_row(org.id, ExamCycleRow, cycle["id"], status=status)
    detail = err(
        client.post(f"{URL}/{session['id']}/cancel", json={"reason": "x"}, headers=h), 409, "cycle_not_cancellable"
    )
    assert detail["details"]["status"] == status
    assert ok(client.get(f"{URL}/{session['id']}", headers=h)) == session
    assert paper_status(client, h, papers[0]["id"]) == "scheduled"
    assert outbox("examinations.exam-session.cancelled", org.id) == []


def test_cancelling_in_progress_still_needs_a_reason_and_a_scheduled_session(client, org, h, cycle, papers):
    first, second = (make_session(client, h, cycle["id"], [p["id"]]) for p in papers)
    set_row(org.id, ExamCycleRow, cycle["id"], status="in_progress")
    err(client.post(f"{URL}/{first['id']}/cancel", json={}, headers=h), 400, "missing_field")
    err(client.post(f"{URL}/{first['id']}/cancel", json={"reason": " "}, headers=h), 400, "invalid_text")
    set_row(org.id, ExamSessionRow, second["id"], status="completed")
    err(client.post(f"{URL}/{second['id']}/cancel", json={"reason": "x"}, headers=h), 409, "session_not_scheduled")
    assert ok(client.get(f"{URL}/{first['id']}", headers=h)) == first


def test_cancel_records_the_reason_returns_the_papers_to_draft_and_frees_them(client, org, h, cycle, papers):
    ids = [p["id"] for p in papers]
    session = make_session(client, h, cycle["id"], ids)
    cancelled = ok(client.post(f"{URL}/{session['id']}/cancel", json={"reason": "  flood  "}, headers=h))
    assert (cancelled["status"], cancelled["cancel_reason"]) == ("cancelled", "flood")
    assert cancelled["papers"] == []  # a paper is in at most one session, so the cancelled one keeps none
    assert ok(client.get(f"{URL}/{session['id']}", headers=h)) == cancelled
    for paper_id in ids:
        paper = ok(client.get(f"{PAPERS}/{paper_id}", headers=h))
        assert (paper["status"], paper["exam_session_id"]) == ("draft", None)
    again = make_session(client, h, cycle["id"], ids)  # the papers can be scheduled again
    assert again["id"] != session["id"] and len(again["papers"]) == 2
    err(client.post(f"{URL}/{session['id']}/cancel", json={"reason": "x"}, headers=h), 409, "session_not_scheduled")
    err(client.patch(f"{URL}/{session['id']}", json={"venue_label": "x"}, headers=h), 409, "session_not_scheduled")


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({}, "missing_field"),
        ({"reason": " "}, "invalid_text"),
        ({"reason": 5}, "invalid_text"),
        ({"reason": "r" * 501}, "text_too_long"),
        ({"reason": "x", "extra": 1}, "unknown_field"),
    ],
)
def test_cancelling_needs_a_reason_and_changes_nothing_without_one(client, org, h, cycle, papers, body, code):
    session = make_session(client, h, cycle["id"], [papers[0]["id"]])
    err(client.post(f"{URL}/{session['id']}/cancel", json=body, headers=h), 400, code)
    assert ok(client.get(f"{URL}/{session['id']}", headers=h)) == session
    assert paper_status(client, h, papers[0]["id"]) == "scheduled"
    assert outbox("examinations.exam-session.cancelled", org.id) == []


def test_scheduling_and_cancelling_publish_the_contracted_events(client, org, h, cycle, papers):
    user, headers = org.user("examinations-controller")
    ids = [p["id"] for p in papers]
    session = ok(client.post(URL, json=session_body(cycle["id"], ids), headers=headers), 201)
    scheduled = outbox("examinations.exam-session.scheduled", org.id)
    assert len(scheduled) == 1
    event = scheduled[0]
    assert {k: v for k, v in event.items() if k != "papers"} == {
        "organisation_id": org.id,
        "exam_session_id": session["id"],
        "exam_cycle_id": cycle["id"],
        "starts_at": DEFAULT_STARTS,
        "ends_at": DEFAULT_ENDS,
        "venue_label": "Hall A",
    }
    assert sorted(event["papers"], key=lambda p: p["exam_paper_id"]) == sorted(
        [{"exam_paper_id": p["id"], "course_offering_id": p["course_offering_id"]} for p in papers],
        key=lambda p: p["exam_paper_id"],
    )
    ok(client.post(f"{URL}/{session['id']}/cancel", json={"reason": "flood"}, headers=headers))
    (cancelled,) = outbox("examinations.exam-session.cancelled", org.id)
    assert {k: v for k, v in cancelled.items() if k != "exam_paper_ids"} == {
        "organisation_id": org.id,
        "exam_session_id": session["id"],
        "exam_cycle_id": cycle["id"],
        "reason": "flood",
        "cancelled_at": NOW.isoformat(),
    }
    assert sorted(cancelled["exam_paper_ids"]) == sorted(ids)
    assert sorted(all_outbox(org.id)) == [  # the cycle's own event comes from the fixture; papers publish none
        "examinations.exam-cycle.created",
        "examinations.exam-session.cancelled",
        "examinations.exam-session.scheduled",
    ]
    from eos_core.events import OutboxEvent

    with session_for(org.id) as db:
        events = (
            db.query(OutboxEvent)
            .filter(OutboxEvent.organisation_id == org.id, OutboxEvent.name.like("examinations.exam-session.%"))
            .all()
        )
        assert {e.actor for e in events} == {user} and {e.organisation_id for e in events} == {org.id}


def test_every_change_is_audited_with_the_actor_changed_fields_and_reason(client, org, h, cycle, papers):
    user, headers = org.user("examinations-controller")
    session = ok(client.post(URL, json=session_body(cycle["id"], [papers[0]["id"]]), headers=headers), 201)
    ok(client.patch(f"{URL}/{session['id']}", json={"venue_label": "Hall B", "reason": "repairs"}, headers=headers))
    ok(client.post(f"{URL}/{session['id']}/cancel", json={"reason": "flood"}, headers=headers))
    entries = {e.action: e for e in audit_entries(org.id, session["id"])}
    assert sorted(entries) == ["exam_session.cancelled", "exam_session.rescheduled", "exam_session.scheduled"]
    assert {e.actor for e in entries.values()} == {user} and {e.entity_type for e in entries.values()} == {
        "exam_session"
    }
    scheduled = entries["exam_session.scheduled"]
    assert scheduled.before is None and scheduled.after["exam_paper_ids"] == [papers[0]["id"]]
    moved = entries["exam_session.rescheduled"]
    assert (moved.before, moved.after, moved.reason) == (
        {"venue_label": "Hall A"},
        {"venue_label": "Hall B"},
        "repairs",
    )
    cancel = entries["exam_session.cancelled"]
    assert (cancel.before, cancel.reason) == ({"status": "scheduled"}, "flood")
    assert cancel.after == {"status": "cancelled", "exam_paper_ids": [papers[0]["id"]]}
    paper_actions = sorted(e.action for e in audit_entries(org.id, papers[0]["id"]))
    assert paper_actions == ["exam_paper.created", "exam_paper.returned_to_draft", "exam_paper.scheduled"]
    assert all(e.organisation_id == org.id for e in audit_entries(org.id))


def test_list_is_ordered_by_start_and_filters_and_pages(client, org, h, cycle):
    other_cycle = make_cycle(client, h)
    a_papers = make_papers(client, h, cycle["id"], uid())
    b_papers = make_papers(client, h, cycle["id"], uid(), ["END"])
    c_papers = make_papers(client, h, other_cycle["id"], uid(), ["END"])

    def at(day: str, hour: int = 9) -> dict:
        return {"starts_at": f"2026-{day}T{hour:02d}:00:00+00:00", "ends_at": f"2026-{day}T{hour + 2:02d}:00:00+00:00"}

    late = make_session(client, h, cycle["id"], [a_papers[0]["id"]], **at("12-02"))
    early = make_session(client, h, cycle["id"], [a_papers[1]["id"]], **at("11-21"))
    middle = make_session(client, h, cycle["id"], [b_papers[0]["id"]], **at("11-28"))
    elsewhere = make_session(client, h, other_cycle["id"], [c_papers[0]["id"]], **at("11-30"))
    ids = lambda r: [s["id"] for s in r["items"]]  # noqa: E731
    assert ids(ok(client.get(URL, headers=h))) == [early["id"], middle["id"], elsewhere["id"], late["id"]]
    assert ids(ok(client.get(f"{URL}?exam_cycle_id={cycle['id']}", headers=h))) == [
        early["id"],
        middle["id"],
        late["id"],
    ]
    assert ids(ok(client.get(f"{URL}?date_from=2026-11-28", headers=h))) == [middle["id"], elsewhere["id"], late["id"]]
    assert ids(ok(client.get(f"{URL}?date_to=2026-11-28", headers=h))) == [
        early["id"],
        middle["id"],
    ]  # the day is included
    assert ids(ok(client.get(f"{URL}?date_from=2026-11-22&date_to=2026-11-30", headers=h))) == [
        middle["id"],
        elsewhere["id"],
    ]
    assert ids(ok(client.get(f"{URL}?course_offering_id={a_papers[0]['course_offering_id']}", headers=h))) == [
        early["id"],
        late["id"],
    ]
    page = ok(client.get(f"{URL}?limit=2&offset=1", headers=h))
    assert page["total"] == 4 and ids(page) == [middle["id"], elsewhere["id"]]
    ok(client.post(f"{URL}/{late['id']}/cancel", json={"reason": "x"}, headers=h))
    assert ids(ok(client.get(f"{URL}?status=cancelled", headers=h))) == [late["id"]]
    assert ok(client.get(f"{URL}?status=completed", headers=h))["total"] == 0
    err(client.get(f"{URL}?status=bogus", headers=h), 400, "invalid_choice")
    err(client.get(f"{URL}?date_from=soon", headers=h), 400, "invalid_date")
    err(client.get(f"{URL}?course_offering_id=x", headers=h), 400, "invalid_id")
    err(client.get(f"{URL}?exam_cycle_id=x", headers=h), 400, "invalid_id")


def test_invigilators_assigned_counts_the_sessions_assigned_invigilation_duties(client, org, h, cycle, papers):
    session = make_session(client, h, cycle["id"], [papers[0]["id"]])
    with session_for(org.id) as db:  # the duties operations are a later slice: write the rows directly
        for status in ("assigned", "assigned", "cancelled"):
            db.add(
                ExamDutyRow(
                    organisation_id=org.id,
                    exam_cycle_id=cycle["id"],
                    staff_id=uid(),
                    duty_type="invigilation",
                    exam_session_id=session["id"],
                    status=status,
                )
            )
        db.commit()
    assert ok(client.get(f"{URL}/{session['id']}", headers=h))["invigilators_assigned"] == 2
    assert ok(client.get(URL, headers=h))["items"][0]["invigilators_assigned"] == 2


def test_each_organisation_sees_and_changes_only_its_own_sessions(client, org, other_org, h, cycle, papers):
    other_h = other_org.controller()
    g = make_grading(client, other_h)
    ok(client.post(f"{BASE}/grading-schemes/{g['id']}/set-default", headers=other_h))
    their_cycle = make_cycle(client, other_h)
    their_papers = make_papers(client, other_h, their_cycle["id"], uid())
    mine = make_session(client, h, cycle["id"], [papers[0]["id"]])
    theirs = make_session(client, other_h, their_cycle["id"], [their_papers[0]["id"]])
    assert [s["id"] for s in ok(client.get(URL, headers=h))["items"]] == [mine["id"]]
    assert [s["id"] for s in ok(client.get(URL, headers=other_h))["items"]] == [theirs["id"]]
    for r in (
        client.get(f"{URL}/{theirs['id']}", headers=h),
        client.patch(f"{URL}/{theirs['id']}", json={"venue_label": "x"}, headers=h),
        client.post(f"{URL}/{theirs['id']}/cancel", json={"reason": "x"}, headers=h),
    ):
        err(r, 404, "exam_session_not_found")
    assert ok(client.get(f"{URL}/{theirs['id']}", headers=other_h)) == theirs
    assert paper_status(client, other_h, their_papers[0]["id"]) == "scheduled"
    assert audit_entries(org.id, theirs["id"]) == []
    assert [e["exam_session_id"] for e in outbox("examinations.exam-session.scheduled", org.id)] == [mine["id"]]
    with session_for(org.id) as db:  # the links of the other organisation are not visible either
        links = db.scalars(repo.q(db, ExamSessionPaperRow))
        assert [link.exam_session_id for link in links] == [mine["id"]]
