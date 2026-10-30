"""Plan limits and usage: what the plan allows, the user ceiling identity's hook asks for, and usage against
limits with users counted by identity (a declared dependency)."""

import pytest
from eos_billing.application.service import plan_limits, seed_plans, start_trial, usage_vs_limits, user_limit
from eos_core.db import SessionLocal, init_db
from eos_core.tenant import organisation_scope
from eos_identity.application.service import create_user


@pytest.fixture(scope="module", autouse=True)
def _tables():
    init_db()
    with SessionLocal() as db:
        seed_plans(db)


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s
        s.rollback()


def test_an_organisation_without_a_subscription_has_the_trial_limits(db):
    assert plan_limits(db, "org-none") == {"users": 25, "students": 500, "storage_gb": 2}
    assert user_limit(db, "org-none") == 25


def test_usage_counts_active_users_and_names_what_is_at_the_limit(db, monkeypatch):
    org = "org-usage"
    with organisation_scope(org):
        start_trial(db, organisation_id=org)
        db.flush()
        for n in range(2):
            create_user(
                db,
                organisation_id=org,
                email=f"u{n}@usage.example.com",
                name="U",
                password="Passw0rd!x",
                roles=["student"],
            )
    u = usage_vs_limits(db, org)
    assert u["plan"] == "trial" and u["limits"]["users"] == 25
    assert u["usage"] == {"users": 2, "students": None, "storage_gb": None} and u["at_limit"] == []
    # a plan without the key, or with 0, has no limit
    from eos_billing.domain.models import Plan

    db.add(Plan(id="open", title="Open", limits={"users": 0}))
    db.flush()
    from eos_billing.application.service import get_subscription

    get_subscription(db, org).plan_id = "open"
    db.flush()
    assert user_limit(db, org) is None and usage_vs_limits(db, org)["at_limit"] == []
    db.get(Plan, "open").limits = {"users": 2}
    db.flush()
    assert user_limit(db, org) == 2 and usage_vs_limits(db, org)["at_limit"] == ["users"]
