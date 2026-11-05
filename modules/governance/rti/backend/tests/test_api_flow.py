"""Referrals, response, transfer, appeal, decision and closing (contract /referrals, /respond, /transfer, /appeal,
/appeal-decision, /close), the events they publish and who may see what."""

from datetime import UTC, datetime

import pytest
from conftest import Desk, audit, days, outbox

MISSING = "00000000-0000-4000-8000-000000000000"


def code(response) -> str:
    return response.json()["detail"]["code"]


def refer(desk: Desk, request_id: str, question: str = "Which committee fixed the cut-off marks?", **extra) -> dict:
    body = {"custodian_id": desk.custodian_id, "question": question, **extra}
    return desk.ok(desk.post(f"/requests/{request_id}/referrals", body))


# ---------------------------------------------------------------- referrals


def test_a_custodian_is_asked_and_answers_without_seeing_the_applicant(desk, org):
    r = desk.assigned()
    f = refer(desk, r["id"], due_on=days(10))
    assert (f["status"], f["custodian_id"], f["due_on"], f["reply"]) == ("open", desk.custodian_id, days(10), None)
    assert desk.ok(desk.get(f"/requests/{r['id']}"))["status"] == "assigned"  # a referral does not move the request

    mine = desk.ok(desk.get("/referrals", desk.custodian))
    assert mine["items"] == [
        {
            "id": f["id"],
            "request_number": r["number"],
            "question": f["question"],
            "due_on": days(10),
            "status": "open",
            "reply": None,
            "replied_at": None,
        }
    ]
    replied = desk.ok(desk.post(f"/referrals/{f['id']}/reply", {"reply": "The admission committee."}, desk.custodian))
    assert (replied["status"], replied["reply"]) == ("replied", "The admission committee.") and replied["replied_at"]
    assert set(replied) == {"id", "request_number", "question", "due_on", "status", "reply", "replied_at"}
    assert audit(org.id, f["id"]) == sorted(["referral.created", "referral.replied"])

    everything = (
        desk.get("/referrals", desk.custodian).text + desk.get("/referrals?status=replied", desk.custodian).text
    )
    for secret in ("Asha", "asha.verma", "Park Road", "98450", "Admission records", "merit list", "request_id"):
        assert secret not in everything, secret
    seen = desk.ok(desk.get(f"/requests/{r['id']}"))["referrals"]
    assert [x["reply"] for x in seen] == ["The admission committee."] and seen[0]["request_id"] == r["id"]


def test_officers_list_the_referrals_of_a_request(desk):
    r, other = desk.assigned(), desk.assigned()
    a, b = refer(desk, r["id"]), refer(desk, other["id"])
    refer(desk, r["id"], "And which year was that?")
    items = desk.ok(desk.get(f"/referrals?request_id={r['id']}"))["items"]
    assert len(items) == 2 and {i["request_id"] for i in items} == {r["id"]}
    assert len(desk.ok(desk.get("/referrals"))["items"]) == 3
    assert [i["id"] for i in desk.ok(desk.get(f"/referrals?request_id={other['id']}"))["items"]] == [b["id"]]
    assert desk.ok(desk.get("/referrals?status=replied"))["items"] == []
    desk.ok(desk.post(f"/referrals/{a['id']}/reply", {"reply": "Done."}, desk.custodian))
    assert [i["id"] for i in desk.ok(desk.get("/referrals?status=replied"))["items"]] == [a["id"]]
    assert desk.ok(desk.get("/referrals?limit=1"))["next_cursor"] == "1"
    assert desk.ok(desk.get("/referrals?limit=1", desk.appellate))["items"][0][
        "request_id"
    ]  # appellate has request:read


