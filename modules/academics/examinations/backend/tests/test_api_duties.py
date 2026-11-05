"""listExamDuties, assignExamDuty, cancelExamDuty, listMyDuties."""

from datetime import UTC, datetime

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BASE,
    CONTROLLER,
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
    make_session_for_duties,
    ok,
    outbox,
    session_for,
    set_row,
    uid,
)
from eos_core.config import permissions_for  # noqa: E402
from eos_examinations.infrastructure import repository as repo  # noqa: E402
from eos_examinations.infrastructure.models import (  # noqa: E402
    ExamCycleRow,
    ExamDutyRow,
    ExamPaperRow,
    ExamSessionRow,
    OfferingRef,
)

URL = f"{BASE}/duties"
ME = f"{BASE}/me/duties"


def at(day: str, start: int, end: int) -> dict:
    return {"starts_at": f"2026-11-{day}T{start:02d}:00:00+00:00", "ends_at": f"2026-11-{day}T{end:02d}:00:00+00:00"}


def new_session(client, h, cycle_id: str, start: int, end: int, day: str = "26") -> dict:
    """A scheduled session of a fresh offering's paper, on 2026-11-<day> from `start` to `end` o'clock UTC."""
    paper = make_papers(client, h, cycle_id, uid(), ["END"])[0]
    return make_session(client, h, cycle_id, [paper["id"]], **at(day, start, end))


@pytest.fixture
def world(client, h):
    return make_session_for_duties(client, h)  # cycle, session, a draft paper


def invigilation(client, h, staff, session_id):
    return client.post(
        URL, json={"staff_id": staff, "duty_type": "invigilation", "exam_session_id": session_id}, headers=h
    )


def evaluation(client, h, staff, paper_id, kind="evaluation"):
    return client.post(URL, json={"staff_id": staff, "duty_type": kind, "exam_paper_id": paper_id}, headers=h)


# ------------------------------------------------------------------------------------------------- permissions

ROUTES = [
    ("GET", "/duties", {"examinations:duty:read-department", "examinations:duty:read-all"}),
    ("POST", "/duties", {"examinations:duty:assign"}),
    ("POST", "/duties/{id}/cancel", {"examinations:duty:assign"}),
    ("GET", "/me/duties", {"examinations:duty:read-own"}),
]


@pytest.mark.parametrize(("method", "path", "keys"), ROUTES)
def test_no_token_is_401(client, method, path, keys):
    assert (
        client.request(method, BASE + path.replace("{id}", uid()), json={} if method == "POST" else None).status_code
        == 401
    )


@pytest.mark.parametrize(("method", "path", "keys"), ROUTES, ids=[f"{m} {p}" for m, p, _ in ROUTES])
@pytest.mark.parametrize("role", [CONTROLLER, HEAD, FACULTY, VIEWER, STUDENT])
def test_a_role_is_refused_exactly_when_it_holds_none_of_the_routes_keys(client, org, method, path, keys, role):
    _, headers = org.user(role)
    response = client.request(
        method, BASE + path.replace("{id}", uid()), json={} if method == "POST" else None, headers=headers
    )
    if keys & permissions_for([role]):
        assert response.status_code != 403, (role, method, path, response.text)
    else:
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "forbidden"


def test_the_role_grants_this_slice_relies_on():
    assert {k for k in permissions_for([CONTROLLER]) if ":duty:" in k} == {
        "examinations:duty:read-all",
        "examinations:duty:read-department",
        "examinations:duty:assign",
    }
    assert {k for k in permissions_for([HEAD]) if ":duty:" in k} == {"examinations:duty:read-department"}
    assert {k for k in permissions_for([FACULTY]) if ":duty:" in k} == {"examinations:duty:read-own"}
    assert not [k for k in permissions_for([STUDENT, VIEWER]) if ":duty:" in k]


def test_a_denied_write_changes_nothing(client, org, h, world):
    cycle, session, paper = world
    _, faculty = org.user(FACULTY)
    before = (len(audit_entries(org.id)), len(all_outbox(org.id)))
    assert invigilation(client, faculty, uid(), session["id"]).status_code == 403
    assert client.post(f"{URL}/{uid()}/cancel", json={"reason": "x"}, headers=faculty).status_code == 403
    assert ok(client.get(URL, headers=h))["total"] == 0
    assert (len(audit_entries(org.id)), len(all_outbox(org.id))) == before


# ------------------------------------------------------------------------------------------------- assign: the request


def test_assign_an_invigilation_duty_returns_it_and_it_can_be_listed(client, org, h, world):
    cycle, session, paper = world
    staff = uid()
    created = invigilation(client, h, staff, session["id"])
    assert created.status_code == 201
    duty = created.json()
    assert duty == {
        "id": duty["id"],
        "organisation_id": org.id,
        "exam_cycle_id": cycle["id"],
        "staff_id": staff,
        "duty_type": "invigilation",
        "exam_session_id": session["id"],
        "exam_paper_id": None,
        "status": "assigned",
        "cancel_reason": None,
        "starts_at": session["starts_at"],
        "ends_at": session["ends_at"],
        "venue_label": "Hall A",
        "course_code": None,
    }
    assert ok(client.get(URL, headers=h)) == {"items": [duty], "total": 1}


