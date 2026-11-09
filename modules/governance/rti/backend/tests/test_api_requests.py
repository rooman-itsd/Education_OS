"""Recording, listing, reading, correcting and assigning requests (contract /requests, /requests/{id}, /assign)."""

from datetime import UTC, datetime

import pytest
from conftest import APPLICANT, Desk, audit, days, outbox


def body(**over) -> dict:
    base = {
        "received_via": "email",
        "received_on": days(-1),
        "applicant": dict(APPLICANT),
        "subject": "Faculty recruitment 2024",
        "information_sought": "The selection committee minutes.",
        "fee": {"status": "exempt"},
    }
    base.update(over)
    return base


# ---------------------------------------------------------------- recording


def test_recording_numbers_the_request_and_publishes_received(desk, org):
    r = desk.request(received_on=days(-1))
    assert (r["number"], r["status"], r["officer_id"], r["closure"], r["overdue"]) == (
        "RTI-000001",
        "received",
        None,
        None,
        False,
    )
    assert r["created_by"] == desk.officer_id and r["organisation_id"] == org.id
    assert r["applicant"]["name"] == "Asha Verma" and r["applicant"]["person_id"] is None
    assert r["fee"] == {"status": "paid", "amount": {"amount": "10.00", "currency": "INR"}, "mode": "cash"}
    # 30 calendar days after 4 November 2026 is 4 December; due until the end of that day in India.
    assert r["due_at"] == "2026-12-04T18:29:59+00:00"
    assert audit(org.id, r["id"]) == sorted(["request.recorded"])
    (event,) = outbox("rti.request.received", org.id)
    assert event == {
        "organisation_id": org.id,
        "request_id": r["id"],
        "number": "RTI-000001",
        "received_via": "post",
        "received_on": days(-1),
    }


def test_numbers_run_on_per_organisation_with_the_configured_prefix(desk, other_org, settings):
    assert [desk.request()["number"] for _ in range(3)] == ["RTI-000001", "RTI-000002", "RTI-000003"]
    elsewhere = Desk(desk.client, other_org)
    assert elsewhere.request()["number"] == "RTI-000001"
    settings(request_number_prefix="GOV7")
    assert desk.request()["number"] == "GOV7-000004"


def test_a_fee_amount_without_a_currency_is_in_the_default_currency(desk, settings):
    r = desk.ok(desk.post("/requests", body(fee={"status": "paid", "amount": {"amount": "7"}})))
    assert r["fee"]["amount"] == {"amount": "7.00", "currency": "INR"}
    settings(default_currency="USD")
    r = desk.ok(desk.post("/requests", body(fee={"status": "paid", "amount": {"amount": "7.5"}})))
    assert r["fee"]["amount"] == {"amount": "7.50", "currency": "USD"}


def test_no_timeline_setting_means_no_due_date(desk, settings):
    settings.unset("response_days", "appeal_window_days", "appeal_decide_days")
    r = desk.request(received_on=days(-500))
    assert (r["due_at"], r["overdue"]) == (None, False)


def test_working_days_skip_weekends(desk, settings):
    settings(response_days=5, day_counting="working")
    r = desk.request(received_on=days(0))  # Thursday 5 November; five working days later is Thursday the 12th
    assert r["due_at"] == "2026-11-12T18:29:59+00:00"


def test_today_is_the_date_in_india(desk, clock):
    clock.set(datetime(2026, 11, 5, 19, 0, tzinfo=UTC))  # 00:30 on the 6th in India
    assert desk.ok(desk.post("/requests", body(received_on="2026-11-06")))["received_on"] == "2026-11-06"
    assert desk.post("/requests", body(received_on="2026-11-07")).status_code == 422