def test_a_custodian_sees_only_their_own_referrals(desk, org):
    r = desk.assigned()
    mine, theirs = refer(desk, r["id"]), None
    other_id, other = org.user("rti-custodian")
    theirs = desk.ok(
        desk.post(f"/requests/{r['id']}/referrals", {"custodian_id": other_id, "question": "Another question?"})
    )
    assert [i["id"] for i in desk.ok(desk.get("/referrals", desk.custodian))["items"]] == [mine["id"]]
    assert [i["id"] for i in desk.ok(desk.get("/referrals", other))["items"]] == [theirs["id"]]
    assert desk.ok(desk.get(f"/referrals?request_id={r['id']}", other))["items"][0]["id"] == theirs["id"]
    assert desk.post(f"/referrals/{mine['id']}/reply", {"reply": "Not mine"}, other).status_code == 404
    assert desk.post(f"/referrals/{mine['id']}/reply", {"reply": "Not an officer's"}).status_code == 403
    assert desk.get(f"/requests/{r['id']}", desk.custodian).status_code == 403
    assert desk.get("/requests", desk.custodian).status_code == 403


def test_a_referral_can_be_answered_once(desk):
    f = refer(desk, desk.assigned()["id"])
    desk.ok(desk.post(f"/referrals/{f['id']}/reply", {"reply": "First."}, desk.custodian))
    again = desk.post(f"/referrals/{f['id']}/reply", {"reply": "Second."}, desk.custodian)
    assert (again.status_code, code(again)) == (409, "already_replied")
    for bad in (MISSING, "not-a-uuid", "a%00b"):
        assert desk.post(f"/referrals/{bad}/reply", {"reply": "x"}, desk.custodian).status_code == 404


@pytest.mark.parametrize(
    "bad",
    [{}, {"reply": ""}, {"reply": "   "}, {"reply": "x" * 10_001}, {"reply": "a\u0000b"}, {"reply": "x", "extra": 1}],
)
def test_a_bad_reply_is_a_422(desk, bad):
    f = refer(desk, desk.assigned()["id"])
    assert desk.post(f"/referrals/{f['id']}/reply", bad, desk.custodian).status_code == 422


def test_referral_rules(desk):
    received = desk.request()
    refused = desk.post(
        f"/requests/{received['id']}/referrals", {"custodian_id": desk.custodian_id, "question": "A question?"}
    )
    assert (refused.status_code, code(refused)) == (409, "invalid_status")  # only while assigned
    r = desk.assigned()
    for question in (
        "Please send papers of Asha Verma",
        "Mail asha.verma@example.org the answer",
        "Phone +91 98450 00000",
    ):
        refused = desk.post(f"/requests/{r['id']}/referrals", {"custodian_id": desk.custodian_id, "question": question})
        assert (refused.status_code, code(refused)) == (422, "applicant_details_in_question"), question
    bad = [
        {"question": "A question?"},
        {"custodian_id": "me", "question": "A question?"},
        {"custodian_id": desk.custodian_id},
        {"custodian_id": desk.custodian_id, "question": "ab"},
        {"custodian_id": desk.custodian_id, "question": "x" * 10_001},
        {"custodian_id": desk.custodian_id, "question": "A question?", "due_on": "soon"},
        {"custodian_id": desk.custodian_id, "question": "A question?", "due_on": "0001-01-01"},
        {"custodian_id": desk.custodian_id, "question": "A question?", "due_on": "9999-12-31"},
        {"custodian_id": desk.custodian_id, "question": "A\u0000 question?"},
    ]
    for body in bad:
        assert desk.post(f"/requests/{r['id']}/referrals", body).status_code == 422, body
    desk.respond(r["id"])
    after = desk.post(f"/requests/{r['id']}/referrals", {"custodian_id": desk.custodian_id, "question": "Too late?"})
    assert after.status_code == 409


@pytest.mark.parametrize(
    "query", ["request_id=x", f"request_id={MISSING},{MISSING}", "status=bogus", "request_id=a%00b"]
)
def test_a_bad_referral_filter_is_a_422(desk, query):
    assert desk.get(f"/referrals?{query}").status_code == 422


