"""Applications (stories O6, O7, S1, S3, S4, S5): applying with a self-declaration, the fixed status sequence, the
offer, rejection and withdrawal, the placed flag, the student's own views and every error code they raise."""

import pytest
from pc_support import BASE, applied, apply, code, company, day, drive, move, ok, opening, outbox


def test_apply_with_a_declaration(client, org):
    o = opening(client, org)
    declared = {"programme": " MBA ", "graduating_year": 2027, "cgpa": 7.8, "active_backlogs": 0}
    a = ok(apply(client, org, o, declared=declared), 201)
    assert a["status"] == "applied" and a["opening_id"] == o["id"] and a["opening_title"] == o["title"]
    assert a["declared"] == {"programme": "MBA", "graduating_year": 2027, "cgpa": 7.8, "active_backlogs": 0}
    assert a["offer"] is None and a["reason"] is None and a["organisation_id"] == org.id
    assert "student_placed" not in a and "student_id" not in a and "declares_eligible" not in a
    [ev] = outbox(org.id, "placement-career.application.submitted")
    assert ev.payload == {
        "organisation_id": org.id,
        "application_id": a["id"],
        "opening_id": o["id"],
        "student_id": org.ids["student"],
    }
    staff = ok(client.get(f"{BASE}/applications/{a['id']}", headers=org.officer))
    assert staff["student_id"] == org.ids["student"] and staff["student_name"] == "Asha Rao"
    assert staff["declares_eligible"] is True and staff["student_placed"] is False
    assert [h["status"] for h in staff["history"]] == ["applied"] and staff["history"][0]["by"] == org.ids["student"]


def test_a_token_without_a_name_gives_an_empty_student_name(client, org):
    a = applied(client, org, who="student3")
    assert ok(client.get(f"{BASE}/applications/{a['id']}", headers=org.officer))["student_name"] == ""


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"declares_eligible": False}, "declaration_required"),
        ({"declares_eligible": None}, "declaration_required"),
        ({"declared": {"cgpa": 11}}, "invalid_eligibility"),
        ({"declared": {"cgpa": -0.5}}, "invalid_eligibility"),
        ({"declared": {"active_backlogs": -1}}, "invalid_eligibility"),
        # caps the code enforces: an integer too large for the column is 422, never a 500
        ({"declared": {"active_backlogs": 101}}, "invalid_eligibility"),
        ({"declared": {"active_backlogs": 3_000_000_000}}, "invalid_eligibility"),
        ({"declared": {"active_backlogs": 2**64}}, "invalid_eligibility"),
        ({"declared": {"graduating_year": 1899}}, "invalid_eligibility"),
        ({"declared": {"graduating_year": 2101}}, "invalid_eligibility"),
        ({"declared": {"graduating_year": 3_000_000_000}}, "invalid_eligibility"),
        ({"declared": {"graduating_year": 2**64}}, "invalid_eligibility"),
    ],
)
def test_invalid_application(client, org, body, expected):
    o = opening(client, org)
    r = client.post(
        f"{BASE}/me/applications", json={"opening_id": o["id"], "declares_eligible": True, **body}, headers=org.student
    )
    assert code(r, 422) == expected
    r = client.post(f"{BASE}/me/applications", json={"opening_id": o["id"]}, headers=org.student)
    assert code(r, 422) == "declaration_required"


def test_apply_only_to_an_open_opening_until_its_last_day(client, org, clock, other_org):
    assert code(apply(client, org, {"id": "nope"}), 404) == "not_found"
    draft = opening(client, org, publish=False)
    assert code(apply(client, org, draft), 404) == "not_found"  # a student cannot see a draft
    assert code(apply(client, org, opening(client, other_org)), 404) == "not_found"
    closed = opening(client, org)
    ok(client.post(f"{BASE}/openings/{closed['id']}/close", headers=org.officer))
    assert code(apply(client, org, closed), 409) == "opening_not_open"
    o = opening(client, org, applications_close_on=day(1))
    clock.advance(days=1)  # the last day itself, IST
    assert ok(apply(client, org, o), 201)["status"] == "applied"
    clock.advance(hours=13)  # 00:30 IST the day after
    assert code(apply(client, org, o, who="student2"), 409) == "applications_closed"


def test_one_application_per_student_and_opening_even_withdrawn(client, org):
    o = opening(client, org)
    a = applied(client, org, o)
    assert code(apply(client, org, o), 409) == "already_applied"
    ok(client.post(f"{BASE}/me/applications/{a['id']}/withdraw", headers=org.student))
    assert code(apply(client, org, o), 409) == "already_applied"
    assert ok(apply(client, org, o, who="student2"), 201)["status"] == "applied"


