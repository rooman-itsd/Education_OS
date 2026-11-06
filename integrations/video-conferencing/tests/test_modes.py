"""Modes (mock, sandbox, live), the start-up refusal, and that no secret ever reaches a log, a repr or an error."""

from __future__ import annotations

import json
import logging

import pytest
from eos_video_conferencing.application.adapter import VideoConferencingAdapter, get_adapter, startup_check
from eos_video_conferencing.domain.context import Context
from eos_video_conferencing.domain.errors import AdapterError
from eos_video_conferencing.infrastructure.config import Config
from vc_support import DATA_KEY, JITSI_SECRET, ZOOM_SECRET, create_input


def test_mock_is_the_default_mode_and_touches_no_network(adapter, transport, org):
    ctx = org.ctx("zoom", mode=None, secrets={})
    out = adapter.create_meeting(ctx, create_input()).output
    assert out["join_url"].startswith("https://mock.zoom.example/j/") and out["passcode"] == "mock-pass"
    assert adapter.healthcheck(ctx).output["status"] == "healthy"
    assert adapter.create_meeting(ctx, create_input()).output["meeting_id"] == out["meeting_id"]
    assert not transport.requests


@pytest.mark.parametrize("provider", ["zoom", "teams", "webex", "jitsi"])
def test_mock_mode_supports_the_whole_port(adapter, transport, org, provider):
    ctx = org.ctx(provider, mode="mock", secrets={})
    out = adapter.create_meeting(ctx, create_input()).output
    who = {"meeting_key": "class-session-1"}
    assert adapter.update_meeting(ctx, {**who, "duration_minutes": 50}).error is None
    assert (
        adapter.join_link(ctx, {**who, "person_id": org.id, "display_name": "A"}).output["url"].startswith("https://")
    )
    assert adapter.get_meeting(ctx, who).output["meeting_id"] == out["meeting_id"]
    att, rec = adapter.fetch_attendance(ctx, who), adapter.list_recordings(ctx, who)
    if provider == "jitsi":
        assert att.error["code"] == rec.error["code"] == "unsupported"
    else:
        assert (
            att.output["participants"][0]["display_name"] == "Mock Student"
            and rec.output["items"][0]["provider_recording_id"] == "mock-rec-1"
        )
        imported = adapter.import_recording(ctx, {**who, "provider_recording_id": "mock-rec-1"})
        assert imported.error is None and imported.output["bytes"] == len(b"mock recording bytes")
    assert adapter.cancel_meeting(ctx, who).output["status"] == "cancelled"
    assert not transport.requests


def test_mock_authorisation_round_trip(adapter, org):
    ctx = org.ctx("zoom", mode="mock", secrets={})
    assert (
        adapter.begin_authorisation(
            ctx, {"state": "s", "code_challenge": "C" * 43, "redirect_uri": "https://hub.example/cb"}
        )
        .output["authorize_url"]
        .startswith("https://mock.zoom.example/")
    )
    done = adapter.complete_authorisation(
        ctx, {"code": "c", "code_verifier": "V" * 43, "redirect_uri": "https://hub.example/cb"}
    ).output
    assert done["secrets"]["access_token"] == "mock-access-token"
    assert adapter.revoke_authorisation(ctx).output == {"revoked": True}


def test_mock_mode_still_verifies_signatures_for_real(adapter, org):
    from vc_support import fixture, request

    raw = fixture("zoom/event_meeting_ended.json").encode()
    assert (
        adapter.verify_inbound(org.ctx("zoom", mode="mock"), request(raw, {}, suffix="c")).output["verdict"] == "reject"
    )


def test_the_configured_mode_applies_when_the_hub_names_none(transport, clock, org, monkeypatch):
    monkeypatch.setenv("VIDEO_CONFERENCING_MODE", "sandbox")
    a = VideoConferencingAdapter(client_factory=transport.factory(), clock=clock)
    transport.on("POST", r"oauth/token", "zoom/token_s2s.json")
    transport.on("POST", r"/meetings$", "zoom/create_meeting.json", status=201)
    assert (
        a.create_meeting(org.ctx("zoom", mode=None), create_input())
        .output["join_url"]
        .startswith("https://zoom.example/")
    )
    assert len(transport.sent("POST", "/meetings$")) == 1


def test_a_bad_mode_value_is_not_configured(adapter, org, monkeypatch):
    monkeypatch.setenv("VIDEO_CONFERENCING_MODE", "production")
    assert adapter.create_meeting(org.ctx("zoom", mode=None), create_input()).error["code"] == "not_configured"


