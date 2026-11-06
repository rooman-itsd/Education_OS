"""Microsoft Teams through Graph onlineMeetings, against replayed fixtures."""

from __future__ import annotations

import json
from datetime import timedelta

import httpx
import pytest
from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_video_conferencing.infrastructure import crypto
from eos_video_conferencing.infrastructure.config import Config
from eos_video_conferencing.infrastructure.models import GraphSubscription, Meeting
from sqlalchemy import select
from vc_support import body_of, create_input, form_of

G = r"https://graph\.example/v1\.0"
ORGANISER = "teacher@college.example.com"
MEETING = "MSpkYzE3NjcyNS01MTA1LTQyZjQtYjRjZS00ZDE5YzRiYTVjNzEqMCoqMTk6bWVldGluZ19ZMkV5.example"


@pytest.fixture(autouse=True)
def graph(monkeypatch):
    monkeypatch.setenv("VIDEO_CONFERENCING_TEAMS_GRAPH_BASE_URL", "https://graph.example/v1.0")


def make(adapter, transport, org, key="class-session-1", subscription=True, **over):
    transport.on("POST", r"login\.microsoftonline\.com/.+/oauth2/v2\.0/token", "teams/token.json")
    transport.on("POST", G + r"/users/.+/onlineMeetings$", "teams/create_online_meeting.json", status=201)
    if subscription:
        transport.on("POST", G + "/subscriptions", "teams/subscription_created.json", status=201)
    r = adapter.create_meeting(org.ctx("teams"), create_input(key, **over))
    assert r.error is None, r.error
    return r.output


def test_create_posts_an_online_meeting_for_the_organiser_and_returns_one_link(adapter, transport, org):
    out = make(adapter, transport, org)
    req = transport.last("POST", r"onlineMeetings$")
    assert req.url.path == f"/v1.0/users/{ORGANISER}/onlineMeetings"
    b = body_of(req)
    assert b["subject"] == "Physics XI A: Optics" and b["startDateTime"] == "2026-11-09T04:30:00.0000000Z"
    assert b["endDateTime"] == "2026-11-09T05:15:00.0000000Z" and b["recordAutomatically"] is True
    assert out["join_url"].startswith("https://teams.example/l/meetup-join/") and out["host_join_url"] is None
    assert out["passcode"] == "aB3dE5" and out["dial_in"][0]["number"] == "+91 80 1234 5678"
    assert out["provider_meeting_id"] == MEETING


def test_the_token_is_fetched_per_tenant_with_client_credentials_and_reused(adapter, transport, org):
    make(adapter, transport, org, "a")
    make(adapter, transport, org, "b", subscription=False)
    tokens = transport.sent("POST", "oauth2/v2.0/token")
    assert len(tokens) == 1 and "11111111-2222-3333-4444-555555555555" in str(tokens[0].url)
    assert form_of(tokens[0]) == {
        "client_id": "platform-teams-id",
        "client_secret": "platform-teams-secret",
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }
    assert transport.last("POST", r"onlineMeetings$").headers["authorization"] == "Bearer graph-access-token-1"


def test_a_tenant_without_the_access_policy_gets_the_powershell_hint(adapter, transport, org):
    transport.on("POST", "oauth2/v2.0/token", "teams/token.json")
    transport.on("POST", G + r"/users/.+/onlineMeetings$", "teams/error_no_access_policy.json", status=403)
    e = adapter.create_meeting(org.ctx("teams"), create_input()).error
    assert e["code"] == "auth_failed" and e["provider_code"] == "access_policy_missing" and e["retryable"] is False
    assert "New-CsApplicationAccessPolicy" in e["detail"] and "Grant-CsApplicationAccessPolicy" in e["detail"]


def test_an_organiser_who_is_not_a_user_is_invalid_request(adapter, transport, org):
    transport.on("POST", "oauth2/v2.0/token", "teams/token.json")
    transport.on("POST", G + r"/users/.+/onlineMeetings$", "teams/error_user_not_found.json", status=404)
    e = adapter.create_meeting(org.ctx("teams"), create_input()).error
    assert e["code"] == "invalid_request" and "host_not_licensed" in e["detail"]


