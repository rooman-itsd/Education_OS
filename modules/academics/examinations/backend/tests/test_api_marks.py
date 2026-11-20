"""listMarks, enterMarks, submitMarks, moderateMarks, lockMarks (FR-10 to FR-12). Candidates are written straight through the
model: nothing creates them yet (registration and eligibility are a later slice), and a paper is put in `marks_entry` with
`set_row` because no operation moves it there yet."""

from pathlib import Path

import pytest
import yaml

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BASE,
    FACULTY,
    HEAD,
    STUDENT,
    VIEWER,
    all_outbox,
    audit_entries,
    err,
    make_cycle,
    make_duty,
    make_grading,
    make_papers,
    ok,
    session_for,
    set_row,
    uid,
)
from eos_examinations.application.access import MARKS_READ_DEPARTMENT, Actor  # noqa: E402
from eos_examinations.infrastructure.models import CandidateRow, ExamDutyRow, ExamPaperRow, MarkEntryRow  # noqa: E402

CONTRACT = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
)
SCHEMAS = CONTRACT["components"]["schemas"]


@pytest.fixture
def cycle(client, h) -> dict:
    scheme = make_grading(client, h)
    ok(client.post(f"{BASE}/grading-schemes/{scheme['id']}/set-default", headers=h))
    return make_cycle(client, h)


def add_candidate(org_id: str, paper: dict, status: str = "eligible", student_id: str | None = None) -> str:
    row = CandidateRow(
        organisation_id=org_id,
        exam_cycle_id=paper["exam_cycle_id"],
        exam_paper_id=paper["id"],
        course_offering_id=paper["course_offering_id"],
        student_id=student_id or uid(),
        eligibility_status=status,
        eligibility_reasons=[],
    )
    with session_for(org_id) as db:
        db.add(row)
        db.commit()
        return row.id


@pytest.fixture
def paper(client, org, h, cycle) -> dict:
    """An END paper (max 100) in `marks_entry`, with three eligible candidates (`paper["eligible"]`), one pending and one
    ineligible."""
    paper = make_papers(client, h, cycle["id"], None, ["END"])[0]
    set_row(org.id, ExamPaperRow, paper["id"], status="marks_entry")
    paper["status"] = "marks_entry"
    paper["eligible"] = [add_candidate(org.id, paper) for _ in range(3)]
    paper["pending"] = add_candidate(org.id, paper, "pending")
    paper["ineligible"] = add_candidate(org.id, paper, "ineligible")
    return paper


def evaluator(client, org, h, paper, duty="evaluation") -> dict:
    """A faculty user with a duty on the paper: their headers."""
    user_id, headers = org.user(FACULTY)
    make_duty(client, h, user_id, duty, paper_id=paper["id"])
    headers["user_id"] = user_id
    return headers


def auth(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if k != "user_id"}


URL = f"{BASE}/papers"


def marks(client, headers, paper_id):
    return ok(client.get(f"{URL}/{paper_id}/marks", headers=auth(headers)))


def enter(client, headers, paper_id, *entries):
    return client.put(f"{URL}/{paper_id}/marks", json={"entries": list(entries)}, headers=auth(headers))


def moderate(client, headers, paper_id, **body):
    return client.post(f"{URL}/{paper_id}/moderation", json=body, headers=auth(headers))


def row_of(listing: dict, candidate_id: str) -> dict:
    return next(i for i in listing["items"] if i["candidate_id"] == candidate_id)


def paper_status(org, paper_id: str) -> str:
    with session_for(org.id) as db:
        return db.get(ExamPaperRow, paper_id).status


def complete(client, headers, paper):
    first, second, third = paper["eligible"]
    ok(
        enter(
            client,
            headers,
            paper["id"],
            {"candidate_id": first, "marks_obtained": 70},
            {"candidate_id": second, "marks_obtained": 40.5},
            {"candidate_id": third, "absent": True},
        )
    )


# ---------------------------------------------------------------- listMarks


