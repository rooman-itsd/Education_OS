"""Updating, disabling, enabling and erasing users (DPDP s.12 correction and erasure; offboarding; gap D10 of the
November 2026 DPDP pass). Every route is the caller's own organisation only, the organisation's last active admin
can never be disabled, erased or lose `org-admin`, and an erased user leaves no personal data in identity_user."""

from __future__ import annotations

import uuid

import pytest
from eos_core.events import OutboxEvent
from eos_core.security import create_token, verify_password
from eos_core.tenant import organisation_scope, platform_scope
from eos_identity.application import service
from eos_identity.domain.models import User
from oidc_fake import ORGS
from sqlalchemy import select

PREFIX = "/api/v1/identity"
PILOT = ORGS["pilot"][0]  # an active organisation the faked tenancy hooks know, so password sign-in works


def _org() -> str:
    return f"org-{uuid.uuid4().hex[:12]}"


def _person(db, org: str, roles=("faculty",), *, name: str | None = None, email: str | None = None) -> User:
    tag = uuid.uuid4().hex[:8]
    with platform_scope():
        u = service.create_user(
            db,
            organisation_id=org,
            email=email or f"p-{tag}@lifecycle.example.com",
            name=name or f"Person {tag}",
            password="Passw0rd!x",
            roles=list(roles),
        )
        db.commit()
    return u


def _as(user: User) -> dict:
    token = create_token(user_id=user.id, organisation_id=user.organisation_id, roles=list(user.roles))
    return {"Authorization": f"Bearer {token}"}


def _reload(db, user_id: str) -> User:
    db.expire_all()
    with platform_scope():
        return db.get(User, user_id)


def _events(db, name: str, user_id: str) -> list[OutboxEvent]:
    db.expire_all()
    with platform_scope():
        rows = db.scalars(select(OutboxEvent).where(OutboxEvent.name == name))
        return [e for e in rows if (e.payload or {}).get("user_id") == user_id]


@pytest.fixture
def org_with_admin(db):
    org = _org()
    return org, _person(db, org, roles=("org-admin",))


# ---- update -----------------------------------------------------------------------------------------------


def test_admin_corrects_name_email_and_roles(client, db, org_with_admin):
    org, admin = org_with_admin
    u = _person(db, org, roles=("faculty",))
    r = client.patch(
        f"{PREFIX}/users/{u.id}",
        json={"name": "Corrected Name", "email": "New.Address@Lifecycle.example.com", "roles": ["hod"]},
        headers=_as(admin),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["name"], body["email"], body["roles"]) == (
        "Corrected Name",
        "new.address@lifecycle.example.com",
        ["hod"],
    )
    (ev,) = _events(db, "identity.user.updated", u.id)
    assert ev.organisation_id == org and ev.actor == admin.id
    # the audit record is permanent: the event names the changed fields, never the name or the address
    assert ev.payload == {"user_id": u.id, "changed": ["name", "email", "roles"], "roles": ["hod"]}


def test_update_changing_nothing_publishes_nothing(client, db, org_with_admin):
    org, admin = org_with_admin
    u = _person(db, org, name="Same")
    r = client.patch(f"{PREFIX}/users/{u.id}", json={"name": "Same"}, headers=_as(admin))
    assert r.status_code == 200 and not _events(db, "identity.user.updated", u.id)


def test_email_of_another_user_is_a_conflict(client, db, org_with_admin):
    org, admin = org_with_admin
    a, b = _person(db, org), _person(db, org)
    r = client.patch(f"{PREFIX}/users/{a.id}", json={"email": b.email.upper()}, headers=_as(admin))
    assert r.status_code == 409 and r.json()["code"] == "email_taken"
    assert _reload(db, a.id).email == a.email


@pytest.mark.parametrize("roles", [["super-admin"], ["service"], ["faculty", "service"]])
def test_update_follows_the_role_assignment_rules(client, db, org_with_admin, roles):
    org, admin = org_with_admin
    u = _person(db, org)
    r = client.patch(f"{PREFIX}/users/{u.id}", json={"roles": roles}, headers=_as(admin))
    assert r.status_code == 403
    assert _reload(db, u.id).roles == ["faculty"]


