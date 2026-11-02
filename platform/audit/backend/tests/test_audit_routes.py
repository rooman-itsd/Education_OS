"""The HTTP surface in contracts/openapi.yaml: who may call what, and that every super admin read across
organisations leaves a trail."""

from __future__ import annotations

import uuid

import pytest
from audit_support import PREFIX, Org, SuperAdmin, new_record
from eos_audit.api.router import PLATFORM_READ, READ, WRITE
from eos_core.config import permissions_for


@pytest.fixture
def org(audit_db):
    return Org(audit_db)


@pytest.fixture
def other(audit_db):
    return Org(audit_db)


@pytest.fixture
def root(audit_db):
    return SuperAdmin(audit_db)


def _post(audit_client, org, user, **over):
    return audit_client.post(f"{PREFIX}/records", json=new_record(**over), headers=org.headers(user))


# --- who may call what -----------------------------------------------------------------------------------


def test_every_route_needs_a_token(audit_client):
    assert audit_client.post(f"{PREFIX}/records", json=new_record()).status_code == 401
    assert audit_client.get(f"{PREFIX}/records").status_code == 401
    assert audit_client.get(f"{PREFIX}/records/{uuid.uuid4()}").status_code == 401
    assert audit_client.get(f"{PREFIX}/entities/application/x/history").status_code == 401


def test_a_member_without_an_audit_role_reads_nothing(audit_client, org):
    h = org.headers(org.member)
    assert audit_client.get(f"{PREFIX}/records", headers=h).status_code == 403
    assert audit_client.get(f"{PREFIX}/entities/application/x/history", headers=h).status_code == 403


def test_writing_is_not_a_privilege_a_user_holds(audit_client, org):
    """audit:record:write is held by modules through the SDK; an organisation admin cannot append records."""
    assert _post(audit_client, org, org.admin).status_code == 403


def test_the_catalogue_gives_each_role_what_its_dashboard_needs():
    assert READ in permissions_for(["org-admin"])
    assert {READ, PLATFORM_READ, "platform:audit:redact"} <= permissions_for(["super-admin"], super_admin=True)
    assert WRITE in permissions_for(["service"])
    for role in ("org-admin", "super-admin", "member"):
        assert WRITE not in permissions_for([role], super_admin=role == "super-admin")


# --- POST /records ---------------------------------------------------------------------------------------


def test_a_writer_records_an_action_as_themselves_in_their_organisation(audit_client, org):
    r = _post(audit_client, org, org.writer)
    assert r.status_code == 201
    body = r.json()
    assert body["organisation_id"] == org.id and body["actor"] == org.writer.id and body["actor_name"] == "writer"


def test_the_organisation_comes_from_the_token_never_the_body(audit_client, org, other):
    r = audit_client.post(
        f"{PREFIX}/records", json=new_record(organisation_id=other.id), headers=org.headers(org.writer)
    )
    assert r.status_code == 201 and r.json()["organisation_id"] == org.id


def test_a_replayed_client_token_is_a_200_with_the_original(audit_client, org):
    first = _post(audit_client, org, org.writer, client_token="replay-1", summary="first")
    again = _post(audit_client, org, org.writer, client_token="replay-1", summary="second")
    assert first.status_code == 201 and again.status_code == 200
    assert again.json()["id"] == first.json()["id"] and again.json()["summary"] == "first"


def test_impersonation_is_recorded_from_the_token(audit_client, org, root):
    r = audit_client.post(
        f"{PREFIX}/records", json=new_record(), headers=org.headers(org.writer, impersonated_by=root.id)
    )
    assert r.json()["context"]["impersonated_by"] == root.id


def test_a_forged_impersonated_by_in_the_body_is_dropped(audit_client, org, root):
    """Otherwise any writer could pin an action on a super admin."""
    r = _post(audit_client, org, org.writer, context={"impersonated_by": root.id, "request_id": "req-1"})
    assert r.status_code == 201
    assert r.json()["context"] == {"request_id": "req-1"}