def test_listing_shows_one_row_per_eligible_candidate_and_unmarked_ones_have_nothing(client, org, h, paper):
    listing = marks(client, h, paper["id"])
    assert listing["exam_paper_id"] == paper["id"] and listing["max_marks"] == 100.0
    assert listing["paper_status"] == "marks_entry" and listing["total"] == 3
    assert {i["candidate_id"] for i in listing["items"]} == set(paper["eligible"])  # not the pending or ineligible
    for item in listing["items"]:
        assert item["id"] is None and item["status"] is None and item["marks_obtained"] is None
        assert item["absent"] is False and item["final_marks"] is None and item["student_id"]


def test_a_paper_without_eligible_candidates_lists_nothing(client, org, h, cycle):
    other = make_papers(client, h, cycle["id"], None, ["END"])[0]
    assert marks(client, h, other["id"]) == {
        "exam_paper_id": other["id"],
        "max_marks": 100.0,
        "paper_status": "draft",
        "items": [],
        "total": 0,
    }


def test_the_listing_needs_a_key_and_a_scope(client, org, other_org, h, paper):
    assert client.get(f"{URL}/{paper['id']}/marks").status_code == 401
    for role in (STUDENT, VIEWER):  # no marks key at all
        _, headers = org.user(role)
        assert client.get(f"{URL}/{paper['id']}/marks", headers=headers).status_code == 403
    _, no_duty = org.user(FACULTY)  # read-assigned, but no duty on this paper
    assert err(client.get(f"{URL}/{paper['id']}/marks", headers=no_duty), 403, "forbidden")
    _, head = org.user(HEAD)  # read-assigned and read-department: the department grants nothing, the duty is missing
    assert client.get(f"{URL}/{paper['id']}/marks", headers=head).status_code == 403
    assert err(client.get(f"{URL}/{uid()}/marks", headers=h), 404, "exam_paper_not_found")
    assert client.get(f"{URL}/{paper['id']}/marks", headers=other_org.controller()).status_code == 404


def test_an_evaluator_or_a_moderator_reads_their_paper_but_a_cancelled_duty_no_longer_counts(client, org, h, paper):
    for duty in ("evaluation", "moderation"):
        headers = evaluator(client, org, h, paper, duty)
        assert marks(client, headers, paper["id"])["total"] == 3
    headers = evaluator(client, org, h, paper)
    with session_for(org.id) as db:
        duty = db.query(ExamDutyRow).filter_by(staff_id=headers["user_id"], exam_paper_id=paper["id"]).one()
        duty.status = "cancelled"
        db.commit()
    assert client.get(f"{URL}/{paper['id']}/marks", headers=auth(headers)).status_code == 403


def test_a_department_key_alone_grants_nothing(org, client, paper):
    """The caller's department is unknown (Q13): a `read-department` key is no scope on its own."""
    from eos_examinations.application import marks as mks

    actor = Actor(user_id=uid(), organisation_id=org.id, permissions={MARKS_READ_DEPARTMENT})
    with session_for(org.id) as db:
        db.info["organisation_id"] = org.id
        with pytest.raises(Exception) as raised:
            mks.list_marks(db, actor, paper["id"])
    assert getattr(raised.value, "status", None) == 403


# ---------------------------------------------------------------- enterMarks


def test_an_evaluator_enters_marks_and_absences_and_the_listing_follows(client, org, h, paper):
    headers = evaluator(client, org, h, paper)
    first, second, third = paper["eligible"]
    body = ok(
        enter(
            client,
            headers,
            paper["id"],
            {"candidate_id": first, "marks_obtained": 70},
            {"candidate_id": third, "absent": True},
        )
    )
    assert body["exam_paper_id"] == paper["id"] and len(body["items"]) == 3
    one, gone, unmarked = row_of(body, first), row_of(body, third), row_of(body, second)
    assert one["marks_obtained"] == 70.0 and one["final_marks"] == 70.0 and one["status"] == "entered"
    assert one["entered_by"] == headers["user_id"] and one["entered_at"] and one["id"]
    assert gone["absent"] is True and gone["marks_obtained"] is None and gone["final_marks"] is None
    assert unmarked["id"] is None and unmarked["status"] is None
    assert marks(client, headers, paper["id"])["items"] == body["items"]


