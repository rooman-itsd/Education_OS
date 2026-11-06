"""Zoom through the meetings port, against replayed fixtures: create, change, cancel, join links, attendance, recordings,
OAuth and the error mapping of docs/prd.md."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_video_conferencing.infrastructure.models import Attendance, AuditEntry, Meeting
from sqlalchemy import select
from vc_support import START, Org, body_of, create_input, form_of

API = r"https://api\.zoom\.us/v2"


def routes(t, *, token=True):
    if token:
        t.on("POST", r"zoom\.us/oauth/token\?grant_type=account_credentials", "zoom/token_s2s.json")
    return t


def make(adapter, transport, org, key="class-session-1", **over):
    routes(transport).on("POST", API + r"/users/.+/meetings$", "zoom/create_meeting.json", status=201)
    r = adapter.create_meeting(org.ctx("zoom"), create_input(key, **over))
    assert r.error is None, r.error
    return r.output


def test_create_sends_the_meeting_and_returns_both_links(adapter, transport, org):
    out = make(adapter, transport, org)
    sent = body_of(transport.last("POST", API + r"/users/.+/meetings$"))
    assert sent["topic"] == "Physics XI A: Optics" and sent["type"] == 2
    assert (
        sent["start_time"] == "2026-11-09T04:30:00Z" and sent["duration"] == 45 and sent["timezone"] == "Asia/Kolkata"
    )
    assert sent["settings"]["waiting_room"] is True and sent["settings"]["auto_recording"] == "cloud"
    assert sent["settings"]["join_before_host"] is False
    assert (
        transport.last("POST", API + r"/users/.+/meetings$").url.path
        == "/v2/users/teacher@college.example.com/meetings"
    )
    assert out["join_url"].startswith("https://zoom.example/j/85746065432")
    assert "zak=" in out["host_join_url"] and out["passcode"] == "Qw7rT2"
    assert out["provider_meeting_id"] == "85746065432"
    assert out["dial_in"] == [{"number": "+91 22 7120 1234", "country": "India"}]
    assert transport.last("POST", API + r"/users/.+/meetings$").headers["authorization"] == "Bearer s2s-access-token-1"


def test_s2s_token_request_uses_account_credentials_and_basic_auth(adapter, transport, org):
    make(adapter, transport, org)
    req = transport.last("POST", "oauth/token")
    q = parse_qs(urlsplit(str(req.url)).query)
    assert q == {"grant_type": ["account_credentials"], "account_id": ["acct-1"]}
    assert req.headers["authorization"].startswith("Basic ")


def test_the_same_meeting_key_returns_the_first_meeting_without_calling_zoom_again(adapter, transport, org):
    first = make(adapter, transport, org)
    again = adapter.create_meeting(org.ctx("zoom"), create_input("class-session-1", title="A different title")).output
    assert again["meeting_id"] == first["meeting_id"] and again["join_url"] == first["join_url"]
    assert len(transport.sent("POST", API + r"/users/.+/meetings$")) == 1


def test_join_links_and_passcode_are_stored_encrypted(adapter, transport, org):
    out = make(adapter, transport, org)
    with platform_scope(), SessionLocal() as db:
        raw = db.scalar(select(Meeting).where(Meeting.id == out["meeting_id"]))
        for stored, clear in (
            (raw.join_url, out["join_url"]),
            (raw.host_join_url, out["host_join_url"]),
            (raw.passcode, out["passcode"]),
        ):
            assert stored and clear not in stored and "zoom.example" not in stored


def test_a_host_who_is_not_a_zoom_user_is_invalid_request_and_the_key_can_be_retried(adapter, transport, org):
    routes(transport).on("POST", API + r"/users/.+/meetings$", "zoom/error_user_not_found.json", status=404)
    r = adapter.create_meeting(org.ctx("zoom"), create_input("retry-me"))
    assert (
        r.error["code"] == "invalid_request"
        and "host_not_licensed" in r.error["detail"]
        and r.error["provider_code"] == "1001"
    )
    assert r.error["retryable"] is False and "teacher@" not in json.dumps(r.error)
    transport.routes.clear()
    make(adapter, transport, org, "retry-me")  # the failed attempt left nothing behind


def test_update_patches_only_what_changed_and_keeps_the_links(adapter, transport, org):
    first = make(adapter, transport, org)
    transport.on("PATCH", API + r"/meetings/85746065432$", status=204)
    r = adapter.update_meeting(
        org.ctx("zoom"),
        {"meeting_key": "class-session-1", "starts_at": "2026-11-09T05:00:00+00:00", "duration_minutes": 60},
    )
    assert r.error is None and r.output["links_changed"] is False and r.output["join_url"] == first["join_url"]
    assert body_of(transport.last("PATCH", "meetings/85746065432")) == {
        "start_time": "2026-11-09T05:00:00Z",
        "duration": 60,
    }
    with platform_scope(), SessionLocal() as db:
        m = db.scalar(select(Meeting).where(Meeting.id == first["meeting_id"]))
        assert m.duration_minutes == 60


def test_cancel_deletes_at_zoom_and_a_second_cancel_is_not_an_error(adapter, transport, org):
    make(adapter, transport, org)
    transport.on("DELETE", API + r"/meetings/85746065432", status=204)
    assert (
        adapter.cancel_meeting(org.ctx("zoom"), {"meeting_key": "class-session-1", "reason": "teacher unwell"}).output[
            "status"
        ]
        == "cancelled"
    )
    assert adapter.cancel_meeting(org.ctx("zoom"), {"meeting_key": "class-session-1"}).output["status"] == "cancelled"
    assert len(transport.sent("DELETE", "meetings/85746065432")) == 1
    assert (
        adapter.update_meeting(org.ctx("zoom"), {"meeting_key": "class-session-1", "title": "x"}).error["code"]
        == "conflict"
    )
    assert (
        adapter.join_link(
            org.ctx("zoom"), {"meeting_key": "class-session-1", "person_id": org.id, "display_name": "A"}
        ).error
        is not None
    )


def test_a_meeting_zoom_already_deleted_cancels_cleanly(adapter, transport, org):
    make(adapter, transport, org)
    transport.on("DELETE", API + r"/meetings/", "zoom/error_meeting_not_found.json", status=404)
    assert adapter.cancel_meeting(org.ctx("zoom"), {"meeting_key": "class-session-1"}).output["status"] == "cancelled"


def test_join_link_gives_attendees_the_join_url_and_hosts_the_start_url(adapter, transport, org):
    out = make(adapter, transport, org)
    who = {
        "meeting_key": "class-session-1",
        "person_id": "00000000-0000-4000-8000-000000000001",
        "display_name": "Anita",
    }
    assert adapter.join_link(org.ctx("zoom"), {**who, "role": "attendee"}).output["url"] == out["join_url"]
    assert adapter.join_link(org.ctx("zoom"), {**who, "role": "host"}).output["url"] == out["host_join_url"]
    assert adapter.join_link(org.ctx("zoom"), {**who, "role": "co_host"}).output["url"] == out["host_join_url"]


def test_get_meeting_reports_status_from_the_adapters_own_record(adapter, transport, org):
    out = make(adapter, transport, org)
    got = adapter.get_meeting(org.ctx("zoom"), {"meeting_key": "class-session-1"}).output
    assert got == {
        "meeting_id": out["meeting_id"],
        "status": "scheduled",
        "started_at": None,
        "ended_at": None,
        "provider_meeting_id": "85746065432",
    }
    assert adapter.get_meeting(org.ctx("zoom"), {"meeting_key": "nope"}).error["code"] == "not_found"


@pytest.mark.parametrize(
    ("status", "headers", "code", "retryable"),
    [(401, {}, "auth_failed", False), (403, {}, "auth_failed", False), (500, {}, "provider_error", True), (503, {}, "provider_error", True),
     (429, {"retry-after": "42"}, "throttled", True), (400, {}, "invalid_request", False), (409, {}, "conflict", False), (418, {}, "rejected", False)],
)  # fmt: skip
def test_provider_answers_map_to_the_contracts_error_codes(adapter, transport, org, status, headers, code, retryable):
    routes(transport).on(
        "POST",
        API + r"/users/.+/meetings$",
        status=status,
        body={"code": 1234, "message": "provider prose that must not leak"},
        headers=headers,
    )
    r = adapter.create_meeting(org.ctx("zoom"), create_input())
    assert r.error["code"] == code and r.error["retryable"] is retryable and r.error["provider_code"] == "1234"
    assert "prose" not in json.dumps(r.error)
    if status == 429:
        assert r.error["retry_after_s"] == 42


def test_a_daily_limit_answer_says_when_zoom_resets(adapter, transport, org, clock):
    routes(transport).on("POST", API + r"/users/.+/meetings$", "zoom/error_daily_limit.json", status=429)
    r = adapter.create_meeting(org.ctx("zoom"), create_input())
    assert r.error["code"] == "throttled" and r.error["retry_after_s"] == 18 * 3600  # 06:00 UTC to 00:00 UTC


@pytest.mark.parametrize("exc", [httpx.ConnectTimeout("t"), httpx.ConnectError("c"), httpx.ReadTimeout("r")])
def test_network_failures_are_transport_unavailable(adapter, transport, org, exc):
    routes(transport).on("POST", API + r"/users/.+/meetings$", raises=exc)
    r = adapter.create_meeting(org.ctx("zoom"), create_input())
    assert r.error["code"] == "transport_unavailable" and r.error["retryable"] is True


def test_a_refused_s2s_credential_is_auth_failed(adapter, transport, org):
    transport.on("POST", "oauth/token", status=401, body={"reason": "Invalid client_id or client_secret"})
    assert adapter.create_meeting(org.ctx("zoom"), create_input()).error["code"] == "auth_failed"


def test_a_connection_with_no_token_at_all_is_auth_failed(adapter, org):
    assert adapter.create_meeting(org.ctx("zoom", secrets={}), create_input()).error["code"] == "auth_failed"


def test_the_hubs_oauth_token_is_used_when_the_institution_authorised_roommans_app(adapter, transport, org):
    transport.on("POST", API + r"/users/.+/meetings$", "zoom/create_meeting.json", status=201)
    r = adapter.create_meeting(org.ctx("zoom", secrets={"access_token": "from-the-hub"}), create_input())
    assert r.error is None
    assert transport.last("POST", "meetings").headers["authorization"] == "Bearer from-the-hub"
    assert not transport.sent("POST", "oauth/token")


def test_authorisation_url_carries_pkce_and_state(adapter):
    ctx = {"organisation_id": "o", "connection_id": "c", "provider": "zoom", "mode": "sandbox"}
    url = adapter.begin_authorisation(
        ctx, {"state": "st-1", "code_challenge": "C" * 43, "redirect_uri": "https://hub.example/cb", "scope_hint": []}
    ).output["authorize_url"]
    q = parse_qs(urlsplit(url).query)
    assert url.startswith("https://zoom.us/oauth/authorize?")
    assert q["state"] == ["st-1"] and q["code_challenge"] == ["C" * 43] and q["code_challenge_method"] == ["S256"]
    assert (
        q["client_id"] == ["platform-zoom-id"]
        and q["redirect_uri"] == ["https://hub.example/cb"]
        and q["response_type"] == ["code"]
    )


def test_complete_refresh_and_revoke_authorisation(adapter, transport):
    ctx = {"organisation_id": "o", "connection_id": "c", "provider": "zoom", "mode": "sandbox"}
    transport.on("POST", r"zoom\.us/oauth/token$", "zoom/token_authorization_code.json")
    transport.on("GET", API + "/users/me", "zoom/users_me.json")
    done = adapter.complete_authorisation(
        ctx, {"code": "abc", "code_verifier": "V" * 43, "redirect_uri": "https://hub.example/cb"}
    ).output
    assert done["secrets"] == {"access_token": "zoom-access-1", "refresh_token": "zoom-refresh-1"}
    assert (
        done["provider_subject"] == "Qm8kAccountId01"
        and "recording:read" in done["granted_scopes"]
        and done["expires_at"]
    )
    form = form_of(transport.last("POST", r"oauth/token$"))
    assert form == {
        "grant_type": "authorization_code",
        "code": "abc",
        "redirect_uri": "https://hub.example/cb",
        "code_verifier": "V" * 43,
    }
    assert transport.last("POST", "oauth/token").headers["authorization"].startswith("Basic ")
    assert transport.last("GET", "users/me").headers["authorization"] == "Bearer zoom-access-1"

    r = adapter.refresh_authorisation({**ctx, "secrets": {"refresh_token": "old"}})
    assert (
        r.output["secrets"]["access_token"] == "zoom-access-1"
        and form_of(transport.last("POST", r"oauth/token$"))["refresh_token"] == "old"
    )
    assert adapter.refresh_authorisation(ctx).error["code"] == "auth_failed"

    transport.on("POST", r"zoom\.us/oauth/revoke", status=200, body={"status": "success"})
    assert adapter.revoke_authorisation({**ctx, "secrets": {"access_token": "a"}}).output == {"revoked": True}


def test_a_refused_authorisation_code_is_auth_failed(adapter, transport):
    ctx = {"organisation_id": "o", "connection_id": "c", "provider": "zoom", "mode": "sandbox"}
    transport.on(
        "POST", r"oauth/token$", status=400, body={"reason": "Invalid authorization code", "error": "invalid_grant"}
    )
    r = adapter.complete_authorisation(
        ctx, {"code": "bad", "code_verifier": "V" * 43, "redirect_uri": "https://hub.example/cb"}
    )
    assert r.error["code"] == "auth_failed"


def test_healthcheck_reads_users_me_and_never_creates(adapter, transport, org):
    routes(transport).on("GET", API + "/users/me", "zoom/users_me.json")
    assert adapter.healthcheck(org.ctx("zoom")).output["status"] == "healthy"
    assert {r.method for r in transport.requests} <= {"GET", "POST"} and not transport.sent("POST", "/meetings")
    transport.routes.clear()
    transport.on("GET", API + "/users/me", status=401, body={"code": 124, "message": "Invalid access token."})
    transport.on("POST", "oauth/token", "zoom/token_s2s.json")
    zoom_ctx = org.ctx("zoom", secrets={"access_token": "revoked"})
    assert adapter.healthcheck(zoom_ctx).output["status"] == "auth_failed"
    transport.routes.clear()
    transport.on("GET", API + "/users/me", status=502)
    assert adapter.healthcheck(zoom_ctx).output["status"] == "unreachable"


def ended(adapter, transport, org, key="class-session-1"):
    """A created meeting that Zoom's meeting.ended webhook has closed."""
    from vc_support import ZOOM_SECRET, fixture, request, zoom_signature

    make(adapter, transport, org, key)
    raw = fixture("zoom/event_meeting_ended.json").encode()
    ctx = org.ctx("zoom", secrets={"webhook_secret_token": ZOOM_SECRET})
    adapter.parse_inbound(ctx, request(raw, zoom_signature(raw, int(adapter.clock().timestamp()))))