# ---------------------------------------------------------------- response


def test_responding_records_the_response(desk, org):
    r = desk.assigned(received_on=days(-3))
    d = desk.respond(r["id"], dispatched_on=days(-1), dispatch_mode="email", summary="Sent by email.")
    assert (d["status"], d["closure"], d["overdue"]) == ("responded", None, False) and d["responded_at"]
    assert d["response"] == {
        "type": "information_provided",
        "summary": "Sent by email.",
        "dispatched_on": days(-1),
        "dispatch_mode": "email",
        "responded_by": desk.officer_id,
    }
    assert audit(org.id, r["id"]) == sorted(["request.recorded", "request.assigned", "request.responded"])
    assert outbox("rti.request.closed", org.id) == []  # responding does not close


@pytest.mark.parametrize("kind", ["partly_provided", "refused"])
def test_withholding_information_needs_grounds(desk, kind):
    r = desk.assigned()
    refused = desk.post(
        f"/requests/{r['id']}/respond",
        {"type": kind, "summary": "Part supplied.", "dispatched_on": days(0), "dispatch_mode": "post"},
    )
    assert (refused.status_code, code(refused)) == (422, "grounds_required")
    d = desk.respond(r["id"], type=kind, grounds="Personal information of third parties.")
    assert d["response"]["grounds"] == "Personal information of third parties."


def test_responding_is_only_possible_while_assigned(desk):
    for request in (desk.request(), desk.responded()):
        refused = desk.post(
            f"/requests/{request['id']}/respond",
            {
                "type": "refused",
                "summary": "No.",
                "grounds": "None.",
                "dispatched_on": days(0),
                "dispatch_mode": "post",
            },
        )
        assert (refused.status_code, code(refused)) == (409, "invalid_status")


def test_the_response_date_is_between_receipt_and_today(desk):
    r = desk.assigned(received_on=days(-5))
    for when in (days(1), days(-6), "0001-01-01", "9999-12-31"):
        refused = desk.post(
            f"/requests/{r['id']}/respond",
            {"type": "information_provided", "summary": "Sent.", "dispatched_on": when, "dispatch_mode": "post"},
        )
        assert refused.status_code == 422, when
    assert desk.respond(r["id"], dispatched_on=days(-5))["response"]["dispatched_on"] == days(-5)


@pytest.mark.parametrize(
    "bad",
    [
        {"type": "ignored"},
        {"type": None},
        {"summary": "ab"},
        {"summary": "  "},
        {"summary": "x" * 10_001},
        {"grounds": "ab"},
        {"dispatch_mode": "carrier pigeon"},
        {"dispatch_mode": None},
        {"dispatched_on": "never"},
        {"dispatched_on": None},
        {"summary": "Sent\u0000"},
        {"extra": 1},
    ],
)
def test_a_bad_response_is_a_422(desk, bad):
    r = desk.assigned()
    body = {"type": "information_provided", "summary": "Sent.", "dispatched_on": days(0), "dispatch_mode": "post"}
    body.update(bad)
    assert desk.post(f"/requests/{r['id']}/respond", body).status_code == 422, bad


# ---------------------------------------------------------------- transfer