def test_entering_again_overwrites_and_an_unchanged_entry_writes_nothing(client, org, h, paper):
    headers = evaluator(client, org, h, paper)
    first = paper["eligible"][0]
    created = row_of(ok(enter(client, headers, paper["id"], {"candidate_id": first, "marks_obtained": 70})), first)
    entry_audits = len([a for a in audit_entries(org.id) if a.action == "mark_entry.entered"])
    same = row_of(ok(enter(client, headers, paper["id"], {"candidate_id": first, "marks_obtained": 70.0})), first)
    assert same == created  # nothing changed: the same row, the same time, no new audit entry
    assert len([a for a in audit_entries(org.id) if a.action == "mark_entry.entered"]) == entry_audits
    changed = row_of(ok(enter(client, headers, paper["id"], {"candidate_id": first, "absent": True})), first)
    assert changed["id"] == created["id"] and changed["absent"] is True and changed["marks_obtained"] is None
    again = row_of(ok(enter(client, headers, paper["id"], {"candidate_id": first, "marks_obtained": 55.25})), first)
    assert again["id"] == created["id"] and again["marks_obtained"] == 55.25 and again["absent"] is False
    entry = audit_entries(org.id, created["id"])
    assert [a.action for a in entry] == ["mark_entry.entered"] * 3  # the clock is frozen, so the order is not asserted
    assert {"marks_obtained": "70", "absent": False} in [a.before for a in entry]
    assert any(
        a.before == {"marks_obtained": "70", "absent": False} and a.after == {"marks_obtained": None, "absent": True}
        for a in entry
    )


def test_entering_is_all_or_none(client, org, h, paper):
    headers = evaluator(client, org, h, paper)
    first, second, _ = paper["eligible"]
    response = enter(
        client,
        headers,
        paper["id"],
        {"candidate_id": first, "marks_obtained": 70},
        {"candidate_id": second, "marks_obtained": 101},
    )
    assert err(response, 422, "marks_out_of_range")
    assert marks(client, headers, paper["id"])["items"][0]["id"] is None
    with session_for(org.id) as db:
        assert db.query(MarkEntryRow).count() == 0 or all(
            r.candidate_id not in paper["eligible"] for r in db.query(MarkEntryRow).all()
        )


@pytest.mark.parametrize(
    ("entry", "status", "code"),
    [
        ({"marks_obtained": 100.5}, 422, "marks_out_of_range"),
        ({"marks_obtained": -1}, 422, "marks_out_of_range"),
        ({"marks_obtained": 10.123}, 400, "too_many_decimals"),
        ({"marks_obtained": "ten"}, 400, "invalid_number"),
        ({"marks_obtained": 10, "absent": True}, 400, "marks_with_absent"),
        ({}, 400, "marks_required"),
        ({"absent": "yes"}, 400, "invalid_boolean"),
        ({"marks_obtained": 10, "extra": 1}, 400, "unknown_field"),
    ],
)
def test_malformed_and_out_of_range_entries_are_refused(client, org, h, paper, entry, status, code):
    headers = evaluator(client, org, h, paper)
    response = enter(client, headers, paper["id"], {"candidate_id": paper["eligible"][0], **entry})
    assert err(response, status, code)
    assert marks(client, headers, paper["id"])["items"][0]["id"] is None


def test_a_full_mark_and_zero_are_valid_and_the_request_shape_is_checked(client, org, h, paper):
    headers = evaluator(client, org, h, paper)
    first, second, _ = paper["eligible"]
    body = ok(
        enter(
            client,
            headers,
            paper["id"],
            {"candidate_id": first, "marks_obtained": 100},
            {"candidate_id": second, "marks_obtained": 0},
        )
    )
    assert row_of(body, first)["marks_obtained"] == 100.0 and row_of(body, second)["marks_obtained"] == 0.0
    for bad in ({}, {"entries": []}, {"entries": "x"}, {"entries": [1]}, {"entries": [{"marks_obtained": 1}]}):
        assert client.put(f"{URL}/{paper['id']}/marks", json=bad, headers=auth(headers)).status_code == 400
    twice = enter(
        client,
        headers,
        paper["id"],
        {"candidate_id": first, "marks_obtained": 1},
        {"candidate_id": first, "absent": True},
    )
    assert err(twice, 400, "duplicate_candidate")
    assert (
        client.put(f"{URL}/{paper['id']}/marks", json={"entries": [], "x": 1}, headers=auth(headers)).status_code == 400
    )