def test_the_full_sequence_to_an_accepted_offer(client, org):
    o = opening(client, org)
    a = applied(client, org, o)
    ok(move(client, org, a, "shortlisted"))
    ok(move(client, org, a, "in_process"))
    offer = {"ctc_per_annum": "720000", "joining_on": day(60), "notes": "Joins the Bengaluru office"}
    got = ok(move(client, org, a, "offered", offer=offer))
    assert got["offer"] == {"ctc_per_annum": "720000.00", "joining_on": day(60), "notes": "Joins the Bengaluru office"}
    got = ok(move(client, org, a, "accepted", who="coordinator"))
    assert got["status"] == "accepted" and got["student_placed"] is True
    assert [h["status"] for h in got["history"]] == ["applied", "shortlisted", "in_process", "offered", "accepted"]
    assert got["history"][-1]["by"] == org.ids["coordinator"]
    names = [e.name for e in outbox(org.id)]
    assert names == [
        "placement-career.opening.published",
        "placement-career.application.submitted",
        "placement-career.application.shortlisted",
        "placement-career.application.offered",
        "placement-career.application.accepted",
    ]  # moving to in_process publishes nothing
    for name in ("offered", "accepted"):
        [ev] = outbox(org.id, f"placement-career.application.{name}")
        assert ev.payload == {
            "organisation_id": org.id,
            "application_id": a["id"],
            "opening_id": o["id"],
            "company_id": o["company_id"],
            "student_id": org.ids["student"],
        }
    mine = ok(client.get(f"{BASE}/me/applications", headers=org.student))["items"]
    assert mine[0]["status"] == "accepted" and mine[0]["offer"]["ctc_per_annum"] == "720000.00"
    assert "student_placed" not in mine[0]


def test_an_offer_without_details_and_a_declined_answer(client, org):
    a = applied(client, org)
    for step in ("shortlisted", "in_process"):
        ok(move(client, org, a, step))
    got = ok(move(client, org, a, "offered"))
    assert got["offer"] == {"ctc_per_annum": None, "joining_on": None, "notes": None}
    got = ok(move(client, org, a, "declined"))
    assert got["status"] == "declined" and got["student_placed"] is False
    [ev] = outbox(org.id, "placement-career.application.declined")
    assert set(ev.payload) == {"organisation_id", "application_id", "opening_id", "student_id"}


@pytest.mark.parametrize(
    ("path", "target"),
    [
        ([], "in_process"),
        ([], "offered"),
        ([], "accepted"),
        (["shortlisted"], "shortlisted"),
        (["shortlisted"], "offered"),
        (["shortlisted", "in_process"], "accepted"),
        (["shortlisted", "in_process"], "shortlisted"),
        (["shortlisted", "in_process", "offered"], "rejected"),
        (["shortlisted", "in_process", "offered"], "in_process"),
        (["shortlisted", "in_process", "offered", "accepted"], "declined"),
        (["rejected"], "shortlisted"),
    ],
)
def test_steps_are_not_skipped_and_nothing_moves_back(client, org, path, target):
    a = applied(client, org)
    for step in path:
        ok(move(client, org, a, step, reason="Did not clear the test"))
    r = move(client, org, a, target, reason="x")
    assert code(r, 409) == "invalid_transition"


def test_status_values_that_are_not_steps(client, org):
    a = applied(client, org)
    for status in ("applied", "withdrawn", "hired"):
        assert code(move(client, org, a, status), 422) == "invalid_status"
    assert code(move(client, org, a, "rejected"), 422) == "reason_required"
    assert code(move(client, org, a, "rejected", reason="  "), 422) == "reason_required"
    ok(move(client, org, a, "shortlisted"))
    ok(move(client, org, a, "in_process"))
    assert code(move(client, org, a, "offered", offer={"ctc_per_annum": "-1"}), 422) == "invalid_amount"
    assert code(move(client, org, a, "offered", offer={"joining_on": day(-1)}), 422) == "invalid_date"
    assert ok(client.get(f"{BASE}/applications/{a['id']}", headers=org.officer))["status"] == "in_process"
    assert code(move(client, org, {"id": "nope"}, "shortlisted"), 404) == "not_found"


