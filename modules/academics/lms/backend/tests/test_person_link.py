"""student-information.person.account-linked -> person_account, and a learner's own reads through it.

Registrations arrive keyed by the student-information person id; a learner signs in with their identity user id. lms
maps one to the other (common.learner_ids) and falls back to the user id while no link is known."""

from datetime import timedelta

import pytest
from conftest import NOW, STUDENT, Course, deliver, registration_confirmed
from eos_core.db import SessionLocal
from eos_lms.application import consumers as cons
from eos_lms.infrastructure.models import PersonAccount, new_id
from sqlalchemy import select


def link(org_id, person_id, user_id, *, linked=True, at=NOW, event_id=None) -> str:
    payload = {
        "person_id": person_id,
        "identity_user_id": user_id if linked else None,
        "linked": linked,
        "previous_identity_user_id": None if linked else user_id,
    }
    return deliver(org_id, cons.ACCOUNT_LINKED, payload, occurred_at=at, event_id=event_id)


def account(org_id, person_id) -> PersonAccount | None:
    with SessionLocal() as db:
        return db.scalars(
            select(PersonAccount).where(PersonAccount.organisation_id == org_id, PersonAccount.person_id == person_id)
        ).first()


def enrol_by_person(c: Course, section_id: str, name: str) -> tuple[str, str, dict]:
    """A student whose registration names their person id, which is not their sign-in user id."""
    person = new_id()
    user_id, headers = c.org.user(STUDENT)
    deliver(c.org.id, cons.REGISTRATION_CONFIRMED, registration_confirmed(c.offering, person, section_id, name=name))
    return person, user_id, headers


# ---------------------------------------------------------------- the consumer


def test_a_link_is_applied_once(org):
    person, user, event_id = new_id(), new_id(), new_id()
    assert link(org.id, person, user, event_id=event_id) == cons.APPLIED
    assert link(org.id, person, user, event_id=event_id) == cons.DUPLICATE
    assert link(org.id, person, user) == cons.APPLIED  # a republish: the same link again changes nothing
    row = account(org.id, person)
    assert (row.identity_user_id, row.organisation_id) == (user, org.id)


def test_an_older_link_never_replaces_a_newer_one(org):
    person, first, second = new_id(), new_id(), new_id()
    assert link(org.id, person, second, at=NOW) == cons.APPLIED
    assert link(org.id, person, first, at=NOW - timedelta(hours=1)) == cons.STALE
    assert link(org.id, person, second, linked=False, at=NOW - timedelta(minutes=1)) == cons.STALE
    assert account(org.id, person).identity_user_id == second
    assert link(org.id, person, second, linked=False, at=NOW + timedelta(minutes=1)) == cons.APPLIED
    assert account(org.id, person).identity_user_id is None


@pytest.mark.parametrize(
    "payload",
    [
        {"identity_user_id": "u", "linked": True},  # no person
        {"person_id": "p", "identity_user_id": "u", "linked": "yes"},
        {"person_id": "p", "identity_user_id": None, "linked": True},
        {"person_id": "p", "identity_user_id": "not-a-uuid", "linked": True},
    ],
)
def test_a_malformed_link_is_refused(org, payload):
    payload = {k: (new_id() if v == "p" else new_id() if v == "u" else v) for k, v in payload.items()}
    with pytest.raises(ValueError):
        deliver(org.id, cons.ACCOUNT_LINKED, payload)


def test_a_link_without_an_organisation_is_not_ours():
    payload = {"person_id": new_id(), "identity_user_id": new_id(), "linked": True}
    assert deliver(None, cons.ACCOUNT_LINKED, payload) == cons.IGNORED


# ---------------------------------------------------------------- a learner's own reads