def test_only_eligible_candidates_of_the_paper_can_have_marks(client, org, h, cycle, paper):
    headers = evaluator(client, org, h, paper)
    other = make_papers(client, h, cycle["id"], None, ["END"])[0]
    elsewhere = add_candidate(org.id, other)
    for candidate, code in (
        (paper["pending"], "candidate_not_eligible"),
        (paper["ineligible"], "candidate_not_eligible"),
        (elsewhere, "candidate_not_on_paper"),
        (uid(), "candidate_not_on_paper"),
    ):
        assert err(enter(client, headers, paper["id"], {"candidate_id": candidate, "marks_obtained": 1}), 422, code)


def test_entering_needs_marks_entry_and_the_right_scope(client, org, other_org, h, paper):
    headers = evaluator(client, org, h, paper)
    entry = {"candidate_id": paper["eligible"][0], "marks_obtained": 10}
    assert client.put(f"{URL}/{paper['id']}/marks", json={"entries": [entry]}).status_code == 401
    assert enter(client, other_org.controller(), paper["id"], entry).status_code == 404
    moderator = evaluator(client, org, h, paper, "moderation")  # a moderation duty is not an evaluation duty
    assert err(enter(client, moderator, paper["id"], entry), 403, "forbidden")
    _, no_duty = org.user(FACULTY)
    assert enter(client, no_duty, paper["id"], entry).status_code == 403
    for key_less in (STUDENT, VIEWER, HEAD):
        _, nothing = org.user(key_less)
        assert enter(client, nothing, paper["id"], entry).status_code == 403
    # `marks:enter-all` needs no duty
    assert ok(enter(client, h, paper["id"], entry))["items"]
    for status in ("draft", "scheduled", "moderation", "locked"):
        set_row(org.id, ExamPaperRow, paper["id"], status=status)
        assert err(enter(client, headers, paper["id"], entry), 409, "paper_not_in_marks_entry")


def test_entering_is_audited_and_publishes_no_event(client, org, h, paper):
    headers = evaluator(client, org, h, paper)
    before = len(all_outbox(org.id))
    listing = ok(enter(client, headers, paper["id"], {"candidate_id": paper["eligible"][0], "marks_obtained": 33}))
    entry = row_of(listing, paper["eligible"][0])
    [audit] = audit_entries(org.id, entry["id"])
    assert (audit.action, audit.entity_type, audit.actor) == ("mark_entry.entered", "mark_entry", headers["user_id"])
    assert audit.before is None and audit.after == {"marks_obtained": "33", "absent": False}
    assert len(all_outbox(org.id)) == before  # the contract declares no marks event


# ---------------------------------------------------------------- submitMarks


def test_submit_needs_every_eligible_candidate_to_have_marks_or_an_absence(client, org, h, paper):
    headers = evaluator(client, org, h, paper)
    ok(enter(client, headers, paper["id"], {"candidate_id": paper["eligible"][0], "marks_obtained": 10}))
    response = client.post(f"{URL}/{paper['id']}/marks/submit", headers=auth(headers))
    assert err(response, 409, "marks_incomplete")
    assert paper_status(org, paper["id"]) == "marks_entry"


def test_submit_moves_the_paper_to_moderation_once_and_is_audited(client, org, h, paper):
    headers = evaluator(client, org, h, paper)
    complete(client, headers, paper)
    body = ok(client.post(f"{URL}/{paper['id']}/marks/submit", headers=auth(headers)))
    assert body["id"] == paper["id"] and body["status"] == "moderation"
    assert paper_status(org, paper["id"]) == "moderation"
    actions = [a.action for a in audit_entries(org.id, paper["id"])]
    assert actions[-1] == "exam_paper.marks_submitted"
    assert err(client.post(f"{URL}/{paper['id']}/marks/submit", headers=auth(headers)), 409, "paper_not_in_marks_entry")
    assert err(
        enter(client, headers, paper["id"], {"candidate_id": paper["eligible"][0], "absent": True}),
        409,
        "paper_not_in_marks_entry",
    )


