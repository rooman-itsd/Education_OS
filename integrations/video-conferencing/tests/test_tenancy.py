"""No organisation sees, changes or learns of another's meetings (module standard rule 11)."""

from __future__ import annotations

import pytest
from vc_support import PREFIX, create_input

PERSON = "00000000-0000-4000-8000-000000000001"


@pytest.fixture
def zoom(transport):
    transport.on("POST", r"oauth/token", "zoom/token_s2s.json")
    transport.on("POST", r"/users/.+/meetings$", "zoom/create_meeting.json", status=201)
    transport.on("PATCH", r"/meetings/", status=204)
    transport.on("DELETE", r"/meetings/", status=204)
    return transport


def test_the_same_meeting_key_in_two_organisations_is_two_meetings(adapter, zoom, org, other_org):
    a = adapter.create_meeting(org.ctx("zoom"), create_input("shared-key")).output
    b = adapter.create_meeting(other_org.ctx("zoom"), create_input("shared-key")).output
    assert a["meeting_id"] != b["meeting_id"] and len(zoom.sent("POST", "/meetings$")) == 2


@pytest.mark.parametrize("op", ["get_meeting", "cancel_meeting", "fetch_attendance", "list_recordings"])
def test_another_organisations_meeting_is_not_found(adapter, zoom, org, other_org, op):
    adapter.create_meeting(org.ctx("zoom"), create_input("mine"))
    r = getattr(adapter, op)(other_org.ctx("zoom"), {"meeting_key": "mine"})
    assert r.error["code"] == "not_found"
    assert (
        adapter.join_link(
            other_org.ctx("zoom"), {"meeting_key": "mine", "person_id": PERSON, "display_name": "A"}
        ).error["code"]
        == "not_found"
    )
    assert (
        adapter.update_meeting(other_org.ctx("zoom"), {"meeting_key": "mine", "title": "hijack"}).error["code"]
        == "not_found"
    )
    assert not zoom.sent("DELETE", "/meetings/") and not zoom.sent("PATCH", "/meetings/")
    assert adapter.get_meeting(org.ctx("zoom"), {"meeting_key": "mine"}).output["status"] == "scheduled"


def test_a_meeting_made_through_one_provider_is_not_served_to_another_providers_connection(adapter, zoom, org):
    adapter.create_meeting(org.ctx("zoom"), create_input("mine"))
    assert adapter.get_meeting(org.ctx("jitsi"), {"meeting_key": "mine"}).error["code"] == "not_found"
    assert adapter.create_meeting(org.ctx("jitsi"), create_input("mine")).error["code"] == "conflict"


def test_the_operator_view_never_leaks_across_organisations(adapter, zoom, client, org, other_org):
    for o in (org, other_org):
        for i in range(3):
            adapter.create_meeting(o.ctx("zoom"), create_input(f"m-{o.id[:4]}-{i}"))
    # eos_testing's assert_no_cross_tenant_leak reads organisation_id and id from every row; the contract's Meeting
    # schema carries neither (a caller only ever sees its own organisation), so the same check is made on meeting_key.
    mine = {m["meeting_key"] for m in client.get(f"{PREFIX}/meetings", headers=org.admin).json()["items"]}
    theirs = {m["meeting_key"] for m in client.get(f"{PREFIX}/meetings", headers=other_org.admin).json()["items"]}
    assert len(mine) == 3 and len(theirs) == 3 and not mine & theirs
    assert all(k.startswith(f"m-{org.id[:4]}-") for k in mine) and all(
        k.startswith(f"m-{other_org.id[:4]}-") for k in theirs
    )
