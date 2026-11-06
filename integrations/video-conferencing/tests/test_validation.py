"""Bad input is invalid_request with the field named and the value never echoed: never an exception, never a provider call.
Every string, number, list and date is bounded; NaN and Infinity are refused."""

from __future__ import annotations

import json
import uuid

import pytest
from vc_support import START, create_input

BIG = "x" * 100_000


def bad(**over):
    return create_input("k", **over)


CREATE_CASES = {
    "key empty": bad(meeting_key=""),
    "key huge": bad(meeting_key=BIG),
    "key with space": bad(meeting_key="a b"),
    "key not a string": bad(meeting_key=5),
    "key null": bad(meeting_key=None),
    "title empty": bad(title=""),
    "title huge": bad(title=BIG),
    "title control char": bad(title="a\x00b"),
    "title newline": bad(title="a\nb"),
    "title list": bad(title=["x"]),
    "starts naive": bad(starts_at="2026-11-09T04:30:00"),
    "starts garbage": bad(starts_at="tomorrow"),
    "starts year 9999": bad(starts_at="9999-01-01T00:00:00+00:00"),
    "starts year 1": bad(starts_at="0001-01-01T00:00:00+00:00"),
    "starts number": bad(starts_at=1e308),
    "starts nan": bad(starts_at=float("nan")),
    "duration zero": bad(duration_minutes=0),
    "duration negative": bad(duration_minutes=-5),
    "duration huge": bad(duration_minutes=10**30),
    "duration day+1": bad(duration_minutes=1441),
    "duration float": bad(duration_minutes=45.5),
    "duration nan": bad(duration_minutes=float("nan")),
    "duration inf": bad(duration_minutes=float("inf")),
    "duration -inf": bad(duration_minutes=float("-inf")),
    "duration bool": bad(duration_minutes=True),
    "duration string": bad(duration_minutes="45"),
    "duration null": bad(duration_minutes=None),
    "timezone junk": bad(timezone="Not/AZone"),
    "timezone path": bad(timezone="../../etc/passwd"),
    "timezone huge": bad(timezone="A" * 5000),
    "timezone empty": bad(timezone=""),
    "host missing": {k: v for k, v in bad().items() if k != "host"},
    "host string": bad(host="teacher@college.example.com"),
    "host email junk": bad(host={"email": "not an email"}),
    "host email huge": bad(host={"email": "a" * 400 + "@x.example.com"}),
    "host email with comma": bad(host={"email": "a@x.example.com,b@x.example.com"}),
    "host person id": bad(host={"email": "t@college.example.com", "person_id": "nope"}),
    "host provider user path": bad(host={"provider_user_id": "../../admin"}),
    "host provider user huge": bad(host={"provider_user_id": BIG}),
    "cohost too many": bad(co_hosts=[{"email": f"c{i}@college.example.com"} for i in range(51)]),
    "cohost not list": bad(co_hosts="x"),
    "cohost entry bad": bad(co_hosts=[{"email": "nope"}]),
    "options record": bad(options={"record": "everywhere"}),
    "options waiting room": bad(options={"waiting_room": "maybe"}),
    "options domain": bad(options={"auto_admit_domain": "evil.com/../x"}),
    "meeting id": bad(meeting_id="not-a-uuid"),
    "caller module": bad(caller_module="Has Space"),
}


@pytest.mark.parametrize("name", CREATE_CASES)
@pytest.mark.parametrize("provider", ["zoom", "teams", "webex", "jitsi"])
def test_create_refuses_bad_input_without_calling_anyone(adapter, transport, org, provider, name):
    r = adapter.create_meeting(org.ctx(provider), CREATE_CASES[name])
    assert r.output is None and r.error["code"] == "invalid_request" and r.error["retryable"] is False
    assert len(r.error["detail"]) < 400 and "xxxx" not in r.error["detail"] and "etc/passwd" not in r.error["detail"]
    assert not transport.requests


@pytest.mark.parametrize("input_", [None, [], "x", 5, {}, {"meeting_key": ""}])
@pytest.mark.parametrize(
    "op",
    [
        "create_meeting",
        "update_meeting",
        "cancel_meeting",
        "join_link",
        "get_meeting",
        "fetch_attendance",
        "list_recordings",
        "import_recording",
    ],
)
def test_every_operation_refuses_a_malformed_input_object(adapter, transport, org, op, input_):
    r = getattr(adapter, op)(org.ctx("zoom"), input_)
    assert r.error["code"] == "invalid_request" and not transport.requests