def test_submit_needs_the_scope_and_a_paper_in_marks_entry(client, org, h, paper):
    _, no_duty = org.user(FACULTY)
    assert client.post(f"{URL}/{paper['id']}/marks/submit", headers=no_duty).status_code == 403
    assert client.post(f"{URL}/{paper['id']}/marks/submit").status_code == 401
    assert client.post(f"{URL}/{uid()}/marks/submit", headers=h).status_code == 404
    set_row(org.id, ExamPaperRow, paper["id"], status="scheduled")
    assert err(client.post(f"{URL}/{paper['id']}/marks/submit", headers=h), 409, "paper_not_in_marks_entry")


def test_a_paper_without_eligible_candidates_can_be_submitted(client, org, h, cycle):
    empty = make_papers(client, h, cycle["id"], None, ["END"])[0]
    set_row(org.id, ExamPaperRow, empty["id"], status="marks_entry")
    assert ok(client.post(f"{URL}/{empty['id']}/marks/submit", headers=h))["status"] == "moderation"


# ---------------------------------------------------------------- moderateMarks


@pytest.fixture
def moderated_paper(client, org, h, paper):
    """The paper after entry and submission: in `moderation`, one 70, one 40.5, one absent."""
    headers = evaluator(client, org, h, paper)
    complete(client, headers, paper)
    ok(client.post(f"{URL}/{paper['id']}/marks/submit", headers=auth(headers)))
    paper["status"] = "moderation"
    return paper


def test_a_moderator_adjusts_uniformly_and_the_original_marks_are_kept(client, org, h, moderated_paper):
    paper = moderated_paper
    first, second, third = paper["eligible"]
    moderator = evaluator(client, org, h, paper, "moderation")
    body = ok(moderate(client, moderator, paper["id"], reason="paper was harder", uniform_delta=5))
    one, two, gone = row_of(body, first), row_of(body, second), row_of(body, third)
    assert (one["marks_obtained"], one["moderation_delta"], one["final_marks"]) == (70.0, 5.0, 75.0)
    assert (two["marks_obtained"], two["moderation_delta"], two["final_marks"]) == (40.5, 5.0, 45.5)
    assert one["moderation_reason"] == "paper was harder" and one["moderated_by"] == moderator["user_id"]
    assert one["status"] == "moderated" and two["status"] == "moderated"
    assert gone["absent"] is True and gone["moderation_delta"] is None and gone["status"] == "entered"
    audit = [a for a in audit_entries(org.id, one["id"]) if a.action == "mark_entry.moderated"]
    assert len(audit) == 1 and audit[0].reason == "paper was harder"
    assert audit[0].after == {"moderation_delta": "5", "status": "moderated"}


def test_per_candidate_adjustments_replace_an_earlier_moderation(client, org, h, moderated_paper):
    paper = moderated_paper
    first, second, _ = paper["eligible"]
    moderator = evaluator(client, org, h, paper, "moderation")
    ok(moderate(client, moderator, paper["id"], reason="uniform", uniform_delta=5))
    body = ok(
        moderate(
            client,
            moderator,
            paper["id"],
            reason="one script",
            adjustments=[{"candidate_id": first, "delta": -10}],
        )
    )
    one, two = row_of(body, first), row_of(body, second)
    assert (one["moderation_delta"], one["final_marks"], one["moderation_reason"]) == (-10.0, 60.0, "one script")
    assert (two["moderation_delta"], two["moderation_reason"]) == (5.0, "uniform")  # not mentioned, so untouched


def test_moderation_stays_within_zero_and_the_maximum_and_is_all_or_none(client, org, h, moderated_paper):
    paper = moderated_paper
    first, second, _ = paper["eligible"]
    moderator = evaluator(client, org, h, paper, "moderation")
    assert err(
        moderate(client, moderator, paper["id"], reason="r", uniform_delta=40), 422, "moderated_marks_out_of_range"
    )
    assert err(
        moderate(client, moderator, paper["id"], reason="r", uniform_delta=-41), 422, "moderated_marks_out_of_range"
    )
    too_far = [{"candidate_id": first, "delta": 5}, {"candidate_id": second, "delta": 60}]
    assert err(
        moderate(client, moderator, paper["id"], reason="r", adjustments=too_far), 422, "moderated_marks_out_of_range"
    )
    for item in marks(client, moderator, paper["id"])["items"]:
        assert item["moderation_delta"] is None and item["status"] == "entered"  # none of it was applied
    ok(moderate(client, moderator, paper["id"], reason="edge", uniform_delta=30))  # 70 + 30 = 100 is allowed