@pytest.mark.parametrize("kind", ["evaluation", "moderation"])
def test_assign_a_paper_duty_has_null_session_fields(client, org, h, world, kind):
    cycle, session, paper = world
    duty = ok(evaluation(client, h, uid(), paper["id"], kind), 201)
    assert (duty["duty_type"], duty["exam_paper_id"], duty["exam_session_id"]) == (kind, paper["id"], None)
    assert (duty["starts_at"], duty["ends_at"], duty["venue_label"], duty["course_code"]) == (None, None, None, None)
    assert duty["exam_cycle_id"] == cycle["id"]


def test_a_paper_duty_serves_the_course_code_only_from_the_offering_read_model(client, org, h, world):
    cycle, session, paper = world
    first = ok(evaluation(client, h, uid(), paper["id"]), 201)
    assert first["course_code"] is None  # the read model has no row: nothing is made up
    with session_for(org.id) as db:
        db.add(
            OfferingRef(
                organisation_id=org.id,
                course_offering_id=paper["course_offering_id"],
                course_id=uid(),
                academic_period_id=uid(),
                course_code="SPS101",
                course_title="Sports Physiology",
                credits=4,
                department_id=uid(),
            )
        )
        db.commit()
    second = ok(evaluation(client, h, uid(), paper["id"]), 201)
    assert second["course_code"] == "SPS101"
    assert ok(client.get(f"{URL}?exam_paper_id={paper['id']}", headers=h))["total"] == 2


@pytest.mark.parametrize(
    ("body", "code", "field"),
    [
        ({}, "missing_field", "staff_id"),
        ({"staff_id": "x", "duty_type": "invigilation"}, "invalid_id", "staff_id"),
        ({"staff_id": "{staff}"}, "missing_field", "duty_type"),
        ({"staff_id": "{staff}", "duty_type": "usher", "exam_session_id": "{session}"}, "invalid_choice", "duty_type"),
        ({"staff_id": "{staff}", "duty_type": "invigilation", "exam_session_id": "x"}, "invalid_id", "exam_session_id"),
        (
            {"staff_id": "{staff}", "duty_type": "invigilation", "exam_session_id": None},
            "invalid_id",
            "exam_session_id",
        ),
        ({"staff_id": "{staff}", "duty_type": "evaluation", "exam_paper_id": "x"}, "invalid_id", "exam_paper_id"),
        ({"staff_id": "{staff}", "duty_type": "invigilation"}, "invigilation_needs_session", "exam_session_id"),
        (
            {"staff_id": "{staff}", "duty_type": "invigilation", "exam_paper_id": "{paper}"},
            "invigilation_needs_session",
            "exam_session_id",
        ),
        (
            {
                "staff_id": "{staff}",
                "duty_type": "invigilation",
                "exam_session_id": "{session}",
                "exam_paper_id": "{paper}",
            },
            "invigilation_needs_session",
            "exam_session_id",
        ),
        ({"staff_id": "{staff}", "duty_type": "evaluation"}, "paper_duty_needs_paper", "exam_paper_id"),
        (
            {"staff_id": "{staff}", "duty_type": "moderation", "exam_session_id": "{session}"},
            "paper_duty_needs_paper",
            "exam_paper_id",
        ),
        (
            {
                "staff_id": "{staff}",
                "duty_type": "evaluation",
                "exam_session_id": "{session}",
                "exam_paper_id": "{paper}",
            },
            "paper_duty_needs_paper",
            "exam_paper_id",
        ),
        (
            {"staff_id": "{staff}", "duty_type": "evaluation", "exam_paper_id": "{paper}", "status": "completed"},
            "unknown_field",
            "status",
        ),
        (
            {"staff_id": "{staff}", "duty_type": "evaluation", "exam_paper_id": "{paper}", "exam_cycle_id": "{staff}"},
            "unknown_field",
            "exam_cycle_id",
        ),
    ],
)
def test_a_malformed_request_is_400_and_assigns_nothing(client, org, h, world, body, code, field):
    cycle, session, paper = world
    fill = {"staff": uid(), "session": session["id"], "paper": paper["id"]}
    body = {k: fill.get(v.strip("{}"), v) if isinstance(v, str) and v.startswith("{") else v for k, v in body.items()}
    detail = err(client.post(URL, json=body, headers=h), 400, code)
    assert detail["details"]["field"] == field
    assert ok(client.get(URL, headers=h))["total"] == 0
    assert all_outbox(org.id).count("examinations.duty.assigned") == 0


def test_an_unknown_or_foreign_session_or_paper_is_422(client, org, other_org, h, world):
    cycle, session, paper = world
    detail = err(invigilation(client, h, uid(), uid()), 422, "unknown_session")
    assert detail["details"]["field"] == "exam_session_id"
    err(evaluation(client, h, uid(), uid()), 422, "unknown_paper")
    other_h = other_org.controller()
    scheme = make_grading(client, other_h)
    ok(client.post(f"{BASE}/grading-schemes/{scheme['id']}/set-default", headers=other_h))
    their_cycle = make_cycle(client, other_h)
    their_paper = make_papers(client, other_h, their_cycle["id"], uid())[0]
    their_session = make_session(client, other_h, their_cycle["id"], [their_paper["id"]])
    err(invigilation(client, h, uid(), their_session["id"]), 422, "unknown_session")
    err(evaluation(client, h, uid(), their_paper["id"]), 422, "unknown_paper")
    assert ok(client.get(URL, headers=h))["total"] == 0 and ok(client.get(URL, headers=other_h))["total"] == 0