@pytest.mark.parametrize("assign_first", [False, True])
def test_a_transfer_is_final_and_publishes_closed(desk, org, assign_first):
    r = desk.assigned() if assign_first else desk.request()
    d = desk.ok(
        desk.post(
            f"/requests/{r['id']}/transfer",
            {
                "authority_name": "State Higher Education Council",
                "transferred_on": days(0),
                "reason": "Holds the records.",
            },
        )
    )
    assert (d["status"], d["closure"], d["overdue"]) == ("transferred", "transferred", False) and d["closed_at"]
    assert d["transfer"] == {
        "authority_name": "State Higher Education Council",
        "transferred_on": days(0),
        "reason": "Holds the records.",
        "transferred_by": desk.officer_id,
    }
    (event,) = outbox("rti.request.closed", org.id)
    assert event == {
        "organisation_id": org.id,
        "request_id": r["id"],
        "number": r["number"],
        "closure": "transferred",
        "response_type": None,
        "appealed": False,
        "closed_at": d["closed_at"],
    }
    assert audit(org.id, r["id"]).count("request.transferred") == 1
    for path, body in (("assign", {"officer_id": desk.officer_id}), ("close", None), ("transfer", None)):
        payload = body or {"authority_name": "X", "transferred_on": days(0), "reason": "Again."}
        assert desk.post(f"/requests/{r['id']}/{path}", payload).status_code == 409, path
    assert desk.patch(f"/requests/{r['id']}", {"subject": "Changed my mind"}).status_code == 409


def test_a_transfer_after_a_response_is_409(desk):
    r = desk.responded()
    refused = desk.post(
        f"/requests/{r['id']}/transfer",
        {"authority_name": "Council", "transferred_on": days(0), "reason": "Wrong body."},
    )
    assert (refused.status_code, code(refused)) == (409, "invalid_status")


@pytest.mark.parametrize(
    "bad",
    [
        {"authority_name": ""},
        {"authority_name": "a" * 201},
        {"authority_address": "a" * 1001},
        {"transferred_on": days(1)},
        {"transferred_on": days(-9)},  # before the request was received
        {"transferred_on": "0001-01-01"},
        {"reason": "no"},
        {"reason": None},
        {"authority_name": "Coun\u0000cil"},
        {"extra": 1},
    ],
)
def test_a_bad_transfer_is_a_422(desk, bad):
    r = desk.request(received_on=days(-3))
    body = {"authority_name": "Council", "transferred_on": days(0), "reason": "Wrong body."}
    body.update(bad)
    assert desk.post(f"/requests/{r['id']}/transfer", body).status_code == 422, bad


# ---------------------------------------------------------------- appeal


def test_an_appeal_is_recorded_decided_and_closed(desk, org):
    r = desk.responded(type="partly_provided", grounds="Third party data.")
    appealed = desk.ok(
        desk.post(f"/requests/{r['id']}/appeal", {"filed_on": days(0), "grounds": "More can be given."}, desk.appellate)
    )
    assert appealed["status"] == "appealed"
    # 30 calendar days from 5 November is 5 December, to the end of the day in India.
    assert appealed["appeal"] == {
        "filed_on": days(0),
        "grounds": "More can be given.",
        "outcome": None,
        "decision_note": None,
        "decided_by": None,
        "decided_on": None,
        "due_at": "2026-12-05T18:29:59+00:00",
    }
    decided = desk.ok(
        desk.post(
            f"/requests/{r['id']}/appeal-decision",
            {"outcome": "partly_upheld", "decision_note": "Parts to be released.", "decided_on": days(0)},
            desk.appellate,
        )
    )
    assert decided["status"] == "appeal_decided" and decided["appeal"]["outcome"] == "partly_upheld"
    assert decided["appeal"]["decided_by"] == desk.appellate_id
    closed = desk.ok(desk.post(f"/requests/{r['id']}/close"))
    assert (closed["status"], closed["closure"]) == ("closed", "appeal_decided") and closed["closed_at"]
    (event,) = outbox("rti.request.closed", org.id)
    assert (event["closure"], event["response_type"], event["appealed"]) == ("appeal_decided", "partly_provided", True)
    assert audit(org.id, r["id"]) == sorted(
        [
            "request.recorded",
            "request.assigned",
            "request.responded",
            "appeal.filed",
            "appeal.decided",
            "request.closed",
        ]
    )