def test_moderation_requests_are_checked(client, org, h, moderated_paper):
    paper = moderated_paper
    first = paper["eligible"][0]
    moderator = evaluator(client, org, h, paper, "moderation")
    adjustment = [{"candidate_id": first, "delta": 1}]
    cases = [
        ({"uniform_delta": 1}, "invalid_text"),  # no reason is the contract's 400 (required)
        ({"reason": "r"}, "moderation_kind"),
        ({"reason": "r", "uniform_delta": 1, "adjustments": adjustment}, "moderation_kind"),
        ({"reason": "  ", "uniform_delta": 1}, "invalid_text"),
        ({"reason": "r" * 501, "uniform_delta": 1}, "text_too_long"),
        ({"reason": "r", "uniform_delta": 1.234}, "too_many_decimals"),
        ({"reason": "r", "adjustments": []}, "invalid_adjustments"),
        ({"reason": "r", "adjustments": [{"candidate_id": first}]}, "invalid_adjustments"),
        ({"reason": "r", "adjustments": adjustment * 2}, "duplicate_candidate"),
    ]
    for body, code in cases:
        response = client.post(f"{URL}/{paper['id']}/moderation", json=body, headers=auth(moderator))
        assert response.status_code == 400, (body, response.text)
        assert response.json()["detail"]["code"] in (code, "missing_field"), body
    assert (
        client.post(
            f"{URL}/{paper['id']}/moderation", json={"reason": "r", "x": 1}, headers=auth(moderator)
        ).status_code
        == 400
    )


def test_only_marked_eligible_candidates_of_the_paper_can_be_adjusted(client, org, h, moderated_paper):
    paper = moderated_paper
    moderator = evaluator(client, org, h, paper, "moderation")
    absent = paper["eligible"][2]
    for candidate, code in (
        (absent, "no_marks_to_moderate"),
        (paper["pending"], "candidate_not_eligible"),
        (uid(), "candidate_not_eligible"),
    ):
        response = moderate(
            client, moderator, paper["id"], reason="r", adjustments=[{"candidate_id": candidate, "delta": 1}]
        )
        assert err(response, 422, code)


def test_moderation_needs_the_moderator_key_a_moderation_duty_and_a_paper_in_moderation(
    client, org, h, moderated_paper
):
    paper = moderated_paper
    body = {"reason": "r", "uniform_delta": 1}
    assert client.post(f"{URL}/{paper['id']}/moderation", json=body).status_code == 401
    assert (
        client.post(f"{URL}/{uid()}/moderation", json=body, headers=h).status_code == 403
    )  # the controller holds no moderate key
    _, no_duty = org.user(FACULTY)
    assert client.post(f"{URL}/{paper['id']}/moderation", json=body, headers=no_duty).status_code == 403
    evaluator_only = evaluator(client, org, h, paper, "evaluation")
    assert err(moderate(client, evaluator_only, paper["id"], **body), 403, "forbidden")
    _, head_no_duty = org.user(HEAD)  # the department grants nothing (Q13): a duty is still needed
    assert client.post(f"{URL}/{paper['id']}/moderation", json=body, headers=head_no_duty).status_code == 403
    head_id, head = org.user(HEAD)
    make_duty(client, h, head_id, "moderation", paper_id=paper["id"])
    assert ok(client.post(f"{URL}/{paper['id']}/moderation", json=body, headers=head))["items"]
    moderator = evaluator(client, org, h, paper, "moderation")
    assert moderate(client, moderator, uid(), **body).status_code == 404
    set_row(org.id, ExamPaperRow, paper["id"], status="marks_entry")
    assert err(moderate(client, moderator, paper["id"], **body), 409, "paper_not_in_moderation")


# ---------------------------------------------------------------- lockMarks