def test_reject_with_a_reason_the_student_sees(client, org):
    a = applied(client, org)
    ok(move(client, org, a, "shortlisted"))
    got = ok(move(client, org, a, "rejected", reason="Did not clear the aptitude round"))
    assert got["status"] == "rejected" and got["reason"] == "Did not clear the aptitude round"
    mine = ok(client.get(f"{BASE}/me/applications", headers=org.student))["items"][0]
    assert mine["reason"] == "Did not clear the aptitude round"
    [ev] = outbox(org.id, "placement-career.application.rejected")
    assert "reason" not in ev.payload


def test_an_offer_or_reason_sent_with_another_step_is_not_recorded(client, org):
    a = applied(client, org)
    got = ok(move(client, org, a, "shortlisted", reason="ignored", offer={"ctc_per_annum": "1"}))
    assert got["offer"] is None and got["reason"] is None


def test_withdraw_before_an_offer(client, org):
    a = applied(client, org)
    ok(move(client, org, a, "shortlisted"))
    got = ok(client.post(f"{BASE}/me/applications/{a['id']}/withdraw", headers=org.student))
    assert got["status"] == "withdrawn"
    [ev] = outbox(org.id, "placement-career.application.withdrawn")
    assert ev.payload["application_id"] == a["id"] and ev.payload["student_id"] == org.ids["student"]
    r = client.post(f"{BASE}/me/applications/{a['id']}/withdraw", headers=org.student)
    assert code(r, 409) == "not_withdrawable"
    assert code(move(client, org, a, "in_process"), 409) == "invalid_transition"
    offered = applied(client, org)
    for step in ("shortlisted", "in_process", "offered"):
        ok(move(client, org, offered, step))
    r = client.post(f"{BASE}/me/applications/{offered['id']}/withdraw", headers=org.student)
    assert code(r, 409) == "not_withdrawable"


def test_students_reach_only_their_own_applications(client, org):
    a = applied(client, org)
    assert code(client.post(f"{BASE}/me/applications/{a['id']}/withdraw", headers=org.student2), 404) == "not_found"
    assert code(client.post(f"{BASE}/me/applications/nope/withdraw", headers=org.student), 404) == "not_found"
    assert ok(client.get(f"{BASE}/me/applications", headers=org.student2))["items"] == []
    for path in ("/applications", f"/applications/{a['id']}"):
        assert code(client.get(f"{BASE}{path}", headers=org.student), 403) == "forbidden"
    assert code(move(client, org, a, "shortlisted", who="student"), 403) == "forbidden"


def test_placed_students_are_flagged_and_not_blocked(client, org):
    first = applied(client, org)
    second_opening = opening(client, org)
    for step in ("shortlisted", "in_process", "offered", "accepted"):
        ok(move(client, org, first, step))
    # no one-offer rule: the placed student still applies and can be offered again
    second = applied(client, org, second_opening)
    other = applied(client, org, second_opening, who="student2")
    for step in ("shortlisted", "in_process", "offered"):
        ok(move(client, org, second, step))
    rows = ok(client.get(f"{BASE}/applications", params={"opening_id": second_opening["id"]}, headers=org.officer))
    flags = {r["student_id"]: r["student_placed"] for r in rows["items"]}
    assert flags == {org.ids["student"]: True, org.ids["student2"]: False}
    placed = ok(client.get(f"{BASE}/applications", params={"student_placed": True}, headers=org.officer))["items"]
    assert {r["id"] for r in placed} == {first["id"], second["id"]}
    unplaced = ok(client.get(f"{BASE}/applications", params={"student_placed": False}, headers=org.officer))["items"]
    assert [r["id"] for r in unplaced] == [other["id"]]


def test_application_filters_order_and_pages(client, org):
    d = drive(client, org)
    in_drive = opening(client, org, dr=d)
    alone = opening(client, org)
    a1 = applied(client, org, in_drive)
    a2 = applied(client, org, alone)
    a3 = applied(client, org, in_drive, who="student2")
    ok(move(client, org, a3, "shortlisted"))

    def ids(**params):
        return [r["id"] for r in ok(client.get(f"{BASE}/applications", params=params, headers=org.officer))["items"]]

    assert ids() == [a3["id"], a2["id"], a1["id"]]  # newest first
    assert ids(opening_id=alone["id"]) == [a2["id"]]
    assert ids(drive_id=d["id"]) == [a3["id"], a1["id"]]
    assert ids(status="shortlisted") == [a3["id"]]
    assert ids(student_id=org.ids["student"]) == [a2["id"], a1["id"]]
    row = ok(client.get(f"{BASE}/applications", params={"opening_id": alone["id"]}, headers=org.officer))["items"][0]
    assert "history" not in row and row["drive_id"] is None and row["company"]["id"] == alone["company_id"]
    first = ok(client.get(f"{BASE}/applications", params={"limit": 2}, headers=org.officer))
    rest = ok(
        client.get(f"{BASE}/applications", params={"limit": 2, "cursor": first["next_cursor"]}, headers=org.officer)
    )
    assert [r["id"] for r in first["items"] + rest["items"]] == ids() and rest["next_cursor"] is None
    assert code(client.get(f"{BASE}/applications", params={"cursor": "zz"}, headers=org.officer), 400) == (
        "invalid_cursor"
    )
    assert client.get(f"{BASE}/applications", params={"status": "hired"}, headers=org.officer).status_code == 422


