"""notification:message:send is held only by `service`, and no person can use it over HTTP.

Relies on identity's guard (create_user refuses `service`; current_principal drops it from any token), which
merges before this module is enabled. These are the end-to-end checks with notification mounted; identity's own
tests are in test_person_roles.py."""

from eos_core.config import permissions_for
from eos_core.db import SessionLocal
from eos_core.security import create_token, hash_password
from eos_core.tenant import organisation_scope
from eos_identity.domain.models import User
from eos_testing import register_and_login
from eos_testing.tenancy import auth

SEND = "notification:message:send"


def test_a_service_role_already_on_a_row_or_in_a_token_cannot_send(client):
    a = register_and_login(client, slug="send-legacy")
    org = a["org"]["id"]
    with organisation_scope(org), SessionLocal() as db:
        row = User(
            organisation_id=org,
            email="legacy@send.example.com",
            name="Legacy",
            password_hash=hash_password("Passw0rd!x"),
            roles=["student", "service"],
        )
        db.add(row)
        db.commit()
        user_id = row.id
    token = auth(create_token(user_id=user_id, organisation_id=org, roles=["student", "service"]))
    me = client.get("/api/v1/identity/auth/me", headers=token).json()
    assert "service" in me["roles"] and SEND not in me["permissions"]
    r = client.post(
        "/api/v1/notification/messages",
        json={"template": "billing.trial.reminder", "recipient": {"address": "x@send.example.com"}},
        headers=token,
    )
    assert r.status_code == 403


def test_the_service_block_still_holds_the_send_key():
    """The guard is about people, not the catalogue: the key keeps its one holder."""
    assert SEND in permissions_for(["service"])
    assert SEND not in permissions_for(["org-admin", "member"])
