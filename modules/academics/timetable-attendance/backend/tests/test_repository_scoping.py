"""Every query of the repository is limited to the session's organisation, also on SQLite, which has no row-level
security (eos_core.db.scoped). Never trusts an organisation id given by a client: the session's is the only one."""

import uuid
from datetime import UTC, datetime

import pytest
from eos_core.db import SessionLocal, init_db
from eos_timetable_attendance.infrastructure import repository as repo
from eos_timetable_attendance.infrastructure.models import AuditEntry, TimetableRow
from sqlalchemy.exc import IntegrityError

ORG_A, ORG_B = str(uuid.uuid4()), str(uuid.uuid4())


@pytest.fixture(scope="module", autouse=True)
def _tables():
    init_db()


def _db(organisation_id: str | None):
    db = SessionLocal()
    if organisation_id:
        db.info["organisation_id"] = organisation_id
    return db


def _timetable(org: str) -> TimetableRow:
    return TimetableRow(
        organisation_id=org, academic_period_id=str(uuid.uuid4()), name="Odd term", version=0, status="draft"
    )


def _audit(org: str, token: str) -> AuditEntry:
    return AuditEntry(
        organisation_id=org,
        client_token=token,
        action="timetable.created",
        entity_type="timetable",
        entity_id=str(uuid.uuid4()),
        summary="timetable created",
        occurred_at=datetime.now(UTC),
    )


def test_a_query_sees_only_its_own_organisations_rows():
    a, b = _timetable(ORG_A), _timetable(ORG_B)
    with _db(ORG_A) as db:
        db.add_all([a, b])
        db.commit()
    with _db(ORG_A) as db:
        ids = {r.id for r in db.scalars(repo.q(db, TimetableRow))}
        assert a.id in ids and b.id not in ids
        assert repo.get(db, TimetableRow, a.id) is not None
        assert repo.get(db, TimetableRow, b.id) is None  # another organisation's row is not found
    with _db(ORG_B) as db:
        ids = {r.id for r in db.scalars(repo.q(db, TimetableRow))}
        assert b.id in ids and a.id not in ids
        assert repo.get(db, TimetableRow, a.id) is None


def test_a_session_without_an_organisation_sees_nothing():
    with _db(None) as db:
        assert list(db.scalars(repo.q(db, TimetableRow))) == []
        assert list(db.scalars(repo.q(db, AuditEntry))) == []


def test_an_audit_token_is_unique_within_an_organisation_but_not_across_them():
    token = str(uuid.uuid4())
    with _db(ORG_A) as db:
        db.add(_audit(ORG_A, token))
        db.commit()
    with _db(ORG_B) as db:
        db.add(_audit(ORG_B, token))
        db.commit()
        assert repo.audit_entry_by_token(db, ORG_B, token).organisation_id == ORG_B
        assert repo.audit_entry_by_token(db, ORG_A, token) is None  # scoped: the other organisation's is not visible
    with _db(ORG_A) as db:
        db.add(_audit(ORG_A, token))
        with pytest.raises(IntegrityError) as caught:
            db.commit()
        assert repo.is_audit_token_conflict(caught.value)
        assert not repo.is_slot_date_conflict(caught.value)
        assert not repo.is_session_conflict(caught.value)
        assert not repo.is_record_conflict(caught.value)


def test_the_publication_queries_see_only_their_own_organisations_rows():
    from eos_timetable_attendance.infrastructure.models import AttendanceSessionRow, ScheduledClassRow, TermRef

    period = str(uuid.uuid4())
    shared_timetable_id = None
    rows = {}
    for org in (ORG_A, ORG_B):
        with _db(org) as db:
            t = _timetable(org)
            db.add(t)
            db.flush()
            shared_timetable_id = shared_timetable_id or t.id
            c = ScheduledClassRow(
                organisation_id=org,
                timetable_id=t.id,
                academic_period_id=period,
                course_offering_id=str(uuid.uuid4()),
                section_id=str(uuid.uuid4()),
                instructor_assignment_id=str(uuid.uuid4()),
                instructor_id=str(uuid.uuid4()),
                class_date=datetime(2026, 11, 10, tzinfo=UTC).date(),
                starts_at=datetime(2026, 11, 10, 9, tzinfo=UTC),
                ends_at=datetime(2026, 11, 10, 10, tzinfo=UTC),
                status="scheduled",
            )
            db.add(c)
            db.flush()
            db.add(
                AttendanceSessionRow(
                    organisation_id=org,
                    scheduled_class_id=c.id,
                    status="open",
                    opened_at=datetime(2026, 11, 10, 9, tzinfo=UTC),
                    opened_by=str(uuid.uuid4()),
                    marking_deadline=datetime(2026, 11, 11, 9, tzinfo=UTC),
                )
            )
            db.add(
                TermRef(
                    organisation_id=org,
                    academic_period_id=period,
                    code="T",
                    name="Term",
                    starts_on=datetime(2026, 7, 1, tzinfo=UTC).date(),
                    ends_on=datetime(2026, 11, 30, tzinfo=UTC).date(),
                )
            )
            db.commit()
            rows[org] = (t.id, c.id)
    for org, other in ((ORG_A, ORG_B), (ORG_B, ORG_A)):
        with _db(org) as db:
            own_timetable, own_class = rows[org]
            foreign_timetable, foreign_class = rows[other]
            assert [r.id for r in repo.classes_of_timetable(db, own_timetable)] == [own_class]
            assert repo.classes_of_timetable(db, foreign_timetable) == []  # another organisation's timetable
            assert repo.class_ids_with_session(db, [own_class, foreign_class]) == {own_class}
            assert repo.term_ref(db, period).organisation_id == org
    with _db(None) as db:  # no organisation on the session: nothing matches
        assert repo.term_ref(db, period) is None
        assert repo.classes_of_timetable(db, rows[ORG_A][0]) == []
        assert repo.class_ids_with_session(db, [rows[ORG_A][1]]) == set()