def test_an_appeal_is_refused_while_the_window_is_not_configured(desk, settings):
    settings.unset("appeal_window_days")
    r = desk.responded()
    body = {"filed_on": days(0), "grounds": "Incomplete."}
    for request_id in (r["id"], desk.request()["id"]):  # whatever the request's status
        refused = desk.post(f"/requests/{request_id}/appeal", body, desk.appellate)
        assert refused.status_code == 409 and code(refused) == "appeal_window_not_configured"
        assert refused.json()["detail"]["message"] == "Appeal window is not configured"
    assert desk.post(f"/requests/{MISSING}/appeal", body, desk.appellate).status_code == 404
    # and a responded request stays responded: there is no fallback
    refused = desk.post(f"/requests/{r['id']}/close")
    assert refused.status_code == 409 and refused.json()["detail"]["message"] == "Appeal window is not configured"
    assert desk.ok(desk.get(f"/requests/{r['id']}"))["status"] == "responded"


def test_an_appeal_needs_a_responded_request(desk):
    for request in (desk.request(), desk.assigned()):
        refused = desk.post(
            f"/requests/{request['id']}/appeal", {"filed_on": days(0), "grounds": "Incomplete."}, desk.appellate
        )
        assert (refused.status_code, code(refused)) == (409, "invalid_status")
    appealed = desk.appealed()
    again = desk.post(f"/requests/{appealed['id']}/appeal", {"filed_on": days(0), "grounds": "Twice."}, desk.appellate)
    assert (again.status_code, code(again)) == (409, "invalid_status")


def test_the_appeal_window_runs_from_the_day_of_dispatch_and_counts_the_filing_date_not_the_recording_date(desk, clock):
    r = desk.responded(received_on=days(-10), dispatched_on=days(-3))  # window: 30 days from 2 November = 2 December
    path = f"/requests/{r['id']}/appeal"
    clock.set(datetime(2026, 12, 10, 6, 0, tzinfo=UTC))  # recorded late, on 10 December
    late = desk.post(path, {"filed_on": "2026-12-03", "grounds": "Filed too late."}, desk.appellate)
    assert (late.status_code, code(late)) == (409, "appeal_window_passed")
    ok = desk.ok(desk.post(path, {"filed_on": "2026-12-02", "grounds": "Filed on the last day."}, desk.appellate))
    assert ok["appeal"]["filed_on"] == "2026-12-02"


def test_an_appeal_cannot_be_dated_before_the_response_or_after_today(desk):
    r = desk.responded(received_on=days(-10), dispatched_on=days(-3))
    path = f"/requests/{r['id']}/appeal"
    for when in (days(-4), days(1), "0001-01-01", "9999-12-31"):
        assert desk.post(path, {"filed_on": when, "grounds": "Dated wrongly."}, desk.appellate).status_code == 422, when


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"filed_on": "x", "grounds": "Incomplete."},
        {"filed_on": "2026-11-05", "grounds": "no"},
        {"filed_on": "2026-11-05", "grounds": "In\u0000complete"},
        {"filed_on": "2026-11-05", "grounds": "Incomplete.", "extra": 1},
    ],
)
def test_a_bad_appeal_is_a_422(desk, bad):
    r = desk.responded()
    assert desk.post(f"/requests/{r['id']}/appeal", bad, desk.appellate).status_code == 422


def test_an_appeal_decision_rules(desk):
    r = desk.appealed()
    path = f"/requests/{r['id']}/appeal-decision"
    base = {"outcome": "dismissed", "decision_note": "No merit.", "decided_on": days(0)}
    for bad in (
        {"outcome": "granted"},
        {"outcome": None},
        {"decision_note": "no"},
        {"decided_on": days(1)},
        {"decided_on": days(-1)},  # before it was filed
        {"decided_on": "0001-01-01"},
        {"decision_note": "No\u0000 merit."},
        {"extra": 1},
    ):
        assert desk.post(path, {**base, **bad}, desk.appellate).status_code == 422, bad
    assert desk.post(path, base, desk.appellate).status_code == 200
    again = desk.post(path, base, desk.appellate)
    assert (again.status_code, code(again)) == (409, "invalid_status")
    not_appealed = desk.responded()
    assert desk.post(f"/requests/{not_appealed['id']}/appeal-decision", base, desk.appellate).status_code == 409