@pytest.mark.parametrize("body", [{}, {"status": "active"}, {"roles": []}, {"name": ""}, {"email": "not-an-email"}])
def test_update_refuses_an_empty_or_invalid_body(client, db, org_with_admin, body):
    org, admin = org_with_admin
    u = _person(db, org)
    assert client.patch(f"{PREFIX}/users/{u.id}", json=body, headers=_as(admin)).status_code == 422


def test_learner_made_staff_must_fit_the_plan(client, db, org_with_admin, monkeypatch):
    org, admin = org_with_admin
    student = _person(db, org, roles=("student",))
    monkeypatch.setattr(service.hooks, "user_limit", lambda db, o: 1)  # the admin already takes the one seat
    r = client.patch(f"{PREFIX}/users/{student.id}", json={"roles": ["faculty"]}, headers=_as(admin))
    assert r.status_code == 409 and r.json()["code"] == "plan_limit_reached"
    assert _reload(db, student.id).roles == ["student"]


# ---- permissions and organisations ---------------------------------------------------------------------


def test_another_organisations_user_is_not_found_and_untouched(client, db, org_with_admin):
    _, admin = org_with_admin
    other_org = _org()
    other_admin = _person(db, other_org, roles=("org-admin",))
    victim = _person(db, other_org, name="Victim")
    calls = [
        ("patch", f"/users/{victim.id}", {"json": {"name": "Hijacked"}}),
        ("post", f"/users/{victim.id}/disable", {}),
        ("post", f"/users/{victim.id}/enable", {}),
        ("delete", f"/users/{victim.id}", {}),
        ("post", f"/users/{other_admin.id}/disable", {}),
    ]
    for method, path, kw in calls:
        r = getattr(client, method)(f"{PREFIX}{path}", headers=_as(admin), **kw)
        assert r.status_code == 404, f"{method} {path}: {r.status_code}"
    v = _reload(db, victim.id)
    assert (v.name, v.status) == ("Victim", "active")
    assert _reload(db, other_admin.id).status == "active"
    assert not _events(db, "identity.user.updated", victim.id) and not _events(db, "identity.user.erased", victim.id)


def test_unknown_user_is_not_found(client, org_with_admin):
    _, admin = org_with_admin
    assert client.post(f"{PREFIX}/users/{uuid.uuid4()}/disable", headers=_as(admin)).status_code == 404


def test_a_member_without_the_keys_is_refused(client, db, org_with_admin):
    org, _ = org_with_admin
    member, target = _person(db, org, roles=("faculty",)), _person(db, org)
    h = _as(member)
    assert client.patch(f"{PREFIX}/users/{target.id}", json={"name": "X"}, headers=h).status_code == 403
    assert client.post(f"{PREFIX}/users/{target.id}/disable", headers=h).status_code == 403
    assert client.post(f"{PREFIX}/users/{target.id}/enable", headers=h).status_code == 403
    assert client.delete(f"{PREFIX}/users/{target.id}", headers=h).status_code == 403


def test_the_org_admin_catalogue_role_holds_every_key(client, org_with_admin):
    _, admin = org_with_admin
    perms = set(client.get(f"{PREFIX}/auth/me", headers=_as(admin)).json()["permissions"])
    assert {"identity:user:read", "identity:user:manage", "identity:user:erase"} <= perms


# ---- the last admin --------------------------------------------------------------------------------------


def test_the_last_admin_cannot_be_disabled_erased_or_demoted(client, db, org_with_admin):
    _, admin = org_with_admin
    h = _as(admin)
    for r in (
        client.post(f"{PREFIX}/users/{admin.id}/disable", headers=h),
        client.delete(f"{PREFIX}/users/{admin.id}", headers=h),
        client.patch(f"{PREFIX}/users/{admin.id}", json={"roles": ["faculty"]}, headers=h),
    ):
        assert r.status_code == 409 and r.json()["code"] == "last_admin"
    a = _reload(db, admin.id)
    assert (a.status, a.roles, a.email) == ("active", ["org-admin"], admin.email)


