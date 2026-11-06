"""Against a real Jitsi server with token authentication (docker-jitsi-meet). Skipped unless one is named:

    docker run ... jitsi/web with ENABLE_AUTH=1 AUTH_TYPE=jwt JWT_APP_ID=eos-college JWT_APP_SECRET=<secret>
    VIDEO_CONFERENCING_TEST_JITSI_URL=http://localhost:8000 VIDEO_CONFERENCING_TEST_JITSI_SECRET=<secret> pytest tests/test_live_jitsi.py

Nothing here runs in CI, and the other tests never open a socket."""

from __future__ import annotations

import os

import httpx
import pytest
from eos_video_conferencing.application.adapter import VideoConferencingAdapter
from vc_support import create_input

URL, SECRET = (
    os.environ.get("VIDEO_CONFERENCING_TEST_JITSI_URL"),
    os.environ.get("VIDEO_CONFERENCING_TEST_JITSI_SECRET"),
)
pytestmark = pytest.mark.skipif(
    not (URL and SECRET), reason="no Jitsi server named in VIDEO_CONFERENCING_TEST_JITSI_URL"
)


def test_a_live_jitsi_answers_the_healthcheck_and_serves_the_room_page(monkeypatch, org, no_network):
    monkeypatch.undo()  # the autouse network guard is lifted for this opt-in test
    ctx = org.ctx(
        "jitsi", mode="sandbox", settings={"base_url": URL, "app_id": "eos-college"}, secrets={"app_secret": SECRET}
    )
    adapter = VideoConferencingAdapter()
    assert adapter.healthcheck(ctx).output["status"] == "healthy"
    adapter.create_meeting(ctx, create_input())
    link = adapter.join_link(
        ctx, {"meeting_key": "class-session-1", "person_id": org.id, "display_name": "Anita", "role": "host"}
    ).output["url"]
    assert httpx.get(link.split("?")[0]).status_code < 500