def test_a_refusal_from_the_service_is_a_422_with_a_reason(audit_client, org):
    r = _post(audit_client, org, org.writer, after={"password": "hunter2"})
    assert r.status_code == 422 and "looks like a secret" in r.json()["detail"]


# --- reading ---------------------------------------------------------------------------------------------


def test_an_organisation_admin_reads_only_their_own_records(audit_client, org, other):
    mine = _post(audit_client, org, org.writer).json()["id"]
    theirs = _post(audit_client, other, other.writer).json()["id"]
    page = audit_client.get(f"{PREFIX}/records", headers=org.headers(org.admin)).json()
    assert [r["id"] for r in page["items"]] == [mine]
    assert audit_client.get(f"{PREFIX}/records/{theirs}", headers=org.headers(org.admin)).status_code == 404


def test_an_organisation_user_cannot_widen_their_view_with_organisation_id(audit_client, org, other):
    """The contract: organisation_id is super admin only, and ignored for other callers."""
    _post(audit_client, other, other.writer)
    page = audit_client.get(f"{PREFIX}/records", params={"organisation_id": other.id}, headers=org.headers(org.admin))
    assert page.status_code == 200 and page.json()["total"] == 0


def test_history_through_the_api_is_oldest_first(audit_client, org):
    _post(audit_client, org, org.writer, action="application.created", entity_id="app-1")
    _post(audit_client, org, org.writer, action="application.accepted", entity_id="app-1")
    story = audit_client.get(f"{PREFIX}/entities/application/app-1/history", headers=org.headers(org.admin)).json()
    assert [r["action"] for r in story["items"]] == ["application.created", "application.accepted"]
    assert story["total"] == 2
    offset_story = audit_client.get(
        f"{PREFIX}/entities/application/app-1/history", params={"offset": 1}, headers=org.headers(org.admin)
    ).json()
    assert [r["action"] for r in offset_story["items"]] == ["application.accepted"]
    assert offset_story["total"] == 2


def test_a_page_larger_than_the_contract_allows_is_refused(audit_client, org):
    assert (
        audit_client.get(f"{PREFIX}/records", params={"limit": 201}, headers=org.headers(org.admin)).status_code == 422
    )


# --- the super admin -------------------------------------------------------------------------------------


def _trail(audit_client, root) -> list[dict]:
    page = audit_client.get(f"{PREFIX}/records", params={"action": "audit_trail.read"}, headers=root.headers).json()
    return page["items"]


def test_without_an_organisation_the_super_admin_sees_platform_records_only(audit_client, org, root):
    _post(audit_client, org, org.writer)
    assert audit_client.get(f"{PREFIX}/records", headers=root.headers).json()["total"] == 0


def test_reading_another_organisation_leaves_a_trail(audit_client, org, root):
    recorded = _post(audit_client, org, org.writer).json()["id"]
    page = audit_client.get(f"{PREFIX}/records", params={"organisation_id": org.id}, headers=root.headers).json()
    assert [r["id"] for r in page["items"]] == [recorded]
    (trail,) = _trail(audit_client, root)
    assert trail["actor"] == root.id and trail["entity_type"] == "organisation" and trail["entity_id"] == org.id
    assert trail["organisation_id"] is None  # a platform-level record: among the super admin's own actions


def test_opening_one_record_of_another_organisation_leaves_a_trail_too(audit_client, org, root):
    recorded = _post(audit_client, org, org.writer).json()["id"]
    r = audit_client.get(f"{PREFIX}/records/{recorded}", headers=root.headers)
    assert r.status_code == 200 and r.json()["id"] == recorded
    (trail,) = _trail(audit_client, root)
    assert trail["entity_id"] == org.id and trail["context"] == {"read": "record"}


def test_reading_platform_records_is_not_itself_a_cross_organisation_read(audit_client, root):
    audit_client.get(f"{PREFIX}/records", headers=root.headers)
    assert _trail(audit_client, root) == []