# ---------------------------------------------------------------- close


def test_a_responded_request_closes_once_the_appeal_window_is_over(desk, clock, org):
    r = desk.responded()  # dispatched 5 November; the window ends on 5 December
    refused = desk.post(f"/requests/{r['id']}/close")
    assert (refused.status_code, code(refused)) == (409, "appeal_window_open")
    clock.set(datetime(2026, 12, 5, 18, 29, 59, tzinfo=UTC))  # still the 5th in India
    assert desk.post(f"/requests/{r['id']}/close").status_code == 409
    clock.set(datetime(2026, 12, 5, 18, 30, 0, tzinfo=UTC))  # the 6th
    closed = desk.ok(desk.post(f"/requests/{r['id']}/close"))
    assert (closed["status"], closed["closure"]) == ("closed", "responded")
    (event,) = outbox("rti.request.closed", org.id)
    assert event["closure"] == "responded" and event["response_type"] == "information_provided"
    assert event["appealed"] is False and event["closed_at"] == closed["closed_at"]
    assert desk.post(f"/requests/{r['id']}/close").status_code == 409  # closed is final
    assert (
        desk.post(f"/requests/{r['id']}/appeal", {"filed_on": days(0), "grounds": "Late."}, desk.appellate).status_code
        == 409
    )


def test_working_days_move_the_end_of_the_window(desk, clock, settings):
    settings(appeal_window_days=3, day_counting="working")
    r = desk.responded(dispatched_on=days(0))  # Thursday 5 November; three working days later is Tuesday the 10th
    clock.set(datetime(2026, 11, 10, 18, 29, tzinfo=UTC))
    assert desk.post(f"/requests/{r['id']}/close").status_code == 409
    clock.set(datetime(2026, 11, 10, 18, 30, tzinfo=UTC))
    assert desk.post(f"/requests/{r['id']}/close").status_code == 200


@pytest.mark.parametrize("make", ["request", "assigned"])
def test_only_responded_or_appeal_decided_requests_close(desk, make):
    r = getattr(desk, make)()
    refused = desk.post(f"/requests/{r['id']}/close")
    assert (refused.status_code, code(refused)) == (409, "invalid_status")
    appealed = desk.appealed()
    assert desk.post(f"/requests/{appealed['id']}/close").status_code == 409


# ---------------------------------------------------------------- who may do what


def test_the_roles_see_and_do_only_what_the_catalogue_gives_them(desk, org):
    r = desk.assigned()
    appellate, viewer = desk.appellate, desk.viewer
    assert desk.get(f"/requests/{r['id']}", appellate).status_code == 200  # request:read
    assert desk.get("/requests", appellate).status_code == 200
    assert desk.post(f"/requests/{r['id']}/assign", {"officer_id": desk.officer_id}, appellate).status_code == 403
    assert desk.post("/requests", {}, appellate).status_code == 403
    for path in ("/requests", f"/requests/{r['id']}", "/referrals"):
        assert desk.get(path, viewer).status_code == 403, path
    assert (
        desk.post(f"/requests/{r['id']}/appeal", {"filed_on": days(0), "grounds": "Nope."}, desk.officer).status_code
        == 403
    )
    assert desk.get("/stats/nearing-deadline", viewer).status_code == 200
    assert desk.get("/stats/nearing-deadline", desk.custodian).status_code == 403
    _, nobody = org.user("student")
    assert desk.get("/stats/nearing-deadline", nobody).status_code == 403


def test_referrals_do_not_leak_applicant_data_to_viewers_of_the_stats(desk):
    desk.assigned()
    text = desk.get("/stats/nearing-deadline", desk.viewer).text
    for secret in ("Asha", "asha.verma", "Admission records", "applicant"):
        assert secret not in text
