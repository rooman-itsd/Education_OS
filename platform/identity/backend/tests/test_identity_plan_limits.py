"""create_user refuses a staff account past the plan's user limit. The limit comes through `hooks.user_limit`, which
the host wires to billing; alone, identity has no limit and the count is its own. Learners (students, applicants
and roles that extend them) are the plan's `students`: never counted as users, never refused here."""

from types import SimpleNamespace

import pytest
from eos_core.db import SessionLocal, init_db
from eos_core.tenant import organisation_scope
from eos_identity.application import service
from eos_identity.application.service import PlanLimitReachedError, count_staff_users, create_user


@pytest.fixture(scope="module", autouse=True)
def _tables():
    init_db()


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s
        s.rollback()


def _person(db, org: str, n: int, status: str = "active", roles: tuple[str, ...] = ("faculty",)):
    user = create_user(
        db,
        organisation_id=org,
        email=f"p{n}@{org}.example.com",
        name=f"P{n}",
        password="Passw0rd!x",
        roles=list(roles),
    )
    user.status = status
    db.flush()
    return user


def test_without_a_wired_limit_any_number_of_users_is_fine(db):
    assert service.hooks.user_limit(db, "org-free") is None
    for n in range(3):
        _person(db, "org-free", n)
    assert count_staff_users(db, "org-free") == 3


def test_the_limit_counts_active_users_of_that_organisation_only(db, monkeypatch):
    monkeypatch.setattr(service.hooks, "user_limit", lambda db, org: 2)
    with organisation_scope("org-a"):
        _person(db, "org-a", 1)
        _person(db, "org-a", 2, status="disabled")  # a disabled person frees the seat
        _person(db, "org-a", 3)
        assert count_staff_users(db, "org-a") == 2
        with pytest.raises(PlanLimitReachedError) as e:
            _person(db, "org-a", 4)
    assert (e.value.limit, e.value.allowed, e.value.used) == ("users", 2, 2)
    assert "allows 2 users" in str(e.value)
    with organisation_scope("org-b"):
        _person(db, "org-b", 1)  # another organisation has its own count
    assert count_staff_users(db, "org-b") == 1 and count_staff_users(db, "org-a") == 2


def test_the_refusal_writes_nothing(db, monkeypatch):
    monkeypatch.setattr(service.hooks, "user_limit", lambda db, org: 1)
    with organisation_scope("org-c"):
        _person(db, "org-c", 1)
        with pytest.raises(PlanLimitReachedError):
            _person(db, "org-c", 2)
    assert count_staff_users(db, "org-c") == 1


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


class _FakePostgres:
    """Stands in for a Postgres session: records what lock_user_seats sends."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def execute(self, statement, params=None):
        self.sent.append((str(statement), params))


def test_on_postgres_the_count_runs_under_a_per_organisation_advisory_lock():
    """Review note on PR 363: two POST /users at limit - 1 must not both pass."""
    fake = _FakePostgres()
    service.lock_user_seats(fake, "org-1")
    service.lock_user_seats(fake, "org-1")
    service.lock_user_seats(fake, "org-2")
    (sql, first), (_, again), (_, other) = fake.sent
    assert sql == "SELECT pg_advisory_xact_lock(:space, :key)"  # released when the transaction ends
    assert first["space"] == service.USER_SEATS_LOCK and first == again  # one lock per organisation
    assert other["key"] != first["key"] and -(2**31) <= first["key"] < 2**31  # fits the int4 key


def test_create_user_takes_the_lock_before_it_counts_and_only_under_a_limit(db, monkeypatch):
    calls = []
    count = service.count_staff_users
    monkeypatch.setattr(service, "lock_user_seats", lambda db, org: calls.append(("lock", org)))
    monkeypatch.setattr(service, "count_staff_users", lambda db, org: calls.append(("count", org)) or count(db, org))
    with organisation_scope("org-e"):
        _person(db, "org-e", 1)  # no limit wired: neither
        assert calls == []
        monkeypatch.setattr(service.hooks, "user_limit", lambda db, org: 5)
        _person(db, "org-e", 2)
    assert calls == [("lock", "org-e"), ("count", "org-e")]


def test_on_sqlite_the_lock_is_a_no_op(db):
    service.lock_user_seats(db, "org-f")  # no advisory locks in SQLite: nothing sent, nothing raised


# Second review of PR 363, point 3: learners do not take staff seats.


@pytest.mark.parametrize(
    ("roles", "learner"),
    [
        (["student"], True),
        (["applicant"], True),
        (["law-student"], True),  # its dashboard layout extends student
        (["musician"], True),  # likewise (music-academy profile)
        (["faculty"], False),
        (["org-admin"], False),
        (["faculty", "student"], True),  # any learner role makes a learner
        ([], False),
    ],
)
def test_who_is_a_learner(roles, learner):
    assert service.is_learner(roles) is learner


def test_the_26th_student_on_a_25_user_plan_is_not_refused_and_staff_are_counted_alone(db, monkeypatch):
    monkeypatch.setattr(service.hooks, "user_limit", lambda db, org: 25)
    with organisation_scope("org-g"):
        for n in range(24):
            _person(db, "org-g", n)  # 24 staff
        for n in range(30):  # far past 25 accounts in all: learners are not users
            _person(db, "org-g", 100 + n, roles=("student",))
        _person(db, "org-g", 200, roles=("applicant",))
        _person(db, "org-g", 201, roles=("law-student",))
        assert count_staff_users(db, "org-g") == 24
        _person(db, "org-g", 24)  # the 25th staff account fits
        with pytest.raises(PlanLimitReachedError) as e:
            _person(db, "org-g", 25)  # the 26th does not
        assert (e.value.allowed, e.value.used) == (25, 25)
        _person(db, "org-g", 300, roles=("student",))  # and a student still does
    assert count_staff_users(db, "org-g") == 25


def test_creating_a_learner_takes_no_seat_lock(db, monkeypatch):
    monkeypatch.setattr(service.hooks, "user_limit", lambda db, org: 1)
    monkeypatch.setattr(service, "lock_user_seats", lambda db, org: pytest.fail("a learner needs no seat"))
    with organisation_scope("org-h"):
        _person(db, "org-h", 1, roles=("student",))