BAD_BODIES = {
    "no applicant": {"applicant": None},
    "no applicant name": {"applicant": {"address": "x"}},
    "blank applicant name": {"applicant": {"name": "   "}},
    "name too long": {"applicant": {"name": "a" * 201}},
    "address too long": {"applicant": {"name": "A", "address": "a" * 1001}},
    "email without domain": {"applicant": {"name": "A", "email": "asha@"}},
    "email with spaces": {"applicant": {"name": "A", "email": "a b@example.org"}},
    "email too long": {"applicant": {"name": "A", "email": "a@" + "b" * 250 + ".org"}},
    "phone too long": {"applicant": {"name": "A", "phone": "9" * 41}},
    "person id not a uuid": {"applicant": {"name": "A", "person_id": "asha"}},
    "unknown applicant field": {"applicant": {"name": "A", "caste": "x"}},
    "channel unknown": {"received_via": "pigeon"},
    "no channel": {"received_via": None},
    "received_on not a date": {"received_on": "yesterday"},
    "received_on before 1900": {"received_on": "1899-12-31"},
    "received_on year 0001": {"received_on": "0001-01-01"},
    "received_on year 9999": {"received_on": "9999-12-31"},
    "received_on tomorrow": {"received_on": days(1)},
    "subject too short": {"subject": "ab"},
    "subject blank": {"subject": "     "},
    "subject too long": {"subject": "s" * 201},
    "information too short": {"information_sought": "x"},
    "information too long": {"information_sought": "x" * 10_001},
    "fee status unknown": {"fee": {"status": "waived"}},
    "no fee": {"fee": None},
    "fee amount negative": {"fee": {"status": "paid", "amount": {"amount": "-1"}}},
    "fee amount a float": {"fee": {"status": "paid", "amount": {"amount": 10.5}}},
    "fee amount three decimals": {"fee": {"status": "paid", "amount": {"amount": "1.234"}}},
    "fee amount too big": {"fee": {"status": "paid", "amount": {"amount": "12345678901"}}},
    "fee amount exponent": {"fee": {"status": "paid", "amount": {"amount": "1e3"}}},
    "currency lower case": {"fee": {"status": "paid", "amount": {"amount": "1", "currency": "inr"}}},
    "fee mode too long": {"fee": {"status": "paid", "mode": "m" * 101}},
    "receipt too long": {"fee": {"status": "paid", "receipt_reference": "r" * 101}},
    "extra field": {"priority": "urgent"},
    "NUL in subject": {"subject": "Faculty\u0000 recruitment"},
    "NUL in nested name": {"applicant": {"name": "Asha\u0000"}},
    "NUL in fee mode": {"fee": {"status": "paid", "mode": "cash\u0000"}},
}


@pytest.mark.parametrize("name", sorted(BAD_BODIES))
def test_a_bad_body_is_a_422_never_a_500(desk, name):
    assert desk.post("/requests", body(**BAD_BODIES[name])).status_code == 422, name


def test_a_body_that_is_not_an_object_is_a_422(desk):
    for raw in ([], "text", 5, None):
        assert desk.post("/requests", raw).status_code == 422


def test_the_extremes_that_are_allowed_are_accepted(desk):
    r = desk.ok(
        desk.post(
            "/requests",
            body(
                received_on="1900-01-01",
                applicant={"name": "A" * 200, "address": "a" * 1000, "email": "a@b.co", "phone": "9" * 40},
                subject="s" * 200,
                information_sought="x" * 10_000,
                fee={"status": "paid", "amount": {"amount": "9999999999.99"}},
            ),
        )
    )
    assert r["fee"]["amount"]["amount"] == "9999999999.99"
    assert r["overdue"] is True


# ---------------------------------------------------------------- reading


def test_the_detail_has_everything_and_each_read_is_audited(desk, org):
    r = desk.request()
    d = desk.ok(desk.get(f"/requests/{r['id']}"))
    assert d["referrals"] == [] and d["response"] is None and d["transfer"] is None and d["appeal"] is None
    desk.ok(desk.get(f"/requests/{r['id']}"))
    assert audit(org.id, r["id"]) == sorted(["request.recorded", "request.read", "request.read"])


@pytest.mark.parametrize(
    "path", ["/requests/00000000-0000-4000-8000-000000000000", "/requests/not-a-uuid", "/requests/a%00b"]
)
def test_an_unknown_request_is_404(desk, path):
    assert desk.get(path).status_code == 404
    assert desk.patch(path, {"subject": "Anything"}).status_code == 404
    assert desk.post(path + "/close").status_code == 404


def test_the_list_is_newest_first_and_each_row_read_is_audited(desk, org):
    made = [desk.request(subject=f"Request number {n}") for n in range(3)]
    page = desk.ok(desk.get("/requests"))
    assert [i["number"] for i in page["items"]] == ["RTI-000003", "RTI-000002", "RTI-000001"]
    assert page["next_cursor"] is None
    assert audit(org.id, made[0]["id"]) == sorted(["request.recorded", "request.read"])