def test_attendance_folds_rejoins_matches_the_roster_and_names_only_the_unmatched(adapter, transport, org, clock):
    ended(adapter, transport, org)
    clock.now = clock.now.replace(day=9, hour=6, minute=0)  # three quarters of an hour after the class ended
    transport.on("GET", API + r"/past_meetings/kXyZ12abcdEFgh%3D%3D/participants", "zoom/past_participants.json")
    anita, vikram = "00000000-0000-4000-8000-0000000000a1", "00000000-0000-4000-8000-0000000000a2"
    r = adapter.fetch_attendance(
        org.ctx("zoom"),
        {
            "meeting_key": "class-session-1",
            "roster": [
                {"person_id": anita, "email": "Anita.Rao@college.example.com"},
                {"person_id": vikram, "email": "vikram@college.example.com"},
            ],
        },
    )
    assert r.error is None
    rows = {p["email"] or p["display_name"]: p for p in r.output["participants"]}
    assert (
        rows["anita.rao@college.example.com"]["person_id"] == anita
        and rows["anita.rao@college.example.com"]["total_seconds"] == 2520
    )
    assert len(rows["anita.rao@college.example.com"]["intervals"]) == 2
    assert rows["vikram@college.example.com"]["person_id"] == vikram
    assert rows["Guest Phone"]["person_id"] is None
    assert r.output["complete"] is True
    with platform_scope(), SessionLocal() as db:
        stored = db.scalars(select(Attendance).where(Attendance.meeting_id == r.output["meeting_id"])).all()
        assert sorted(a.display_name or "-" for a in stored) == [
            "-",
            "-",
            "Guest Phone",
        ]  # only the unmatched are named
        assert not any(hasattr(a, "email") for a in stored)