def test_a_student_registered_by_person_id_sees_their_course_once_linked(course):
    c = course
    c.material(title="Week 1 notes")
    person, user_id, headers = enrol_by_person(c, c.section_a, "Deepa")
    assert c.get("/me/course-materials", headers)["items"] == []  # registration by person id, no link yet
    link(c.org.id, person, user_id)
    assert [i["title"] for i in c.get("/me/course-materials", headers)["items"]] == ["Week 1 notes"]
    assert [s["id"] for s in c.get("/course-spaces", headers)["items"]] == [c.space["id"]]


def test_linked_work_is_recorded_under_the_person_and_meets_the_registration(course):
    c = course
    x = c.assignment()
    qz = c.quiz()
    person, user_id, headers = enrol_by_person(c, c.section_a, "Deepa")
    link(c.org.id, person, user_id)
    sub = c.post(f"/assignments/{x['id']}/submissions", {"text": "mine"}, 201, headers)
    assert sub["student_id"] == person
    attempt = c.post(f"/quizzes/{qz['id']}/attempts", None, 201, headers)
    assert attempt["student_id"] == person
    assert c.post(f"/attempts/{attempt['id']}/submit", None, headers=headers)["status"] in ("submitted", "graded")
    assert [s["id"] for s in c.get("/me/submissions", headers)["items"]] == [sub["id"]]
    assert [t["id"] for t in c.get("/me/quiz-attempts", headers)["items"]] == [attempt["id"]]
    # The instructor's gradebook row for the registration carries the submission.
    book = c.get(f"/course-spaces/{c.space['id']}/gradebook", c.teacher)
    deepa = next(s for s in book["students"] if s["student_id"] == person)
    assert deepa["cells"][0]["status"] == "submitted"
    c.put(
        "/grades",
        {"item_type": "assignment", "item_id": x["id"], "entries": [{"student_id": person, "points": 7}]},
        c.teacher,
    )
    c.post("/grades/release", {"item_type": "assignment", "item_id": x["id"]}, headers=c.teacher)
    assert [g["points"] for g in c.get("/me/grades", headers)["items"][0]["grades"]] == [7]


def test_work_recorded_under_the_user_id_stays_the_learners_after_the_link(course):
    """A student registered by user id (dev data, or before the link) keeps their work when a link arrives later."""
    c = course
    x = c.assignment(max_attempts=2)
    first = c.post(f"/assignments/{x['id']}/submissions", {"text": "first"}, 201, c.student)
    person = new_id()
    link(c.org.id, person, c.student_id)
    assert [s["id"] for s in c.get("/me/submissions", c.student)["items"]] == [first["id"]]
    assert c.get("/me/course-materials", c.student)["items"] == []  # nothing published, but no 403 either
    second = c.post(f"/assignments/{x['id']}/submissions", {"text": "second"}, 201, c.student)
    assert second["attempt"] == 2 and second["student_id"] == person
    assert {s["id"] for s in c.get(f"/me/submissions?assignment_id={x['id']}", c.student)["items"]} >= {second["id"]}


def test_unlinking_ends_the_mapping(course):
    c = course
    c.material()
    person, user_id, headers = enrol_by_person(c, c.section_a, "Deepa")
    link(c.org.id, person, user_id)
    assert c.get("/me/course-materials", headers)["items"]
    link(c.org.id, person, user_id, linked=False, at=NOW + timedelta(minutes=1))
    assert c.get("/me/course-materials", headers)["items"] == []


def test_a_link_in_one_organisation_maps_nothing_in_another(client, org, other_org):
    a, b = Course(client, org), Course(client, other_org)
    a.material()
    b.material()
    person, user_id, headers = enrol_by_person(a, a.section_a, "Deepa")
    # The same account linked to the person in the other organisation only.
    link(other_org.id, person, user_id)
    assert account(org.id, person) is None
    assert a.get("/me/course-materials", headers)["items"] == []
    link(org.id, person, user_id)
    mine = {i["material_id"] for i in a.get("/me/course-materials", headers)["items"]}
    assert mine and mine <= {m["id"] for m in a.get(f"/course-spaces/{a.space['id']}/materials", a.teacher)["items"]}
