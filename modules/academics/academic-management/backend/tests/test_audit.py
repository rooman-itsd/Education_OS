"""Every state change leaves an audit record (FR-16; RULES.md definition of done). The audit SDK does not exist yet, so
academic_management_audit_entry stands in for it, as hostel's and helpdesk's tables do. Entries are written in the
same transaction as the change and its event, and belong to the changed row's organisation."""

from datetime import date

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see test_api_deps.py)")

from conftest import BASE, assign, make_course, make_offering, make_programme, make_term, ok, outbox  # noqa: E402
from eos_academic_management.application import roster, service  # noqa: E402
from eos_academic_management.application.access import Actor  # noqa: E402
from eos_academic_management.infrastructure import repository as repo  # noqa: E402
from eos_academic_management.infrastructure.models import AuditEntry, TermRow  # noqa: E402
from eos_core.db import SessionLocal, new_id  # noqa: E402
from eos_core.tenant import platform_scope  # noqa: E402
from sqlalchemy import select  # noqa: E402

HOD = "department-admin"


def audit(organisation_id: str, entity_id: str | None = None) -> list[tuple[str, str | None, str | None]]:
    """(action, actor, reason) of one organisation's audit entries, optionally for one entity, sorted: the test clock
    is frozen, so occurred_at does not order them."""
    with SessionLocal() as db, platform_scope():
        q = select(AuditEntry).where(AuditEntry.organisation_id == organisation_id)
        if entity_id is not None:
            q = q.where(AuditEntry.entity_id == entity_id)
        return sorted((r.action, r.actor, r.reason) for r in db.scalars(q))


def actions(organisation_id: str, entity_id: str | None = None) -> list[str]:
    return [a for a, _, _ in audit(organisation_id, entity_id)]


RECORD_FIELDS = ("client_token", "action", "entity_type", "entity_id", "summary", "before", "after", "actor")


def records(organisation_id: str, entity_id: str | None = None, action: str | None = None) -> list[dict]:
    """The platform/audit Record fields of one organisation's entries, as plain dicts."""
    with SessionLocal() as db, platform_scope():
        q = select(AuditEntry).where(AuditEntry.organisation_id == organisation_id)
        if entity_id is not None:
            q = q.where(AuditEntry.entity_id == entity_id)
        if action is not None:
            q = q.where(AuditEntry.action == action)
        return [{f: getattr(r, f) for f in RECORD_FIELDS} for r in db.scalars(q)]