def test_attendance_is_not_complete_until_the_provider_has_had_time_to_finalise_it(adapter, transport, org, clock):
    ended(
        adapter, transport, org
    )  # ended 05:15 on the 9th: the clock is on the 5th, so the delay has not passed either
    transport.on("GET", API + r"/past_meetings/.+/participants", "zoom/past_participants.json")
    assert adapter.fetch_attendance(org.ctx("zoom"), {"meeting_key": "class-session-1"}).output["complete"] is False
    clock.now = clock.now.replace(day=9, hour=5, minute=20)
    assert adapter.fetch_attendance(org.ctx("zoom"), {"meeting_key": "class-session-1"}).output["complete"] is False
    clock.advance(minutes=11)
    assert adapter.fetch_attendance(org.ctx("zoom"), {"meeting_key": "class-session-1"}).output["complete"] is True


def test_attendance_without_the_ended_event_finds_the_instance_itself(adapter, transport, org):
    make(adapter, transport, org)
    transport.on(
        "GET",
        API + r"/past_meetings/85746065432/instances",
        body={
            "meetings": [
                {"uuid": "old==", "start_time": "2026-11-02T04:30:00Z"},
                {"uuid": "kXyZ12abcdEFgh==", "start_time": "2026-11-09T04:30:00Z"},
            ]
        },
    )
    transport.on("GET", API + r"/past_meetings/kXyZ12abcdEFgh%3D%3D/participants", "zoom/past_participants.json")
    r = adapter.fetch_attendance(org.ctx("zoom"), {"meeting_key": "class-session-1"})
    assert r.error is None and r.output["complete"] is False and len(r.output["participants"]) == 3