# ------------------------------------------------------------------------------------------------- assign: the rules


@pytest.mark.parametrize("status", ["draft", "scheduled", "in_progress", "evaluation"])
def test_duties_can_be_assigned_through_the_evaluation_status(client, org, h, world, status):
    cycle, session, paper = world
    set_row(org.id, ExamCycleRow, cycle["id"], status=status)
    assert invigilation(client, h, uid(), session["id"]).status_code == 201
    assert evaluation(client, h, uid(), paper["id"]).status_code == 201


@pytest.mark.parametrize("status", ["results_published", "closed"])
def test_duties_cannot_be_assigned_once_results_are_published_or_the_cycle_is_closed(client, org, h, world, status):
    cycle, session, paper = world
    set_row(org.id, ExamCycleRow, cycle["id"], status=status)
    for response in (invigilation(client, h, uid(), session["id"]), evaluation(client, h, uid(), paper["id"])):
        assert err(response, 409, "cycle_not_open_for_duties")["details"]["status"] == status
    assert ok(client.get(URL, headers=h))["total"] == 0


def test_a_cancelled_or_completed_session_takes_no_duty(client, org, h, world):
    cycle, session, paper = world
    done = new_session(client, h, cycle["id"], 9, 11, day="27")
    set_row(org.id, ExamSessionRow, done["id"], status="completed")
    ok(client.post(f"{BASE}/sessions/{session['id']}/cancel", json={"reason": "flood"}, headers=h))
    assert (
        err(invigilation(client, h, uid(), session["id"]), 409, "session_not_scheduled")["details"]["status"]
        == "cancelled"
    )
    assert (
        err(invigilation(client, h, uid(), done["id"]), 409, "session_not_scheduled")["details"]["status"]
        == "completed"
    )
    assert ok(client.get(URL, headers=h))["total"] == 0


@pytest.mark.parametrize("pipeline", ["draft", "scheduled", "marks_entry", "moderation", "locked"])
def test_evaluation_and_moderation_ignore_the_papers_pipeline_status(client, org, h, world, pipeline):
    cycle, session, paper = world
    set_row(org.id, ExamPaperRow, paper["id"], status=pipeline)
    assert evaluation(client, h, uid(), paper["id"]).status_code == 201
    assert evaluation(client, h, uid(), paper["id"], "moderation").status_code == 201


def test_more_invigilators_than_required_may_be_assigned(client, org, h, world):
    cycle, session, paper = world
    assert session["invigilators_required"] == 2
    for _ in range(4):
        ok(invigilation(client, h, uid(), session["id"]), 201)
    shown = ok(client.get(f"{BASE}/sessions/{session['id']}", headers=h))
    assert (shown["invigilators_required"], shown["invigilators_assigned"]) == (2, 4)


def test_the_same_staff_type_and_target_twice_is_409_but_each_variation_is_allowed(client, org, h, world):
    cycle, session, paper = world
    staff = uid()
    first = ok(invigilation(client, h, staff, session["id"]), 201)
    detail = err(invigilation(client, h, staff, session["id"]), 409, "duty_exists")
    assert detail["details"]["exam_duty_id"] == first["id"] and detail["details"]["status"] == "assigned"
    ok(invigilation(client, h, uid(), session["id"]), 201)  # another staff member, same session
    ok(evaluation(client, h, staff, paper["id"]), 201)
    err(evaluation(client, h, staff, paper["id"]), 409, "duty_exists")
    ok(evaluation(client, h, staff, paper["id"], "moderation"), 201)  # another type, same paper
    err(evaluation(client, h, staff, paper["id"], "moderation"), 409, "duty_exists")
    ok(evaluation(client, h, uid(), paper["id"]), 201)  # another staff member, same paper
    assert ok(client.get(f"{URL}?staff_id={staff}", headers=h))["total"] == 3


def test_a_cancelled_duty_can_be_assigned_again_and_a_completed_one_cannot(client, org, h, world):
    cycle, session, paper = world
    staff = uid()
    first = ok(invigilation(client, h, staff, session["id"]), 201)
    ok(client.post(f"{URL}/{first['id']}/cancel", json={"reason": "unwell"}, headers=h))
    second = ok(invigilation(client, h, staff, session["id"]), 201)  # the target is free again
    assert second["id"] != first["id"]
    err(invigilation(client, h, staff, session["id"]), 409, "duty_exists")
    set_row(org.id, ExamDutyRow, second["id"], status="completed")
    detail = err(invigilation(client, h, staff, session["id"]), 409, "duty_exists")
    assert detail["details"]["status"] == "completed"
    statuses = sorted(d["status"] for d in ok(client.get(f"{URL}?staff_id={staff}", headers=h))["items"])
    assert statuses == ["cancelled", "completed"]