def test_every_state_change_through_the_api_is_audited(client, org):
    admin_id, admin = org.user("org-admin")
    hod_id, h = org.user(HOD)
    odd = make_term(client, admin)
    ok(client.patch(f"{BASE}/terms/{odd['id']}", json={"name": "Odd 2026"}, headers=admin))
    ok(client.post(f"{BASE}/terms/{odd['id']}/activate", headers=admin))
    even = make_term(client, admin, code="2027-EVEN", start="2026-12-01", end="2027-04-30")
    ok(client.post(f"{BASE}/terms/{even['id']}/activate", headers=admin))

    p = make_programme(client, admin, duration_terms=2, credits_required=8)
    ok(client.patch(f"{BASE}/programmes/{p['id']}", json={"name": "Renamed"}, headers=admin))
    c1, c2 = make_course(client, admin, "C1", 4), make_course(client, admin, "C2", 4)
    ok(client.patch(f"{BASE}/courses/{c1['id']}", json={"lecture_hours": 3}, headers=admin))
    items = [
        {"course_id": c1["id"], "programme_term": 1, "category": "core", "credits": 4},
        {"course_id": c2["id"], "programme_term": 2, "category": "core", "credits": 4},
    ]
    cur = ok(client.post(f"{BASE}/programmes/{p['id']}/curricula", json={"items": items[:1]}, headers=admin), 201)
    ok(client.put(f"{BASE}/curricula/{cur['id']}", json={"items": items}, headers=admin))
    ok(client.post(f"{BASE}/curricula/{cur['id']}/publish", headers=admin))

    o = make_offering(client, h, c1["id"], odd["id"])
    ok(client.patch(f"{BASE}/offerings/{o['id']}", json={"programme_ids": [p["id"]]}, headers=h))
    b = ok(client.post(f"{BASE}/offerings/{o['id']}/sections", json={"code": "B", "capacity": 3}, headers=h), 201)
    ok(client.patch(f"{BASE}/sections/{b['id']}", json={"capacity": 4}, headers=h))
    teacher, _ = org.user("faculty")
    assign(client, h, o["id"], teacher)
    helper = assign(client, h, o["id"], org.user("faculty")[0], role="co_instructor")
    ok(client.post(f"{BASE}/faculty-assignments/{helper['id']}/end", headers=h))
    ok(client.post(f"{BASE}/offerings/{o['id']}/status", json={"status": "open", "reason": "Timetable out"}, headers=h))
    ok(client.post(f"{BASE}/programmes/{p['id']}/archive", headers=admin))
    ok(client.post(f"{BASE}/courses/{c2['id']}/archive", headers=admin))

    names = set(actions(org.id))
    for expected in (
        "term.created",
        "term.updated",
        "term.activated",
        "term.closed",
        "programme.created",
        "programme.updated",
        "programme.archived",
        "course.created",
        "course.updated",
        "course.archived",
        "curriculum.created",
        "curriculum.items_replaced",
        "curriculum.published",
        "offering.created",
        "offering.updated",
        "offering.open",
        "section.created",
        "section.updated",
        "faculty_assignment.created",
        "faculty_assignment.ended",
    ):
        assert expected in names, expected
    assert actions(org.id, odd["id"]) == ["term.activated", "term.closed", "term.created", "term.updated"]
    assert ("programme.created", admin_id, None) in audit(org.id, p["id"])
    assert ("offering.open", hod_id, "Timetable out") in audit(org.id, o["id"])  # the reason is kept


def test_a_request_that_changes_nothing_writes_no_audit_entry(client, org):
    _, admin = org.user("org-admin")
    term = make_term(client, admin)
    ok(client.patch(f"{BASE}/terms/{term['id']}", json={"name": term["name"]}, headers=admin))
    ok(client.post(f"{BASE}/terms/{term['id']}/activate", headers=admin))
    ok(client.post(f"{BASE}/terms/{term['id']}/activate", headers=admin))  # already active: nothing changes
    assert actions(org.id, term["id"]) == ["term.activated", "term.created"]


def test_the_same_curriculum_items_in_another_order_change_nothing_and_are_not_audited(client, org):
    """Items carry no position (they are read back by programme term), so a reordered list is the same curriculum."""
    _, admin = org.user("org-admin")
    p = make_programme(client, admin, duration_terms=2, credits_required=8)
    c1, c2 = make_course(client, admin, "C1", 4), make_course(client, admin, "C2", 4)
    items = [
        {"course_id": c1["id"], "programme_term": 1, "category": "core", "credits": 4},
        {"course_id": c2["id"], "programme_term": 2, "category": "elective", "credits": 4},
    ]
    cur = ok(client.post(f"{BASE}/programmes/{p['id']}/curricula", json={"items": items}, headers=admin), 201)
    same = ok(client.put(f"{BASE}/curricula/{cur['id']}", json={"items": items[::-1]}, headers=admin))
    assert same["items"] == cur["items"]  # nothing rewritten: the item ids are unchanged
    assert actions(org.id, cur["id"]) == ["curriculum.created"]

    changed = [items[0], {**items[1], "category": "core"}]
    replaced = ok(client.put(f"{BASE}/curricula/{cur['id']}", json={"items": changed}, headers=admin))
    assert [i["category"] for i in replaced["items"]] == ["core", "core"]
    assert actions(org.id, cur["id"]) == ["curriculum.created", "curriculum.items_replaced"]


