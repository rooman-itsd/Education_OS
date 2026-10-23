"""Races the pre-checks cannot see: two creates of one code, and two registrations for a section's last seat.

Each race is tested twice: deterministically, by letting the pre-check pass as it would when the competing write is
not yet visible, and with two real threads on the throwaway SQLite database. Row locking itself (SELECT ... FOR
UPDATE) only takes effect on PostgreSQL; here it is checked by compiling the query for that dialect."""

import threading

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see test_api_deps.py)")

from conftest import BASE, make_course, make_offering, make_programme, make_term, ok, open_offering  # noqa: E402
from eos_academic_management.application import roster, service  # noqa: E402
from eos_academic_management.application.errors import AcademicManagementError  # noqa: E402
from eos_academic_management.infrastructure import repository as repo  # noqa: E402
from eos_academic_management.infrastructure.models import (  # noqa: E402
    CourseRow,
    CurriculumRow,
    ProcessedEventRow,
    RosterEntryRow,
)
from eos_core.db import SessionLocal, new_id  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

ADMIN = "org-admin"


def term_body(code="DUP"):
    return {"code": code, "name": code, "starts_on": "2031-01-01", "ends_on": "2031-02-01"}


def create(client, h, kind, code, term=None, offering=None):
    if kind == "term":
        start = {"A": "2031-01-01", "B": "2031-03-01"}.get(code[-1], "2031-05-01")
        return client.post(f"{BASE}/terms", json={**term_body(code), "starts_on": start, "ends_on": start}, headers=h)
    if kind == "programme":
        body = {
            "code": code,
            "name": code,
            "level": "diploma",
            "department_id": new_id(),
            "duration_terms": 1,
            "credits_required": 1,
        }
        return client.post(f"{BASE}/programmes", json=body, headers=h)
    if kind == "course":
        body = {"code": code, "title": code, "credits": 1, "course_type": "theory", "department_id": new_id()}
        return client.post(f"{BASE}/courses", json=body, headers=h)
    return client.post(f"{BASE}/offerings/{offering['id']}/sections", json={"code": code, "capacity": 5}, headers=h)


def offering_for(client, h):
    return make_offering(client, h, make_course(client, h, f"C{new_id()[:6]}")["id"], make_term(client, h)["id"])


# ---------------------------------------------------------------- 1. duplicate codes


@pytest.mark.parametrize("kind", ["term", "programme", "course", "section"])
def test_an_ordinary_duplicate_code_is_409(client, org, kind):
    _, h = org.user(ADMIN)
    offering = offering_for(client, h) if kind == "section" else None
    assert create(client, h, kind, "DUP-A", offering=offering).status_code == 201
    if kind == "term":  # same code, dates that do not overlap: only the code clashes
        r = client.post(
            f"{BASE}/terms", json={**term_body("DUP-A"), "starts_on": "2031-07-01", "ends_on": "2031-07-02"}, headers=h
        )
    else:
        r = create(client, h, kind, "DUP-A", offering=offering)
    detail = r.json()["detail"]
    assert (r.status_code, detail["code"], detail["details"]["field"]) == (409, "duplicate_code", "code")


@pytest.mark.parametrize("kind", ["term", "programme", "course", "section"])
def test_a_duplicate_that_slips_past_the_pre_check_is_still_409(client, org, monkeypatch, kind):
    """The race: both requests ran ensure_unique_code before either inserted. The database constraint decides."""
    _, h = org.user(ADMIN)
    offering = offering_for(client, h) if kind == "section" else None
    first = create(client, h, kind, "RACE-A" if kind == "term" else "RACE", offering=offering)
    assert first.status_code == 201
    monkeypatch.setattr(service, "ensure_unique_code", lambda code, existing: None)  # the pre-check saw nothing
    if kind == "term":
        r = client.post(
            f"{BASE}/terms", json={**term_body("RACE-A"), "starts_on": "2031-09-01", "ends_on": "2031-09-02"}, headers=h
        )
    else:
        r = create(client, h, kind, "RACE", offering=offering)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "duplicate_code")