def test_the_database_refuses_a_duplicate_the_application_check_missed(client, org, h, world, monkeypatch):
    """Two requests racing past the application check: the partial unique index of ex_0003 turns the loser into 409."""
    cycle, session, paper = world
    staff = uid()
    ok(invigilation(client, h, staff, session["id"]), 201)
    ok(evaluation(client, h, staff, paper["id"]), 201)
    monkeypatch.setattr(repo, "live_duplicate_duty", lambda *a, **k: None)  # as if both saw no duty yet
    entries, events = len(audit_entries(org.id)), len(all_outbox(org.id))
    err(invigilation(client, h, staff, session["id"]), 409, "duty_exists")
    err(evaluation(client, h, staff, paper["id"]), 409, "duty_exists")
    assert ok(client.get(f"{URL}?staff_id={staff}", headers=h))["total"] == 2  # the losers left no row
    assert (len(audit_entries(org.id)), len(all_outbox(org.id))) == (entries, events)  # nor audit entry or event


def test_the_unique_indexes_cover_live_duties_only_and_one_organisation_at_a_time(client, org, other_org, h, world):
    from sqlalchemy.exc import IntegrityError

    cycle, session, paper = world
    staff = uid()
    ok(invigilation(client, h, staff, session["id"]), 201)

    def row(org_id, status):
        return ExamDutyRow(
            organisation_id=org_id,
            exam_cycle_id=cycle["id"],
            staff_id=staff,
            duty_type="invigilation",
            exam_session_id=session["id"],
            status=status,
        )

    with session_for(org.id) as db:
        db.add_all([row(org.id, "cancelled"), row(org.id, "cancelled")])
        db.commit()  # cancelled duties repeat freely
    for live in ("assigned", "completed"):
        with session_for(org.id) as db:
            db.add(row(org.id, live))
            with pytest.raises(IntegrityError) as caught:
                db.commit()
            assert repo.violates(caught.value, "duty_on_session")
    with session_for(other_org.id) as db:
        db.add(row(other_org.id, "assigned"))  # another organisation has its own space (SQLite does not enforce the FK)
        db.commit()


def test_overlapping_invigilation_is_409_and_back_to_back_is_allowed(client, org, h, world):
    cycle, _, _ = world
    staff = uid()
    morning = new_session(client, h, cycle["id"], 9, 12)
    overlapping = new_session(client, h, cycle["id"], 11, 14)
    back_to_back = new_session(client, h, cycle["id"], 12, 15)
    inside = new_session(client, h, cycle["id"], 10, 11)
    ok(invigilation(client, h, staff, morning["id"]), 201)
    for clash in (overlapping, inside):
        detail = err(invigilation(client, h, staff, clash["id"]), 409, "invigilation_overlap")
        assert detail["details"]["exam_session_id"] == morning["id"]
    ok(invigilation(client, h, staff, back_to_back["id"]), 201)  # [9,12) and [12,15) only touch
    ok(invigilation(client, h, uid(), overlapping["id"]), 201)  # another staff member is free
    assert ok(client.get(f"{URL}?staff_id={staff}", headers=h))["total"] == 2


def test_an_evaluation_duty_is_not_an_invigilation_clash(client, org, h, world):
    cycle, session, paper = world
    staff = uid()
    ok(invigilation(client, h, staff, session["id"]), 201)
    ok(evaluation(client, h, staff, paper["id"]), 201)


def test_a_cancelled_duty_or_a_cancelled_session_does_not_block_a_new_assignment(client, org, h, world):
    cycle, _, _ = world
    staff = uid()
    first = new_session(client, h, cycle["id"], 9, 12, day="28")
    clash = new_session(client, h, cycle["id"], 10, 13, day="28")
    third = new_session(client, h, cycle["id"], 11, 14, day="28")
    duty = ok(invigilation(client, h, staff, first["id"]), 201)
    err(invigilation(client, h, staff, clash["id"]), 409, "invigilation_overlap")
    ok(client.post(f"{URL}/{duty['id']}/cancel", json={"reason": "swapped"}, headers=h))
    other = ok(invigilation(client, h, staff, clash["id"]), 201)  # the cancelled duty no longer holds the time
    # now the session itself is cancelled: its duty is left `assigned`, but no longer blocks
    ok(client.post(f"{BASE}/sessions/{clash['id']}/cancel", json={"reason": "flood"}, headers=h))
    assert (
        ok(client.get(f"{URL}?exam_session_id={clash['id']}", headers=h))["items"][0]["status"] == "assigned"
    )  # no cascade
    assert other["status"] == "assigned"
    ok(invigilation(client, h, staff, third["id"]), 201)


def test_cancelling_a_session_leaves_its_duties_assigned(client, org, h, world):
    cycle, session, paper = world
    duty = ok(invigilation(client, h, uid(), session["id"]), 201)
    ok(client.post(f"{BASE}/sessions/{session['id']}/cancel", json={"reason": "flood"}, headers=h))
    shown = ok(client.get(f"{URL}?exam_session_id={session['id']}", headers=h))["items"]
    assert [(d["id"], d["status"], d["cancel_reason"]) for d in shown] == [(duty["id"], "assigned", None)]
    assert "examinations.duty.cancelled" not in all_outbox(org.id)


# ------------------------------------------------------------------------------------------------- cancel