@pytest.mark.parametrize("tenant", ["", "../evil", "a/b", "x" * 200, None, 5])
def test_a_bad_tenant_id_is_not_configured_and_never_reaches_a_url(adapter, transport, org, tenant):
    assert (
        adapter.create_meeting(org.ctx("teams", settings={"tenant_id": tenant}), create_input()).error["code"]
        == "not_configured"
    )
    assert not transport.requests


def test_a_refused_tenant_is_auth_failed(adapter, transport, org):
    transport.on(
        "POST", "oauth2/v2.0/token", status=400, body={"error": "invalid_client", "error_description": "AADSTS7000215"}
    )
    assert adapter.create_meeting(org.ctx("teams"), create_input()).error["code"] == "auth_failed"


def test_update_patches_the_meeting_and_cancel_deletes_it(adapter, transport, org):
    make(adapter, transport, org)
    transport.on("PATCH", G + r"/users/.+/onlineMeetings/.+", "teams/create_online_meeting.json")
    transport.on("DELETE", G + r"/users/.+/onlineMeetings/.+", status=204)
    r = adapter.update_meeting(
        org.ctx("teams"),
        {"meeting_key": "class-session-1", "title": "Optics revision", "starts_at": "2026-11-09T06:00:00+00:00"},
    )
    assert r.error is None and r.output["links_changed"] is False and r.output["host_join_url"] is None
    b = body_of(transport.last("PATCH", "onlineMeetings"))
    assert (
        b["subject"] == "Optics revision"
        and b["startDateTime"] == "2026-11-09T06:00:00.0000000Z"
        and b["endDateTime"] == "2026-11-09T06:45:00.0000000Z"
    )
    assert adapter.cancel_meeting(org.ctx("teams"), {"meeting_key": "class-session-1"}).output["status"] == "cancelled"
    assert transport.last("DELETE", "onlineMeetings").url.path.endswith(MEETING)


def test_moving_a_teams_meeting_to_another_host_is_unsupported(adapter, transport, org):
    make(adapter, transport, org)
    r = adapter.update_meeting(
        org.ctx("teams"), {"meeting_key": "class-session-1", "host": {"email": "someone.else@college.example.com"}}
    )
    assert r.error["code"] == "unsupported" and not transport.sent("PATCH", "onlineMeetings")


def test_join_link_is_the_same_for_everyone(adapter, transport, org):
    out = make(adapter, transport, org)
    for role in ("host", "attendee"):
        got = adapter.join_link(
            org.ctx("teams"), {"meeting_key": "class-session-1", "person_id": org.id, "display_name": "A", "role": role}
        ).output
        assert got["url"] == out["join_url"]


def test_attendance_reads_the_latest_report_and_marks_the_meeting_ended(adapter, transport, org, clock):
    make(adapter, transport, org)
    clock.now = clock.now.replace(day=9, hour=6)
    transport.on("GET", G + r"/users/.+/onlineMeetings/.+/attendanceReports$", "teams/attendance_reports.json")
    transport.on("GET", r"/attendanceReports/report-1", "teams/attendance_report.json")
    anita = "00000000-0000-4000-8000-0000000000a1"
    r = adapter.fetch_attendance(
        org.ctx(
            "teams",
            settings={"tenant_id": "11111111-2222-3333-4444-555555555555", "email_domain": "college.example.com"},
        ),
        {"meeting_key": "class-session-1", "roster": [{"person_id": anita, "email": "anita.rao@college.example.com"}]},
    )
    assert r.error is None and r.output["complete"] is True
    by = {p["display_name"]: p for p in r.output["participants"]}
    assert (
        by["Meera Iyer"]["role"] == "host"
        and by["Anita Rao"]["person_id"] == anita
        and by["Anita Rao"]["total_seconds"] == 2520
    )
    assert by["Unknown caller"]["person_id"] is None and len(by["Anita Rao"]["intervals"]) == 2
    assert "expand=attendanceRecords" in str(transport.last("GET", "report-1").url).replace("%24", "$").replace(
        "$expand", "expand"
    )
    assert adapter.get_meeting(org.ctx("teams"), {"meeting_key": "class-session-1"}).output["status"] == "ended"