def test_publishing_a_curriculum_also_records_the_programme_pointer_change(client, org):
    admin_id, admin = org.user("org-admin")
    p = make_programme(client, admin, duration_terms=1, credits_required=4)
    c = make_course(client, admin, "P1", 4)
    items = [{"course_id": c["id"], "programme_term": 1, "category": "core", "credits": 4}]
    v1 = ok(client.post(f"{BASE}/programmes/{p['id']}/curricula", json={"items": items}, headers=admin), 201)
    ok(client.post(f"{BASE}/curricula/{v1['id']}/publish", headers=admin))
    assert ok(client.get(f"{BASE}/programmes/{p['id']}", headers=admin))["published_curriculum_id"] == v1["id"]
    assert ("curriculum.published", admin_id, None) in audit(org.id, v1["id"])
    assert audit(org.id, p["id"]) == [
        ("programme.created", admin_id, None),
        ("programme.curriculum_published", admin_id, None),
    ]

    again = client.post(f"{BASE}/curricula/{v1['id']}/publish", headers=admin)
    assert again.status_code == 409  # already published: nothing changes, nothing is recorded
    assert actions(org.id, p["id"]) == ["programme.created", "programme.curriculum_published"]

    body = {"copy_from_curriculum_id": v1["id"]}
    v2 = ok(client.post(f"{BASE}/programmes/{p['id']}/curricula", json=body, headers=admin), 201)
    ok(client.post(f"{BASE}/curricula/{v2['id']}/publish", headers=admin))
    assert actions(org.id, p["id"]) == ["programme.created"] + ["programme.curriculum_published"] * 2


def test_a_failed_publication_keeps_neither_the_pointer_nor_its_entries(client, org):
    """The curriculum, the programme pointer, both audit entries and the event share one transaction."""
    admin_id, admin = org.user("org-admin")
    p = make_programme(client, admin, duration_terms=1, credits_required=4)
    c = make_course(client, admin, "P1", 4)
    items = [{"course_id": c["id"], "programme_term": 1, "category": "core", "credits": 4}]
    cur = ok(client.post(f"{BASE}/programmes/{p['id']}/curricula", json={"items": items}, headers=admin), 201)

    def failing_commit():
        raise RuntimeError("commit failed")

    with SessionLocal() as db:
        db.info["organisation_id"] = org.id
        db.commit = failing_commit
        with pytest.raises(RuntimeError):
            service.publish_curriculum(db, Actor(user_id=admin_id, organisation_id=org.id), cur["id"])
        db.rollback()
    assert ok(client.get(f"{BASE}/programmes/{p['id']}", headers=admin))["published_curriculum_id"] is None
    assert ok(client.get(f"{BASE}/curricula/{cur['id']}", headers=admin))["status"] == "draft"
    assert actions(org.id, p["id"]) == ["programme.created"]
    assert actions(org.id, cur["id"]) == ["curriculum.created"]
    assert not [n for n, _, _ in outbox(org.id) if n.endswith("curriculum.published")]


def test_a_refused_request_writes_no_audit_entry(client, org):
    _, admin = org.user("org-admin")
    make_term(client, admin)
    before = audit(org.id)
    duplicate = {"code": "2026-ODD", "name": "x", "starts_on": "2027-01-01", "ends_on": "2027-02-01"}
    assert client.post(f"{BASE}/terms", json=duplicate, headers=admin).status_code == 409
    assert client.patch(f"{BASE}/terms/{new_id()}", json={"name": "x"}, headers=admin).status_code == 404
    assert audit(org.id) == before


def test_the_entry_is_rolled_back_with_the_change_and_its_event(org):
    """The audit entry, the row and the outbox event share one transaction: when it does not commit, none remain."""
    actor = Actor(user_id=new_id(), organisation_id=org.id)
    body = {"code": "ROLLBACK", "name": "Never kept", "starts_on": date(2026, 7, 1), "ends_on": date(2026, 11, 30)}

    def failing_commit():
        raise RuntimeError("commit failed")

    with SessionLocal() as db:
        db.info["organisation_id"] = org.id
        db.commit = failing_commit
        with pytest.raises(RuntimeError):
            service.create_term(db, actor, body)
        assert actions(org.id) == []  # flushed but not committed: not visible outside the transaction
        db.rollback()
    with SessionLocal() as db:
        db.info["organisation_id"] = org.id
        assert db.scalars(repo.q(db, TermRow)).all() == []
    assert audit(org.id) == []
    assert outbox(org.id) == []


