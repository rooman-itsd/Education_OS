"""create_user refuses a person past the plan's user limit. The limit comes through `hooks.user_limit`, which the
host wires to billing; alone, identity has no limit and the count is its own."""

import pytest
from eos_core.db import SessionLocal, init_db
from eos_core.tenant import organisation_scope
from eos_identity.application import service
from eos_identity.application.service import PlanLimitReachedError, count_active_users, create_user


@pytest.fixture(scope="module", autouse=True)
def _tables():
    init_db()


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s
        s.rollback()


def _person(db, org: str, n: int, status: str = "active"):
    user = create_user(
        db, organisation_id=org, email=f"p{n}@{org}.example.com", name=f"P{n}", password="Passw0rd!x", roles=["student"]
    )
    user.status = status
    db.flush()
    return user


def test_without_a_wired_limit_any_number_of_users_is_fine(db):
    assert service.hooks.user_limit(db, "org-free") is None
    for n in range(3):
        _person(db, "org-free", n)
    assert count_active_users(db, "org-free") == 3


def test_the_limit_counts_active_users_of_that_organisation_only(db, monkeypatch):
    monkeypatch.setattr(service.hooks, "user_limit", lambda db, org: 2)
    with organisation_scope("org-a"):
        _person(db, "org-a", 1)
        _person(db, "org-a", 2, status="disabled")  # a disabled person frees the seat
        _person(db, "org-a", 3)
        assert count_active_users(db, "org-a") == 2
        with pytest.raises(PlanLimitReachedError) as e:
            _person(db, "org-a", 4)
    assert (e.value.limit, e.value.allowed, e.value.used) == ("users", 2, 2)
    assert "allows 2 users" in str(e.value)
    with organisation_scope("org-b"):
        _person(db, "org-b", 1)  # another organisation has its own count
    assert count_active_users(db, "org-b") == 1 and count_active_users(db, "org-a") == 2


def test_the_refusal_writes_nothing(db, monkeypatch):
    monkeypatch.setattr(service.hooks, "user_limit", lambda db, org: 1)
    with organisation_scope("org-c"):
        _person(db, "org-c", 1)
        with pytest.raises(PlanLimitReachedError):
            _person(db, "org-c", 2)
    assert count_active_users(db, "org-c") == 1


def test_super_admins_and_a_zero_limit_are_never_counted_against_a_plan(db, monkeypatch):
    monkeypatch.setattr(service.hooks, "user_limit", lambda db, org: 0)  # "0" in a plan means no limit
    with organisation_scope("org-d"):
        _person(db, "org-d", 1)
        _person(db, "org-d", 2)
    monkeypatch.setattr(service.hooks, "user_limit", lambda db, org: pytest.fail("no organisation, no limit"))
    create_user(
        db,
        organisation_id=None,
        email="root@limits.example.com",
        name="R",
        password="Passw0rd!x",
        roles=["super-admin"],
    )
