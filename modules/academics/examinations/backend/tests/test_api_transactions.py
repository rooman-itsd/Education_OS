"""A state change is all or nothing: a failure at any step leaves no row, audit entry or event behind, and the audit entry
and the event are written in the same transaction as the change."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BASE,
    all_outbox,
    assessment_body,
    audit_entries,
    component,
    cycle_body,
    grading_body,
    make_assessment,
    make_cycle,
    make_grading,
    ok,
    session_for,
    uid,
)
from eos_examinations.application import service  # noqa: E402
from eos_examinations.application.access import Actor  # noqa: E402
from eos_examinations.application.errors import ExaminationsError  # noqa: E402
from eos_examinations.infrastructure import repository as repo  # noqa: E402
from eos_examinations.infrastructure.models import (  # noqa: E402
    AssessmentComponentRow,
    AssessmentSchemeRow,
    ExamCycleRow,
    GradingBandRow,
    GradingSchemeRow,
)
from sqlalchemy.exc import IntegrityError  # noqa: E402


class InjectedError(RuntimeError):
    pass


def actor(org) -> Actor:
    return Actor(user_id=uid(), organisation_id=org.id, permissions=set())


def counts(org) -> tuple[int, ...]:
    with session_for(org.id) as db:
        tables = (GradingSchemeRow, GradingBandRow, ExamCycleRow, AssessmentSchemeRow, AssessmentComponentRow)
        rows = tuple(repo.count(db, t) for t in tables)
    return (*rows, len(audit_entries(org.id)), len(all_outbox(org.id)))


def fail(*args, **kwargs):
    raise InjectedError("down")


@pytest.fixture
def default_scheme(client, h) -> dict:
    s = make_grading(client, h)
    ok(client.post(f"{BASE}/grading-schemes/{s['id']}/set-default", headers=h))
    return s


def test_a_failing_audit_rolls_back_each_create(org, h, default_scheme, monkeypatch):
    monkeypatch.setattr(service, "_audit", fail)
    before = counts(org)
    for call in (
        lambda db: service.create_grading_scheme(db, actor(org), grading_body()),
        lambda db: service.create_assessment_scheme(db, actor(org), assessment_body()),
        lambda db: service.create_exam_cycle(db, actor(org), cycle_body()),
    ):
        with session_for(org.id) as db, pytest.raises(InjectedError):
            call(db)
        assert counts(org) == before


def test_a_failing_event_rolls_back_the_cycle_and_its_audit_entry(org, h, default_scheme, monkeypatch):
    monkeypatch.setattr(service, "_publish", fail)
    before = counts(org)
    with session_for(org.id) as db, pytest.raises(InjectedError):
        service.create_exam_cycle(db, actor(org), cycle_body())
    assert counts(org) == before


def test_a_failing_event_on_closing_leaves_the_cycle_as_it_was(client, org, h, default_scheme, monkeypatch):
    cycle = make_cycle(client, h)
    with session_for(org.id) as db:
        db.get(ExamCycleRow, cycle["id"]).status = "results_published"
        db.commit()
    monkeypatch.setattr(service, "_publish", fail)
    before = counts(org)
    with session_for(org.id) as db, pytest.raises(InjectedError):
        service.change_exam_cycle_status(db, actor(org), cycle["id"], {"status": "closed"})
    assert counts(org) == before
    with session_for(org.id) as db:
        assert db.get(ExamCycleRow, cycle["id"]).status == "results_published"


def test_a_failing_audit_leaves_an_updated_or_moved_cycle_as_it_was(client, org, h, default_scheme, monkeypatch):
    cycle = make_cycle(client, h)
    monkeypatch.setattr(service, "_audit", fail)
    before = counts(org)
    with session_for(org.id) as db, pytest.raises(InjectedError):
        service.update_exam_cycle(db, actor(org), cycle["id"], {"name": "changed"})
    with session_for(org.id) as db, pytest.raises(InjectedError):
        service.change_exam_cycle_status(db, actor(org), cycle["id"], {"status": "scheduled"})
    assert counts(org) == before
    monkeypatch.undo()
    assert ok(client.get(f"{BASE}/exam-cycles/{cycle['id']}", headers=h)) == cycle


def test_a_failing_audit_keeps_the_old_bands_on_replace(client, org, h, monkeypatch):
    scheme = make_grading(client, h)
    monkeypatch.setattr(service, "_audit", fail)
    before = counts(org)
    with session_for(org.id) as db, pytest.raises(InjectedError):
        service.replace_grading_scheme(db, actor(org), scheme["id"], grading_body("other"))
    assert counts(org) == before
    monkeypatch.undo()
    assert ok(client.get(f"{BASE}/grading-schemes/{scheme['id']}", headers=h)) == scheme


def test_a_failing_audit_keeps_the_old_default(client, org, h, default_scheme, monkeypatch):
    second = make_grading(client, h, "second")
    monkeypatch.setattr(service, "_audit", fail)
    with session_for(org.id) as db, pytest.raises(InjectedError):
        service.set_default_grading_scheme(db, actor(org), second["id"])
    monkeypatch.undo()
    items = {s["name"]: s["is_default"] for s in ok(client.get(f"{BASE}/grading-schemes", headers=h))["items"]}
    assert items == {"10 point": True, "second": False}


def test_a_failing_audit_keeps_the_old_components_on_replace(client, org, h, monkeypatch):
    draft = make_assessment(client, h)
    monkeypatch.setattr(service, "_audit", fail)
    before = counts(org)
    body = assessment_body(draft["course_offering_id"], [component("A", 50), component("B", 50)])
    with session_for(org.id) as db, pytest.raises(InjectedError):
        service.replace_assessment_scheme(db, actor(org), draft["id"], body)
    assert counts(org) == before
    monkeypatch.undo()
    assert ok(client.get(f"{BASE}/assessment-schemes/{draft['id']}", headers=h)) == draft


def test_a_failing_audit_leaves_the_previous_scheme_active_and_the_new_one_draft(client, org, h, monkeypatch):
    offering = uid()
    v1 = make_assessment(client, h, offering)
    ok(client.post(f"{BASE}/assessment-schemes/{v1['id']}/activate", headers=h))
    v2 = make_assessment(client, h, offering)
    calls = []

    def fail_second(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:  # the superseded scheme's entry went in; the activation's does not
            raise InjectedError("down")
        return real(*args, **kwargs)

    real = service._audit
    monkeypatch.setattr(service, "_audit", fail_second)
    before = counts(org)
    with session_for(org.id) as db, pytest.raises(InjectedError):
        service.activate_assessment_scheme(db, actor(org), v2["id"])
    assert counts(org) == before
    monkeypatch.undo()
    assert ok(client.get(f"{BASE}/assessment-schemes/{v1['id']}", headers=h))["status"] == "active"
    assert ok(client.get(f"{BASE}/assessment-schemes/{v2['id']}", headers=h))["status"] == "draft"


def test_a_refused_request_changes_nothing(client, org, h, default_scheme):
    cycle = make_cycle(client, h)
    before = counts(org)
    for call in (
        lambda db: service.create_exam_cycle(db, actor(org), cycle_body(ends_on="2000-01-01")),
        lambda db: service.update_exam_cycle(db, actor(org), cycle["id"], {"starts_on": "2030-01-01"}),
        lambda db: service.change_exam_cycle_status(db, actor(org), cycle["id"], {"status": "closed"}),
        lambda db: service.create_assessment_scheme(db, actor(org), {}),
    ):
        with session_for(org.id) as db, pytest.raises(ExaminationsError):
            call(db)
    assert counts(org) == before


def test_a_session_that_failed_is_clean_for_the_next_request(client, org, h, default_scheme, monkeypatch):
    monkeypatch.setattr(service, "_audit", fail)
    with session_for(org.id) as db:
        with pytest.raises(InjectedError):
            service.create_exam_cycle(db, actor(org), cycle_body())
        monkeypatch.undo()
        created = service.create_exam_cycle(db, actor(org), cycle_body())  # the same session, nothing left over
    assert [c["id"] for c in ok(client.get(f"{BASE}/exam-cycles", headers=h))["items"]] == [created["id"]]
    assert len(all_outbox(org.id)) == 1


def _violation(table_and_columns: str) -> IntegrityError:
    class OrigError(Exception):
        pass

    return IntegrityError("insert", {}, OrigError(f"UNIQUE constraint failed: {table_and_columns}"))


@pytest.mark.parametrize(
    ("columns", "code"),
    [
        ("examinations_grading_scheme.organisation_id", "default_changed"),
        (
            "examinations_assessment_scheme.organisation_id, examinations_assessment_scheme.course_offering_id",
            "active_scheme_changed",
        ),
        (
            "examinations_assessment_scheme.organisation_id, examinations_assessment_scheme.course_offering_id, "
            "examinations_assessment_scheme.version",
            "version_taken",
        ),
    ],
)
def test_a_concurrent_uniqueness_violation_is_a_409_and_rolls_back(client, org, h, monkeypatch, columns, code):
    """Two requests racing for the default, the active scheme or a version: the loser gets the contract's 409."""
    monkeypatch.setattr(service, "_audit", lambda *a, **k: (_ for _ in ()).throw(_violation(columns)))
    before = counts(org)
    with session_for(org.id) as db, pytest.raises(ExaminationsError) as caught:
        service.create_grading_scheme(db, actor(org), grading_body())
    assert (caught.value.status, caught.value.code) == (409, code)
    assert counts(org) == before


def test_any_other_integrity_error_is_not_turned_into_a_409(org, monkeypatch):
    monkeypatch.setattr(service, "_audit", lambda *a, **k: (_ for _ in ()).throw(_violation("somewhere.else")))
    with session_for(org.id) as db, pytest.raises(IntegrityError):
        service.create_grading_scheme(db, actor(org), grading_body())