def test_paging_walks_every_request_once(desk):
    numbers = [desk.request()["number"] for _ in range(5)]
    seen, cursor = [], None
    for _ in range(10):
        url = "/requests?limit=2" + (f"&cursor={cursor}" if cursor else "")
        page = desk.ok(desk.get(url))
        seen += [i["number"] for i in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == numbers[::-1]


@pytest.mark.parametrize(
    "cursor", ["abc", "-1", "1.5", "١٢", "1e3", "0x10", " 1", "1 ", "99999999", "1" * 17, "a%00b", "٣"]
)
def test_a_cursor_that_is_not_plain_digits_is_a_422(desk, cursor):
    for path in ("/requests", "/referrals"):
        assert desk.get(f"{path}?cursor={cursor}").status_code == 422, (path, cursor)


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=101", "limit=-1", "limit=abc", "limit=1.5", "limit=99999999999999999999"]
)
def test_a_bad_limit_is_a_422(desk, query):
    assert desk.get(f"/requests?{query}").status_code == 422


def test_filters(desk):
    a = desk.request(subject="Alpha 100% records", received_via="post")
    b = desk.assigned(subject="Beta records", received_via="email")
    c = desk.responded()
    ids = lambda q: [i["id"] for i in desk.ok(desk.get(f"/requests{q}"))["items"]]  # noqa: E731
    assert ids("?status=received") == [a["id"]]
    assert sorted(ids("?status=received,assigned")) == sorted([a["id"], b["id"]])
    assert ids("?status=responded") == [c["id"]]
    assert ids("?received_via=email") == [b["id"]]
    assert ids("?q=BETA") == [b["id"]]
    assert ids(f"?q={a['number'].lower()}") == [a["id"]]
    assert ids("?q=100%25") == [a["id"]]  # a % in q is a character, not a wildcard
    assert ids("?q=%25") == [a["id"]]
    assert ids("?q=_") == []  # nor is _
    assert len(ids("?q=")) == 3 and len(ids("?q=%20%20")) == 3  # blank means no filter
    assert sorted(ids(f"?officer={desk.officer_id}")) == sorted([b["id"], c["id"]])
    assert sorted(ids("?officer=me")) == sorted([b["id"], c["id"]])
    assert ids(f"?officer={desk.officer_id.upper()}") == ids("?officer=me")


@pytest.mark.parametrize(
    "query",
    [
        "status=bogus",
        "status=received,bogus",
        "officer=nobody",
        "officer=00000000-0000-4000-8000-000000000000,00000000-0000-4000-8000-000000000001",
        "received_via=pigeon",
        "overdue=perhaps",
        "q=" + "x" * 201,
        "status=" + "x" * 201,
        "q=a%00b",
        "status=a%00b",
        "officer=a%00b",
    ],
)
def test_a_bad_filter_is_a_422(desk, query):
    assert desk.get(f"/requests?{query}").status_code == 422, query


def test_the_overdue_filter(desk):
    late = desk.request(received_on=days(-40))  # due 5 days ago
    fine = desk.request(received_on=days(-10))
    answered = desk.respond(desk.assigned(received_on=days(-60))["id"])  # responded: not waiting on anything
    got = lambda q: [i["id"] for i in desk.ok(desk.get(f"/requests{q}"))["items"]]  # noqa: E731
    assert desk.ok(desk.get(f"/requests/{late['id']}"))["overdue"] is True
    assert got("?overdue=true") == [late["id"]]
    assert sorted(got("?overdue=false")) == sorted([fine["id"], answered["id"]])
    assert got("?overdue=true&status=assigned") == []
    # paging after the filter
    more = [desk.request(received_on=days(-50)) for _ in range(2)]
    page = desk.ok(desk.get("/requests?overdue=true&limit=2"))
    assert len(page["items"]) == 2 and page["next_cursor"]
    rest = desk.ok(desk.get(f"/requests?overdue=true&limit=2&cursor={page['next_cursor']}"))
    assert len(rest["items"]) == 1 and rest["next_cursor"] is None
    assert {i["id"] for i in page["items"] + rest["items"]} == {late["id"], *(m["id"] for m in more)}