@pytest.mark.parametrize(
    ("op", "input_"),
    [
        ("update_meeting", {"meeting_key": "k", "duration_minutes": float("nan")}),
        ("update_meeting", {"meeting_key": "k", "starts_at": "2026-11-09T04:30:00"}),
        ("update_meeting", {"meeting_key": "k", "title": BIG}),
        ("cancel_meeting", {"meeting_key": "k", "reason": BIG}),
        ("cancel_meeting", {"meeting_key": "k", "reason": "a\x00b"}),
        ("join_link", {"meeting_key": "k", "person_id": "x", "display_name": "A"}),
        ("join_link", {"meeting_key": "k", "person_id": str(uuid.uuid4()), "display_name": ""}),
        ("join_link", {"meeting_key": "k", "person_id": str(uuid.uuid4()), "display_name": "A", "role": "emperor"}),
        ("join_link", {"meeting_key": "k", "person_id": str(uuid.uuid4()), "display_name": "A" * 500}),
        ("fetch_attendance", {"meeting_key": "k", "roster": [{"person_id": "x", "email": "a@b.example.com"}]}),
        ("fetch_attendance", {"meeting_key": "k", "roster": [{"person_id": str(uuid.uuid4()), "email": "nope"}] * 3}),
        ("fetch_attendance", {"meeting_key": "k", "roster": "x"}),
        ("import_recording", {"meeting_key": "k", "provider_recording_id": "../x"}),
        ("import_recording", {"meeting_key": "k", "provider_recording_id": ""}),
        ("import_recording", {"meeting_key": "k", "provider_recording_id": BIG}),
    ],
)  # fmt: skip
def test_other_operations_refuse_bad_fields(adapter, transport, org, op, input_):
    r = getattr(adapter, op)(org.ctx("zoom"), input_)
    assert r.error["code"] == "invalid_request" and not transport.requests


def test_a_roster_of_five_thousand_is_fine_and_five_thousand_and_one_is_not(adapter, org):
    one = {"person_id": str(uuid.uuid4()), "email": "a@college.example.com"}
    assert (
        adapter.fetch_attendance(org.ctx("zoom"), {"meeting_key": "k", "roster": [one] * 5001}).error["code"]
        == "invalid_request"
    )
    assert (
        adapter.fetch_attendance(org.ctx("zoom"), {"meeting_key": "k", "roster": [one] * 5000}).error["code"]
        == "not_found"
    )


def test_valid_extremes_are_accepted(adapter, transport, org):
    transport.on("POST", r"oauth/token", "zoom/token_s2s.json")
    transport.on("POST", r"/meetings$", "zoom/create_meeting.json", status=201)
    ok = create_input(
        "k" * 128,
        title="t" * 300,
        duration_minutes=1440,
        starts_at="2000-01-01T00:00:00+00:00",
        timezone="Pacific/Kiritimati",
    )
    assert adapter.create_meeting(org.ctx("zoom"), ok).error is None


def test_input_errors_name_fields_not_values(adapter, org):
    e = adapter.create_meeting(org.ctx("zoom"), bad(duration_minutes=0, title="secret-title\x00")).error
    assert "duration_minutes" in e["detail"] and "title" in e["detail"] and "secret-title" not in e["detail"]


@pytest.mark.parametrize("ctx", [None, "x", {}, {"organisation_id": "o"}, {"organisation_id": "o", "connection_id": "c", "provider": "zoom", "mode": "yolo"},
                                 {"organisation_id": "o", "connection_id": "c", "provider": "zoom", "settings": []},
                                 {"organisation_id": "o", "connection_id": "c", "provider": "nonesuch"}])  # fmt: skip
def test_a_malformed_call_context_is_an_error_result(adapter, ctx):
    r = adapter.create_meeting(ctx, create_input())
    assert r.output is None and r.error["code"] in ("invalid_request", "not_configured")


def test_the_unexpected_is_a_generic_error_that_leaks_nothing(adapter, org, monkeypatch, caplog):
    def boom(*a, **k):
        raise RuntimeError("secret-internal-detail teacher@college.example.com")

    monkeypatch.setattr(adapter, "_create", boom)
    r = adapter.create_meeting(org.ctx("zoom"), create_input())
    assert r.error["code"] == "provider_error" and "secret-internal" not in json.dumps(r.error)


_ = START