def test_entries_belong_to_their_organisation_and_are_scoped_to_it(client, org, other_org):
    for o in (org, other_org):
        _, admin = o.user("org-admin")
        make_term(client, admin)
    for mine, theirs in ((org, other_org), (other_org, org)):
        with SessionLocal() as db:
            db.info["organisation_id"] = mine.id
            seen = db.scalars(repo.q(db, AuditEntry)).all()
        assert seen and {e.organisation_id for e in seen} == {mine.id}
        assert not [e for e in seen if e.organisation_id == theirs.id]


# ---------------------------------------------------------------- roster read model, applied from events


def _deliver(name: str, organisation_id: str, payload: dict) -> str:
    envelope = {
        "id": new_id(),
        "name": f"enrolment-registration.{name}",
        "version": 1,
        "organisation_id": organisation_id,
        "actor": None,
        "occurred_at": "2026-10-22T09:00:00+00:00",
        "payload": payload,
    }
    with SessionLocal() as db:
        return roster.handle_event(db, envelope)


@pytest.fixture
def open_course(client, org):
    """An open offering with sections A (capacity 1) and B (capacity 2)."""
    _, h = org.user(HOD)
    _, admin = org.user("org-admin")
    term, course = make_term(client, admin), make_course(client, admin)
    o = make_offering(client, h, course["id"], term["id"], (("A", 1), ("B", 2)))
    assign(client, h, o["id"], org.user("faculty")[0])
    ok(client.post(f"{BASE}/offerings/{o['id']}/status", json={"status": "open"}, headers=h))
    a, b = ok(client.get(f"{BASE}/offerings/{o['id']}", headers=h))["sections"]
    return o, a, b


def _registration(o, section) -> dict:
    return {
        "registration_id": new_id(),
        "person_id": new_id(),
        "course_offering_id": o["id"],
        "section_id": section["id"],
        "academic_period_id": o["academic_period_id"],
    }


def _roster_audit(organisation_id: str) -> list[tuple[str, str | None]]:
    return [(a, actor) for a, actor, _ in audit(organisation_id) if a.startswith("roster_entry.")]


def test_roster_changes_from_enrolment_events_are_audited_without_an_actor(org, open_course):
    o, a, b = open_course
    p = _registration(o, a)
    assert _deliver("course-registration.confirmed", org.id, p) == roster.APPLIED
    move = {**p, "from_section_id": a["id"], "to_section_id": b["id"]}
    assert _deliver("section-allocation.changed", org.id, move) == roster.APPLIED
    assert _deliver("course-registration.withdrawn", org.id, {**p, "section_id": b["id"]}) == roster.APPLIED
    assert _roster_audit(org.id) == [
        ("roster_entry.confirmed", None),
        ("roster_entry.section_changed", None),
        ("roster_entry.withdrawn", None),
    ]  # sorted by action, see audit()


def test_rejected_and_repeated_roster_events_write_no_audit_entry(org, open_course):
    o, a, _ = open_course
    first = _registration(o, a)
    assert _deliver("course-registration.confirmed", org.id, first) == roster.APPLIED
    assert _deliver("course-registration.confirmed", org.id, _registration(o, a)) == roster.REJECTED_SECTION_FULL
    withdrawn = {**first}
    assert _deliver("course-registration.withdrawn", org.id, withdrawn) == roster.APPLIED
    assert _deliver("course-registration.withdrawn", org.id, withdrawn) == roster.APPLIED  # already withdrawn
    assert _roster_audit(org.id) == [("roster_entry.confirmed", None), ("roster_entry.withdrawn", None)]


def test_a_repeated_confirmation_is_audited_only_when_it_changes_the_row(org, open_course):
    """A new envelope id with the same data is applied (the row is upserted) but changes nothing, so no entry."""
    o, _, b = open_course
    p = _registration(o, b)
    assert _deliver("course-registration.confirmed", org.id, p) == roster.APPLIED
    assert _deliver("course-registration.confirmed", org.id, p) == roster.APPLIED
    assert _roster_audit(org.id) == [("roster_entry.confirmed", None)]
    assert _deliver("course-registration.confirmed", org.id, {**p, "student_name": "Asha"}) == roster.APPLIED
    assert _roster_audit(org.id) == [("roster_entry.confirmed", None), ("roster_entry.confirmed", None)]