def test_due_today_is_not_overdue_until_the_day_has_passed(desk, clock):
    r = desk.request(received_on=days(-30))  # due today
    assert desk.ok(desk.get(f"/requests/{r['id']}"))["overdue"] is False
    clock.set(datetime(2026, 11, 5, 18, 29, 59, tzinfo=UTC))  # the last second of the 5th in India
    assert desk.ok(desk.get(f"/requests/{r['id']}"))["overdue"] is False
    clock.set(datetime(2026, 11, 5, 18, 30, 0, tzinfo=UTC))
    assert desk.ok(desk.get(f"/requests/{r['id']}"))["overdue"] is True


def test_a_changed_setting_applies_to_requests_already_recorded(desk, settings):
    r = desk.request(received_on=days(-10))
    assert desk.ok(desk.get(f"/requests/{r['id']}"))["overdue"] is False
    settings(response_days=5)  # worked out when read, not stored
    got = desk.ok(desk.get(f"/requests/{r['id']}"))
    assert got["overdue"] is True and got["due_at"] == "2026-10-31T18:29:59+00:00"


# ---------------------------------------------------------------- correcting


def test_correcting_replaces_the_applicant_and_the_fee_and_is_audited(desk, org):
    r = desk.request()
    patched = desk.ok(
        desk.patch(
            f"/requests/{r['id']}",
            {
                "applicant": {"name": "Asha K. Verma", "email": "asha@example.org"},
                "fee": {"status": "pending"},
                "subject": "Admission records of 2024",
            },
        )
    )
    assert patched["applicant"] == {"name": "Asha K. Verma", "email": "asha@example.org", "person_id": None}
    assert patched["fee"] == {"status": "pending"}
    assert patched["subject"] == "Admission records of 2024"
    assert patched["information_sought"] == r["information_sought"]  # not sent, not changed
    assert audit(org.id, r["id"]) == sorted(["request.recorded", "request.corrected"])
    assert desk.ok(desk.patch(f"/requests/{r['id']}", {"information_sought": "The cut-off marks."}))["subject"] == (
        "Admission records of 2024"
    )


def test_a_correction_can_be_made_while_assigned_only(desk):
    r = desk.assigned()
    assert desk.patch(f"/requests/{r['id']}", {"subject": "A better subject"}).status_code == 200
    desk.respond(r["id"])
    refused = desk.patch(f"/requests/{r['id']}", {"subject": "Too late now"})
    assert (refused.status_code, refused.json()["detail"]["code"]) == (409, "invalid_status")


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"subject": None},
        {"subject": "ab"},
        {"applicant": {}},
        {"fee": {"status": "gift"}},
        {"status": "closed"},
        {"number": "RTI-000009"},
    ],
)
def test_a_bad_correction_is_a_422(desk, bad):
    r = desk.request()
    assert desk.patch(f"/requests/{r['id']}", bad).status_code == 422, bad


# ---------------------------------------------------------------- assigning


def test_assigning_and_reassigning(desk, org):
    r = desk.request()
    first = desk.ok(desk.post(f"/requests/{r['id']}/assign", {"officer_id": desk.officer_id}))
    assert (first["status"], first["officer_id"]) == ("assigned", desk.officer_id) and first["assigned_at"]
    other = "00000000-0000-4000-8000-0000000000AA"
    second = desk.ok(desk.post(f"/requests/{r['id']}/assign", {"officer_id": other}))
    assert (second["status"], second["officer_id"]) == ("assigned", other.lower())
    assert audit(org.id, r["id"]) == sorted(["request.recorded", "request.assigned", "request.assigned"])


def test_assigning_a_request_that_was_answered_is_409(desk):
    r = desk.responded()
    refused = desk.post(f"/requests/{r['id']}/assign", {"officer_id": desk.officer_id})
    assert (refused.status_code, refused.json()["detail"]["code"]) == (409, "invalid_status")


@pytest.mark.parametrize(
    "bad", [{}, {"officer_id": "me"}, {"officer_id": None}, {"officer_id": 5}, {"officer_id": "x", "extra": 1}]
)
def test_assigning_to_something_that_is_not_a_person_id_is_422(desk, bad):
    r = desk.request()
    assert desk.post(f"/requests/{r['id']}/assign", bad).status_code == 422


def test_a_bad_setting_is_a_deployment_error_not_a_caller_error(desk, settings):
    settings(response_days="soon")
    with pytest.raises(ValueError, match="RTI_RESPONSE_DAYS"):
        desk.client.post("/api/v1/rti/requests", json=body(), headers=desk.officer)
