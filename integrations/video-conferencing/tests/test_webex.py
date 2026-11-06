"""Webex through the meetings port, against replayed fixtures."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest
from vc_support import WEBEX_SECRET, body_of, create_input, form_of

W = r"https://webexapis\.com/v1"
SERIES = "a8e3f2c0d1b24c6e9f7a5b3c1d2e4f60"
INSTANCE = SERIES + "_I_400111"


def make(adapter, transport, org, key="class-session-1", **over):
    transport.on("POST", W + "/meetings$", "webex/create_meeting.json", status=200)
    r = adapter.create_meeting(org.ctx("webex"), create_input(key, **over))
    assert r.error is None, r.error
    return r.output


def test_create_schedules_on_behalf_of_the_host_without_sending_invitations(adapter, transport, org):
    out = make(adapter, transport, org, co_hosts=[{"email": "assistant@college.example.com"}])
    sent = body_of(transport.last("POST", "/meetings$"))
    assert (
        sent["title"] == "Physics XI A: Optics"
        and sent["start"] == "2026-11-09T04:30:00Z"
        and sent["end"] == "2026-11-09T05:15:00Z"
    )
    assert (
        sent["hostEmail"] == "teacher@college.example.com"
        and sent["sendEmail"] is False
        and sent["timezone"] == "Asia/Kolkata"
    )
    assert (
        sent["invitees"] == [{"email": "assistant@college.example.com", "coHost": True}]
        and sent["enabledAutoRecordMeeting"] is True
    )
    assert sent["siteUrl"] == "college.webex.example"
    assert out["join_url"] == out["host_join_url"] == "https://college.webex.example/college/j.php?MTID=m123"
    assert out["passcode"] == "pW4rD9" and "hostKey" not in str(out) and "123456" not in str(out)
    assert transport.last("POST", "/meetings$").headers["authorization"] == "Bearer webex-access-1"


def test_update_puts_the_whole_schedule_and_cancel_deletes(adapter, transport, org):
    make(adapter, transport, org)
    transport.on("GET", W + f"/meetings/{SERIES}$", "webex/meeting_get.json")
    transport.on("PUT", W + f"/meetings/{SERIES}$", "webex/create_meeting.json")
    transport.on("DELETE", W + f"/meetings/{SERIES}", status=204)
    assert (
        adapter.update_meeting(
            org.ctx("webex"), {"meeting_key": "class-session-1", "duration_minutes": 60, "title": "Revision"}
        ).error
        is None
    )
    b = body_of(transport.last("PUT", "/meetings/"))
    assert (
        b["title"] == "Revision"
        and b["end"] == "2026-11-09T05:30:00Z"
        and b["password"] == "pW4rD9"
        and b["hostEmail"] == "teacher@college.example.com"
    )
    assert adapter.cancel_meeting(org.ctx("webex"), {"meeting_key": "class-session-1"}).output["status"] == "cancelled"
    q = parse_qs(urlsplit(str(transport.last("DELETE", "/meetings/").url)).query)
    assert q == {"sendEmail": ["false"], "hostEmail": ["teacher@college.example.com"]}


def test_rate_limit_and_failures_map_to_the_contract(adapter, transport, org):
    transport.on("POST", W + "/meetings$", status=429, body={"message": "slow down"}, headers={"retry-after": "30"})
    e = adapter.create_meeting(org.ctx("webex"), create_input()).error
    assert (e["code"], e["retryable"], e["retry_after_s"]) == ("throttled", True, 30)
    transport.routes.clear()
    transport.on("POST", W + "/meetings$", status=401, body={"message": "bad token"})
    assert adapter.create_meeting(org.ctx("webex"), create_input()).error["code"] == "auth_failed"
    transport.routes.clear()
    transport.on(
        "POST",
        W + "/meetings$",
        status=400,
        body={"message": "Invalid host email address", "errors": [{"description": "hostEmail is not a valid host"}]},
    )
    e = adapter.create_meeting(org.ctx("webex"), create_input()).error
    assert e["code"] == "invalid_request" and "host_not_licensed" in e["detail"]
    assert adapter.create_meeting(org.ctx("webex", secrets={}), create_input("other")).error["code"] == "auth_failed"


def test_attendance_finds_the_ended_instance_and_folds_rejoins(adapter, transport, org, clock):
    make(adapter, transport, org)
    transport.on("GET", W + r"/meetings\?", "webex/meetings_ended.json")
    transport.on("GET", W + r"/meetingParticipants\?", "webex/meeting_participants.json")
    r = adapter.fetch_attendance(org.ctx("webex"), {"meeting_key": "class-session-1"})
    assert r.error is None
    q = parse_qs(
        urlsplit(
            str(transport.last("GET", "/meetingParticipants")).url
            if False
            else str(transport.last("GET", "/meetingParticipants").url)
        ).query
    )
    assert q["meetingId"] == [INSTANCE]
    by = {p["email"]: p for p in r.output["participants"]}
    assert by["teacher@college.example.com"]["role"] == "host"
    assert (
        by["anita.rao@college.example.com"]["total_seconds"] == 1140 + 1380
        and len(by["anita.rao@college.example.com"]["intervals"]) == 2
    )


def test_recordings_listed_and_imported_through_the_presigned_link_without_the_token(
    adapter, transport, org, documents
):
    make(adapter, transport, org)
    transport.on("GET", W + r"/recordings\?", "webex/recordings.json")
    transport.on("GET", W + r"/recordings/wrec-1$", "webex/recording_get.json")
    transport.on("GET", r"webex-dl\.example/rec/wrec-1\.mp4", body=b"x" * 22)
    items = adapter.list_recordings(org.ctx("webex"), {"meeting_key": "class-session-1"}).output["items"]
    assert items[0]["provider_recording_id"] == "wrec-1" and items[0]["bytes"] == 22 and items[0]["kind"] == "video"
    r = adapter.import_recording(
        org.ctx("webex"), {"meeting_key": "class-session-1", "provider_recording_id": "wrec-1"}
    )
    assert r.error is None and r.output["bytes"] == 22 and documents.stored[0]["data"] == b"x" * 22
    assert "authorization" not in transport.last("GET", "webex-dl.example").headers


def test_authorisation_flow(adapter, transport):
    ctx = {"organisation_id": "o", "connection_id": "c", "provider": "webex", "mode": "sandbox"}
    url = adapter.begin_authorisation(
        ctx, {"state": "st", "code_challenge": "C" * 43, "redirect_uri": "https://hub.example/cb"}
    ).output["authorize_url"]
    q = parse_qs(urlsplit(url).query)
    assert (
        url.startswith("https://webexapis.com/v1/authorize?")
        and q["client_id"] == ["platform-webex-id"]
        and q["code_challenge_method"] == ["S256"]
    )
    assert "meeting:admin_schedule_write" in q["scope"][0]
    transport.on("POST", W + "/access_token", "webex/token.json")
    transport.on("GET", W + "/people/me", "webex/people_me.json")
    done = adapter.complete_authorisation(
        ctx, {"code": "c1", "code_verifier": "V" * 43, "redirect_uri": "https://hub.example/cb"}
    ).output
    assert done["secrets"] == {"access_token": "webex-access-1", "refresh_token": "webex-refresh-1"} and done[
        "provider_subject"
    ].startswith("Y2lzY29")
    f = form_of(transport.last("POST", "/access_token"))
    assert (
        f["grant_type"] == "authorization_code"
        and f["client_secret"] == "platform-webex-secret"
        and f["code_verifier"] == "V" * 43
    )
    again = adapter.refresh_authorisation({**ctx, "secrets": {"refresh_token": "r"}})
    assert (
        again.output["secrets"]["access_token"] == "webex-access-1"
        and form_of(transport.last("POST", "/access_token"))["grant_type"] == "refresh_token"
    )
    assert adapter.revoke_authorisation(ctx).output == {"revoked": False}


def test_webhooks_are_registered_with_the_connections_secret(adapter, transport, org):
    transport.on("POST", W + "/webhooks$", "webex/webhook_created.json")
    provider, _ = adapter._provider(
        __import__("eos_video_conferencing.domain.context", fromlist=["Context"]).Context.coerce(org.ctx("webex"))
    )
    ids = provider.register_webhooks(
        __import__("eos_video_conferencing.domain.context", fromlist=["Context"]).Context.coerce(org.ctx("webex")),
        "https://educationos.example/hook",
    )
    assert len(ids) == 3
    sent = [body_of(r) for r in transport.sent("POST", "/webhooks")]
    assert {(s["resource"], s["event"]) for s in sent} == {
        ("meetings", "started"),
        ("meetings", "ended"),
        ("recordings", "created"),
    }
    assert all(s["secret"] == WEBEX_SECRET and s["targetUrl"] == "https://educationos.example/hook" for s in sent)


def test_healthcheck(adapter, transport, org):
    transport.on("GET", W + "/people/me", "webex/people_me.json")
    assert adapter.healthcheck(org.ctx("webex")).output["status"] == "healthy"


@pytest.mark.parametrize("bad", ["../x", "a b", "x" * 300])
def test_a_hostile_recording_id_is_invalid_input_never_a_url(adapter, transport, org, bad):
    make(adapter, transport, org)
    assert (
        adapter.import_recording(
            org.ctx("webex"), {"meeting_key": "class-session-1", "provider_recording_id": bad}
        ).error["code"]
        == "invalid_request"
    )