def test_attendance_pages_are_followed_and_bounded(adapter, transport, org):
    make(adapter, transport, org)
    transport.on(
        "GET",
        API + r"/past_meetings/85746065432/instances",
        body={"meetings": [{"uuid": "u1", "start_time": "2026-11-09T04:30:00Z"}]},
    )
    transport.on(
        "GET",
        API + r"/past_meetings/u1/participants",
        status=200,
        body={
            "participants": [
                {"id": "a", "name": "A", "user_email": "a@x.example.com", "join_time": START, "duration": 5}
            ],
            "next_page_token": "forever",
        },
    )
    r = adapter.fetch_attendance(org.ctx("zoom"), {"meeting_key": "class-session-1"})
    assert r.error is None and len(transport.sent("GET", "participants")) == 50


def test_recordings_are_listed_by_kind_and_only_when_completed(adapter, transport, org):
    make(adapter, transport, org)
    transport.on("GET", API + r"/meetings/85746065432/recordings", "zoom/recordings.json")
    items = adapter.list_recordings(org.ctx("zoom"), {"meeting_key": "class-session-1"}).output["items"]
    assert [(i["provider_recording_id"], i["kind"], i["bytes"]) for i in items] == [
        ("rec-video-1", "video", 20),
        ("rec-chat-1", "chat", 120),
    ]