def test_cancel_records_the_reason_and_keeps_the_rest_of_the_duty(client, org, h, world):
    cycle, session, paper = world
    duty = ok(invigilation(client, h, uid(), session["id"]), 201)
    cancelled = ok(client.post(f"{URL}/{duty['id']}/cancel", json={"reason": "  unwell  "}, headers=h))
    assert cancelled == {**duty, "status": "cancelled", "cancel_reason": "unwell"}
    assert ok(client.get(f"{URL}?status=cancelled", headers=h))["items"] == [cancelled]
    err(client.post(f"{URL}/{duty['id']}/cancel", json={"reason": "again"}, headers=h), 409, "duty_not_assigned")


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({}, "missing_field"),
        ({"reason": ""}, "invalid_text"),
        ({"reason": "   "}, "invalid_text"),
        ({"reason": 5}, "invalid_text"),
        ({"reason": "r" * 501}, "text_too_long"),
        ({"reason": "x", "status": "completed"}, "unknown_field"),
    ],
)
def test_cancelling_needs_a_reason_and_changes_nothing_without_one(client, org, h, world, body, code):
    cycle, session, paper = world
    duty = ok(invigilation(client, h, uid(), session["id"]), 201)
    err(client.post(f"{URL}/{duty['id']}/cancel", json=body, headers=h), 400, code)
    assert ok(client.get(f"{URL}?status=assigned", headers=h))["items"] == [duty]
    assert outbox("examinations.duty.cancelled", org.id) == []


@pytest.mark.parametrize("status", ["draft", "in_progress", "evaluation", "results_published", "closed"])
def test_a_duty_can_be_cancelled_in_any_cycle_status(client, org, h, world, status):
    cycle, session, paper = world
    duty = ok(evaluation(client, h, uid(), paper["id"]), 201)
    set_row(org.id, ExamCycleRow, cycle["id"], status=status)
    assert ok(client.post(f"{URL}/{duty['id']}/cancel", json={"reason": "x"}, headers=h))["status"] == "cancelled"


def test_a_missing_or_foreign_duty_is_404(client, org, other_org, h, world):
    cycle, session, paper = world
    other_h = other_org.controller()
    scheme = make_grading(client, other_h)
    ok(client.post(f"{BASE}/grading-schemes/{scheme['id']}/set-default", headers=other_h))
    their_cycle = make_cycle(client, other_h)
    their_paper = make_papers(client, other_h, their_cycle["id"], uid())[0]
    theirs = ok(evaluation(client, other_h, uid(), their_paper["id"]), 201)
    for duty_id in (uid(), "not-a-uuid", theirs["id"]):
        err(client.post(f"{URL}/{duty_id}/cancel", json={"reason": "x"}, headers=h), 404, "exam_duty_not_found")
    assert ok(client.get(f"{URL}?staff_id={theirs['staff_id']}", headers=other_h))["items"][0]["status"] == "assigned"
    assert audit_entries(org.id, theirs["id"]) == []


# ------------------------------------------------------------------------------------------------- listExamDuties


def test_a_holder_of_read_all_sees_every_duty_of_the_organisation_only(client, org, other_org, h, world):
    cycle, session, paper = world
    mine = [ok(invigilation(client, h, uid(), session["id"]), 201), ok(evaluation(client, h, uid(), paper["id"]), 201)]
    other_h = other_org.controller()
    scheme = make_grading(client, other_h)
    ok(client.post(f"{BASE}/grading-schemes/{scheme['id']}/set-default", headers=other_h))
    their_paper = make_papers(client, other_h, make_cycle(client, other_h)["id"], uid())[0]
    theirs = ok(evaluation(client, other_h, uid(), their_paper["id"]), 201)
    shown = ok(client.get(URL, headers=h))
    assert shown["total"] == 2 and {d["id"] for d in shown["items"]} == {d["id"] for d in mine}
    assert [d["id"] for d in ok(client.get(URL, headers=other_h))["items"]] == [theirs["id"]]
    assert ok(client.get(f"{URL}?staff_id={theirs['staff_id']}", headers=h)) == {"items": [], "total": 0}


def test_a_department_head_alone_gets_an_empty_list_not_a_403(client, org, h, world):
    cycle, session, paper = world
    ok(invigilation(client, h, uid(), session["id"]), 201)
    _, head = org.user(HEAD)
    assert client.get(URL, headers=head).status_code == 200
    assert ok(client.get(URL, headers=head)) == {"items": [], "total": 0}
    assert ok(client.get(f"{URL}?exam_cycle_id={cycle['id']}&limit=5&offset=2", headers=head)) == {
        "items": [],
        "total": 0,
    }
    err(client.get(f"{URL}?status=bogus", headers=head), 400, "invalid_choice")  # filters are still checked
    assert ok(client.get(URL, headers=h))["total"] == 1  # the same duty is there for read-all