def test_live_refuses_to_start_without_its_credentials(monkeypatch):
    for k in ("ZOOM_CLIENT_ID", "TEAMS_CLIENT_SECRET", "WEBEX_CLIENT_SECRET", "DATA_KEY", "PUBLIC_BASE_URL"):
        monkeypatch.delenv("VIDEO_CONFERENCING_" + k)
    monkeypatch.setenv("VIDEO_CONFERENCING_MODE", "live")
    with pytest.raises(AdapterError) as e:
        get_adapter()
    detail = e.value.detail
    for need in (
        "VIDEO_CONFERENCING_DATA_KEY",
        "VIDEO_CONFERENCING_ZOOM_CLIENT_ID",
        "VIDEO_CONFERENCING_TEAMS_CLIENT_SECRET",
        "VIDEO_CONFERENCING_WEBEX_CLIENT_SECRET",
        "VIDEO_CONFERENCING_PUBLIC_BASE_URL",
    ):
        assert need in detail
    assert e.value.code == "not_configured"


def test_live_starts_when_everything_is_set_and_only_checks_the_providers_it_serves(monkeypatch):
    monkeypatch.setenv("VIDEO_CONFERENCING_MODE", "live")
    assert get_adapter().describe()["adapter"] == "video-conferencing"
    for k in ("ZOOM_CLIENT_ID", "TEAMS_CLIENT_ID"):
        monkeypatch.delenv("VIDEO_CONFERENCING_" + k)
    with pytest.raises(AdapterError):
        startup_check()
    monkeypatch.setenv("VIDEO_CONFERENCING_PROVIDERS", "webex,jitsi")
    startup_check()  # an institution on Webex and Jitsi needs neither Zoom's nor Microsoft's app


def test_sandbox_needs_the_data_key_but_not_the_platform_apps(monkeypatch):
    monkeypatch.setenv("VIDEO_CONFERENCING_MODE", "sandbox")
    monkeypatch.delenv("VIDEO_CONFERENCING_TEAMS_CLIENT_ID")
    startup_check()
    monkeypatch.delenv("VIDEO_CONFERENCING_DATA_KEY")
    with pytest.raises(AdapterError, match="DATA_KEY"):
        startup_check()


def test_without_a_data_key_nothing_outside_mock_is_stored(adapter, transport, org, monkeypatch):
    monkeypatch.delenv("VIDEO_CONFERENCING_DATA_KEY")
    transport.on("POST", r"oauth/token", "zoom/token_s2s.json")
    transport.on("POST", r"/meetings$", "zoom/create_meeting.json", status=201)
    r = adapter.create_meeting(org.ctx("zoom"), create_input())
    assert r.error["code"] == "not_configured" and "DATA_KEY" in r.error["detail"]
    monkeypatch.setenv("VIDEO_CONFERENCING_DATA_KEY", "not-a-fernet-key")
    assert adapter.create_meeting(org.ctx("zoom"), create_input("two")).error["code"] == "not_configured"


def test_a_different_key_cannot_read_stored_links(adapter, transport, org, monkeypatch):
    from cryptography.fernet import Fernet

    transport.on("POST", r"oauth/token", "zoom/token_s2s.json")
    transport.on("POST", r"/meetings$", "zoom/create_meeting.json", status=201)
    assert adapter.create_meeting(org.ctx("zoom"), create_input()).error is None
    monkeypatch.setenv("VIDEO_CONFERENCING_DATA_KEY", Fernet.generate_key().decode())
    e = adapter.create_meeting(org.ctx("zoom"), create_input()).error
    assert e["code"] == "not_configured" and "decrypted" in e["detail"]


SECRETS = [
    "s2s-secret",
    "s2s-access-token-1",
    "webex-access-1",
    "graph-access-token-1",
    JITSI_SECRET,
    ZOOM_SECRET,
    DATA_KEY,
    "platform-zoom-secret",
    "platform-teams-secret",
    "platform-webex-secret",
]


def test_no_secret_reaches_the_log_a_repr_or_an_error(adapter, transport, org, caplog):
    caplog.set_level(logging.DEBUG)
    transport.on("POST", r"oauth/token", "zoom/token_s2s.json")
    transport.on(
        "POST",
        r"/meetings$",
        status=500,
        body={"code": 1, "message": "s2s-access-token-1 appears in this provider message"},
    )
    transport.on("POST", r"oauth2/v2.0/token", "teams/token.json")
    transport.on(
        "POST",
        r"/onlineMeetings$",
        status=500,
        body={"error": {"code": "x", "message": "graph-access-token-1 in the message"}},
    )
    results = [adapter.create_meeting(org.ctx(p), create_input(f"k-{p}")) for p in ("zoom", "teams", "webex", "jitsi")]
    results.append(
        adapter.begin_authorisation(
            org.ctx("zoom"), {"state": "s", "code_challenge": "C" * 43, "redirect_uri": "https://hub.example/cb"}
        )
    )
    dump = (
        json.dumps([r.to_dict() for r in results], default=str)
        + repr(Context.coerce(org.ctx("zoom")))
        + caplog.text
        + repr(Config.load())
        + Config.load().describe()
    )
    for secret in SECRETS:
        assert secret not in dump, secret
    assert "appears in this provider message" not in dump


def test_the_context_repr_hides_secrets(org):
    assert "s2s-secret" not in repr(Context.coerce(org.ctx("zoom")))