def test_attendance_before_any_report_exists_is_empty_and_incomplete(adapter, transport, org):
    make(adapter, transport, org)
    transport.on("GET", r"/attendanceReports$", body={"value": []})
    r = adapter.fetch_attendance(org.ctx("teams"), {"meeting_key": "class-session-1"})
    assert r.output == {"meeting_id": r.output["meeting_id"], "participants": [], "complete": False}


def test_recordings_and_transcripts_are_listed_and_imported(adapter, transport, org, documents):
    make(adapter, transport, org)
    transport.on("GET", r"/onlineMeetings/.+/recordings$", "teams/recordings.json")
    transport.on("GET", r"/onlineMeetings/.+/transcripts$", "teams/transcripts.json")
    items = adapter.list_recordings(org.ctx("teams"), {"meeting_key": "class-session-1"}).output["items"]
    assert [(i["provider_recording_id"], i["kind"]) for i in items] == [("rec-1", "video"), ("tr-1", "transcript")]
    transport.on("GET", r"/recordings/rec-1/content", body=b"VIDEO", status=200)
    r = adapter.import_recording(org.ctx("teams"), {"meeting_key": "class-session-1", "provider_recording_id": "rec-1"})
    assert r.error is None and documents.stored[0]["data"] == b"VIDEO" and r.output["bytes"] == 5


def test_due_attendance_lists_meetings_whose_report_should_exist(adapter, transport, org, clock):
    make(adapter, transport, org, "soon")
    assert adapter.due_attendance(org.ctx("teams")).output == {"meeting_keys": []}
    clock.now = clock.now.replace(day=9, hour=5, minute=29)  # 14 minutes after the 05:15 end
    assert adapter.due_attendance(org.ctx("teams")).output == {"meeting_keys": []}
    clock.advance(minutes=2)
    assert adapter.due_attendance(org.ctx("teams")).output == {"meeting_keys": ["soon"]}


# --- the recordings subscription -------------------------------------------------------------------------------


def sub_rows(org):
    with platform_scope(), SessionLocal() as db:
        return db.scalars(select(GraphSubscription).where(GraphSubscription.organisation_id == org.id)).all()


def test_the_first_meeting_creates_a_subscription_with_a_derived_client_state_that_is_not_stored(
    adapter, transport, org, clock
):
    make(adapter, transport, org)
    b = body_of(transport.last("POST", "/subscriptions"))
    assert b["changeType"] == "created" and b["resource"] == "communications/onlineMeetings/getAllRecordings"
    assert (
        b["notificationUrl"]
        == f"https://educationos.example/api/v1/integration-hub/inbound/video-conferencing/{org.connection_id}"
    )
    assert b["lifecycleNotificationUrl"] == b["notificationUrl"]
    assert (
        b["expirationDateTime"] == "2026-11-08T05:55:00.0000000Z" and b["latestSupportedTlsVersion"] == "v1_2"
    )  # under 3 days
    (row,) = sub_rows(org)
    assert row.subscription_id == "sub-7f1c" and row.client_state_ref != b["clientState"]
    assert b["clientState"] == crypto.client_state(Config.load(), org.connection_id, row.client_state_ref)
    make(adapter, transport, org, "second", subscription=False)  # a live subscription is reused
    assert len(transport.sent("POST", "/subscriptions")) == 1


def test_a_failed_subscription_does_not_fail_the_meeting_and_is_retried_by_renew(adapter, transport, org):
    transport.on("POST", "oauth2/v2.0/token", "teams/token.json")
    transport.on("POST", G + r"/users/.+/onlineMeetings$", "teams/create_online_meeting.json", status=201)
    transport.on("POST", G + "/subscriptions", (502, "{}", {}, None), (201, json.dumps({"id": "sub-2"}), {}, None))
    assert adapter.create_meeting(org.ctx("teams"), create_input()).error is None and not sub_rows(org)
    assert adapter.renew_subscriptions(org.ctx("teams")).output == {"renewed": True}
    assert [s.subscription_id for s in sub_rows(org)] == ["sub-2"]