def test_import_streams_the_recording_into_documents_once(adapter, transport, org, documents):
    make(adapter, transport, org)
    transport.on("GET", API + r"/meetings/85746065432/recordings", "zoom/recordings.json")
    transport.on("GET", r"us06web\.zoom\.us/rec/download/abc", body=b"0123456789" * 2)
    ask = {"meeting_key": "class-session-1", "provider_recording_id": "rec-video-1"}
    r = adapter.import_recording(org.ctx("zoom"), ask)
    assert r.error is None
    assert r.output["bytes"] == 20 and r.output["sha256"] == hashlib.sha256(b"0123456789" * 2).hexdigest()
    assert documents.stored[0]["data"] == b"0123456789" * 2 and documents.stored[0]["organisation_id"] == org.id
    assert documents.stored[0]["content_type"] == "video/mp4"
    assert transport.last("GET", "rec/download/abc").headers["authorization"] == "Bearer s2s-access-token-1"
    assert adapter.import_recording(org.ctx("zoom"), ask).output == r.output and len(documents.stored) == 1


def test_import_refuses_a_recording_zoom_does_not_have_and_an_oversize_one(adapter, transport, org, monkeypatch):
    make(adapter, transport, org)
    transport.on("GET", API + r"/meetings/85746065432/recordings", "zoom/recordings.json")
    assert (
        adapter.import_recording(
            org.ctx("zoom"), {"meeting_key": "class-session-1", "provider_recording_id": "nope"}
        ).error["code"]
        == "not_found"
    )
    monkeypatch.setenv("VIDEO_CONFERENCING_MAX_RECORDING_BYTES", "10")
    transport.on("GET", r"us06web\.zoom\.us/rec/download/abc", body=b"x" * 20)
    r = adapter.import_recording(
        org.ctx("zoom"), {"meeting_key": "class-session-1", "provider_recording_id": "rec-video-1"}
    )
    assert r.error["code"] == "rejected"