def test_a_section_change_into_the_same_section_is_not_audited(org, open_course):
    o, a, b = open_course
    p = _registration(o, b)
    assert _deliver("course-registration.confirmed", org.id, p) == roster.APPLIED
    stay = {**p, "from_section_id": b["id"], "to_section_id": b["id"]}
    assert _deliver("section-allocation.changed", org.id, stay) == roster.APPLIED
    assert _roster_audit(org.id) == [("roster_entry.confirmed", None)]
    move = {**p, "from_section_id": b["id"], "to_section_id": a["id"]}
    assert _deliver("section-allocation.changed", org.id, move) == roster.APPLIED
    assert _roster_audit(org.id) == [("roster_entry.confirmed", None), ("roster_entry.section_changed", None)]


# ---------------------------------------------------------------- record shape (platform/audit NewRecord)


def _term(organisation_id: str, code: str) -> TermRow:
    return TermRow(
        organisation_id=organisation_id,
        code=code,
        name=f"Term {code}",
        starts_on=date(2030, 1, 1),
        ends_on=date(2030, 2, 1),
        status="upcoming",
    )


def test_the_columns_follow_the_platform_audit_record_contract():
    """Every NewRecord field is a column, except `module` (always this module) and `context` (supplied by the
    gateway, which modules do not see). Read from platform/audit's contract when the repository has it."""
    import os
    from pathlib import Path

    import yaml

    path = Path(os.environ["EOS_REPO_ROOT"]) / "platform" / "audit" / "contracts" / "openapi.yaml"
    if not path.exists():
        pytest.skip("platform/audit contract not in this checkout")
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))["components"]["schemas"]["NewRecord"]
    columns = set(AuditEntry.__table__.columns.keys())
    assert set(contract["properties"]) - {"module", "context"} <= columns
    assert {"organisation_id", "actor", "occurred_at"} <= columns  # Record's own required fields


def test_a_creation_records_chosen_fields_and_an_update_only_the_changed_ones(client, org):
    admin_id, admin = org.user("org-admin")
    term = make_term(client, admin)
    [created] = records(org.id, term["id"], "term.created")
    assert (created["entity_type"], created["entity_id"], created["actor"]) == ("term", term["id"], admin_id)
    assert created["before"] is None
    assert created["after"] == {
        "code": "2026-ODD",
        "name": "Term 2026-ODD",
        "starts_on": "2026-07-01",
        "ends_on": "2026-11-30",
        "status": "upcoming",
    }
    assert created["summary"] == "term 2026-ODD created"
    assert created["client_token"]
    with SessionLocal() as db, platform_scope():  # an absent before is SQL NULL, not the JSON value null
        stored = db.execute(
            select(AuditEntry.__table__.c.before.is_(None)).where(AuditEntry.entity_id == term["id"])
        ).scalar()
    assert stored is True

    ok(client.patch(f"{BASE}/terms/{term['id']}", json={"name": "Odd 2026"}, headers=admin))
    [updated] = records(org.id, term["id"], "term.updated")
    assert (updated["before"], updated["after"]) == ({"name": "Term 2026-ODD"}, {"name": "Odd 2026"})
    assert updated["summary"] == "term 2026-ODD updated: name"
    assert updated["client_token"] != created["client_token"]