def test_renewal_extends_a_subscription_before_it_lapses(adapter, transport, org, clock):
    make(adapter, transport, org)
    assert adapter.renew_subscriptions(org.ctx("teams")).output == {
        "renewed": False
    }  # three days left, lead is 12 hours
    clock.advance(hours=61)  # 11 hours before it ends
    transport.on("PATCH", G + r"/subscriptions/sub-7f1c", "teams/subscription_created.json")
    assert adapter.renew_subscriptions(org.ctx("teams")).output == {"renewed": True}
    assert body_of(transport.last("PATCH", "subscriptions"))["expirationDateTime"] == "2026-11-10T18:55:00.0000000Z"
    assert sub_rows(org)[0].expires_at.replace(tzinfo=None) == clock.now.replace(tzinfo=None) + timedelta(
        days=3
    ) - timedelta(minutes=5)


def test_a_subscription_graph_has_forgotten_is_recreated(adapter, transport, org, clock):
    make(adapter, transport, org)
    clock.advance(hours=61)
    transport.on("PATCH", G + r"/subscriptions/sub-7f1c", status=404, body={"error": {"code": "ResourceNotFound"}})
    transport.routes[:] = [r for r in transport.routes if r[0] != "POST" or "subscriptions" not in r[1].pattern]
    transport.on("POST", G + "/subscriptions", body={"id": "sub-new"}, status=201)
    assert adapter.renew_subscriptions(org.ctx("teams")).output == {"renewed": True}
    assert [s.subscription_id for s in sub_rows(org)] == ["sub-new"]


def test_without_a_public_url_the_subscription_is_not_configured(adapter, transport, org, monkeypatch):
    monkeypatch.delenv("VIDEO_CONFERENCING_PUBLIC_BASE_URL")
    transport.on("POST", "oauth2/v2.0/token", "teams/token.json")
    assert adapter.renew_subscriptions(org.ctx("teams")).error["code"] == "not_configured"


def test_healthcheck_is_the_token_exchange_and_creates_nothing(adapter, transport, org):
    transport.on("POST", "oauth2/v2.0/token", "teams/token.json")
    assert adapter.healthcheck(org.ctx("teams")).output["status"] == "healthy"
    assert all("onlineMeetings" not in str(r.url) for r in transport.requests)
    transport.routes.clear()
    transport.on("POST", "oauth2/v2.0/token", status=401, body={"error": "invalid_client"})
    from eos_video_conferencing.infrastructure.providers import teams

    teams._TOKENS.clear()
    assert adapter.healthcheck(org.ctx("teams")).output["status"] == "auth_failed"
    transport.routes.clear()
    transport.on("POST", "oauth2/v2.0/token", raises=httpx.ConnectError("down"))
    assert adapter.healthcheck(org.ctx("teams")).output["status"] == "unreachable"


def test_admin_consent_url_and_completion(adapter, transport, org):
    ctx = org.ctx("teams", secrets={})
    url = adapter.begin_authorisation(
        ctx, {"state": "st", "code_challenge": "C" * 43, "redirect_uri": "https://hub.example/cb"}
    ).output["authorize_url"]
    assert (
        url.startswith("https://login.microsoftonline.com/11111111-2222-3333-4444-555555555555/adminconsent?")
        and "client_id=platform-teams-id" in url
    )
    transport.on("POST", "oauth2/v2.0/token", "teams/token.json")
    done = adapter.complete_authorisation(
        ctx,
        {
            "code": "99999999-2222-3333-4444-555555555555",
            "code_verifier": "V" * 43,
            "redirect_uri": "https://hub.example/cb",
        },
    ).output
    assert done["provider_subject"] == "99999999-2222-3333-4444-555555555555" and done["secrets"] == {}
    assert (
        adapter.complete_authorisation(
            ctx, {"code": "../../x", "code_verifier": "V" * 43, "redirect_uri": "https://hub.example/cb"}
        ).error["code"]
        == "invalid_request"
    )


def test_meeting_rows_hold_the_organiser_for_later_calls(adapter, transport, org):
    make(adapter, transport, org)
    with platform_scope(), SessionLocal() as db:
        assert db.scalar(select(Meeting.host_user_id).where(Meeting.organisation_id == org.id)) == ORGANISER