def test_the_bearer_token_never_goes_to_a_host_that_is_not_zoom(adapter, transport, org):
    make(adapter, transport, org)
    body = json.loads(__import__("vc_support").fixture("zoom/recordings.json"))
    body["recording_files"][0]["download_url"] = "https://evil.example/zoom.us/x"
    transport.on("GET", API + r"/meetings/85746065432/recordings", body=body)
    r = adapter.import_recording(
        org.ctx("zoom"), {"meeting_key": "class-session-1", "provider_recording_id": "rec-video-1"}
    )
    assert r.error["code"] == "invalid_request" and not transport.sent("GET", "evil.example")


def test_audit_trail_records_each_change_without_links_or_names(adapter, transport, org):
    out = make(adapter, transport, org)
    transport.on("PATCH", "meetings/85746065432", status=204).on("DELETE", "meetings/85746065432", status=204)
    adapter.update_meeting(org.ctx("zoom"), {"meeting_key": "class-session-1", "duration_minutes": 50})
    adapter.cancel_meeting(org.ctx("zoom"), {"meeting_key": "class-session-1"})
    with platform_scope(), SessionLocal() as db:
        rows = db.scalars(
            select(AuditEntry).where(AuditEntry.entity_id == out["meeting_id"]).order_by(AuditEntry.occurred_at)
        ).all()
        assert [r.action for r in rows] == ["meeting.created", "meeting.updated", "meeting.cancelled"]
        assert all(r.organisation_id == org.id for r in rows)
        assert START not in repr([vars(r) for r in rows])


def test_a_live_meeting_cannot_be_changed_or_cancelled(adapter, transport, org):
    from vc_support import ZOOM_SECRET, fixture, request, zoom_signature

    make(adapter, transport, org)
    raw = fixture("zoom/event_meeting_started.json").encode()
    ctx = org.ctx("zoom", secrets={"webhook_secret_token": ZOOM_SECRET})
    adapter.parse_inbound(ctx, request(raw, zoom_signature(raw, int(adapter.clock().timestamp()))))
    assert adapter.cancel_meeting(org.ctx("zoom"), {"meeting_key": "class-session-1"}).error["code"] == "conflict"
    assert (
        adapter.update_meeting(org.ctx("zoom"), {"meeting_key": "class-session-1", "title": "x"}).error["code"]
        == "conflict"
    )
    assert not transport.sent("DELETE", "meetings")


_ = (timedelta, Org)