def test_list_filters_pages_and_orders_newest_first(client, org, h, world):
    cycle, session, paper = world
    other_cycle = make_cycle(client, h)
    other_session = new_session(client, h, other_cycle["id"], 9, 11)
    other_paper = make_papers(client, h, other_cycle["id"], uid(), ["END"])[0]
    staff = uid()
    a = ok(invigilation(client, h, staff, session["id"]), 201)
    b = ok(evaluation(client, h, staff, paper["id"]), 201)
    c = ok(invigilation(client, h, uid(), other_session["id"]), 201)
    d = ok(evaluation(client, h, uid(), other_paper["id"], "moderation"), 201)
    ok(client.post(f"{URL}/{b['id']}/cancel", json={"reason": "x"}, headers=h))

    def ids(query: str) -> list[str]:
        return sorted(x["id"] for x in ok(client.get(f"{URL}?{query}", headers=h))["items"])

    assert ids("") == sorted([a["id"], b["id"], c["id"], d["id"]])
    assert ids(f"exam_cycle_id={cycle['id']}") == sorted([a["id"], b["id"]])
    assert ids(f"staff_id={staff}") == sorted([a["id"], b["id"]])
    assert ids("duty_type=invigilation") == sorted([a["id"], c["id"]])
    assert ids("duty_type=moderation") == [d["id"]]
    assert ids(f"exam_session_id={session['id']}") == [a["id"]]
    assert ids(f"exam_paper_id={paper['id']}") == [b["id"]]
    assert ids("status=cancelled") == [b["id"]]
    assert ids("status=assigned&duty_type=evaluation") == []
    assert ids(f"staff_id={staff}&status=assigned") == [a["id"]]
    page = ok(client.get(f"{URL}?limit=3&offset=0", headers=h))
    rest = ok(client.get(f"{URL}?limit=3&offset=3", headers=h))
    assert page["total"] == rest["total"] == 4 and len(page["items"]) == 3 and len(rest["items"]) == 1
    assert sorted(x["id"] for x in page["items"] + rest["items"]) == ids("")
    for query, code in (
        ("status=bogus", "invalid_choice"),
        ("duty_type=usher", "invalid_choice"),
        ("staff_id=x", "invalid_id"),
        ("exam_cycle_id=x", "invalid_id"),
        ("exam_session_id=x", "invalid_id"),
        ("exam_paper_id=x", "invalid_id"),
    ):
        err(client.get(f"{URL}?{query}", headers=h), 400, code)
    assert client.get(f"{URL}?limit=0", headers=h).status_code == 422  # the shared Limit query bound


# ------------------------------------------------------------------------------------------------- listMyDuties


def test_my_duties_default_to_upcoming_assigned_duties_only(client, org, h, world):
    cycle, session, paper = world
    me, mine = org.user(FACULTY)
    past = new_session(client, h, cycle["id"], 9, 11, day="24")
    cancelled_session = new_session(client, h, cycle["id"], 9, 11, day="29")
    later = new_session(client, h, cycle["id"], 14, 16, day="27")
    set_row(
        org.id,
        ExamSessionRow,
        past["id"],
        starts_at=datetime(2026, 11, 1, 9, tzinfo=UTC),
        ends_at=datetime(2026, 11, 1, 11, tzinfo=UTC),
    )
    d_later = ok(invigilation(client, h, me, later["id"]), 201)
    d_soon = ok(invigilation(client, h, me, session["id"]), 201)
    d_past = ok(invigilation(client, h, me, past["id"]), 201)
    d_cancelled_session = ok(invigilation(client, h, me, cancelled_session["id"]), 201)
    ok(client.post(f"{BASE}/sessions/{cancelled_session['id']}/cancel", json={"reason": "flood"}, headers=h))
    d_eval = ok(evaluation(client, h, me, paper["id"]), 201)  # no date
    d_mod = ok(evaluation(client, h, me, paper["id"], "moderation"), 201)
    d_cancelled = ok(invigilation(client, h, me, new_session(client, h, cycle["id"], 9, 11, day="30")["id"]), 201)
    ok(client.post(f"{URL}/{d_cancelled['id']}/cancel", json={"reason": "x"}, headers=h))
    ok(invigilation(client, h, uid(), session["id"]), 201)  # someone else's duty
    upcoming = ok(client.get(ME, headers=mine))["items"]
    # dated duties by session start, then the undated ones in the order they were assigned
    assert [d["id"] for d in upcoming] == [d_soon["id"], d_later["id"], d_eval["id"], d_mod["id"]]
    assert all(d["status"] == "assigned" and d["staff_id"] == me for d in upcoming)
    assert set(ok(client.get(f"{ME}?include_past=false", headers=mine))["items"][i]["id"] for i in range(4)) == {
        d["id"] for d in upcoming
    }
    everything = ok(client.get(f"{ME}?include_past=true", headers=mine))["items"]
    assert [d["id"] for d in everything] == [
        d_past["id"],
        d_soon["id"],
        d_later["id"],
        d_cancelled_session["id"],
        d_eval["id"],
        d_mod["id"],
    ]
    assert d_cancelled["id"] not in {d["id"] for d in everything}  # a cancelled duty is never listed
    assert all(d["status"] == "assigned" for d in everything)


def test_my_duties_has_no_total_and_an_empty_one_is_an_empty_list(client, org, h, world):
    _, mine = org.user(FACULTY)
    assert ok(client.get(ME, headers=mine)) == {"items": []}
    assert ok(client.get(f"{ME}?include_past=true", headers=mine)) == {"items": []}


@pytest.mark.parametrize("value", ["yes", "1", "TRUE", "", "True"])
def test_a_bad_include_past_is_400(client, org, value):
    _, mine = org.user(FACULTY)
    err(client.get(f"{ME}?include_past={value}", headers=mine), 400, "invalid_boolean")