def test_two_concurrent_creates_of_one_code_give_one_201_and_one_409(client, org):
    _, h = org.user(ADMIN)
    barrier, statuses = threading.Barrier(2), []

    def post():
        barrier.wait()
        body = {"code": "SAME", "title": "Same", "credits": 1, "course_type": "theory", "department_id": new_id()}
        statuses.append(client.post(f"{BASE}/courses", json=body, headers=h).status_code)

    threads = [threading.Thread(target=post) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(statuses) == [201, 409]
    assert ok(client.get(f"{BASE}/courses?q=same", headers=h))["total"] == 1


def _integrity_error(make) -> IntegrityError:
    with SessionLocal() as db:
        try:
            make(db)
            db.flush()
        except IntegrityError as err:
            db.rollback()
            return err
    raise AssertionError("no integrity error was raised")


def test_only_code_constraints_count_as_duplicate_codes(client, org):
    _, h = org.user(ADMIN)
    programme = make_programme(client, h)
    org_id = org.id
    code_clash = _integrity_error(
        lambda db: db.add_all(
            [
                CourseRow(
                    organisation_id=org_id,
                    code="K",
                    title="K",
                    credits=1,
                    course_type="theory",
                    department_id="d",
                    status="active",
                ),
                CourseRow(
                    organisation_id=org_id,
                    code="K",
                    title="K",
                    credits=1,
                    course_type="theory",
                    department_id="d",
                    status="active",
                ),
            ]
        )
    )
    version_clash = _integrity_error(
        lambda db: db.add_all(
            [
                CurriculumRow(organisation_id=org_id, programme_id=programme["id"], version=7, status="draft"),
                CurriculumRow(organisation_id=org_id, programme_id=programme["id"], version=7, status="draft"),
            ]
        )
    )
    missing_value = _integrity_error(
        lambda db: db.add(
            CourseRow(
                organisation_id=org_id,
                code="N",
                title=None,
                credits=1,
                course_type="theory",
                department_id="d",
                status="active",
            )
        )
    )
    assert repo.is_code_conflict(code_clash) is True
    assert repo.is_code_conflict(version_clash) is False
    assert repo.is_code_conflict(missing_value) is False


def test_postgres_constraint_names_are_recognised():
    class Diag:
        def __init__(self, name):
            self.constraint_name = name

    class PgError(Exception):
        def __init__(self, name):
            super().__init__("duplicate key value violates unique constraint")
            self.diag = Diag(name)

    code, version = PgError("uq_academic_management_course_code"), PgError("uq_academic_management_curriculum_version")
    assert repo.is_code_conflict(IntegrityError("INSERT", {}, code)) is True
    assert repo.is_code_conflict(IntegrityError("INSERT", {}, version)) is False
    assert repo.is_version_conflict(IntegrityError("INSERT", {}, version)) is True
    assert repo.is_version_conflict(IntegrityError("INSERT", {}, code)) is False


def test_a_curriculum_version_that_slips_past_the_read_is_409(client, org, monkeypatch):
    """The race: two creates on one programme read the same versions before either inserted. The database's version
    constraint refuses the second, which answers 409 concurrent_version instead of failing with a server error."""
    _, h = org.user(ADMIN)
    programme = make_programme(client, h)
    assert ok(client.post(f"{BASE}/programmes/{programme['id']}/curricula", json={}, headers=h), 201)["version"] == 1
    monkeypatch.setattr(repo, "curricula_of", lambda db, programme_id: [])  # the competing create is not visible
    r = client.post(f"{BASE}/programmes/{programme['id']}/curricula", json={}, headers=h)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "concurrent_version")
    monkeypatch.undo()
    assert ok(client.post(f"{BASE}/programmes/{programme['id']}/curricula", json={}, headers=h), 201)["version"] == 2


def test_another_integrity_error_is_not_turned_into_a_409(org):
    with SessionLocal() as db:
        db.info["organisation_id"] = org.id
        row = CourseRow(
            organisation_id=org.id,
            code="Z",
            title=None,
            credits=1,
            course_type="theory",
            department_id="d",
            status="active",
        )
        with pytest.raises(IntegrityError):
            service._insert_coded(db, row)


def test_a_409_from_the_constraint_is_the_same_error_as_the_pre_check(org):
    with SessionLocal() as db:
        db.info["organisation_id"] = org.id
        for _ in range(2):
            row = CourseRow(
                organisation_id=org.id,
                code="SAME2",
                title="t",
                credits=1,
                course_type="theory",
                department_id="d",
                status="active",
            )
            try:
                service._insert_coded(db, row)
                db.commit()
            except AcademicManagementError as err:
                assert (err.status, err.body()) == (
                    409,
                    {
                        "code": "duplicate_code",
                        "message": "code 'SAME2' is already in use",
                        "details": {"field": "code"},
                    },
                )


