"""Self-hosted Jitsi: no API, so rooms are random names and join links are JWTs we sign (docs/prd.md)."""

from __future__ import annotations

import time
from datetime import timedelta

import jwt
import pytest
from vc_support import JITSI_SECRET, START, create_input

PERSON = "00000000-0000-4000-8000-000000000001"


def make(adapter, org, key="class-session-1", **over):
    r = adapter.create_meeting(org.ctx("jitsi"), create_input(key, **over))
    assert r.error is None, r.error
    return r.output


def link(adapter, org, role="attendee", key="class-session-1", **ctx):
    return adapter.join_link(
        org.ctx("jitsi", **ctx),
        {
            "meeting_key": key,
            "person_id": PERSON,
            "display_name": "Anita Rao",
            "email": "anita@college.example.com",
            "role": role,
        },
    )


def claims(url: str) -> dict:
    token = url.split("?jwt=")[1]
    # the test clock is fixed in the past, so expiry is asserted from the claims rather than by the library
    return jwt.decode(
        token, JITSI_SECRET, algorithms=["HS256"], audience="jitsi", options={"verify_exp": False, "verify_nbf": False}
    )


def test_create_makes_a_random_room_and_calls_nothing(adapter, transport, org):
    a, b = make(adapter, org, "a"), make(adapter, org, "b")
    assert a["join_url"] != b["join_url"] and a["join_url"].startswith("https://meet.college.example/")
    room = a["join_url"].rsplit("/", 1)[1]
    assert len(room) >= 24 and room.isalnum()  # not guessable, unlike a class name
    assert a["host_join_url"] is None and a["passcode"] is None and a["provider_meeting_id"] is None
    assert not transport.requests


def test_room_prefix_comes_from_the_connection(adapter, org):
    out = adapter.create_meeting(
        org.ctx("jitsi", settings={"base_url": "https://meet.college.example", "app_id": "x", "room_prefix": "phys"}),
        create_input(),
    ).output
    assert out["join_url"].rsplit("/", 1)[1].startswith("phys-")


def test_the_join_link_is_a_signed_token_with_jitsis_documented_claims(adapter, org, clock):
    make(adapter, org)
    out = link(adapter, org).output
    assert out["url"].startswith("https://meet.college.example/") and "?jwt=" in out["url"]
    c = claims(out["url"])
    room = out["url"].split("?")[0].rsplit("/", 1)[1]
    assert (c["iss"], c["aud"], c["sub"], c["room"]) == ("eos-college", "jitsi", "meet.college.example", room)
    assert c["context"]["user"] == {
        "id": PERSON,
        "name": "Anita Rao",
        "moderator": False,
        "email": "anita@college.example.com",
    }
    assert c["moderator"] is False
    assert jwt.get_unverified_header(out["url"].split("?jwt=")[1])["alg"] == "HS256"
    assert c["exp"] == int((clock.now + timedelta(seconds=7200)).timestamp()) and out["expires_at"].startswith(
        "2026-11-05T08:00:00"
    )


def test_only_hosts_and_co_hosts_are_moderators(adapter, org):
    make(adapter, org)
    assert [
        claims(link(adapter, org, role).output["url"])["context"]["user"]["moderator"]
        for role in ("host", "co_host", "attendee")
    ] == [True, True, False]


def test_a_token_never_outlives_the_meeting_by_more_than_an_hour(adapter, org, clock):
    make(adapter, org)  # 04:30 to 05:15 on the 9th
    clock.now = clock.now.replace(day=9, hour=5, minute=0)
    c = claims(link(adapter, org).output["url"])
    assert c["exp"] == int((clock.now.replace(hour=6, minute=15)).timestamp())


def test_a_link_is_refused_once_the_meeting_is_over_or_cancelled(adapter, org, clock):
    make(adapter, org)
    clock.now = clock.now.replace(day=9, hour=7)
    assert link(adapter, org).error["code"] == "conflict"
    clock.now = clock.now.replace(day=5, hour=6)
    assert adapter.cancel_meeting(org.ctx("jitsi"), {"meeting_key": "class-session-1"}).output["status"] == "cancelled"
    assert link(adapter, org).error["code"] == "conflict"


def test_links_are_minted_not_stored(adapter, org):
    from eos_core.db import SessionLocal
    from eos_core.tenant import platform_scope
    from eos_video_conferencing.infrastructure.models import Meeting
    from sqlalchemy import select

    make(adapter, org)
    url = link(adapter, org).output["url"]
    with platform_scope(), SessionLocal() as db:
        m = db.scalar(select(Meeting).where(Meeting.organisation_id == org.id))
        assert url.split("?jwt=")[1] not in repr(vars(m))


def test_update_changes_the_schedule_only_and_keeps_the_room(adapter, org):
    first = make(adapter, org)
    r = adapter.update_meeting(
        org.ctx("jitsi"),
        {"meeting_key": "class-session-1", "starts_at": "2026-11-09T06:00:00+00:00", "duration_minutes": 90},
    )
    assert r.error is None and r.output["links_changed"] is False and r.output["join_url"] == first["join_url"]


def test_the_token_secret_must_be_set_outside_mock_mode_and_a_wrong_secret_does_not_verify(adapter, org):
    make(adapter, org)
    assert link(adapter, org, secrets={}).error["code"] == "not_configured"
    url = link(adapter, org).output["url"]
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(
            url.split("?jwt=")[1], "some-other-secret-of-sufficient-length-0123", algorithms=["HS256"], audience="jitsi"
        )


def test_attendance_and_recordings_are_unsupported(adapter, org):
    make(adapter, org)
    for op, args in (
        (adapter.fetch_attendance, {"meeting_key": "class-session-1"}),
        (adapter.list_recordings, {"meeting_key": "class-session-1"}),
        (adapter.import_recording, {"meeting_key": "class-session-1", "provider_recording_id": "x"}),
    ):
        e = op(org.ctx("jitsi"), args).error
        assert e["code"] == "unsupported" and e["retryable"] is False


@pytest.mark.parametrize(
    "url",
    [
        "",
        "ftp://x",
        "https://user:pw@meet.example",
        "https://meet.example?x=1",
        "javascript:alert(1)",
        "https://",
        "//meet.example",
        "https://meet.example:notaport",
    ],
)
def test_a_bad_base_url_is_not_configured(adapter, org, url):
    r = adapter.create_meeting(org.ctx("jitsi", settings={"base_url": url, "app_id": "x"}), create_input())
    assert r.error["code"] == "not_configured"


def test_live_mode_wants_https(adapter, org):
    r = adapter.create_meeting(
        org.ctx("jitsi", mode="live", settings={"base_url": "http://meet.local", "app_id": "x"}), create_input()
    )
    assert r.error["code"] == "not_configured"
    assert (
        adapter.create_meeting(
            org.ctx("jitsi", mode="sandbox", settings={"base_url": "http://localhost:8000", "app_id": "x"}),
            create_input("local"),
        ).error
        is None
    )


def test_healthcheck_asks_the_server_in_sandbox_and_nothing_in_mock(adapter, transport, org):
    transport.on("GET", r"meet\.college\.example/$", status=200, body="<html>")
    assert adapter.healthcheck(org.ctx("jitsi")).output["status"] == "healthy"
    transport.routes.clear()
    assert (
        adapter.healthcheck(org.ctx("jitsi", mode="mock")).output["status"] == "healthy"
        and len(transport.requests) == 1
    )


_ = (START, time)
