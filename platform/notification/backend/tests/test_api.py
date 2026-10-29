"""The router mounted alone (no eos_backend, tenancy or billing), the way the module will be tested in CI."""

import pytest
from eos_core import config as core_config
from eos_core.security import create_token
from eos_core.tenant import platform_scope
from eos_identity.application.service import create_user
from eos_notification.api.router import router
from eos_testing.tenancy import assert_no_cross_tenant_leak
from fastapi import FastAPI
from fastapi.testclient import TestClient
from notification_support import PREFIX, auth, reminder_request, verify_request

SECRET = "s3cr3t-token-value"


@pytest.fixture(autouse=True)
def grants(monkeypatch):
    """notification:message:send is granted only to the `service` block, which no person may hold (platform/
    identity is to refuse it on a user), so the HTTP send route is exercised through one test-only role instead
    of a user carrying `service`. The real catalogue is otherwise untouched."""
    real = core_config.load_role_grants()
    monkeypatch.setattr(core_config, "load_role_grants", lambda: {**real, "test-sender": {"notification:message:send"}})


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix=PREFIX)
    return TestClient(app)


def post(client, org, user, path, body):
    return client.post(f"{PREFIX}{path}", json=body, headers=org.headers(user))


def get(client, org, user, path):
    return client.get(f"{PREFIX}{path}", headers=org.headers(user))


def test_every_route_needs_a_token(client):
    for method, path in [("get", "/messages"), ("post", "/messages"), ("get", "/templates"), ("get", "/inbox")]:
        assert getattr(client, method)(f"{PREFIX}{path}").status_code == 401


def test_a_plain_member_cannot_send_read_history_or_edit_templates(client, org):
    assert post(client, org, org.member, "/messages", reminder_request()).status_code == 403
    assert get(client, org, org.member, "/messages").status_code == 403
    assert (
        post(
            client, org, org.member, "/templates", {"key": "x", "channel": "email", "locale": "en", "body": "b"}
        ).status_code
        == 403
    )


def test_send_returns_202_then_200_for_a_replay_and_never_returns_a_secret(client, org):
    body = verify_request()
    first = post(client, org, org.sender, "/messages", body)
    assert first.status_code == 202, first.text
    out = first.json()
    assert out["status"] == "sending"  # `sent` is presented as `sending` until the contract adds it
    assert out["recipient_address"] == "a***@college.example.com" and out["organisation_id"] == org.id
    assert SECRET not in first.text and "variables" not in out and "body" not in out
    again = post(client, org, org.sender, "/messages", body)
    assert again.status_code == 200 and again.json()["id"] == out["id"]


def test_validation_errors_are_422_with_a_detail(client, org):
    r = post(client, org, org.sender, "/messages", reminder_request(template="made.up"))
    assert r.status_code == 422 and r.json() == {"detail": "unknown template"}


def test_history_is_scoped_and_other_organisations_ids_are_404(client, org, other_org):
    sent = post(client, org, org.sender, "/messages", reminder_request()).json()
    post(client, other_org, other_org.sender, "/messages", reminder_request())
    assert get(client, org, org.admin, f"/messages/{sent['id']}").status_code == 200
    assert get(client, other_org, other_org.admin, f"/messages/{sent['id']}").status_code == 404
    assert_no_cross_tenant_leak(client, f"{PREFIX}/messages", org.token(org.admin), other_org.token(other_org.admin))
    rows = get(client, org, org.admin, "/messages").json()
    assert rows["total"] == 1 and rows["items"][0]["organisation_id"] == org.id


def test_status_filter_uses_the_contract_values_only(client, org):
    post(client, org, org.sender, "/messages", reminder_request())
    assert get(client, org, org.admin, "/messages?status=sending").json()["total"] == 1
    assert get(client, org, org.admin, "/messages?status=sent").status_code == 422


def test_resend_is_not_part_of_this_release(client, org):
    sent = post(client, org, org.sender, "/messages", reminder_request()).json()
    r = client.post(f"{PREFIX}/messages/{sent['id']}/resend", headers=org.headers(org.admin))
    assert r.status_code in (404, 405)
    assert all("resend" not in route.path for route in router.routes)


def test_an_organisation_override_changes_the_next_mail(client, org):
    body = {
        "key": "billing.trial.reminder",
        "channel": "email",
        "locale": "en",
        "subject": "S",
        "body": "ORG WORDING ${trial_ends_on}",
    }
    assert post(client, org, org.admin, "/templates", body).status_code == 201
    post(client, org, org.sender, "/messages", reminder_request())
    from eos_notification.infrastructure import transport as transport_module

    assert transport_module.sent[-1]["body"] == "ORG WORDING 2026-10-20"


def test_the_verification_template_cannot_be_overridden_and_preview_hides_secrets(client, org):
    bad = {"key": "tenancy.organisation.verify", "channel": "email", "locale": "en", "body": "x ${token}"}
    assert post(client, org, org.admin, "/templates", bad).status_code == 422
    r = post(
        client,
        org,
        org.admin,
        "/templates/tenancy.organisation.verify/preview",
        {"variables": {"organisation_name": "C", "token": "REAL"}},
    )
    assert r.status_code == 200 and "REAL" not in r.text and "[secret]" in r.json()["body"]


