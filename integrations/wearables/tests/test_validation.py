"""Bad input is invalid_request with the field named and the value never echoed: never an exception, never a provider call.
Every string, number, list and date is bounded; NaN and Infinity are refused."""

from __future__ import annotations

import uuid

import pytest
from wear_support import link_input

BIG = "x" * 100_000
PERSON = "00000000-0000-4000-8000-0000000000a1"
LINK = {
    "person id": link_input("nope", "strava"),
    "person missing": {k: v for k, v in link_input(PERSON, "strava").items() if k != "person_id"},
    "provider empty": link_input(PERSON, ""),
    "provider huge": link_input(PERSON, BIG),
    "types not list": link_input(PERSON, "strava", data_types="activity"),
    "types unknown": link_input(PERSON, "strava", data_types=["everything"]),
    "types too many": link_input(PERSON, "strava", data_types=["activity"] * 6),
    "return url": link_input(PERSON, "strava", return_url="javascript:alert(1)"),
    "return url huge": link_input(PERSON, "strava", return_url="https://x.example/" + BIG),
    "link id": link_input(PERSON, "strava", account_link_id="x"),
    "state missing": {k: v for k, v in link_input(PERSON, "strava").items() if k != "state"},
    "state huge": link_input(PERSON, "strava", state=BIG),
    "state control char": link_input(PERSON, "strava", state="a\x00b"),
    "challenge short": link_input(PERSON, "strava", code_challenge="abc"),
    "challenge chars": link_input(PERSON, "strava", code_challenge="!" * 43),
    "redirect": link_input(PERSON, "strava", redirect_uri="ftp://x"),
    "redirect huge": link_input(PERSON, "strava", redirect_uri="https://x.example/" + BIG),
    "minor not bool": link_input(PERSON, "strava", minor="maybe"),
}


@pytest.mark.parametrize("name", LINK)
def test_link_account_refuses_bad_input_without_calling_anyone(adapter, transport, org, name):
    r = adapter.link_account(org.ctx("strava"), LINK[name])
    assert r.output is None and r.error["code"] == "invalid_request" and r.error["retryable"] is False
    assert len(r.error["detail"]) < 400 and "xxxx" not in r.error["detail"] and "javascript" not in r.error["detail"]
    assert not transport.requests


@pytest.mark.parametrize("input_", [None, [], "x", 5, {}, {"account_link_id": "x"}, {"account_link_id": ""}])
@pytest.mark.parametrize("op", ["link_account", "unlink_account", "sync", "request_backfill", "read", "link_status"])
def test_every_operation_refuses_a_malformed_input_object(adapter, transport, org, op, input_):
    r = getattr(adapter, op)(org.ctx("strava"), input_)
    assert r.error["code"] == "invalid_request" and not transport.requests


@pytest.mark.parametrize(
    ("op", "input_"),
    [
        ("unlink_account", {"account_link_id": str(uuid.uuid4()), "reason": BIG}),
        ("unlink_account", {"account_link_id": str(uuid.uuid4()), "reason": "a\x00b"}),
        ("sync", {"account_link_id": str(uuid.uuid4()), "from": "yesterday"}),
        ("sync", {"account_link_id": str(uuid.uuid4()), "from": "1999-12-31"}),
        ("sync", {"account_link_id": str(uuid.uuid4()), "to": "2101-01-01"}),
        ("sync", {"account_link_id": str(uuid.uuid4()), "from": "2026-11-05", "to": "2026-11-01"}),
        ("sync", {"account_link_id": str(uuid.uuid4()), "from": "2020-01-01", "to": "2026-11-05"}),
        ("sync", {"account_link_id": str(uuid.uuid4()), "from": 20261105}),
        ("sync", {"account_link_id": str(uuid.uuid4()), "data_types": ["sleep"] * 6}),
        ("sync", {"account_link_id": str(uuid.uuid4()), "data_types": [None]}),
        ("request_backfill", {"account_link_id": str(uuid.uuid4()), "from": float("nan")}),
        ("link_status", {"person_ids": ["x"]}),
        ("link_status", {"person_ids": [str(uuid.uuid4())] * 201}),
        ("link_status", {"person_ids": "x"}),
        ("link_status", {}),
    ],
)  # fmt: skip
def test_other_operations_refuse_bad_fields(adapter, transport, org, op, input_):
    r = getattr(adapter, op)(org.ctx("strava"), input_)
    assert r.error["code"] == "invalid_request" and not transport.requests


def test_two_hundred_person_ids_are_fine(adapter, org):
    assert adapter.link_status(org.ctx("strava"), {"person_ids": [str(uuid.uuid4()) for _ in range(200)]}).output == {
        "items": []
    }


def test_the_valid_extremes_are_accepted(adapter, org):
    assert (
        adapter.read(
            org.ctx("polar"),
            {
                "person_id": PERSON,
                "data_type": "sleep",
                "from": "2000-01-01",
                "to": "2002-01-01",
                "purpose": "a" * 40,
                "limit": 500,
            },
        ).error["code"]
        == "consent_required"
    )


@pytest.mark.parametrize("ctx", [None, "x", {}, {"organisation_id": "o"}, {"organisation_id": "o", "connection_id": "c", "provider": "strava", "mode": "yolo"},
                                 {"organisation_id": "o", "connection_id": "c", "provider": "strava", "settings": []},
                                 {"organisation_id": "o", "connection_id": "c", "provider": "nonesuch"}])  # fmt: skip
def test_a_malformed_call_context_is_an_error_result(adapter, ctx):
    r = adapter.sync(ctx, {"account_link_id": str(uuid.uuid4())})
    assert r.output is None and r.error["code"] in ("invalid_request", "not_configured", "not_found")


@pytest.mark.parametrize("bad", [None, {}, {"state": "s"}, {"state": "s", "code_challenge": "C" * 43, "redirect_uri": "ftp://x"}, {"state": BIG, "code_challenge": "C" * 43, "redirect_uri": "https://x.example"},
                                 {"state": "s", "code_challenge": "C" * 43, "redirect_uri": "https://x.example", "scope_hint": "x"}])  # fmt: skip
def test_authorisation_inputs_are_checked_too(adapter, org, bad):
    assert adapter.begin_authorisation(org.ctx("strava"), bad).error["code"] == "invalid_request"
    assert adapter.complete_authorisation(org.ctx("strava"), bad).error["code"] == "invalid_request"


def test_the_unexpected_is_a_generic_error_that_leaks_nothing(adapter, org, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret-internal-detail athlete@example.com")

    monkeypatch.setattr(adapter, "_link_new", boom)
    r = adapter.link_account(org.ctx("strava"), link_input(PERSON, "strava"))
    assert r.error["code"] == "provider_error" and "secret-internal" not in str(r.error)