def test_a_disabled_admin_does_not_count_as_another_admin(client, db, org_with_admin):
    org, admin = org_with_admin
    second = _person(db, org, roles=("org-admin",))
    assert client.post(f"{PREFIX}/users/{second.id}/disable", headers=_as(admin)).status_code == 200
    r = client.post(f"{PREFIX}/users/{admin.id}/disable", headers=_as(admin))
    assert r.status_code == 409 and r.json()["code"] == "last_admin"


def test_with_a_second_admin_one_can_step_down(client, db, org_with_admin):
    org, admin = org_with_admin
    second = _person(db, org, roles=("org-admin",))
    r = client.patch(f"{PREFIX}/users/{admin.id}", json={"roles": ["faculty"]}, headers=_as(second))
    assert r.status_code == 200, r.text
    r = client.post(f"{PREFIX}/users/{second.id}/disable", headers=_as(second))
    assert r.status_code == 409  # now the last one


# ---- disable and enable ------------------------------------------------------------------------------------


def test_disabled_user_cannot_sign_in_and_existing_token_stops_at_once(client, db):
    admin = _person(db, PILOT, roles=("org-admin",))
    u = _person(db, PILOT)
    login = {"email": u.email, "password": "Passw0rd!x", "organisation_slug": "pilot"}
    r = client.post(f"{PREFIX}/auth/login", json=login)
    assert r.status_code == 200, r.text
    held = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get(f"{PREFIX}/auth/me", headers=held).status_code == 200

    r = client.post(f"{PREFIX}/users/{u.id}/disable", headers=_as(admin))
    assert r.status_code == 200 and r.json()["status"] == "disabled"
    assert client.post(f"{PREFIX}/auth/login", json=login).status_code == 401
    assert client.get(f"{PREFIX}/auth/me", headers=held).status_code == 401  # the token issued before
    (ev,) = _events(db, "identity.user.disabled", u.id)
    assert ev.payload == {"user_id": u.id} and ev.actor == admin.id

    # disabling again changes nothing and publishes nothing
    assert client.post(f"{PREFIX}/users/{u.id}/disable", headers=_as(admin)).status_code == 200
    assert len(_events(db, "identity.user.disabled", u.id)) == 1

    r = client.post(f"{PREFIX}/users/{u.id}/enable", headers=_as(admin))
    assert r.status_code == 200 and r.json()["status"] == "active"
    assert client.post(f"{PREFIX}/auth/login", json=login).status_code == 200
    assert len(_events(db, "identity.user.enabled", u.id)) == 1


def test_disabled_user_is_refused_by_the_realm_too(client, db, realm):
    """Keycloak authenticates, identity decides (ADR-0006): the realm account is not touched, but a realm token for
    a disabled user is refused on every request."""
    admin = _person(db, PILOT, roles=("org-admin",))
    u = _person(db, PILOT)
    sub = "kc-" + uuid.uuid4().hex
    with platform_scope():
        _reload(db, u.id).oidc_subject = sub
        db.commit()
    bearer = {"Authorization": f"Bearer {realm.token(sub=sub)}"}
    assert client.get(f"{PREFIX}/auth/me", headers=bearer).status_code == 200
    assert client.post(f"{PREFIX}/users/{u.id}/disable", headers=_as(admin)).status_code == 200
    assert client.get(f"{PREFIX}/auth/me", headers=bearer).status_code == 401


def test_disabled_staff_free_a_seat_and_enabling_needs_one(client, db, org_with_admin, monkeypatch):
    org, admin = org_with_admin
    u = _person(db, org)
    assert service.count_staff_users(db, org) == 2
    assert client.post(f"{PREFIX}/users/{u.id}/disable", headers=_as(admin)).status_code == 200
    assert service.count_staff_users(db, org) == 1
    _person(db, org)  # the freed seat is taken
    monkeypatch.setattr(service.hooks, "user_limit", lambda db, o: 2)
    r = client.post(f"{PREFIX}/users/{u.id}/enable", headers=_as(admin))
    assert r.status_code == 409 and r.json()["code"] == "plan_limit_reached"
    assert _reload(db, u.id).status == "disabled"