def test_template_listing_merges_platform_defaults_and_this_organisations_overrides(client, org, other_org):
    post(
        client,
        org,
        org.admin,
        "/templates",
        {
            "key": "billing.trial.expired",
            "channel": "email",
            "locale": "en",
            "subject": "S",
            "body": "B ${organisation_name}",
        },
    )
    mine = get(client, org, org.admin, "/templates?channel=email").json()
    theirs = get(client, other_org, other_org.admin, "/templates?channel=email").json()
    assert {i["scope"] for i in mine["items"]} == {"platform", "organisation"}
    assert {i["scope"] for i in theirs["items"]} == {"platform"}


def test_a_person_manages_their_own_preferences_but_not_someone_elses(client, org):
    own = f"/preferences/{org.member.id}"
    assert get(client, org, org.member, own).status_code == 200
    r = client.put(
        f"{PREFIX}{own}", json={"channels": {"transactional": [], "reminder": []}}, headers=org.headers(org.member)
    )
    assert r.status_code == 200 and r.json()["channels"]["transactional"] == ["email", "in_app"]
    assert get(client, org, org.member, f"/preferences/{org.admin.id}").status_code == 403
    assert get(client, org, org.admin, own).status_code == 200  # org-admin holds preference:manage


def test_a_super_admin_without_an_organisation_is_refused(client, db):
    # A super admin belongs to no organisation, so the row can only be written as the platform: on PostgreSQL
    # the tenant_isolation WITH CHECK refuses a NULL organisation_id from a tenant-scoped transaction.
    with platform_scope():
        sa = create_user(
            db,
            organisation_id=None,
            email="root@platform.example",
            name="root",
            password="Secret123!",
            roles=[],
            is_super_admin=True,
        )
        db.commit()
    token = create_token(user_id=sa.id, organisation_id=None, roles=[], super_admin=True)
    for path in ("/inbox", "/messages"):
        assert client.get(f"{PREFIX}{path}", headers=auth(token)).status_code == 403


def test_inbox_round_trip_and_privacy(client, org):
    sent = post(client, org, org.sender, "/messages", reminder_request(user_id=org.member.id, channel="in_app")).json()
    assert sent["status"] == "delivered"
    inbox = get(client, org, org.member, "/inbox").json()
    assert inbox["unread"] == 1 and inbox["items"][0]["id"] == sent["id"]
    assert get(client, org, org.admin, "/inbox").json() == {"items": [], "unread": 0}
    assert post(client, org, org.admin, f"/inbox/{sent['id']}/read", None).status_code == 404
    assert client.post(f"{PREFIX}/inbox/{sent['id']}/read", headers=org.headers(org.member)).status_code == 204
    assert get(client, org, org.member, "/inbox").json()["unread"] == 0


# --- leak tests over HTTP, using the shared helper every module uses -----------------------------------


def test_inbox_does_not_leak_across_organisations(client, org, other_org):
    """The shared leak helper, applied to /inbox as well as /messages: each tenant has a real in-app message,
    and neither may see the other's. /messages is covered above; the inbox is the other list endpoint that
    returns tenant rows."""
    mine = post(client, org, org.sender, "/messages", reminder_request(user_id=org.member.id, channel="in_app"))
    theirs = post(
        client, other_org, other_org.sender, "/messages",
        reminder_request(user_id=other_org.member.id, channel="in_app"),
    )  # fmt: skip
    assert mine.status_code == 202 and theirs.status_code == 202

    assert_no_cross_tenant_leak(client, f"{PREFIX}/inbox", org.token(org.member), other_org.token(other_org.member))


def test_one_organisation_cannot_read_another_organisations_preferences_over_http(client, org, other_org):
    """A 404, not a 403: whether a user id exists in another tenant is itself information."""
    response = get(client, org, org.admin, f"/preferences/{other_org.member.id}")
    assert response.status_code == 404


def test_one_organisation_cannot_write_another_organisations_preferences_over_http(client, org, other_org):
    response = client.put(
        f"{PREFIX}/preferences/{other_org.member.id}",
        json={"channels": {"reminder": ["email"]}},
        headers=org.headers(org.admin),
    )
    assert response.status_code == 404
    # and the other organisation's settings are untouched
    assert get(client, other_org, other_org.member, f"/preferences/{other_org.member.id}").status_code == 200


def test_templates_share_platform_defaults_but_never_another_organisations_override(client, org, other_org):
    """/templates is deliberately NOT a candidate for the shared leak helper: platform defaults are the same
    rows for every tenant by design, so identical ids across tenants are correct there. What must never cross
    is an organisation's own override."""
    body = {"key": "billing.trial.reminder", "channel": "email", "locale": "en",
            "subject": "Theirs only", "body": "Trial for ${organisation_name} ends ${trial_ends_on} "
                                              "(${days_left})"}  # fmt: skip
    assert post(client, other_org, other_org.admin, "/templates", body).status_code == 201

    mine = get(client, org, org.admin, "/templates").json()["items"]
    assert not any(item.get("subject") == "Theirs only" for item in mine)
    assert any(item["key"] == "billing.trial.reminder" for item in mine)  # the platform default is still there