def test_updates_record_the_changed_fields_only(client, org):
    _, admin = org.user("org-admin")
    _, h = org.user(HOD)
    p = make_programme(client, admin, credits_required=8)
    ok(client.patch(f"{BASE}/programmes/{p['id']}", json={"credits_required": 10.5}, headers=admin))
    [programme] = records(org.id, p["id"], "programme.updated")
    assert (programme["before"], programme["after"]) == ({"credits_required": 8}, {"credits_required": 10.5})

    term, course = make_term(client, admin), make_course(client, admin)
    o = make_offering(client, h, course["id"], term["id"])
    assign(client, h, o["id"], org.user("faculty")[0])
    ok(client.post(f"{BASE}/offerings/{o['id']}/status", json={"status": "open", "reason": "Ready"}, headers=h))
    [status] = records(org.id, o["id"], "offering.open")
    assert (status["before"], status["after"]) == ({"status": "planned"}, {"status": "open"})

    c1, c2 = make_course(client, admin, "I1", 4), make_course(client, admin, "I2", 4)
    items = [
        {"course_id": c1["id"], "programme_term": 1, "category": "core", "credits": 4},
        {"course_id": c2["id"], "programme_term": 2, "category": "elective", "credits": 4},
    ]
    cur = ok(client.post(f"{BASE}/programmes/{p['id']}/curricula", json={"items": items[:1]}, headers=admin), 201)
    ok(client.put(f"{BASE}/curricula/{cur['id']}", json={"items": items}, headers=admin))
    [replaced] = records(org.id, cur["id"], "curriculum.items_replaced")
    assert replaced["before"] == {"items": []}  # nothing removed
    assert replaced["after"] == {"items": [items[1]]}  # only the item added


def test_personal_details_and_free_text_are_never_copied(client, org, open_course):
    _, admin = org.user("org-admin")
    c = make_course(client, admin, "D1")
    ok(client.patch(f"{BASE}/courses/{c['id']}", json={"description": "Week 1: sets"}, headers=admin))
    [course] = records(org.id, c["id"], "course.updated")
    assert (course["before"], course["after"]) == ({}, {})  # the change is recorded, its text is not
    assert course["summary"] == "course D1 updated: description"

    o, a, _ = open_course
    p = {**_registration(o, a), "student_name": "Asha Rao", "roll_number": "R-77"}
    assert _deliver("course-registration.confirmed", org.id, p) == roster.APPLIED
    assert _deliver("course-registration.confirmed", org.id, {**p, "student_name": "Asha K"}) == roster.APPLIED
    renamed = [r for r in records(org.id, action="roster_entry.confirmed") if r["before"] is not None]
    assert [(r["before"], r["after"]) for r in renamed] == [({}, {})]
    assert renamed[0]["summary"].endswith(": student_name")

    stored = repr(records(org.id))
    for secret in ("Asha", "R-77", "Week 1"):
        assert secret not in stored
    for r in records(org.id):
        assert not (set(r["before"] or {}) | set(r["after"] or {})) & service.NOT_RECORDED


def test_a_repeated_client_token_returns_the_original_record_and_appends_nothing(org):
    actor = Actor(user_id=new_id(), organisation_id=org.id)
    with SessionLocal() as db:
        db.info["organisation_id"] = org.id
        term = _term(org.id, "TOK")
        db.add(term)
        first = service._audit(db, actor, "term.created", "term", term, after={"code": "TOK"}, client_token="retry-1")
        again = service._audit(db, actor, "term.created", "term", term, after={"code": "TOK"}, client_token="retry-1")
        assert (again.id, again.action) == (first.id, "term.created")
        db.commit()
    assert [r["client_token"] for r in records(org.id)] == ["retry-1"]


def test_a_token_recorded_concurrently_returns_that_record_and_keeps_the_transaction(org, monkeypatch):
    """Another request records the token between this one's check and its insert: the unique constraint refuses the
    insert inside a savepoint, the original record is returned, and this request's own change still commits."""
    actor = Actor(user_id=new_id(), organisation_id=org.id)
    with SessionLocal() as other:
        other.info["organisation_id"] = org.id
        term_a = _term(org.id, "RACE-A")
        other.add(term_a)
        first_id = service._audit(other, actor, "term.created", "term", term_a, client_token="race-1").id
        other.commit()

    real, calls = repo.audit_entry_by_token, []

    def missed_once(db, organisation_id, token):
        calls.append(token)
        return None if len(calls) == 1 else real(db, organisation_id, token)

    monkeypatch.setattr(repo, "audit_entry_by_token", missed_once)
    with SessionLocal() as db:
        db.info["organisation_id"] = org.id
        term_b = _term(org.id, "RACE-B")
        db.add(term_b)
        got = service._audit(db, actor, "term.created", "term", term_b, client_token="race-1")
        assert got.id == first_id
        db.commit()
    with SessionLocal() as db:
        db.info["organisation_id"] = org.id
        codes = {t.code for t in db.scalars(repo.q(db, TermRow))}
    assert {"RACE-A", "RACE-B"} <= codes
    assert [r["client_token"] for r in records(org.id)].count("race-1") == 1