# ---------------------------------------------------------------- 2. section capacity


@pytest.fixture
def one_seat(client, org):
    """An open offering whose section A has a single seat."""
    _, h = org.user(ADMIN)
    term, course = make_term(client, h), make_course(client, h)
    o = make_offering(client, h, course["id"], term["id"], (("A", 1),))
    open_offering(client, h, o["id"], new_id())
    return org, o, o["sections"][0]


def confirmation(o, section):
    return {
        "id": new_id(),
        "name": roster.CONFIRMED,
        "version": 1,
        "organisation_id": None,
        "occurred_at": "2026-10-22T09:00:00+00:00",
        "payload": {
            "registration_id": new_id(),
            "person_id": new_id(),
            "course_offering_id": o["id"],
            "section_id": section["id"],
        },
    }


def deliver(envelope) -> str:
    with SessionLocal() as db:
        return roster.handle_event(db, envelope)


def enrolled(org_id, section_id) -> int:
    with SessionLocal() as db:
        db.info["organisation_id"] = org_id
        return repo.enrolled_in_section(db, section_id)


def test_the_section_row_is_locked_for_update_on_postgres(org):
    with SessionLocal() as db:
        db.info["organisation_id"] = org.id
        sql = str(repo.section_lock_query(db, "s1").compile(dialect=postgresql.dialect()))
    assert sql.rstrip().endswith("FOR UPDATE")


def test_the_lock_is_taken_before_the_seats_are_counted(one_seat, monkeypatch):
    org, o, a = one_seat
    calls = []
    real_lock, real_q = repo.section_for_update, repo.q
    monkeypatch.setattr(repo, "section_for_update", lambda db, sid: calls.append("lock") or real_lock(db, sid))
    monkeypatch.setattr(repo, "q", lambda db, model: calls.append(f"read {model.__name__}") or real_q(db, model))
    env = confirmation(o, a)
    env["organisation_id"] = org.id
    assert deliver(env) == roster.APPLIED
    first_roster_read = calls.index("read RosterEntryRow", calls.index("lock"))
    assert calls.index("lock") < first_roster_read


def test_a_seat_taken_between_check_and_write_is_given_back(one_seat, monkeypatch):
    """The race: both registrations passed the capacity check before either wrote. The re-count after the write,
    in the same transaction, rejects the second one and leaves the section at capacity."""
    org, o, a = one_seat
    monkeypatch.setattr(roster, "_admit", lambda *args: None)  # both checks saw a free seat
    first, second = confirmation(o, a), confirmation(o, a)
    first["organisation_id"] = second["organisation_id"] = org.id
    assert deliver(first) == roster.APPLIED
    assert deliver(second) == roster.REJECTED_SECTION_FULL
    assert enrolled(org.id, a["id"]) == 1
    assert deliver(second) == roster.DUPLICATE  # the rejection is recorded: a redelivery is not re-applied


def test_two_concurrent_registrations_for_the_last_seat_admit_one(one_seat):
    org, o, a = one_seat
    envelopes = [confirmation(o, a), confirmation(o, a)]
    for env in envelopes:
        env["organisation_id"] = org.id
    barrier, outcomes = threading.Barrier(2), []

    def run(env):
        barrier.wait()
        outcomes.append(deliver(env))

    threads = [threading.Thread(target=run, args=(env,)) for env in envelopes]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(outcomes) == sorted([roster.APPLIED, roster.REJECTED_SECTION_FULL])
    assert enrolled(org.id, a["id"]) == 1


def test_a_failed_commit_leaves_no_registration_and_no_processed_mark(one_seat, monkeypatch):
    org, o, a = one_seat
    env = confirmation(o, a)
    env["organisation_id"] = org.id

    def failing_commit(self):
        raise RuntimeError("database went away")

    monkeypatch.setattr("sqlalchemy.orm.Session.commit", failing_commit)
    with pytest.raises(RuntimeError):
        deliver(env)
    monkeypatch.undo()
    with SessionLocal() as db:
        assert (
            db.scalars(
                select(RosterEntryRow).where(RosterEntryRow.registration_id == env["payload"]["registration_id"])
            ).first()
            is None
        )
        assert db.scalars(select(ProcessedEventRow).where(ProcessedEventRow.event_id == env["id"])).first() is None
    assert deliver(env) == roster.APPLIED  # the redelivery applies normally
