"""Provider callbacks: signature verification with known-good and tampered payloads, the handshakes (Zoom's url_validation,
Graph's validationToken), and what each verified event does. verify_inbound answers before anything is processed;
parse_inbound runs after the acknowledgement."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_video_conferencing.infrastructure import crypto
from eos_video_conferencing.infrastructure.config import Config
from eos_video_conferencing.infrastructure.models import AuditEntry, GraphSubscription, Meeting, Recording
from sqlalchemy import select
from vc_support import WEBEX_SECRET, ZOOM_SECRET, create_input, fixture, request, zoom_signature

API = r"https://api\.zoom\.us/v2"
NOW_TS = 1793858400  # 2026-11-05 06:00:00 UTC, the tests' clock


def zoom_org_meeting(adapter, transport, org, key="class-session-1"):
    transport.on("POST", r"oauth/token\?grant_type=account_credentials", "zoom/token_s2s.json")
    transport.on("POST", API + r"/users/.+/meetings$", "zoom/create_meeting.json", status=201)
    assert adapter.create_meeting(org.ctx("zoom"), create_input(key)).error is None


def signed(name: str, ts: int = NOW_TS, secret: str = ZOOM_SECRET) -> dict:
    raw = fixture(name).encode()
    return request(raw, zoom_signature(raw, ts, secret))


def verdict(adapter, req, ctx=None) -> dict:
    r = adapter.verify_inbound(ctx, req)
    assert r.error is None
    return r.output


# --- Zoom -------------------------------------------------------------------------------------------------------


def test_a_correctly_signed_zoom_event_is_accepted_and_names_its_connection(adapter, transport, org):
    zoom_org_meeting(adapter, transport, org)
    v = verdict(adapter, signed("zoom/event_meeting_ended.json"))
    assert v["verdict"] == "accept" and v["resolves_to"] == {
        "connection_id": org.connection_id,
        "account_link_subject": "Qm8kAccountId01",
    }
    assert v["dedupe_key"] == hashlib.sha256(fixture("zoom/event_meeting_ended.json").encode()).hexdigest()
    assert (
        verdict(adapter, signed("zoom/event_meeting_ended.json"))["dedupe_key"] == v["dedupe_key"]
    )  # a redelivery has the same key


def test_a_zoom_event_for_a_meeting_we_did_not_create_is_accepted_but_resolves_to_nothing(adapter):
    v = verdict(adapter, signed("zoom/event_meeting_ended.json"))
    assert v["verdict"] == "accept" and v["resolves_to"]["connection_id"] is None


def test_the_signature_formula_is_zooms_documented_v0_hmac(adapter):
    raw = fixture("zoom/event_meeting_ended.json").encode()
    expected = "v0=" + hmac.new(ZOOM_SECRET.encode(), b"v0:1793858400:" + raw, hashlib.sha256).hexdigest()
    assert zoom_signature(raw, NOW_TS)["x-zm-signature"] == expected
    assert (
        verdict(adapter, request(raw, {"X-ZM-Signature": expected, "X-ZM-Request-Timestamp": str(NOW_TS)}))["verdict"]
        == "accept"
    )  # header names are case-insensitive


@pytest.mark.parametrize(
    "mutate",
    ["body", "secret", "stale", "future", "no_signature", "no_timestamp", "bad_prefix", "non_numeric_ts", "empty_sig"],
)
def test_a_zoom_event_that_does_not_verify_is_rejected_with_401(adapter, mutate):
    raw = fixture("zoom/event_meeting_ended.json").encode()
    headers = zoom_signature(raw, NOW_TS)
    if mutate == "body":
        raw = raw.replace(b"85746065432", b"99999999999")
    elif mutate == "secret":
        headers = zoom_signature(raw, NOW_TS, "not-the-secret")
    elif mutate == "stale":
        headers = zoom_signature(raw, NOW_TS - 301)
    elif mutate == "future":
        headers = zoom_signature(raw, NOW_TS + 301)
    elif mutate == "no_signature":
        headers.pop("x-zm-signature")
    elif mutate == "no_timestamp":
        headers.pop("x-zm-request-timestamp")
    elif mutate == "bad_prefix":
        headers["x-zm-signature"] = headers["x-zm-signature"].replace("v0=", "v1=")
    elif mutate == "non_numeric_ts":
        headers = zoom_signature(raw, "12abc")
    elif mutate == "empty_sig":
        headers["x-zm-signature"] = ""
    assert verdict(adapter, request(raw, headers)) == {"verdict": "reject", "reject_status": 401}


def test_the_tolerance_edge_is_inclusive_and_configurable(adapter, monkeypatch):
    assert verdict(adapter, signed("zoom/event_meeting_ended.json", NOW_TS - 300))["verdict"] == "accept"
    monkeypatch.setenv("VIDEO_CONFERENCING_WEBHOOK_TOLERANCE_S", "10")
    assert verdict(adapter, signed("zoom/event_meeting_ended.json", NOW_TS - 11))["verdict"] == "reject"


def test_without_a_configured_secret_nothing_verifies(adapter, monkeypatch):
    monkeypatch.delenv("VIDEO_CONFERENCING_ZOOM_WEBHOOK_SECRET_TOKEN")
    assert verdict(adapter, signed("zoom/event_meeting_ended.json"))["verdict"] == "reject"


def test_zoom_url_validation_is_answered_with_the_encrypted_token(adapter):
    raw = fixture("zoom/event_url_validation.json").encode()
    v = verdict(adapter, request(raw, zoom_signature(raw, NOW_TS)))
    assert (
        v["verdict"] == "handshake"
        and v["handshake_response"]["status"] == 200
        and v["handshake_response"]["content_type"] == "application/json"
    )
    body = json.loads(v["handshake_response"]["body"])
    assert body == {
        "plainToken": "qgg8vlvZRS6UYooatFL8Aw",
        "encryptedToken": hmac.new(ZOOM_SECRET.encode(), b"qgg8vlvZRS6UYooatFL8Aw", hashlib.sha256).hexdigest(),
    }


def test_url_validation_with_the_wrong_secret_proves_nothing_to_zoom(adapter, monkeypatch):
    raw = fixture("zoom/event_url_validation.json").encode()
    monkeypatch.setenv("VIDEO_CONFERENCING_ZOOM_WEBHOOK_SECRET_TOKEN", "some-other-secret")
    body = json.loads(verdict(adapter, request(raw))["handshake_response"]["body"])
    assert (
        body["encryptedToken"] != hmac.new(ZOOM_SECRET.encode(), b"qgg8vlvZRS6UYooatFL8Aw", hashlib.sha256).hexdigest()
    )


@pytest.mark.parametrize("raw", [b"", b"not json", b"[]", b'"x"', b"\xff\xfe", b"{" * 5000, b'{"event": "endpoint.url_validation", "payload": {"plainToken": 5}}',
                                 b'{"event": "endpoint.url_validation", "payload": {"plainToken": "' + b"x" * 300 + b'"}}'])  # fmt: skip
def test_hostile_bodies_are_rejected_not_errors(adapter, raw):
    r = adapter.verify_inbound(None, request(raw, zoom_signature(raw, NOW_TS)))
    assert r.error is None and r.output["verdict"] == "reject"


def test_oversize_and_non_post_requests_are_rejected(adapter):
    big = b'{"event": "x", "pad": "' + b"a" * (1024 * 1024) + b'"}'
    assert verdict(adapter, request(big, zoom_signature(big, NOW_TS)))["verdict"] == "reject"
    raw = fixture("zoom/event_meeting_ended.json").encode()
    assert verdict(adapter, request(raw, zoom_signature(raw, NOW_TS), method="GET"))["verdict"] == "reject"
    assert adapter.verify_inbound(None, "not a dict").output["verdict"] == "reject"
    assert adapter.verify_inbound(None, {"raw_body": 12}).output["verdict"] == "reject"
    assert adapter.parse_inbound(None, {"raw_body": 12}).error["code"] == "invalid_request"


def test_a_connections_own_zoom_app_verifies_with_its_own_secret(adapter, org):
    ctx = org.ctx("zoom", secrets={"webhook_secret_token": "the-institutions-own-secret"})
    raw = fixture("zoom/event_meeting_ended.json").encode()
    assert (
        verdict(
            adapter, request(raw, zoom_signature(raw, NOW_TS, "the-institutions-own-secret"), suffix="conn-1"), ctx
        )["verdict"]
        == "accept"
    )
    assert (
        verdict(adapter, request(raw, zoom_signature(raw, NOW_TS), suffix="conn-1"), ctx)["verdict"] == "reject"
    )  # not Rooman's secret


def parse(adapter, org, name, provider="zoom", **secrets):
    base = {"zoom": {"webhook_secret_token": ZOOM_SECRET}, "webex": {"webhook_secret": WEBEX_SECRET}}.get(provider, {})
    r = adapter.parse_inbound(org.ctx(provider, secrets={**base, **secrets}), request(fixture(name).encode(), {}))
    assert r.error is None, r.error
    return r.output["notifications"]


def meeting(org, key="class-session-1"):
    with platform_scope(), SessionLocal() as db:
        return db.scalar(select(Meeting).where(Meeting.organisation_id == org.id, Meeting.meeting_key == key))


def test_zoom_started_and_ended_move_the_meeting_and_publish_the_ports_notifications(adapter, transport, org):
    zoom_org_meeting(adapter, transport, org)
    started = parse(adapter, org, "zoom/event_meeting_started.json")
    assert started == [
        {
            "port": "meetings",
            "kind": "meeting_started",
            "data": {"meeting_key": "class-session-1", "started_at": "2026-11-09T04:30:05+00:00"},
        }
    ]
    assert meeting(org).status == "started"
    ended = parse(adapter, org, "zoom/event_meeting_ended.json")
    assert [n["kind"] for n in ended] == ["meeting_ended", "attendance_ready"]
    assert ended[0]["data"] == {"meeting_key": "class-session-1", "ended_at": "2026-11-09T05:15:00+00:00"}
    assert ended[1]["data"]["not_before"] == "2026-11-09T05:30:00+00:00"  # ATTENDANCE_DELAY_MIN after the end
    m = meeting(org)
    assert m.status == "ended" and m.provider_instance_id == "kXyZ12abcdEFgh=="
    assert parse(adapter, org, "zoom/event_meeting_ended.json") == []  # a redelivery changes nothing and says nothing


def test_zoom_recording_completed_announces_each_file_once(adapter, transport, org):
    zoom_org_meeting(adapter, transport, org)
    notes = parse(adapter, org, "zoom/event_recording_completed.json")
    assert [(n["kind"], n["data"]["provider_recording_id"], n["data"]["kind"]) for n in notes] == [
        ("recording_ready", "rec-video-1", "video"),
        ("recording_ready", "rec-chat-1", "chat"),
    ]
    assert parse(adapter, org, "zoom/event_recording_completed.json") == []
    with platform_scope(), SessionLocal() as db:
        assert len(db.scalars(select(Recording).where(Recording.organisation_id == org.id)).all()) == 2


def test_zoom_meeting_deleted_cancels_a_scheduled_meeting(adapter, transport, org):
    zoom_org_meeting(adapter, transport, org)
    assert parse(adapter, org, "zoom/event_meeting_deleted.json") == []
    assert meeting(org).status == "cancelled"


def test_participant_events_are_acknowledged_and_left_to_the_attendance_report(adapter, transport, org):
    zoom_org_meeting(adapter, transport, org)
    assert parse(adapter, org, "zoom/event_participant_joined.json") == []


def test_events_for_meetings_we_did_not_create_change_nothing(adapter, org):
    assert parse(adapter, org, "zoom/event_meeting_started.json") == []


def test_an_app_level_event_without_a_connection_finds_the_meeting_by_its_zoom_id(adapter, transport, org):
    zoom_org_meeting(adapter, transport, org)
    raw = fixture("zoom/event_meeting_started.json").encode()
    r = adapter.parse_inbound(None, request(raw, zoom_signature(raw, NOW_TS)))
    assert r.output["notifications"][0]["kind"] == "meeting_started" and meeting(org).status == "started"


def test_a_connection_cannot_move_another_organisations_meeting(adapter, transport, org, other_org):
    zoom_org_meeting(adapter, transport, org)
    assert parse(adapter, other_org, "zoom/event_meeting_ended.json") == []
    assert meeting(org).status == "scheduled"


def test_state_changes_from_events_are_audited(adapter, transport, org):
    zoom_org_meeting(adapter, transport, org)
    parse(adapter, org, "zoom/event_meeting_started.json")
    parse(adapter, org, "zoom/event_meeting_ended.json")
    with platform_scope(), SessionLocal() as db:
        actions = [
            a.action
            for a in db.scalars(
                select(AuditEntry).where(AuditEntry.organisation_id == org.id).order_by(AuditEntry.occurred_at)
            )
        ]
    assert actions == ["meeting.created", "meeting.started", "meeting.ended"]


# --- Microsoft Graph ----------------------------------------------------------------------------------------------


def graph_org(adapter, transport, org):
    transport.on("POST", r"oauth2/v2.0/token", "teams/token.json")
    transport.on("POST", r"/users/.+/onlineMeetings$", "teams/create_online_meeting.json", status=201)
    transport.on("POST", r"/subscriptions$", "teams/subscription_created.json", status=201)
    assert adapter.create_meeting(org.ctx("teams"), create_input()).error is None
    with platform_scope(), SessionLocal() as db:
        sub = db.scalar(select(GraphSubscription).where(GraphSubscription.organisation_id == org.id))
        return crypto.client_state(Config.load(), org.connection_id, sub.client_state_ref)


def notification(name: str, state: str) -> bytes:
    return fixture(name).replace("__CLIENT_STATE__", state).encode()


def test_the_validation_token_is_echoed_as_plain_text(adapter, org):
    v = verdict(
        adapter,
        request(
            b"",
            query={
                "validationToken": "Validation: Testing client application reachability for subscription Request-Id: abc"
            },
            suffix="c",
        ),
        org.ctx("teams"),
    )
    assert v["verdict"] == "handshake" and v["handshake_response"] == {
        "status": 200,
        "content_type": "text/plain",
        "body": "Validation: Testing client application reachability for subscription Request-Id: abc",
    }


@pytest.mark.parametrize("token", ["", "x" * 2049, "a\nb", "a\x00b", "\x7f"])
def test_a_hostile_validation_token_is_rejected(adapter, org, token):
    assert (
        verdict(adapter, request(b"", query={"validationToken": token}, suffix="c"), org.ctx("teams"))["verdict"]
        == "reject"
    )


def test_a_notification_with_the_right_client_state_is_accepted_with_202(adapter, transport, org):
    state = graph_org(adapter, transport, org)
    v = verdict(
        adapter, request(notification("teams/notification_recording.json", state), suffix="c"), org.ctx("teams")
    )
    assert v["verdict"] == "accept" and v["ack_status"] == 202 and v["dedupe_key"]


@pytest.mark.parametrize(
    "variant",
    [
        "wrong_state",
        "no_state",
        "unknown_subscription",
        "other_connection",
        "empty_value",
        "not_an_object",
        "one_bad_among_good",
    ],
)
def test_a_notification_that_does_not_carry_its_subscriptions_client_state_is_rejected(
    adapter, transport, org, other_org, variant
):
    state = graph_org(adapter, transport, org)
    body = json.loads(notification("teams/notification_recording.json", state))
    ctx = org.ctx("teams")
    if variant == "wrong_state":
        body["value"][0]["clientState"] = "x" * 64
    elif variant == "no_state":
        del body["value"][0]["clientState"]
    elif variant == "unknown_subscription":
        body["value"][0]["subscriptionId"] = "sub-unknown"
    elif variant == "other_connection":
        ctx = other_org.ctx("teams")  # the state is valid, but for another connection's subscription table
    elif variant == "empty_value":
        body["value"] = []
    elif variant == "not_an_object":
        body["value"] = ["x"]
    elif variant == "one_bad_among_good":
        body["value"].append({**body["value"][0], "clientState": "nope"})
    assert verdict(adapter, request(json.dumps(body).encode(), suffix="c"), ctx)["verdict"] == "reject"


def test_a_recording_notification_announces_the_recording_for_our_meeting(adapter, transport, org):
    state = graph_org(adapter, transport, org)
    r = adapter.parse_inbound(
        org.ctx("teams"), request(notification("teams/notification_recording.json", state), suffix="c")
    )
    assert r.output["notifications"] == [
        {
            "port": "meetings",
            "kind": "recording_ready",
            "data": {"meeting_key": "class-session-1", "provider_recording_id": "rec-1", "kind": "video"},
        }
    ]


def test_lifecycle_notifications_renew_or_recreate_the_subscription(adapter, transport, org):
    state = graph_org(adapter, transport, org)
    transport.on("PATCH", r"/subscriptions/sub-7f1c", "teams/subscription_created.json")
    assert (
        verdict(
            adapter, request(notification("teams/lifecycle_reauthorization.json", state), suffix="c"), org.ctx("teams")
        )["verdict"]
        == "accept"
    )
    adapter.parse_inbound(
        org.ctx("teams"), request(notification("teams/lifecycle_reauthorization.json", state), suffix="c")
    )
    assert len(transport.sent("PATCH", "/subscriptions/sub-7f1c")) == 1
    transport.routes[:] = [r for r in transport.routes if not (r[0] == "POST" and "subscriptions" in r[1].pattern)]
    transport.on("POST", r"/subscriptions$", body={"id": "sub-after-removal"}, status=201)
    adapter.parse_inbound(org.ctx("teams"), request(notification("teams/lifecycle_removed.json", state), suffix="c"))
    with platform_scope(), SessionLocal() as db:
        assert [
            s.subscription_id
            for s in db.scalars(select(GraphSubscription).where(GraphSubscription.organisation_id == org.id))
        ] == ["sub-after-removal"]


# --- Webex ----------------------------------------------------------------------------------------------------------


def webex_req(
    name: str, header: str = "X-Webex-Signature", algo=hashlib.sha256, secret: str = WEBEX_SECRET, tamper: bool = False
) -> dict:
    raw = fixture(name).encode()
    sig = hmac.new(secret.encode(), raw, algo).hexdigest()
    return request(raw + (b" " if tamper else b""), {header: sig}, suffix="c")


def webex_meeting(adapter, transport, org):
    transport.on("POST", r"webexapis\.com/v1/meetings$", "webex/create_meeting.json")
    assert adapter.create_meeting(org.ctx("webex"), create_input()).error is None


def test_webex_sha256_signature_is_accepted(adapter, org):
    assert verdict(adapter, webex_req("webex/event_meeting_started.json"), org.ctx("webex"))["verdict"] == "accept"


def test_webex_older_sha1_header_is_accepted_and_header_names_are_case_insensitive(adapter, org):
    assert (
        verdict(
            adapter, webex_req("webex/event_meeting_started.json", "X-Spark-Signature", hashlib.sha1), org.ctx("webex")
        )["verdict"]
        == "accept"
    )  # noqa: S324
    assert (
        verdict(adapter, webex_req("webex/event_meeting_started.json", "x-webex-signature"), org.ctx("webex"))[
            "verdict"
        ]
        == "accept"
    )


@pytest.mark.parametrize(
    "variant",
    ["tampered", "wrong_secret", "sha1_value_in_sha256_header", "missing", "uppercase_hex_is_fine_but_empty_is_not"],
)
def test_webex_events_that_do_not_verify_are_rejected(adapter, org, variant):
    ctx = org.ctx("webex")
    if variant == "tampered":
        req = webex_req("webex/event_meeting_started.json", tamper=True)
    elif variant == "wrong_secret":
        req = webex_req("webex/event_meeting_started.json", secret="other")
    elif variant == "sha1_value_in_sha256_header":
        req = webex_req("webex/event_meeting_started.json", "X-Webex-Signature", hashlib.sha1)  # noqa: S324
    elif variant == "missing":
        req = request(fixture("webex/event_meeting_started.json"), {}, suffix="c")
    else:
        req = request(fixture("webex/event_meeting_started.json"), {"X-Webex-Signature": ""}, suffix="c")
    assert verdict(adapter, req, ctx) == {"verdict": "reject", "reject_status": 401}


def test_a_connection_without_a_webhook_secret_verifies_nothing(adapter, org):
    assert (
        verdict(adapter, webex_req("webex/event_meeting_started.json"), org.ctx("webex", secrets={}))["verdict"]
        == "reject"
    )


def test_webex_events_move_the_meeting_by_series_id_and_announce_the_ports_notifications(adapter, transport, org):
    webex_meeting(adapter, transport, org)
    assert parse(adapter, org, "webex/event_meeting_started.json", "webex")[0]["kind"] == "meeting_started"
    ended = parse(adapter, org, "webex/event_meeting_ended.json", "webex")
    assert [n["kind"] for n in ended] == ["meeting_ended", "attendance_ready"]
    assert meeting(org).status == "ended" and meeting(org).provider_instance_id.endswith("_I_400111")
    rec = parse(adapter, org, "webex/event_recording_created.json", "webex")
    assert rec == [
        {
            "port": "meetings",
            "kind": "recording_ready",
            "data": {"meeting_key": "class-session-1", "provider_recording_id": "wrec-1", "kind": "video"},
        }
    ]


def test_every_verify_and_parse_survives_garbage(adapter, org):
    for provider in ("zoom", "teams", "webex", "jitsi"):
        for raw in (b"", b"null", b"{}", b'{"value": 5}', b'{"data": []}', b"\x00\x01", b"[" * 100):
            v = adapter.verify_inbound(org.ctx(provider), request(raw, {}, suffix="c"))
            assert v.error is None and v.output["verdict"] == "reject"
            p = adapter.parse_inbound(org.ctx(provider), request(raw, {}, suffix="c"))
            assert p.error is None and p.output["notifications"] == []
