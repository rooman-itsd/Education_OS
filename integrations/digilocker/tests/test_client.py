"""The HTTP client: wire format against recorded request/response pairs, and the PRD's error mapping."""

from datetime import date

import httpx
import pytest
from dgl_support import NOW, PUSH_ID, PUSH_SECRET, Replay, fixed_clock
from eos_digilocker.domain.errors import AdapterError
from eos_digilocker.infrastructure.client import DigiLockerClient, raise_for_response

BASE = "https://sandbox.digilocker.invalid/public"


def client_for(*names, **kw):
    replay = Replay(*names)
    return DigiLockerClient(replay.client(), BASE, clock=fixed_clock, **kw), replay


def push(client, action="A"):
    client.push_uri(
        client_id=PUSH_ID,
        client_secret=PUSH_SECRET,
        digilocker_id="dl-holder-0001",
        uri="in.ac.example-DGCER-DEG-2026-0001",
        doc_type="DGCER",
        description="B.Sc. Physics degree",
        doc_id="DEG-2026-0001",
        issue_date=date(2026, 11, 5),
        valid_from=None,
        valid_to=None,
        action=action,
    )


def test_push_uri_sends_exactly_the_recorded_request():
    client, replay = client_for("push_uri_accepted.json")
    push(client)  # Replay fails on any request that is not byte-for-byte the recorded fields and HMAC
    assert len(replay.seen) == 1


def test_recorded_refusals_map_to_the_contract_codes():
    """The recorded HMAC-refused and stale-ts answers, replayed through the real client path."""
    from dgl_support import fixture

    for name, code, retryable, provider_code in (
        ("push_uri_hmac_refused.json", "auth_failed", False, "invalid_hmac"),
        ("push_uri_stale_ts.json", "provider_error", True, "invalid_ts"),  # the next attempt signs a fresh ts
    ):
        replay = Replay(name)
        form = fixture(name)["request"]["form"]
        response = replay.client().post("https://sandbox.digilocker.invalid/public/account/1/pushuri", data=form)
        with pytest.raises(AdapterError) as e:
            raise_for_response(response)
        assert (e.value.code, e.value.retryable, e.value.provider_code) == (code, retryable, provider_code)


def test_the_status_mapping():
    cases = {400: "invalid_request", 401: "auth_failed", 403: "auth_failed", 404: "not_found", 422: "invalid_request",
             429: "throttled", 500: "provider_error", 502: "provider_error", 503: "provider_error"}  # fmt: skip
    for status, code in cases.items():
        with pytest.raises(AdapterError) as e:
            raise_for_response(httpx.Response(status, text="<html>provider prose, with a name: Asha Rao</html>"))
        assert e.value.code == code and e.value.provider_code == str(status)
        assert "Asha" not in e.value.detail and "html" not in e.value.detail  # provider text never leaves
    with pytest.raises(AdapterError) as e:
        raise_for_response(httpx.Response(401), token_call=True)
    assert e.value.code == "consent_required"


def test_throttled_carries_a_bounded_retry_after():
    for header, expected in (("30", 30), ("999999", 3600), ("0", 1), ("soon", None), ("-5", 1)):
        with pytest.raises(AdapterError) as e:
            raise_for_response(httpx.Response(429, headers={"retry-after": header}))
        assert e.value.retry_after_s == expected, header


def test_a_provider_error_code_must_be_well_formed_to_be_passed_on():
    with pytest.raises(AdapterError) as e:
        raise_for_response(httpx.Response(400, json={"error": "<script>alert(1)</script>"}))
    assert e.value.provider_code == "400"


def test_network_failures_are_transport_unavailable_and_retryable():
    for exc in (
        httpx.ConnectTimeout("t"),
        httpx.ConnectError("c"),
        httpx.ReadTimeout("r"),
        httpx.RemoteProtocolError("p"),
    ):

        def boom(request, exc=exc):
            raise exc

        client = DigiLockerClient(httpx.Client(transport=httpx.MockTransport(boom)), BASE, clock=fixed_clock)
        with pytest.raises(AdapterError) as e:
            push(client)
        assert (e.value.code, e.value.retryable) == ("transport_unavailable", True)


def test_a_push_that_went_stale_while_being_built_is_not_sent():
    ticks = iter([NOW, NOW.replace(minute=45)])
    replay = Replay("push_uri_accepted.json")
    client = DigiLockerClient(replay.client(), BASE, clock=lambda: next(ticks), push_max_age_s=60)
    with pytest.raises(AdapterError) as e:
        push(client)
    assert e.value.code == "provider_error" and replay.seen == []


def test_account_verify_matches_the_recorded_pairs():
    found, _ = client_for("account_verify_found.json")
    assert found.find_account(client_id=PUSH_ID, client_secret=PUSH_SECRET, mobile="+919800000001") == "dl-holder-0001"
    missing, _ = client_for("account_verify_notfound.json")
    assert missing.find_account(client_id=PUSH_ID, client_secret=PUSH_SECRET, mobile="+919800000001") is None


def test_an_unreadable_answer_is_a_provider_error():
    c = DigiLockerClient(
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="<html>"))), BASE
    )
    with pytest.raises(AdapterError) as e:
        c.find_account(client_id="a", client_secret="b", mobile="+919800000001")
    assert e.value.code == "provider_error"