def test_my_duties_are_the_callers_own_and_stay_inside_their_organisation(client, org, other_org, h, world):
    cycle, session, paper = world
    me, mine = org.user(FACULTY)
    ok(invigilation(client, h, me, session["id"]), 201)
    other_h = other_org.controller()
    scheme = make_grading(client, other_h)
    ok(client.post(f"{BASE}/grading-schemes/{scheme['id']}/set-default", headers=other_h))
    their_paper = make_papers(client, other_h, make_cycle(client, other_h)["id"], uid())[0]
    ok(evaluation(client, other_h, me, their_paper["id"]), 201)  # the same user id in another organisation
    assert len(ok(client.get(ME, headers=mine))["items"]) == 1
    _, theirs = other_org.user(FACULTY, user_id=me)
    assert [d["exam_paper_id"] for d in ok(client.get(ME, headers=theirs))["items"]] == [their_paper["id"]]
    _, stranger = org.user(FACULTY)
    assert ok(client.get(ME, headers=stranger)) == {"items": []}


def test_a_controller_without_read_own_cannot_use_my_duties(client, org, h):
    assert client.get(ME, headers=h).status_code == 403  # holds read-all, not read-own: the grants are unchanged


# ------------------------------------------------------------------------------------------------- audit and events


def test_assigning_audits_the_change_and_publishes_the_contracted_event(client, org, world):
    cycle, session, paper = world
    user, headers = org.user(CONTROLLER)
    staff = uid()
    invigilation_duty = ok(invigilation(client, headers, staff, session["id"]), 201)
    evaluation_duty = ok(evaluation(client, headers, staff, paper["id"]), 201)
    entry = audit_entries(org.id, invigilation_duty["id"])[0]
    assert (entry.action, entry.entity_type, entry.actor, entry.organisation_id) == (
        "exam_duty.assigned",
        "exam_duty",
        user,
        org.id,
    )
    assert entry.before is None and entry.reason is None
    assert entry.after == {
        "exam_cycle_id": cycle["id"],
        "staff_id": staff,
        "duty_type": "invigilation",
        "exam_session_id": session["id"],
        "exam_paper_id": None,
    }
    by_duty = {e["exam_duty_id"]: e for e in outbox("examinations.duty.assigned", org.id)}
    assert by_duty[invigilation_duty["id"]] == {
        "organisation_id": org.id,
        "exam_duty_id": invigilation_duty["id"],
        "exam_cycle_id": cycle["id"],
        "staff_id": staff,
        "duty_type": "invigilation",
        "exam_session_id": session["id"],
        "exam_paper_id": None,
        "starts_at": session["starts_at"],
    }
    assert by_duty[evaluation_duty["id"]]["starts_at"] is None
    assert by_duty[evaluation_duty["id"]]["exam_paper_id"] == paper["id"]
    from eos_core.events import OutboxEvent

    with session_for(org.id) as db:
        events = (
            db.query(OutboxEvent)
            .filter(OutboxEvent.organisation_id == org.id, OutboxEvent.name == "examinations.duty.assigned")
            .all()
        )
        assert len(events) == 2 and {e.actor for e in events} == {user}


def test_cancelling_audits_the_change_with_the_reason_and_publishes_the_contracted_event(client, org, world):
    cycle, session, paper = world
    user, headers = org.user(CONTROLLER)
    staff = uid()
    duty = ok(invigilation(client, headers, staff, session["id"]), 201)
    ok(client.post(f"{URL}/{duty['id']}/cancel", json={"reason": "  unwell  "}, headers=headers))
    entries = {e.action: e for e in audit_entries(org.id, duty["id"])}
    assert sorted(entries) == ["exam_duty.assigned", "exam_duty.cancelled"]
    cancelled = entries["exam_duty.cancelled"]
    assert (cancelled.before, cancelled.after, cancelled.reason, cancelled.actor) == (
        {"status": "assigned"},
        {"status": "cancelled"},
        "unwell",
        user,
    )
    assert outbox("examinations.duty.cancelled", org.id) == [
        {
            "organisation_id": org.id,
            "exam_duty_id": duty["id"],
            "exam_cycle_id": cycle["id"],
            "staff_id": staff,
            "duty_type": "invigilation",
            "reason": "unwell",
            "cancelled_at": NOW.isoformat(),
        }
    ]


def test_only_the_two_duty_events_are_published_and_only_by_successful_changes(client, org, h, world):
    cycle, session, paper = world
    before = all_outbox(org.id)
    duty = ok(invigilation(client, h, uid(), session["id"]), 201)
    err(invigilation(client, h, duty["staff_id"], session["id"]), 409, "duty_exists")  # refused: nothing published
    client.get(URL, headers=h)
    client.get(f"{URL}?staff_id={duty['staff_id']}", headers=h)
    err(client.post(f"{URL}/{uid()}/cancel", json={"reason": "x"}, headers=h), 404, "exam_duty_not_found")
    ok(client.post(f"{URL}/{duty['id']}/cancel", json={"reason": "x"}, headers=h))
    new = all_outbox(org.id)[len(before) :]
    assert sorted(new) == ["examinations.duty.assigned", "examinations.duty.cancelled"]
    assert len(audit_entries(org.id, duty["id"])) == 2  # reads and refusals wrote nothing


# ------------------------------------------------------------------------------------------------- final review


