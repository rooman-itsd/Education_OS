"""Zoom allows 100 meeting create/update calls per host user per day (docs/prd.md, "Rate limits"). The adapter counts them
per host and UTC day, spreads over the connection's host pool, and holds the rest with throttled and the time Zoom resets."""

from __future__ import annotations

import pytest
from vc_support import body_of, create_input

API = r"https://api\.zoom\.us/v2"


@pytest.fixture(autouse=True)
def small_limit(monkeypatch):
    monkeypatch.setenv("VIDEO_CONFERENCING_ZOOM_CREATE_LIMIT_PER_HOST_PER_DAY", "3")


@pytest.fixture
def zoom(transport):
    transport.on("POST", r"oauth/token\?grant_type=account_credentials", "zoom/token_s2s.json")
    transport.on("POST", API + r"/users/.+/meetings$", "zoom/create_meeting.json", status=201)
    transport.on("PATCH", API + r"/meetings/", status=204)
    return transport


def create(adapter, org, n, host="teacher@college.example.com", **ctx):
    return adapter.create_meeting(org.ctx("zoom", **ctx), create_input(f"s-{n}", host={"email": host}))


def test_the_capability_tells_callers_the_limit(adapter, org):
    assert adapter.capabilities(org.ctx("zoom")).output["capabilities"]["create_limit_per_host_per_day"] == 3
    assert adapter.capabilities(org.ctx("teams")).output["capabilities"]["create_limit_per_host_per_day"] == 0


def test_the_default_limit_is_zooms_published_hundred(adapter, org, monkeypatch):
    monkeypatch.delenv("VIDEO_CONFERENCING_ZOOM_CREATE_LIMIT_PER_HOST_PER_DAY")
    assert adapter.capabilities(org.ctx("zoom")).output["capabilities"]["create_limit_per_host_per_day"] == 100


def test_the_fourth_create_for_one_host_is_held_without_calling_zoom(adapter, zoom, org, clock):
    assert [create(adapter, org, i).error for i in range(3)] == [None, None, None]
    sent = len(zoom.sent("POST", "/meetings"))
    r = create(adapter, org, 3)
    assert (
        r.error["code"] == "throttled"
        and r.error["retryable"] is True
        and r.error["provider_code"] == "zoom_daily_limit"
    )
    assert r.error["retry_after_s"] == 18 * 3600  # clock is 06:00 UTC; Zoom resets at 00:00 UTC
    assert len(zoom.sent("POST", "/meetings")) == sent
    assert (
        adapter.get_meeting(org.ctx("zoom"), {"meeting_key": "s-3"}).error["code"] == "not_found"
    )  # nothing was left behind


def test_updates_count_against_the_same_limit(adapter, zoom, org):
    create(adapter, org, 0)
    for _ in range(2):
        assert adapter.update_meeting(org.ctx("zoom"), {"meeting_key": "s-0", "duration_minutes": 30}).error is None
    r = adapter.update_meeting(org.ctx("zoom"), {"meeting_key": "s-0", "duration_minutes": 20})
    assert r.error["code"] == "throttled" and len(zoom.sent("PATCH", "/meetings/")) == 2
    assert create(adapter, org, 1).error["code"] == "throttled"


def test_the_count_resets_at_midnight_utc(adapter, zoom, org, clock):
    for i in range(3):
        create(adapter, org, i)
    assert create(adapter, org, 3).error is not None
    clock.advance(hours=17, minutes=59)
    assert create(adapter, org, 3).error is not None  # 23:59 UTC
    clock.advance(minutes=2)
    assert create(adapter, org, 3).error is None  # 00:01 UTC, the next day


def test_other_hosts_have_their_own_allowance(adapter, zoom, org):
    for i in range(3):
        create(adapter, org, i)
    assert create(adapter, org, 10, host="other.teacher@college.example.com").error is None


def test_other_organisations_do_not_share_an_allowance(adapter, zoom, org, other_org):
    for i in range(3):
        create(adapter, org, i)
    assert create(adapter, other_org, 0).error is None


def test_a_host_pool_takes_the_overflow_and_the_real_host_becomes_alternative_host(adapter, zoom, org):
    settings = {
        "account_id": "acct-1",
        "host_resolution": "pool",
        "host_pool": ["pool1@college.example.com", "pool2@college.example.com"],
    }
    for i in range(3):
        create(adapter, org, i, settings=settings)
    assert zoom.last("POST", "/meetings").url.path == "/v2/users/teacher@college.example.com/meetings"
    assert create(adapter, org, 3, settings=settings).error is None
    req = zoom.last("POST", "/meetings")
    assert req.url.path == "/v2/users/pool1@college.example.com/meetings"
    assert body_of(req)["settings"]["alternative_hosts"] == "teacher@college.example.com"
    for i in (4, 5):
        assert create(adapter, org, i, settings=settings).error is None  # pool1 is now spent
    assert create(adapter, org, 6, settings=settings).error is None
    assert zoom.last("POST", "/meetings").url.path == "/v2/users/pool2@college.example.com/meetings"
    for i in (7, 8):
        assert create(adapter, org, i, settings=settings).error is None
    assert create(adapter, org, 99, settings=settings).error["code"] == "throttled"  # the whole pool is spent