def test_a_disabled_learner_is_enabled_whatever_the_staff_limit(client, db, org_with_admin, monkeypatch):
    org, admin = org_with_admin
    s = _person(db, org, roles=("student",))
    assert client.post(f"{PREFIX}/users/{s.id}/disable", headers=_as(admin)).status_code == 200
    monkeypatch.setattr(service.hooks, "user_limit", lambda db, o: 1)
    assert client.post(f"{PREFIX}/users/{s.id}/enable", headers=_as(admin)).status_code == 200


# ---- erasure ---------------------------------------------------------------------------------------------


def test_erasure_leaves_no_personal_data_in_identity(client, db):
    admin = _person(db, PILOT, roles=("org-admin",))
    name, email = "Asha Erasable", f"asha-{uuid.uuid4().hex[:8]}@lifecycle.example.com"
    u = _person(db, PILOT, roles=("faculty",), name=name, email=email)
    login = {"email": email, "password": "Passw0rd!x", "organisation_slug": "pilot"}
    held = {"Authorization": f"Bearer {client.post(f'{PREFIX}/auth/login', json=login).json()['token']}"}
    with platform_scope():
        _reload(db, u.id).oidc_subject = "kc-" + uuid.uuid4().hex
        db.commit()

    r = client.delete(f"{PREFIX}/users/{u.id}", headers=_as(admin))
    assert r.status_code == 204, r.text

    row = _reload(db, u.id)
    assert row is not None, "the row stays: other modules and the audit trail hold the id"
    values = [str(getattr(row, c.key)) for c in User.__table__.columns]
    assert not any(name.lower() in v.lower() or email.split("@")[0] in v.lower() for v in values), values
    assert (row.status, row.name, row.roles, row.oidc_subject) == ("erased", "Erased user", [], None)
    assert row.email == f"erased-{u.id}@erased.invalid"
    assert not verify_password("Passw0rd!x", row.password_hash)
    # nothing identity published about the user carries the name or the address either
    with platform_scope():
        payloads = [str(e.payload) for e in db.scalars(select(OutboxEvent)) if (e.payload or {}).get("user_id") == u.id]
    assert payloads and not any(email in p or name in p for p in payloads)

    assert client.post(f"{PREFIX}/auth/login", json=login).status_code == 401
    assert client.get(f"{PREFIX}/auth/me", headers=held).status_code == 401
    ids = [x["id"] for x in client.get(f"{PREFIX}/users", headers=_as(admin)).json()]
    assert admin.id in ids and u.id not in ids
    (ev,) = _events(db, "identity.user.erased", u.id)
    assert set(ev.payload) == {"user_id", "erased_at"} and ev.actor == admin.id and ev.organisation_id == PILOT


def test_erasure_is_final_and_idempotent(client, db, org_with_admin):
    org, admin = org_with_admin
    u = _person(db, org)
    h = _as(admin)
    assert client.delete(f"{PREFIX}/users/{u.id}", headers=h).status_code == 204
    assert client.delete(f"{PREFIX}/users/{u.id}", headers=h).status_code == 204
    assert len(_events(db, "identity.user.erased", u.id)) == 1
    assert client.post(f"{PREFIX}/users/{u.id}/enable", headers=h).status_code == 404
    assert client.patch(f"{PREFIX}/users/{u.id}", json={"name": "Back"}, headers=h).status_code == 404
    assert _reload(db, u.id).status == "erased"


def test_an_erased_email_can_be_given_to_a_new_user(client, db, org_with_admin):
    org, admin = org_with_admin
    u = _person(db, org)
    assert client.delete(f"{PREFIX}/users/{u.id}", headers=_as(admin)).status_code == 204
    again = _person(db, org, email=u.email)
    assert again.id != u.id


def test_erased_and_disabled_users_take_no_seat(db):
    org = _org()
    _person(db, org, roles=("org-admin",))
    a, b = _person(db, org), _person(db, org)
    with organisation_scope(org):
        service.disable_user(db, organisation_id=org, user_id=a.id, actor=None)
        service.erase_user(db, organisation_id=org, user_id=b.id, actor=None)
        db.commit()
    assert service.count_staff_users(db, org) == 1
