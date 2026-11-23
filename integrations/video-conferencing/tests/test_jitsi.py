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


@pytest.mark.parametrize(
    "ssrf_url",
    [
        "http://meet.local",
        "http://localhost:8000",
        "https://127.0.0.1:6379",
        "https://127.1.2.3",
        "https://10.0.0.5",
        "https://172.16.0.1",
        "https://192.168.1.1",
        "https://169.254.169.254",
        "https://0.0.0.0",
        "https://[::1]",
        "https://[fe80::1]",
        "https://[fc00::1]",
        "https://[::ffff:127.0.0.1]",
        "https://[::ffff:169.254.169.254]",
        "https://localhost:8443",
    ],
)
def test_base_url_requires_https_and_refuses_ssrf(adapter, org, ssrf_url):
    r = adapter.create_meeting(org.ctx("jitsi", settings={"base_url": ssrf_url, "app_id": "x"}), create_input())
    assert r.error["code"] == "not_configured"


def test_jitsi_mock_secret_fallback_refused_outside_dev_mode(adapter, org, monkeypatch):
    import dataclasses

    from eos_core import settings as core_settings
    from eos_video_conferencing.domain.context import Context
    from eos_video_conferencing.domain.errors import AdapterError
    from eos_video_conferencing.infrastructure.config import Config
    from eos_video_conferencing.infrastructure.providers.jitsi import JitsiProvider

    monkeypatch.setattr(core_settings, "settings", dataclasses.replace(core_settings.settings, dev_mode=False))
    ctx = Context(
        organisation_id=org.id,
        connection_id=org.connection_id,
        provider="jitsi",
        mode="mock",
        settings=org.ctx("jitsi")["settings"],
        secrets={},
    )
    res = adapter.join_link(
        ctx,
        {
            "meeting_key": "class-session-1",
            "person_id": PERSON,
            "display_name": "Anita Rao",
            "email": "anita@college.example.com",
            "role": "attendee",
        },
    )
    assert res.error["code"] == "not_configured"
    assert "mock mode is refused unless EOS_DEV_MODE=true" in res.error["detail"]

    jp = JitsiProvider(Config.load(), None, None)
    with pytest.raises(AdapterError) as e:
        jp._secret(ctx)
    assert e.value.code == "not_configured"
    assert "the connection has no app_secret" in e.value.detail


def test_healthcheck_asks_the_server_and_does_not_echo_status_code(adapter, transport, org):
    transport.on("GET", r"meet\.college\.example/$", status=200, body="<html>")
    hc = adapter.healthcheck(org.ctx("jitsi")).output
    assert hc["status"] == "healthy"
    assert hc["detail"] == "Jitsi server is reachable"
    assert "200" not in hc["detail"]

    # Degraded status also does not echo status code
    transport.routes.clear()
    transport.on("GET", r"meet\.college\.example/$", status=403, body="forbidden")
    hc_degraded = adapter.healthcheck(org.ctx("jitsi")).output
    assert hc_degraded["status"] == "degraded"
    assert hc_degraded["detail"] == "Jitsi server returned unexpected response"
    assert "403" not in hc_degraded["detail"]

    # Mock mode
    transport.routes.clear()
    assert (
        adapter.healthcheck(org.ctx("jitsi", mode="mock")).output["status"] == "healthy"
        and len(transport.requests) == 2
    )


@pytest.mark.parametrize(
    "ssrf_url",
    [
        "https://100.64.0.1",  # shared address space (CGNAT): is_private is False for it, is_global is False too
        "https://100.100.100.200",  # Alibaba Cloud's metadata address
        "https://100.127.255.255",
        "https://198.18.0.1",
        "https://192.0.0.192",
        "https://224.0.0.1",
        "https://255.255.255.255",
        "https://[::]",
        "https://[ff02::1]",
        "https://[::ffff:100.100.100.200]",  # IPv4-mapped
        "https://[::ffff:10.0.0.5]",
        "https://[64:ff9b::7f00:1]",  # NAT64 carrying 127.0.0.1
        "https://[64:ff9b::a9fe:a9fe]",  # NAT64 carrying 169.254.169.254
        "https://[2002:7f00:1::]",  # 6to4 carrying 127.0.0.1
        "https://[2002:a9fe:a9fe::1]",  # 6to4 carrying 169.254.169.254
        "https://2130706433",  # 127.0.0.1 as one decimal number
        "https://0x7f.1",
        "https://127.1",
    ],
)
def test_shared_reserved_and_carried_addresses_are_refused_too(adapter, org, ssrf_url):
    r = adapter.create_meeting(org.ctx("jitsi", settings={"base_url": ssrf_url, "app_id": "x"}), create_input())
    assert r.error["code"] == "not_configured"


def resolving(monkeypatch, *answers):
    """socket.getaddrinfo as the Jitsi provider sees it: each call answers with the next list of addresses (the last one
    repeats), and every call is recorded."""
    from eos_video_conferencing.infrastructure.providers import jitsi

    calls, queue = [], list(answers)

    def fake(host, port, *args, **kwargs):
        calls.append((host, port))
        addresses = queue.pop(0) if len(queue) > 1 else queue[0]
        return [(10 if ":" in a else 2, 1, 6, "", (a, port or 0)) for a in addresses]

    monkeypatch.setattr(jitsi.socket, "getaddrinfo", fake)
    return calls


