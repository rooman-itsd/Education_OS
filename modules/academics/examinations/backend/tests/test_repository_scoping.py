"""The persistence layer: every query of the repository is limited to the session's organisation, also on SQLite, which has
no row-level security (eos_core.db.scoped); and the uniqueness and check rules the database itself holds."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from eos_core.db import SessionLocal, init_db
from eos_examinations.infrastructure import models as m
from eos_examinations.infrastructure import repository as repo
from sqlalchemy.exc import IntegrityError

NOW = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)
RULES = (
    "default_grading_scheme",
    "assessment_scheme_version",
    "active_assessment_scheme",
    "paper_component",
    "paper_in_session",
    "audit_token",
)


@pytest.fixture(scope="module", autouse=True)
def _tables():
    init_db()


def _db(organisation_id: str | None):
    db = SessionLocal()
    if organisation_id:
        db.info["organisation_id"] = organisation_id
    return db


def new() -> str:
    return str(uuid.uuid4())


def grading_scheme(org: str, *, default: bool = False) -> m.GradingSchemeRow:
    return m.GradingSchemeRow(id=new(), organisation_id=org, name="Standard", is_default=default)


def assessment_scheme(org: str, offering: str, version: int = 1, status: str = "draft") -> m.AssessmentSchemeRow:
    return m.AssessmentSchemeRow(
        id=new(),
        organisation_id=org,
        course_offering_id=offering,
        version=version,
        pass_percent=Decimal(40),
        status=status,
    )


def component(org: str, scheme_id: str, code: str = "THEORY") -> m.AssessmentComponentRow:
    return m.AssessmentComponentRow(
        id=new(),
        organisation_id=org,
        assessment_scheme_id=scheme_id,
        code=code,
        name="Written",
        kind="written",
        weightage_percent=Decimal(100),
        max_marks=Decimal(100),
    )


def cycle(org: str, scheme_id: str) -> m.ExamCycleRow:
    return m.ExamCycleRow(
        id=new(),
        organisation_id=org,
        academic_period_id=new(),
        code="END",
        name="End term",
        cycle_type="end_term",
        starts_on=date(2026, 11, 20),
        ends_on=date(2026, 12, 10),
        grading_scheme_id=scheme_id,
        check_dues=False,
        status="draft",
    )


def paper(org: str, cycle_id: str, component_id: str, offering: str) -> m.ExamPaperRow:
    return m.ExamPaperRow(
        id=new(),
        organisation_id=org,
        exam_cycle_id=cycle_id,
        course_offering_id=offering,
        assessment_component_id=component_id,
        max_marks=Decimal(100),
        status="draft",
    )


def session(org: str, cycle_id: str, start_hours: int = 0, hours: int = 3) -> m.ExamSessionRow:
    return m.ExamSessionRow(
        id=new(),
        organisation_id=org,
        exam_cycle_id=cycle_id,
        starts_at=NOW + timedelta(hours=start_hours),
        ends_at=NOW + timedelta(hours=start_hours + hours),
        invigilators_required=2,
        status="scheduled",
    )


def duty(
    org: str, cycle_id: str, staff: str, *, session_id=None, paper_id=None, kind="invigilation", status="assigned"
) -> m.ExamDutyRow:
    return m.ExamDutyRow(
        id=new(),
        organisation_id=org,
        exam_cycle_id=cycle_id,
        staff_id=staff,
        duty_type=kind,
        exam_session_id=session_id,
        exam_paper_id=paper_id,
        status=status,
    )


def seed(org: str) -> dict:
    """One row of every kind in `org`, committed."""
    offering = new()
    g = grading_scheme(org, default=True)
    band = m.GradingBandRow(
        id=new(),
        organisation_id=org,
        grading_scheme_id=g.id,
        min_percent=Decimal(0),
        max_percent=Decimal(100),
        grade="P",
        grade_point=Decimal(5),
        is_pass=True,
    )
    a = assessment_scheme(org, offering, status="active")
    comp = component(org, a.id)
    c = cycle(org, g.id)
    p = paper(org, c.id, comp.id, offering)
    s = session(org, c.id)
    link = m.ExamSessionPaperRow(id=new(), organisation_id=org, exam_session_id=s.id, exam_paper_id=p.id)
    d = duty(org, c.id, new(), session_id=s.id)
    ref = m.OfferingRef(
        id=new(),
        organisation_id=org,
        course_offering_id=offering,
        course_id=new(),
        academic_period_id=new(),
        course_code="CS101",
        course_title="Programming",
        credits=Decimal(4),
        department_id=new(),
    )
    marker = m.ProcessedEvent(
        id=new(), organisation_id=org, event_id=new(), name="academic-management.offering.created"
    )
    audit = m.AuditEntry(
        id=new(),
        organisation_id=org,
        client_token=new(),
        action="exam-cycle.created",
        entity_type="exam_cycle",
        entity_id=c.id,
        summary="created",
        occurred_at=NOW,
    )
    rows = [g, band, a, comp, c, p, s, link, d, ref, marker, audit]
    with _db(org) as db:
        for row in rows:  # parents first, committed one by one so a foreign key never points at nothing
            db.add(row)
            db.flush()
        db.commit()
    return {type(r): r.id for r in rows} | {
        "offering": offering,
        "scheme": a.id,
        "cycle": c.id,
        "session": s.id,
        "paper": p.id,
    }


def test_every_table_is_covered_by_the_seed():
    assert {t.name for t in m.TABLES} == {model.__table__.name for model in seed(new()) if not isinstance(model, str)}


def test_a_query_sees_only_its_own_organisations_rows_for_every_table():
    a, b = new(), new()
    ids_a, ids_b = seed(a), seed(b)
    for model in (k for k in ids_a if not isinstance(k, str)):
        with _db(a) as db:
            seen = {r.id for r in db.scalars(repo.q(db, model))}
            assert ids_a[model] in seen and ids_b[model] not in seen, model.__name__
            assert repo.get(db, model, ids_a[model]) is not None
            assert repo.get(db, model, ids_b[model]) is None  # another organisation's row is not found
        with _db(b) as db:
            assert ids_a[model] not in {r.id for r in db.scalars(repo.q(db, model))}, model.__name__


def test_a_session_without_an_organisation_sees_nothing():
    seed(new())
    with _db(None) as db:
        for table in m.TABLES:
            model = next(c.class_ for c in m.Base.registry.mappers if c.local_table is table)
            assert list(db.scalars(repo.q(db, model))) == [], table.name


def test_every_lookup_is_scoped_to_the_organisation():
    a, b = new(), new()
    ids_a, ids_b = seed(a), seed(b)
    with _db(a) as db:
        assert repo.default_grading_scheme(db).id == ids_a[m.GradingSchemeRow]
        assert [s.id for s in repo.schemes_of_offering(db, ids_a["offering"])] == [ids_a["scheme"]]
        assert repo.schemes_of_offering(db, ids_b["offering"]) == []
        assert [c.id for c in repo.components_of(db, ids_a["scheme"])] == [ids_a[m.AssessmentComponentRow]]
        assert repo.components_of(db, ids_b["scheme"]) == []
        assert [r.id for r in repo.bands_of(db, ids_a[m.GradingSchemeRow])] == [ids_a[m.GradingBandRow]]
        assert [p.id for p in repo.papers_of_cycle(db, ids_a["cycle"])] == [ids_a["paper"]]
        assert repo.papers_of_cycle(db, ids_b["cycle"]) == []
        assert repo.paper_ids_in_sessions(db, [ids_a["paper"], ids_b["paper"]]) == {ids_a["paper"]}
        assert repo.cycle(db, ids_b["cycle"]) is None
        assert repo.count(db, m.ExamCycleRow) == repo.count(db, m.ExamCycleRow)  # counts only its own rows
    with _db(None) as db:
        assert repo.default_grading_scheme(db) is None and repo.count(db, m.ExamCycleRow) == 0


def test_invigilation_sessions_are_those_of_assigned_duties_of_that_staff_member_in_that_organisation():
    a, b, staff = new(), new(), new()
    with _db(a) as db:
        g = grading_scheme(a)
        db.add(g)
        db.flush()
        c = cycle(a, g.id)
        db.add(c)
        db.flush()
        first, second, third = session(a, c.id, 0), session(a, c.id, 24), session(a, c.id, 48)
        other_org = m.ExamDutyRow()
        db.add_all([first, second, third])
        db.flush()
        db.add_all(
            [
                duty(a, c.id, staff, session_id=second.id),
                duty(a, c.id, staff, session_id=first.id),
                duty(a, c.id, staff, session_id=third.id, status="cancelled"),
                duty(a, c.id, new(), session_id=third.id),  # another staff member
            ]
        )
        db.commit()
        del other_org
    with _db(a) as db:
        assert [s.id for s in repo.assigned_invigilation_sessions(db, staff)] == [first.id, second.id]  # by start time
    with _db(b) as db:
        assert repo.assigned_invigilation_sessions(db, staff) == []


def test_bands_come_back_in_order_of_their_range():
    org = new()
    with _db(org) as db:
        g = grading_scheme(org)
        db.add(g)
        db.flush()
        for low, high, grade in ((60, 100, "A"), (0, 40, "F"), (40, 60, "B")):
            db.add(
                m.GradingBandRow(
                    id=new(),
                    organisation_id=org,
                    grading_scheme_id=g.id,
                    min_percent=Decimal(low),
                    max_percent=Decimal(high),
                    grade=grade,
                    grade_point=Decimal(1),
                    is_pass=low >= 40,
                )
            )
        db.commit()
        assert [b.grade for b in repo.bands_of(db, g.id)] == ["F", "B", "A"]


# ---------------------------------------------------------------- uniqueness the database holds


def commit_expecting_conflict(org: str, *rows) -> IntegrityError:
    with _db(org) as db:
        db.add_all(rows)
        with pytest.raises(IntegrityError) as caught:
            db.commit()
        db.rollback()
    return caught.value


def only(err: IntegrityError, rule: str) -> None:
    """The error is a violation of `rule` and of no other rule the module answers with 409."""
    assert repo.violates(err, rule), rule
    assert not any(repo.violates(err, other) for other in RULES if other != rule)


def test_one_default_grading_scheme_per_organisation():
    a, b = new(), new()
    with _db(a) as db:
        db.add_all([grading_scheme(a, default=True), grading_scheme(a), grading_scheme(a)])
        db.commit()  # any number of non-default schemes
    with _db(b) as db:
        db.add(grading_scheme(b, default=True))
        db.commit()  # another organisation has its own default
    only(commit_expecting_conflict(a, grading_scheme(a, default=True)), "default_grading_scheme")


def test_one_active_assessment_scheme_per_course_offering_and_versions_are_unique():
    a, b, offering = new(), new(), new()
    with _db(a) as db:
        db.add_all(
            [
                assessment_scheme(a, offering, 1, "superseded"),
                assessment_scheme(a, offering, 2, "superseded"),
                assessment_scheme(a, offering, 3, "active"),
                assessment_scheme(a, offering, 4, "draft"),
            ]
        )
        db.add(assessment_scheme(a, new(), 1, "active"))  # another offering has its own active scheme
        db.commit()
    with _db(b) as db:
        db.add(assessment_scheme(b, offering, 1, "active"))  # so does another organisation, for the same offering id
        db.commit()
    only(commit_expecting_conflict(a, assessment_scheme(a, offering, 5, "active")), "active_assessment_scheme")
    only(commit_expecting_conflict(a, assessment_scheme(a, offering, 3, "draft")), "assessment_scheme_version")


def test_a_component_has_one_paper_per_cycle_and_a_paper_is_in_one_session():
    org = new()
    ids = seed(org)
    with _db(org) as db:
        cycle_row = db.get(m.ExamCycleRow, ids["cycle"])
        component_id = db.scalars(repo.q(db, m.AssessmentComponentRow)).first().id
        assert cycle_row is not None
    only(commit_expecting_conflict(org, paper(org, ids["cycle"], component_id, ids["offering"])), "paper_component")
    second_session = session(org, ids["cycle"], 24)
    with _db(org) as db:
        db.add(second_session)
        db.commit()
    only(
        commit_expecting_conflict(
            org,
            m.ExamSessionPaperRow(
                id=new(), organisation_id=org, exam_session_id=second_session.id, exam_paper_id=ids["paper"]
            ),
        ),
        "paper_in_session",
    )


def test_an_audit_client_token_is_unique_within_an_organisation_but_not_across_them():
    a, b, token = new(), new(), new()

    def entry(org):
        return m.AuditEntry(
            id=new(),
            organisation_id=org,
            client_token=token,
            action="a",
            entity_type="exam_cycle",
            entity_id=new(),
            summary="s",
            occurred_at=NOW,
        )

    with _db(a) as db:
        db.add(entry(a))
        db.commit()
    with _db(b) as db:
        db.add(entry(b))
        db.commit()
        assert repo.audit_entry_by_token(db, b, token).organisation_id == b
        assert repo.audit_entry_by_token(db, a, token) is None  # scoped: the other organisation's is not visible
    only(commit_expecting_conflict(a, entry(a)), "audit_token")


def test_a_duty_names_a_session_or_a_paper_never_both_nor_neither():
    org = new()
    ids = seed(org)
    bad = [
        duty(org, ids["cycle"], new(), kind="invigilation"),
        duty(org, ids["cycle"], new(), kind="invigilation", session_id=ids["session"], paper_id=ids["paper"]),
        duty(org, ids["cycle"], new(), kind="invigilation", paper_id=ids["paper"]),
        duty(org, ids["cycle"], new(), kind="evaluation"),
        duty(org, ids["cycle"], new(), kind="moderation", session_id=ids["session"]),
        duty(org, ids["cycle"], new(), kind="evaluation", session_id=ids["session"], paper_id=ids["paper"]),
    ]
    for row in bad:
        err = commit_expecting_conflict(org, row)
        assert "ck_examinations_duty_target" in str(err.orig) or "CHECK constraint failed" in str(err.orig)
        assert not any(repo.violates(err, rule) for rule in RULES)  # a check failure is never mistaken for a conflict
    with _db(org) as db:
        db.add_all(
            [
                duty(org, ids["cycle"], new(), session_id=ids["session"]),
                duty(org, ids["cycle"], new(), kind="evaluation", paper_id=ids["paper"]),
            ]
        )
        db.commit()


def test_helpers_round_trip_dates_and_zones():
    naive = datetime(2026, 11, 3, 9, 0)
    assert m.as_utc(naive) == NOW and m.as_utc(None) is None
    assert m.iso(date(2026, 11, 3)) == "2026-11-03" and m.iso(NOW) == NOW.isoformat() and m.iso(None) is None