def test_my_duties_order_is_total_when_session_starts_are_equal(client, org, h, world):
    """Cancelled sessions free the staff member's time, so one staff member can hold assigned duties on sessions that
    start together (all visible with include_past): by start, then end, then the order assigned."""
    cycle, _, _ = world
    me, mine = org.user(FACULTY)
    short_first = new_session(client, h, cycle["id"], 9, 11, day="26")
    long_ = new_session(client, h, cycle["id"], 9, 13, day="26")
    short_second = new_session(client, h, cycle["id"], 9, 11, day="26")
    short_third = new_session(client, h, cycle["id"], 9, 11, day="26")
    d1 = ok(invigilation(client, h, me, short_first["id"]), 201)
    ok(client.post(f"{BASE}/sessions/{short_first['id']}/cancel", json={"reason": "x"}, headers=h))
    d2 = ok(invigilation(client, h, me, long_["id"]), 201)  # the first is cancelled, so this does not clash
    ok(client.post(f"{BASE}/sessions/{long_['id']}/cancel", json={"reason": "x"}, headers=h))
    d3 = ok(invigilation(client, h, me, short_second["id"]), 201)
    ok(client.post(f"{BASE}/sessions/{short_second['id']}/cancel", json={"reason": "x"}, headers=h))
    d4 = ok(invigilation(client, h, me, short_third["id"]), 201)
    expected = [d1["id"], d3["id"], d4["id"], d2["id"]]  # three 9-11 sessions in the order assigned, then the 9-13 one
    for _ in range(5):  # the same answer every time
        shown = ok(client.get(f"{ME}?include_past=true", headers=mine))["items"]
        assert [d["id"] for d in shown] == expected
    assert [d["id"] for d in ok(client.get(ME, headers=mine))["items"]] == [
        d4["id"]
    ]  # only the live session is upcoming


def test_undated_duties_keep_the_order_they_were_assigned(client, org, h, world):
    cycle, session, paper = world
    me, mine = org.user(FACULTY)
    papers = make_papers(client, h, cycle["id"], uid(), ["INT", "END"])
    made = [ok(evaluation(client, h, me, p["id"], kind), 201) for p in papers for kind in ("evaluation", "moderation")]
    for _ in range(3):
        assert [d["id"] for d in ok(client.get(ME, headers=mine))["items"]] == [d["id"] for d in made]


def test_course_code_is_read_only_from_the_callers_organisation(client, org, other_org, h, world):
    cycle, session, paper = world
    with session_for(other_org.id) as db:  # another organisation's row for the very same offering id
        db.add(
            OfferingRef(
                organisation_id=other_org.id,
                course_offering_id=paper["course_offering_id"],
                course_id=uid(),
                academic_period_id=uid(),
                course_code="OTHER-ORG",
                course_title="Not yours",
                credits=3,
                department_id=uid(),
            )
        )
        db.commit()
    duty = ok(evaluation(client, h, uid(), paper["id"]), 201)
    assert duty["course_code"] is None
    assert ok(client.get(f"{URL}?exam_paper_id={paper['id']}", headers=h))["items"][0]["course_code"] is None
    _, mine = org.user(FACULTY, user_id=duty["staff_id"])
    assert ok(client.get(ME, headers=mine))["items"][0]["course_code"] is None
    with session_for(org.id) as db:
        db.add(
            OfferingRef(
                organisation_id=org.id,
                course_offering_id=paper["course_offering_id"],
                course_id=uid(),
                academic_period_id=uid(),
                course_code="MINE",
                course_title="Yours",
                credits=3,
                department_id=uid(),
            )
        )
        db.commit()
    assert ok(client.get(f"{URL}?exam_paper_id={paper['id']}", headers=h))["items"][0]["course_code"] == "MINE"


def _count_statements(fn) -> int:
    from eos_core.db import engine
    from sqlalchemy import event

    seen: list[str] = []

    def record(conn, cursor, statement, *args):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", record)
    return len(seen)


def test_listing_duties_issues_a_constant_number_of_queries(client, org, h, world):
    """The session, paper and course-code lookups are one query each however many duties there are (no N+1)."""
    cycle, session, paper = world
    me, mine = org.user(FACULTY)
    scheme_papers = []
    for _ in range(12):
        offering = uid()
        scheme_papers.append(make_papers(client, h, cycle["id"], offering, ["END"])[0])
        with session_for(org.id) as db:
            db.add(
                OfferingRef(
                    organisation_id=org.id,
                    course_offering_id=offering,
                    course_id=uid(),
                    academic_period_id=uid(),
                    course_code=f"C{len(scheme_papers)}",
                    course_title="t",
                    credits=3,
                    department_id=uid(),
                )
            )
            db.commit()
    ok(invigilation(client, h, me, session["id"]), 201)
    ok(evaluation(client, h, me, scheme_papers[0]["id"]), 201)
    one_each = (
        _count_statements(lambda: ok(client.get(URL, headers=h))),
        _count_statements(lambda: ok(client.get(ME, headers=mine))),
    )
    for p in scheme_papers[1:]:
        ok(evaluation(client, h, me, p["id"]), 201)
    many = (
        _count_statements(lambda: ok(client.get(URL, headers=h))),
        _count_statements(lambda: ok(client.get(ME, headers=mine))),
    )
    assert many == one_each  # twelve paper duties cost no more statements than one
    shown = ok(client.get(URL, headers=h))["items"]
    assert len(shown) == 13 and sum(1 for d in shown if d["course_code"]) == 12
