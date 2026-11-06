"""GET /meetings (contracts/openapi.yaml): who may call it, what it returns and what it never does."""

from __future__ import annotations

import base64
import json
import uuid

import pytest
from eos_core.config import load_role_grants, permissions_for
from eos_video_conferencing.api.router import READ, router
from fastapi.routing import APIRoute
from vc_support import PREFIX, create_input


@pytest.fixture
def zoom(transport):
    transport.on("POST", r"oauth/token", "zoom/token_s2s.json")
    transport.on("POST", r"/users/.+/meetings$", "zoom/create_meeting.json", status=201)
    return transport


def seed(adapter, org, n=5, provider="zoom"):
    for i in range(n):
        day = 9 + i
        assert (
            adapter.create_meeting(
                org.ctx(provider),
                create_input(
                    f"m-{i}",
                    starts_at=f"2026-11-{day:02d}T04:30:00+00:00",
                    caller_module="lms" if i % 2 else "selection-process",
                ),
            ).error
            is None
        )


def test_every_route_needs_a_token_and_the_permission(client, org):
    assert client.get(f"{PREFIX}/meetings").status_code == 401
    assert client.get(f"{PREFIX}/meetings", headers={"Authorization": "Bearer junk"}).status_code == 401
    r = client.get(f"{PREFIX}/meetings", headers=org.faculty)
    assert r.status_code == 403 and r.json()["code"] == "forbidden"


def test_the_catalogue_grants_the_key_to_org_admin_only():
    assert READ in permissions_for(["org-admin"])
    assert {role for role, keys in load_role_grants().items() if READ in keys} == {"org-admin"}


def test_every_route_names_its_permission_for_the_hosts_coverage_check():
    for route in router.routes:
        assert isinstance(route, APIRoute)
        assert {getattr(d.call, "permission", None) for d in route.dependant.dependencies} - {None} == {READ}


def test_the_list_is_newest_first_and_carries_no_links_passcodes_or_people(adapter, zoom, client, org):
    seed(adapter, org)
    body = client.get(f"{PREFIX}/meetings", headers=org.admin).json()
    assert [m["meeting_key"] for m in body["items"]] == ["m-4", "m-3", "m-2", "m-1", "m-0"] and body[
        "next_cursor"
    ] is None
    first = body["items"][0]
    assert set(first) == {
        "meeting_key",
        "caller_module",
        "provider",
        "provider_meeting_id",
        "status",
        "starts_at",
        "duration_minutes",
        "started_at",
        "ended_at",
        "attendance_received",
        "recordings",
    }
    text = json.dumps(body)
    assert "zoom.example" not in text and "Qw7rT2" not in text and "zak=" not in text and "teacher@" not in text
    assert (
        first["provider"] == "zoom"
        and first["status"] == "scheduled"
        and first["attendance_received"] is False
        and first["recordings"] == 0
    )


def test_pages_follow_the_cursor_without_gaps_or_repeats(adapter, zoom, client, org):
    seed(adapter, org, 5)
    seen, cursor = [], None
    for _ in range(5):
        r = client.get(
            f"{PREFIX}/meetings", params={"limit": 2, **({"cursor": cursor} if cursor else {})}, headers=org.admin
        ).json()
        seen += [m["meeting_key"] for m in r["items"]]
        cursor = r["next_cursor"]
        if not cursor:
            break
    assert seen == ["m-4", "m-3", "m-2", "m-1", "m-0"]


def test_filters(adapter, zoom, client, org):
    seed(adapter, org, 5)

    def get(**p):
        return [m["meeting_key"] for m in client.get(f"{PREFIX}/meetings", params=p, headers=org.admin).json()["items"]]

    assert get(caller_module="lms") == ["m-3", "m-1"]
    assert (
        get(provider="jitsi") == []
        and get(status="cancelled") == []
        and len(get(provider="zoom", status="scheduled")) == 5
    )
    assert get(**{"from": "2026-11-11T00:00:00Z", "to": "2026-11-12T23:59:59Z"}) == ["m-3", "m-2"]
    assert get(**{"from": "2026-11-11T00:00:00"}) == ["m-4", "m-3", "m-2"]  # no zone: UTC


@pytest.mark.parametrize("cursor", ["garbage", "!!!", base64.urlsafe_b64encode(b"nope").decode(), base64.urlsafe_b64encode(b"not-a-date|" + b"x" * 36).decode(),
                                    base64.urlsafe_b64encode(b"2026-11-09T04:30:00+00:00|short").decode(), "A" * 200])  # fmt: skip
def test_a_bad_cursor_is_400_invalid_cursor(client, org, cursor):
    r = client.get(f"{PREFIX}/meetings", params={"cursor": cursor}, headers=org.admin)
    assert r.status_code == 400 and r.json()["detail"] == "invalid_cursor" and r.json()["code"] == "invalid_request"


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"limit": -1}, {"limit": "x"}, {"provider": "skype"}, {"status": "weird"}, {"caller_module": "Has Space"},
                                    {"from": "yesterday"}, {"cursor": "A" * 201}, {"limit": "nan"}])  # fmt: skip
def test_bad_parameters_are_422_never_500(client, org, params):
    assert client.get(f"{PREFIX}/meetings", params=params, headers=org.admin).status_code == 422


def test_attendance_and_recordings_are_reported_as_arrived(adapter, zoom, client, org):
    seed(adapter, org, 1)
    zoom.on(
        "GET", r"/past_meetings/.+/instances", body={"meetings": [{"uuid": "u1", "start_time": "2026-11-09T04:30:00Z"}]}
    )
    zoom.on("GET", r"/past_meetings/u1/participants", "zoom/past_participants.json")
    zoom.on("GET", r"/meetings/85746065432/recordings", "zoom/recordings.json")
    adapter.fetch_attendance(org.ctx("zoom"), {"meeting_key": "m-0"})
    adapter.list_recordings(org.ctx("zoom"), {"meeting_key": "m-0"})
    item = client.get(f"{PREFIX}/meetings", headers=org.admin).json()["items"][0]
    assert item["attendance_received"] is True and item["recordings"] == 2


def test_a_user_without_an_organisation_gets_403(client):
    from eos_core.security import create_token

    token = create_token(user_id=str(uuid.uuid4()), organisation_id=None, roles=["org-admin"])
    assert client.get(f"{PREFIX}/meetings", headers={"Authorization": f"Bearer {token}"}).status_code == 403
