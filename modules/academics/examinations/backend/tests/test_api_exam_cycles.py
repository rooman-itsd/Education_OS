"""listExamCycles, createExamCycle, getExamCycle, updateExamCycle, changeExamCycleStatus."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BASE,
    FACULTY,
    HEAD,
    NOW,
    STUDENT,
    VIEWER,
    all_outbox,
    audit_entries,
    cycle_body,
    err,
    make_cycle,
    make_grading,
    ok,
    outbox,
    session_for,
    uid,
)
from eos_examinations.infrastructure.models import ExamCycleRow  # noqa: E402

URL = f"{BASE}/exam-cycles"
GRADING = f"{BASE}/grading-schemes"


@pytest.fixture
def scheme(client, h) -> dict:
    """A grading scheme that is the organisation default."""
    s = make_grading(client, h)
    ok(client.post(f"{GRADING}/{s['id']}/set-default", headers=h))
    return s


def move(client, headers, cycle_id, status):
    return client.post(f"{URL}/{cycle_id}/status", json={"status": status}, headers=headers)


def advance(client, headers, cycle_id, *statuses):
    for status in statuses:
        ok(move(client, headers, cycle_id, status))


def test_the_operations_need_their_keys(client, org, scheme):
    _, head = org.user(HEAD)
    _, viewer = org.user(VIEWER)
    _, faculty = org.user(FACULTY)
    _, student = org.user(STUDENT)
    cycle = make_cycle(client, org.controller())
    assert client.get(URL).status_code == 401
    assert client.post(URL, json=cycle_body()).status_code == 401
    for headers in (head, viewer, faculty):  # exam-cycle:read
        assert client.get(URL, headers=headers).status_code == 200
        assert client.get(f"{URL}/{cycle['id']}", headers=headers).status_code == 200
    assert client.get(URL, headers=student).status_code == 403
    for headers in (head, viewer, faculty, student):  # reading is not managing
        responses = (
            client.post(URL, json=cycle_body(), headers=headers),
            client.patch(f"{URL}/{cycle['id']}", json={"name": "x"}, headers=headers),
            move(client, headers, cycle["id"], "scheduled"),
        )
        for r in responses:
            assert r.status_code == 403
            assert r.json()["detail"]["code"] == "forbidden"
    assert ok(client.get(f"{URL}/{cycle['id']}", headers=org.controller()))["status"] == "draft"


def test_create_uses_the_named_scheme_and_returns_a_draft_cycle(client, org, h, scheme):
    other = make_grading(client, h, "named")
    body = cycle_body(
        grading_scheme_id=other["id"],
        eligibility_cutoff_date="2026-11-10",
        min_attendance_percent=75.5,
        check_dues=True,
    )
    created = ok(client.post(URL, json=body, headers=h), 201)
    assert created == {
        "id": created["id"],
        "organisation_id": org.id,
        "academic_period_id": body["academic_period_id"],
        "code": "2026-ODD-END",
        "name": "Odd semester end term",
        "cycle_type": "end_term",
        "starts_on": "2026-11-20",
        "ends_on": "2026-12-10",
        "grading_scheme_id": other["id"],
        "eligibility_cutoff_date": "2026-11-10",
        "min_attendance_percent": 75.5,
        "check_dues": True,
        "status": "draft",
    }
    assert ok(client.get(f"{URL}/{created['id']}", headers=h)) == created


def test_create_without_a_scheme_uses_the_organisation_default_and_defaults_the_options(client, h, scheme):
    created = make_cycle(client, h)
    assert created["grading_scheme_id"] == scheme["id"]
    assert (created["check_dues"], created["min_attendance_percent"], created["eligibility_cutoff_date"]) == (
        False,
        None,
        None,
    )


def test_create_with_no_scheme_and_no_default_is_an_explicit_422_and_nothing_is_written(client, org, h):
    make_grading(client, h)  # exists, but is not the default
    detail = err(client.post(URL, json=cycle_body(), headers=h), 422, "no_grading_scheme")
    assert detail["details"]["field"] == "grading_scheme_id"
    assert ok(client.get(URL, headers=h))["total"] == 0
    assert audit_entries(org.id) == [] or all(e.entity_type != "exam_cycle" for e in audit_entries(org.id))
    assert outbox("examinations.exam-cycle.created", org.id) == []


def test_create_with_an_unknown_scheme_is_422(client, h, scheme):
    err(client.post(URL, json=cycle_body(grading_scheme_id=uid()), headers=h), 422, "unknown_grading_scheme")


def test_an_invalid_body_is_400_even_when_no_default_exists(client, h):
    err(client.post(URL, json=cycle_body(name=""), headers=h), 400, "invalid_text")


@pytest.mark.parametrize(
    ("change", "code", "field"),
    [
        ({"academic_period_id": "x"}, "invalid_id", "academic_period_id"),
        ({"code": " "}, "invalid_text", "code"),
        ({"code": "c" * 41}, "text_too_long", "code"),
        ({"name": None}, "invalid_text", "name"),
        ({"cycle_type": "annual"}, "invalid_choice", "cycle_type"),
        ({"starts_on": "20261120"}, "invalid_date", "starts_on"),
        ({"starts_on": "2026-13-01"}, "invalid_date", "starts_on"),
        ({"starts_on": 20261120}, "invalid_date", "starts_on"),
        ({"ends_on": "2026-11-19"}, "invalid_cycle_dates", "ends_on"),
        ({"eligibility_cutoff_date": "soon"}, "invalid_date", "eligibility_cutoff_date"),
        ({"min_attendance_percent": 101}, "above_maximum", "min_attendance_percent"),
        ({"min_attendance_percent": -1}, "below_minimum", "min_attendance_percent"),
        ({"min_attendance_percent": "75"}, "invalid_number", "min_attendance_percent"),
        ({"check_dues": "yes"}, "invalid_boolean", "check_dues"),
        ({"grading_scheme_id": "x"}, "invalid_id", "grading_scheme_id"),
        ({"status": "closed"}, "unknown_field", "status"),
        ({"id": uid()}, "unknown_field", "id"),
    ],
)
def test_invalid_input_is_400_and_creates_nothing(client, org, h, scheme, change, code, field):
    detail = err(client.post(URL, json=cycle_body(**change), headers=h), 400, code)
    assert detail["details"]["field"] == field
    assert ok(client.get(URL, headers=h))["total"] == 0
    assert outbox("examinations.exam-cycle.created", org.id) == []


@pytest.mark.parametrize("missing", ["academic_period_id", "code", "name", "cycle_type", "starts_on", "ends_on"])
def test_a_missing_required_field_is_400(client, h, scheme, missing):
    body = cycle_body()
    del body[missing]
    assert client.post(URL, json=body, headers=h).status_code == 400


def test_a_one_day_cycle_is_valid_and_dates_may_not_run_backwards(client, h, scheme):
    assert make_cycle(client, h, starts_on="2026-11-20", ends_on="2026-11-20")["status"] == "draft"
    err(
        client.post(URL, json=cycle_body(starts_on="2026-12-01", ends_on="2026-11-30"), headers=h),
        400,
        "invalid_cycle_dates",
    )


def test_cycle_codes_are_not_unique_until_a_rule_is_agreed(client, h, scheme):
    first, second = make_cycle(client, h), make_cycle(client, h)  # the same code and period twice
    assert first["id"] != second["id"] and first["code"] == second["code"]


def test_list_is_newest_first_and_filters_and_pages(client, h, scheme):
    period = uid()
    made = [
        make_cycle(client, h, academic_period_id=period, cycle_type=kind, code=f"C{i}")
        for i, kind in enumerate(("internal", "mid_term", "end_term"))
    ]
    make_cycle(client, h)  # another period
    advance(client, h, made[0]["id"], "scheduled")
    items = ok(client.get(f"{URL}?academic_period_id={period}", headers=h))
    assert items["total"] == 3 and [c["code"] for c in items["items"]] == ["C2", "C1", "C0"]  # newest first
    assert [c["code"] for c in ok(client.get(f"{URL}?status=scheduled", headers=h))["items"]] == ["C0"]
    assert [c["code"] for c in ok(client.get(f"{URL}?cycle_type=mid_term", headers=h))["items"]] == ["C1"]
    page = ok(client.get(f"{URL}?academic_period_id={period}&limit=2&offset=2", headers=h))
    assert page["total"] == 3 and len(page["items"]) == 1
    assert ok(client.get(URL, headers=h))["total"] == 4
    err(client.get(f"{URL}?status=bogus", headers=h), 400, "invalid_choice")
    err(client.get(f"{URL}?cycle_type=bogus", headers=h), 400, "invalid_choice")
    err(client.get(f"{URL}?academic_period_id=x", headers=h), 400, "invalid_id")


def test_a_missing_cycle_is_404(client, h):
    err(client.get(f"{URL}/{uid()}", headers=h), 404, "exam_cycle_not_found")
    err(client.patch(f"{URL}/{uid()}", json={"name": "x"}, headers=h), 404, "exam_cycle_not_found")
    err(move(client, h, uid(), "scheduled"), 404, "exam_cycle_not_found")


def test_update_changes_the_given_fields_only(client, h, scheme):
    cycle = make_cycle(client, h, min_attendance_percent=75)
    other = make_grading(client, h, "other")
    patch = {
        "name": "  Renamed ",
        "ends_on": "2026-12-20",
        "eligibility_cutoff_date": "2026-11-15",
        "check_dues": True,
        "grading_scheme_id": other["id"],
    }
    updated = ok(client.patch(f"{URL}/{cycle['id']}", json=patch, headers=h))
    assert updated == {
        **cycle,
        "name": "Renamed",
        "ends_on": "2026-12-20",
        "eligibility_cutoff_date": "2026-11-15",
        "check_dues": True,
        "grading_scheme_id": other["id"],
    }
    assert ok(client.get(f"{URL}/{cycle['id']}", headers=h)) == updated
    cleared = ok(
        client.patch(
            f"{URL}/{cycle['id']}", json={"eligibility_cutoff_date": None, "min_attendance_percent": None}, headers=h
        )
    )
    assert cleared["eligibility_cutoff_date"] is None and cleared["min_attendance_percent"] is None
    assert ok(client.patch(f"{URL}/{cycle['id']}", json={}, headers=h)) == cleared  # an empty patch changes nothing


@pytest.mark.parametrize("field", ["code", "academic_period_id", "cycle_type", "status", "id", "organisation_id"])
def test_update_cannot_change_the_fixed_fields(client, h, scheme, field):
    cycle = make_cycle(client, h)
    err(client.patch(f"{URL}/{cycle['id']}", json={field: cycle[field]}, headers=h), 400, "unknown_field")


@pytest.mark.parametrize(
    ("patch", "code"),
    [
        ({"starts_on": "2026-12-11"}, "invalid_cycle_dates"),  # after the stored ends_on
        ({"ends_on": "2026-11-19"}, "invalid_cycle_dates"),  # before the stored starts_on
        ({"starts_on": "2026-12-20", "ends_on": "2026-12-01"}, "invalid_cycle_dates"),
        ({"name": ""}, "invalid_text"),
        ({"min_attendance_percent": 120}, "above_maximum"),
        ({"check_dues": 1}, "invalid_boolean"),
        ({"grading_scheme_id": uid()}, "unknown_grading_scheme"),
        ({"starts_on": "tomorrow"}, "invalid_date"),
    ],
)
def test_an_invalid_update_is_400_and_changes_nothing(client, org, h, scheme, patch, code):
    cycle = make_cycle(client, h)
    before = len(audit_entries(org.id, cycle["id"]))
    err(client.patch(f"{URL}/{cycle['id']}", json=patch, headers=h), 400, code)
    assert ok(client.get(f"{URL}/{cycle['id']}", headers=h)) == cycle
    assert len(audit_entries(org.id, cycle["id"])) == before


def test_update_is_allowed_while_draft_or_scheduled_only(client, h, scheme):
    cycle = make_cycle(client, h)
    advance(client, h, cycle["id"], "scheduled")
    assert (
        ok(client.patch(f"{URL}/{cycle['id']}", json={"name": "scheduled edit"}, headers=h))["name"] == "scheduled edit"
    )
    for status in ("in_progress", "evaluation"):
        advance(client, h, cycle["id"], status)
        detail = err(
            client.patch(f"{URL}/{cycle['id']}", json={"name": "late"}, headers=h), 409, "cycle_not_configurable"
        )
        assert detail["details"]["status"] == status
    assert ok(client.get(f"{URL}/{cycle['id']}", headers=h))["name"] == "scheduled edit"


def test_the_lifecycle_moves_forward_one_status_at_a_time(client, org, h, scheme):
    cycle = make_cycle(client, h)
    assert cycle["status"] == "draft"
    for status in ("scheduled", "in_progress", "evaluation"):
        assert ok(move(client, h, cycle["id"], status))["status"] == status
    assert ok(client.get(f"{URL}/{cycle['id']}", headers=h))["status"] == "evaluation"
    # results_published is set by publication, not here
    err(move(client, h, cycle["id"], "results_published"), 409, "results_published_by_publication")
    assert ok(client.get(f"{URL}/{cycle['id']}", headers=h))["status"] == "evaluation"
    # a cycle cannot be closed before its results are published: only the next status is allowed
    detail = err(move(client, h, cycle["id"], "closed"), 409, "invalid_status_transition")
    assert detail["details"] == {"from": "evaluation", "to": "closed", "allowed": "results_published"}
    with session_for(org.id) as db:  # publication is a later slice: put the cycle at that status directly
        db.get(ExamCycleRow, cycle["id"]).status = "results_published"
        db.commit()
    closed = ok(move(client, h, cycle["id"], "closed"))
    assert closed["status"] == "closed"
    err(move(client, h, cycle["id"], "draft"), 409, "invalid_status_transition")  # a closed cycle is final
    err(move(client, h, cycle["id"], "closed"), 409, "invalid_status_transition")


@pytest.mark.parametrize(
    ("start", "target"),
    [
        ("draft", "in_progress"),  # skipping
        ("draft", "closed"),
        ("draft", "draft"),  # staying
        ("scheduled", "draft"),  # going back
        ("scheduled", "evaluation"),
        ("in_progress", "scheduled"),
    ],
)
def test_other_moves_are_refused_and_change_nothing(client, org, h, scheme, start, target):
    cycle = make_cycle(client, h)
    advance(
        client,
        h,
        cycle["id"],
        *{"draft": [], "scheduled": ["scheduled"], "in_progress": ["scheduled", "in_progress"]}[start],
    )
    before = len(audit_entries(org.id, cycle["id"]))
    err(move(client, h, cycle["id"], target), 409, "invalid_status_transition")
    assert ok(client.get(f"{URL}/{cycle['id']}", headers=h))["status"] == start
    assert len(audit_entries(org.id, cycle["id"])) == before


def test_a_bad_status_body_is_400(client, h, scheme):
    cycle = make_cycle(client, h)
    err(move(client, h, cycle["id"], "finished"), 400, "invalid_choice")
    err(client.post(f"{URL}/{cycle['id']}/status", json={}, headers=h), 400, "missing_field")
    err(
        client.post(f"{URL}/{cycle['id']}/status", json={"status": "scheduled", "x": 1}, headers=h),
        400,
        "unknown_field",
    )


def test_creating_publishes_exam_cycle_created_with_the_contracted_payload(client, org, h, scheme):
    user, headers = org.user("examinations-controller")
    body = cycle_body()
    created = ok(client.post(URL, json=body, headers=headers), 201)
    assert outbox("examinations.exam-cycle.created", org.id) == [
        {
            "organisation_id": org.id,
            "exam_cycle_id": created["id"],
            "academic_period_id": body["academic_period_id"],
            "code": body["code"],
            "name": body["name"],
            "cycle_type": "end_term",
            "starts_on": "2026-11-20",
            "ends_on": "2026-12-10",
        }
    ]
    from eos_core.events import OutboxEvent

    with session_for(org.id) as db:
        event = db.query(OutboxEvent).filter(OutboxEvent.organisation_id == org.id).one()
        assert (event.name, event.actor, event.organisation_id) == ("examinations.exam-cycle.created", user, org.id)


def test_closing_publishes_exam_cycle_closed_and_no_other_status_publishes(client, org, h, scheme):
    cycle = make_cycle(client, h)
    advance(client, h, cycle["id"], "scheduled", "in_progress", "evaluation")
    assert all_outbox(org.id) == ["examinations.exam-cycle.created"]  # moving forward publishes nothing
    with session_for(org.id) as db:
        db.get(ExamCycleRow, cycle["id"]).status = "results_published"
        db.commit()
    ok(move(client, h, cycle["id"], "closed"))
    assert outbox("examinations.exam-cycle.closed", org.id) == [
        {
            "organisation_id": org.id,
            "exam_cycle_id": cycle["id"],
            "academic_period_id": cycle["academic_period_id"],
            "closed_at": NOW.isoformat(),
        }
    ]
    assert sorted(all_outbox(org.id)) == ["examinations.exam-cycle.closed", "examinations.exam-cycle.created"]


def test_updates_and_refused_changes_publish_nothing(client, org, h, scheme):
    cycle = make_cycle(client, h)
    ok(client.patch(f"{URL}/{cycle['id']}", json={"name": "renamed"}, headers=h))
    err(move(client, h, cycle["id"], "closed"), 409, "invalid_status_transition")
    assert all_outbox(org.id) == ["examinations.exam-cycle.created"]


def test_each_change_is_audited_with_the_actor_and_changed_fields(client, org, scheme):
    user, headers = org.user("examinations-controller")
    cycle = ok(client.post(URL, json=cycle_body(), headers=headers), 201)
    ok(client.patch(f"{URL}/{cycle['id']}", json={"name": "Renamed", "check_dues": True}, headers=headers))
    ok(move(client, headers, cycle["id"], "scheduled"))
    entries = {e.action: e for e in audit_entries(org.id, cycle["id"])}
    assert sorted(entries) == ["exam_cycle.created", "exam_cycle.status_changed", "exam_cycle.updated"]
    assert {e.actor for e in entries.values()} == {user}
    assert {e.entity_type for e in entries.values()} == {"exam_cycle"}
    created = entries["exam_cycle.created"]
    assert created.before is None and created.after["code"] == "2026-ODD-END" and created.after["status"] == "draft"
    assert "id" not in created.after and "organisation_id" not in created.after
    updated = entries["exam_cycle.updated"]
    assert updated.before == {"name": "Odd semester end term", "check_dues": False}
    assert updated.after == {"name": "Renamed", "check_dues": True}
    status = entries["exam_cycle.status_changed"]
    assert (status.before, status.after) == ({"status": "draft"}, {"status": "scheduled"})
    assert all(e.organisation_id == org.id and e.occurred_at for e in entries.values())


def test_each_organisation_sees_and_changes_only_its_own_cycles(client, org, other_org, h, scheme):
    other_h = other_org.controller()
    other_scheme = make_grading(client, other_h)
    ok(client.post(f"{GRADING}/{other_scheme['id']}/set-default", headers=other_h))
    mine, theirs = make_cycle(client, h), make_cycle(client, other_h)
    assert [c["id"] for c in ok(client.get(URL, headers=h))["items"]] == [mine["id"]]
    assert ok(client.get(URL, headers=h))["total"] == 1
    assert [c["id"] for c in ok(client.get(URL, headers=other_h))["items"]] == [theirs["id"]]
    err(client.get(f"{URL}/{theirs['id']}", headers=h), 404, "exam_cycle_not_found")
    err(client.patch(f"{URL}/{theirs['id']}", json={"name": "hijack"}, headers=h), 404, "exam_cycle_not_found")
    err(move(client, h, theirs["id"], "scheduled"), 404, "exam_cycle_not_found")
    err(
        client.patch(f"{URL}/{mine['id']}", json={"grading_scheme_id": other_scheme["id"]}, headers=h),
        400,
        "unknown_grading_scheme",
    )
    assert ok(client.get(f"{URL}/{theirs['id']}", headers=other_h))["status"] == "draft"
    assert audit_entries(org.id, theirs["id"]) == []
    assert outbox("examinations.exam-cycle.created", org.id)[0]["exam_cycle_id"] == mine["id"]
    assert len(outbox("examinations.exam-cycle.created", other_org.id)) == 1