def test_the_controller_locks_a_moderated_paper_and_everything_stops_changing(client, org, h, moderated_paper):
    paper = moderated_paper
    moderator = evaluator(client, org, h, paper, "moderation")
    ok(moderate(client, moderator, paper["id"], reason="r", uniform_delta=2))
    body = ok(client.post(f"{URL}/{paper['id']}/lock", headers=h))
    assert body["id"] == paper["id"] and body["status"] == "locked"
    listing = marks(client, h, paper["id"])
    assert listing["paper_status"] == "locked" and {i["status"] for i in listing["items"]} == {"locked"}
    assert row_of(listing, paper["eligible"][0])["final_marks"] == 72.0
    audit = [a for a in audit_entries(org.id, paper["id"]) if a.action == "exam_paper.marks_locked"]
    assert len(audit) == 1 and audit[0].after == {"status": "locked", "entries_locked": 3}
    assert err(moderate(client, moderator, paper["id"], reason="r", uniform_delta=1), 409, "paper_not_in_moderation")
    assert err(
        enter(client, h, paper["id"], {"candidate_id": paper["eligible"][0], "absent": True}),
        409,
        "paper_not_in_marks_entry",
    )
    assert err(client.post(f"{URL}/{paper['id']}/lock", headers=h), 409, "paper_not_in_moderation")


def test_locking_needs_the_lock_key_a_paper_in_moderation_and_complete_marks(client, org, h, moderated_paper):
    paper = moderated_paper
    _, faculty = org.user(FACULTY)
    assert client.post(f"{URL}/{paper['id']}/lock", headers=faculty).status_code == 403
    assert client.post(f"{URL}/{paper['id']}/lock").status_code == 401
    assert client.post(f"{URL}/{uid()}/lock", headers=h).status_code == 404
    add_candidate(org.id, paper)  # became eligible after the marks were submitted: nothing for them yet
    assert err(client.post(f"{URL}/{paper['id']}/lock", headers=h), 409, "marks_incomplete")
    assert paper_status(org, paper["id"]) == "moderation"
    set_row(org.id, ExamPaperRow, paper["id"], status="marks_entry")
    assert err(client.post(f"{URL}/{paper['id']}/lock", headers=h), 409, "paper_not_in_moderation")


def test_the_marks_of_one_organisation_are_invisible_to_another(client, org, other_org, h, paper):
    headers = evaluator(client, org, h, paper)
    entry = {"candidate_id": paper["eligible"][0], "marks_obtained": 10}
    ok(enter(client, headers, paper["id"], entry))
    foreign = other_org.controller()
    for response in (
        client.get(f"{URL}/{paper['id']}/marks", headers=foreign),
        enter(client, foreign, paper["id"], entry),
        client.post(f"{URL}/{paper['id']}/marks/submit", headers=foreign),
        client.post(f"{URL}/{paper['id']}/lock", headers=foreign),
    ):
        assert response.status_code == 404


# ---------------------------------------------------------------- the contract's shapes


def _check_entry(item: dict) -> None:
    schema = SCHEMAS["MarkEntry"]
    assert set(schema["required"]) <= set(item) <= set(schema["properties"])
    assert set(item) == set(schema["properties"])  # every field is served, null when it has no value
    for name, value in item.items():
        types = schema["properties"][name].get("type")
        if isinstance(types, list) and value is not None:
            assert isinstance(value, (str if "string" in types else float, int, bool)), name


def test_the_bodies_have_exactly_the_contracts_fields(client, org, h, paper):
    headers = evaluator(client, org, h, paper)
    listing = marks(client, headers, paper["id"])
    properties = CONTRACT["paths"]["/papers/{exam_paper_id}/marks"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert set(listing) == set(properties["required"]) == set(properties["properties"])
    complete(client, headers, paper)
    entered = marks(client, headers, paper["id"])
    for item in [*listing["items"], *entered["items"]]:
        _check_entry(item)
    put = ok(enter(client, headers, paper["id"], {"candidate_id": paper["eligible"][0], "marks_obtained": 1}))
    assert set(put) == {"exam_paper_id", "items"}
    paper_schema = SCHEMAS["ExamPaper"]
    submitted = ok(client.post(f"{URL}/{paper['id']}/marks/submit", headers=auth(headers)))
    assert set(paper_schema["required"]) <= set(submitted) <= set(paper_schema["properties"])