def health_ctx(org, base_url):
    return org.ctx("jitsi", settings={"base_url": base_url, "app_id": "eos-college"})


@pytest.mark.parametrize(
    "addresses",
    [
        ["10.0.0.5"],
        ["127.0.0.1"],
        ["169.254.169.254"],
        ["100.100.100.200"],  # a public-looking name that resolves into shared address space
        ["93.184.216.34", "10.0.0.5"],  # one bad address among good ones is enough
        ["::1"],
        ["fe80::1%eth0"],
        ["::ffff:169.254.169.254"],
        ["64:ff9b::7f00:1"],
    ],
)
def test_a_name_that_resolves_to_a_blocked_address_is_refused_and_nothing_is_requested(
    adapter, transport, org, monkeypatch, addresses
):
    resolving(monkeypatch, addresses)
    for op in (adapter.healthcheck, lambda c: adapter.create_meeting(c, create_input())):
        r = op(health_ctx(org, "https://meet.college.org"))
        assert r.error["code"] == "not_configured"
    assert not transport.requests


def test_the_healthcheck_connects_to_the_address_it_validated_not_to_a_second_lookup(
    adapter, transport, org, monkeypatch
):
    """DNS rebinding: the name answers with a public address when it is checked and an internal one when it is looked up
    again. The request must go to the address that was checked, with the name kept for Host and TLS."""
    calls = resolving(monkeypatch, ["93.184.216.34"], ["169.254.169.254"])
    transport.on("GET", r"^https://93\.184\.216\.34/$", status=200, body="<html>")
    hc = adapter.healthcheck(health_ctx(org, "https://meet.college.org")).output
    assert hc["status"] == "healthy"
    (sent,) = transport.requests
    assert sent.url.host == "93.184.216.34" and sent.url.scheme == "https"
    assert sent.headers["host"] == "meet.college.org"  # the virtual host the institution's server answers for
    assert sent.extensions["sni_hostname"] == "meet.college.org"  # the TLS name, so the certificate is checked for it
    assert len(calls) == 1  # looked up once for the whole healthcheck, so there is no second answer to be fooled by


def test_the_pinned_request_keeps_the_port_the_path_and_ipv6(adapter, transport, org, monkeypatch):
    resolving(monkeypatch, ["2606:4700:4700::1111"])
    transport.on("GET", r"^https://\[2606:4700:4700::1111\]:8443/jitsi/$", status=200, body="ok")
    adapter.healthcheck(health_ctx(org, "https://meet.college.org:8443/jitsi/"))
    (sent,) = transport.requests
    assert sent.url.port == 8443 and sent.url.path == "/jitsi/"
    assert sent.headers["host"] == "meet.college.org:8443" and sent.extensions["sni_hostname"] == "meet.college.org"


def test_the_lookup_asks_for_the_connections_port(adapter, transport, org, monkeypatch):
    calls = resolving(monkeypatch, ["93.184.216.34"])
    transport.on("GET", r"93\.184\.216\.34", status=200, body="ok")
    adapter.healthcheck(health_ctx(org, "https://meet.college.org:8443"))
    assert calls == [("meet.college.org", 8443)]


def test_a_public_address_literal_is_connected_to_as_it_is(adapter, transport, org, monkeypatch):
    calls = resolving(monkeypatch, ["10.0.0.5"])  # never asked: a literal has nothing to look up
    transport.on("GET", r"^https://93\.184\.216\.34/$", status=200, body="ok")
    assert adapter.healthcheck(health_ctx(org, "https://93.184.216.34")).output["status"] == "healthy"
    assert not calls and "sni_hostname" not in transport.requests[0].extensions


def test_the_healthcheck_does_not_follow_a_redirect_to_an_internal_address(adapter, transport, org, monkeypatch):
    resolving(monkeypatch, ["93.184.216.34"])
    transport.on("GET", r"93\.184\.216\.34", status=302, headers={"location": "http://169.254.169.254/latest/"})
    hc = adapter.healthcheck(health_ctx(org, "https://meet.college.org")).output
    assert "169.254" not in hc["detail"]  # the target is not echoed
    assert len(transport.requests) == 1  # and was never requested: the redirect is not followed


def test_a_name_that_does_not_resolve_is_not_configured(adapter, transport, org, monkeypatch):
    import socket

    from eos_video_conferencing.infrastructure.providers import jitsi

    def refuse(*args, **kwargs):
        raise socket.gaierror("no such host")

    monkeypatch.setattr(jitsi.socket, "getaddrinfo", refuse)
    assert adapter.healthcheck(health_ctx(org, "https://meet.college.org")).error["code"] == "not_configured"
    assert not transport.requests


def test_development_names_are_neither_resolved_nor_allowed_outside_dev_mode(adapter, transport, org, monkeypatch):
    import dataclasses

    from eos_core import settings as core_settings

    calls = resolving(monkeypatch, ["10.0.0.5"])
    transport.on("GET", r"^https://meet\.college\.example/$", status=200, body="ok")
    assert adapter.healthcheck(org.ctx("jitsi")).output["status"] == "healthy" and not calls  # dev mode: .example

    monkeypatch.setattr(core_settings, "settings", dataclasses.replace(core_settings.settings, dev_mode=False))
    assert adapter.healthcheck(org.ctx("jitsi")).error["code"] == "not_configured"  # now it is looked up: 10.0.0.5
    assert calls == [("meet.college.example", 443)]


_ = (START, time)