def test_the_viewer_sees_no_individual_applications(client, org):
    a = applied(client, org)
    assert code(client.get(f"{BASE}/applications", headers=org.viewer), 403) == "forbidden"
    assert code(client.get(f"{BASE}/applications/{a['id']}", headers=org.viewer), 403) == "forbidden"
    assert code(move(client, org, a, "shortlisted", who="viewer"), 403) == "forbidden"
    assert code(client.get(f"{BASE}/me/openings", headers=org.viewer), 403) == "forbidden"
    assert code(apply(client, org, {"id": "x"}, who="viewer"), 403) == "forbidden"


def test_my_openings_shows_what_i_can_still_apply_to(client, org, clock):
    co = company(client, org, contact_email="hr@acme.example")
    d = drive(client, org, co)
    late = opening(client, org, dr=d, applications_close_on=day(9))
    soon = opening(client, org, co=co, applications_close_on=day(1))
    opening(client, org, co=co, publish=False)
    closed = opening(client, org, co=co)
    ok(client.post(f"{BASE}/openings/{closed['id']}/close", headers=org.officer))
    a = applied(client, org, late)
    items = ok(client.get(f"{BASE}/me/openings", headers=org.student))["items"]
    assert [o["id"] for o in items] == [soon["id"], late["id"]]  # soonest closing first
    assert items[0]["my_application"] is None and items[0]["drive"] is None
    assert items[1]["my_application"] == {"id": a["id"], "status": "applied"}
    assert items[1]["drive"]["id"] == d["id"] and items[1]["ctc_per_annum"] == "650000.00"
    assert "contact_email" not in items[1]["company"]
    clock.advance(days=2)  # soon's last day has passed
    items = ok(client.get(f"{BASE}/me/openings", headers=org.student2))["items"]
    assert [o["id"] for o in items] == [late["id"]] and items[0]["my_application"] is None
    assert code(client.get(f"{BASE}/me/openings", headers=org.nobody), 403) == "forbidden"


def test_my_lists_are_cursor_pages(client, org):
    ops = [opening(client, org, applications_close_on=day(i + 1)) for i in range(3)]
    for o in ops:
        applied(client, org, o)
    for path in ("/me/openings", "/me/applications"):
        first = ok(client.get(f"{BASE}{path}", params={"limit": 2}, headers=org.student))
        assert len(first["items"]) == 2 and first["next_cursor"] == "2"
        rest = ok(client.get(f"{BASE}{path}", params={"limit": 2, "cursor": "2"}, headers=org.student))
        assert len(rest["items"]) == 1 and rest["next_cursor"] is None
        assert code(client.get(f"{BASE}{path}", params={"cursor": "two"}, headers=org.student), 400) == "invalid_cursor"
        assert client.get(f"{BASE}{path}", params={"limit": 0}, headers=org.student).status_code == 422
    mine = ok(client.get(f"{BASE}/me/applications", headers=org.student))["items"]
    assert [m["opening_id"] for m in mine] == [o["id"] for o in reversed(ops)]  # newest first
    assert code(client.get(f"{BASE}/me/applications", headers=org.nobody), 403) == "forbidden"


@pytest.mark.parametrize("bad", ["²", "９", "٣"])
@pytest.mark.parametrize(
    ("path", "who"),
    [
        ("/companies", "officer"),
        ("/drives", "officer"),
        ("/openings", "officer"),
        ("/applications", "officer"),
        ("/me/openings", "student"),
        ("/me/applications", "student"),
    ],
)
def test_a_non_ascii_digit_cursor_is_refused(client, org, path, who, bad):
    # str.isdigit() is true for these, but int() rejects "²" and the API never returns the others.
    response = client.get(f"{BASE}{path}", params={"cursor": bad}, headers=getattr(org, who))
    assert code(response, 400) == "invalid_cursor"
