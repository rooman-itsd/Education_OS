"""Plan limits and usage: what the plan allows (typed: PlanLimits), the staff-account ceiling identity's hook asks
for, and usage against limits with users counted by identity (a declared dependency)."""

import logging

import pytest
from eos_billing.application.service import plan_limits, seed_plans, start_trial, usage_vs_limits, user_limit
from eos_billing.domain.limits import PlanLimits
from eos_core.db import SessionLocal, init_db
from eos_core.tenant import organisation_scope
from eos_identity.application.service import create_user
from pydantic import ValidationError


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
    assert plan_limits(db, "org-none") == PlanLimits(users=25, students=500, storage_gb=2)
    assert plan_limits(db, "org-none").stored() == {"users": 25, "students": 500, "storage_gb": 2}
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
                roles=["faculty"],
            )
        create_user(  # a learner: the plan's students, not its users
            db, organisation_id=org, email="s@usage.example.com", name="S", password="Passw0rd!x", roles=["student"]
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


# Second review of PR 363, point 5: limits are typed, validated on the way in and read safely on the way out.


@pytest.mark.parametrize(
    "limits",
    [{"users": "unlimited"}, {"users": "50"}, {"users": -1}, {"users": 2.5}, {"users": True}, {"seats": 5}],
)
def test_a_limit_that_is_not_a_whole_number_of_at_least_zero_is_refused(limits):
    with pytest.raises(ValidationError):
        PlanLimits.model_validate(limits)


def test_valid_limits_and_the_one_no_limit_rule():
    limits = PlanLimits.model_validate({"users": 0, "students": None, "storage_gb": 5})
    assert limits.ceiling("users") is None and limits.ceiling("students") is None  # 0 and null: no limit
    assert limits.ceiling("storage_gb") == 5
    assert limits.stored() == {"users": 0, "storage_gb": 5}


def test_a_bad_value_stored_before_limits_were_typed_cannot_500(db, caplog, monkeypatch):
    # Alembic's fileConfig (the migration tests) disables loggers created before it; this one must speak
    monkeypatch.setattr(logging.getLogger("eos.billing"), "disabled", False)
    from eos_billing.application.service import get_subscription
    from eos_billing.domain.models import Plan

    org = "org-bad-limits"
    with organisation_scope(org):
        start_trial(db, organisation_id=org)
        db.flush()
        create_user(
            db, organisation_id=org, email="t@bad.example.com", name="T", password="Passw0rd!x", roles=["faculty"]
        )
    db.add(Plan(id="legacy", title="Legacy", limits={"users": "unlimited", "students": "50", "storage_gb": -1}))
    db.flush()
    get_subscription(db, org).plan_id = "legacy"
    db.flush()
    with caplog.at_level(logging.WARNING, logger="eos.billing"):
        assert user_limit(db, org) is None
        u = usage_vs_limits(db, org)
    assert u["limits"] == {} and u["at_limit"] == [] and u["usage"]["users"] == 1
    assert any("users='unlimited'" in r.getMessage() and "legacy" in r.getMessage() for r in caplog.records)
    db.get(Plan, "legacy").limits = ["not", "a", "mapping"]
    db.flush()
    assert plan_limits(db, org) == PlanLimits()