def test_a_roster_record_is_keyed_by_its_envelope_id(org, open_course):
    o, a, _ = open_course
    p, event_id = _registration(o, a), new_id()
    envelope = {
        "id": event_id,
        "name": "enrolment-registration.course-registration.confirmed",
        "version": 1,
        "organisation_id": org.id,
        "actor": None,
        "occurred_at": "2026-10-22T09:00:00+00:00",
        "payload": p,
    }
    with SessionLocal() as db:
        assert roster.handle_event(db, dict(envelope)) == roster.APPLIED
    with SessionLocal() as db:
        assert roster.handle_event(db, dict(envelope)) == roster.DUPLICATE
    [record] = records(org.id, action="roster_entry.confirmed")
    assert record["client_token"] == f"event:{event_id}"
    assert (record["entity_type"], record["actor"], record["before"]) == ("roster_entry", None, None)  # system
    assert record["after"] == {
        "person_id": p["person_id"],
        "course_offering_id": o["id"],
        "section_id": a["id"],
        "status": "enrolled",
    }


def _apply_event(name: str, organisation_id: str, payload: dict, actor: str | None = None) -> str:
    envelope = {
        "id": new_id(),
        "name": f"enrolment-registration.{name}",
        "version": 1,
        "organisation_id": organisation_id,
        "actor": actor,
        "occurred_at": "2026-10-22T09:00:00+00:00",
        "payload": payload,
    }
    with SessionLocal() as db:
        return roster.handle_event(db, envelope)


def test_a_roster_record_names_the_user_who_caused_the_change(org, open_course):
    """The envelope's actor is the user who caused the change (platform/event-bus); None only when the system did."""
    o, a, b = open_course
    p, registrar = _registration(o, a), new_id()
    assert _apply_event("course-registration.confirmed", org.id, p, actor=registrar) == roster.APPLIED
    move = {**p, "from_section_id": a["id"], "to_section_id": b["id"]}
    assert _apply_event("section-allocation.changed", org.id, move) == roster.APPLIED
    assert sorted((r["action"], r["actor"]) for r in records(org.id) if r["entity_type"] == "roster_entry") == [
        ("roster_entry.confirmed", registrar),
        ("roster_entry.section_changed", None),
    ]


def test_a_registration_undone_for_capacity_leaves_no_row_and_no_audit_record(org, open_course, monkeypatch):
    """A concurrent registration took the last seat after this one's check: handle_event re-counts, rolls back the
    roster row and its audit record together, and still records the event as processed (no redelivery loop)."""
    o, a, _ = open_course  # section A holds one
    assert _apply_event("course-registration.confirmed", org.id, _registration(o, a)) == roster.APPLIED
    before = records(org.id)
    monkeypatch.setattr(roster, "_admit", lambda *args: None)  # the check passed before the other seat was taken
    second = _registration(o, a)
    envelope = {
        "id": new_id(),
        "name": "enrolment-registration.course-registration.confirmed",
        "version": 1,
        "organisation_id": org.id,
        "actor": new_id(),
        "occurred_at": "2026-10-22T09:00:00+00:00",
        "payload": second,
    }
    with SessionLocal() as db:
        assert roster.handle_event(db, dict(envelope)) == roster.REJECTED_SECTION_FULL
    assert records(org.id) == before
    with SessionLocal() as db:
        db.info["organisation_id"] = org.id
        assert repo.roster_entry(db, second["registration_id"]) is None
        assert roster.handle_event(db, dict(envelope)) == roster.DUPLICATE


def test_a_malformed_event_writes_no_audit_record(org, open_course):
    o, a, _ = open_course
    p = _registration(o, a)
    del p["person_id"]
    assert _apply_event("course-registration.confirmed", org.id, p) == roster.REJECTED_MALFORMED_PAYLOAD
    assert records(org.id, action="roster_entry.confirmed") == []
