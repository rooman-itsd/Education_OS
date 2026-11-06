"""Cross-tenant leak test (module standard rule 11, FR-19): one organisation never sees or changes another's rows, and
consumed events land only in their own organisation."""

from conftest import BASE, Course, deliver, registration_confirmed
from eos_lms.application import consumers as cons
from eos_testing import assert_no_cross_tenant_leak


def seed(client, org) -> tuple[Course, dict]:
    c = Course(client, org)
    m = c.material()
    x = c.assignment()
    sub = c.post(f"/assignments/{x['id']}/submissions", {"text": "mine"}, 201, c.student)
    qz = c.quiz()
    attempt = c.post(f"/quizzes/{qz['id']}/attempts", None, 201, c.student)
    t = c.post(f"/course-spaces/{c.space['id']}/threads", {"title": "Hi", "body": "?"}, 201, c.student)
    p = c.post(f"/threads/{t['id']}/posts", {"body": "Hello"}, 201, c.teacher)
    unit = c.post(f"/course-spaces/{c.space['id']}/units", {"title": "W1", "published": True}, 201, c.teacher)
    c.put(
        "/grades",
        {"item_type": "assignment", "item_id": x["id"], "entries": [{"student_id": c.student_id, "points": 5}]},
        c.teacher,
    )
    c.post("/grades/release", {"item_type": "assignment", "item_id": x["id"]}, headers=c.teacher)
    c.post(f"/assignments/{x['id']}/submissions", {"text": "waiting"}, 201, c.student2)  # keeps the queue non-empty
    ids = {"material": m["id"], "assignment": x["id"], "submission": sub["id"], "quiz": qz["id"]}
    ids |= {"attempt": attempt["id"], "thread": t["id"], "post": p["id"], "unit": unit["id"]}
    return c, ids


def token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def test_no_cross_tenant_leak(client, org, other_org):
    a, a_ids = seed(client, org)
    b, b_ids = seed(client, other_org)
    lists = [
        ("/course-spaces", a.admin, b.admin),
        ("/course-spaces", a.student, b.student),
        ("/me/course-materials", a.student, b.student),
        ("/me/grading-queue", a.teacher, b.teacher),
        ("/me/submissions", a.student, b.student),
        ("/me/quiz-attempts", a.student, b.student),
        ("/me/grades", a.student, b.student),
        ("/reports/coursework-activity", a.admin, b.admin),
    ]
    for path, ha, hb in lists:
        r = client.get(f"{BASE}{path}", headers=ha)
        assert r.status_code == 200 and r.json()["items"], path  # A sees its own rows
        if path in ("/me/course-materials", "/me/grading-queue", "/reports/coursework-activity", "/me/grades"):
            # rows without organisation_id: compare their ids instead
            ra, rb = r.json()["items"], client.get(f"{BASE}{path}", headers=hb).json()["items"]
            key = next(k for k in ("material_id", "item_id", "course_space_id") if k in ra[0])
            assert not {x[key] for x in ra} & {x[key] for x in rb}, path
        else:
            assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(ha), token(hb))


def test_another_organisations_records_are_not_found(client, org, other_org):
    a, ids = seed(client, org)
    b, _ = seed(client, other_org)
    space = a.space["id"]
    gets = [
        f"/course-spaces/{space}",
        f"/course-spaces/{space}/units",
        f"/course-spaces/{space}/materials",
        f"/course-spaces/{space}/assignments",
        f"/course-spaces/{space}/quizzes",
        f"/course-spaces/{space}/threads",
        f"/course-spaces/{space}/gradebook",
        f"/materials/{ids['material']}",
        f"/assignments/{ids['assignment']}",
        f"/assignments/{ids['assignment']}/submissions",
        f"/quizzes/{ids['quiz']}",
        f"/quizzes/{ids['quiz']}/attempts",
        f"/threads/{ids['thread']}",
    ]
    for path in gets:
        assert client.get(f"{BASE}{path}", headers=b.admin).status_code == 404, path
    writes = [
        ("PATCH", f"/course-spaces/{space}", {"title": "x"}, b.admin),
        ("POST", f"/course-spaces/{space}/status", {"status": "archived"}, b.admin),
        ("POST", f"/course-spaces/{space}/units", {"title": "x"}, b.admin),
        ("PATCH", f"/units/{ids['unit']}", {"title": "x"}, b.admin),
        ("POST", f"/course-spaces/{space}/materials", {"material_type": "page", "title": "x", "body": "b"}, b.admin),
        ("PATCH", f"/materials/{ids['material']}", {"title": "x"}, b.admin),
        ("POST", f"/materials/{ids['material']}/status", {"status": "unpublished"}, b.admin),
        ("PATCH", f"/assignments/{ids['assignment']}", {"title": "x"}, b.admin),
        ("POST", f"/assignments/{ids['assignment']}/status", {"status": "closed"}, b.admin),
        ("POST", f"/assignments/{ids['assignment']}/submissions", {"text": "x"}, b.student),
        ("PATCH", f"/quizzes/{ids['quiz']}", {"title": "x"}, b.admin),
        ("POST", f"/quizzes/{ids['quiz']}/status", {"status": "closed"}, b.admin),
        ("POST", f"/quizzes/{ids['quiz']}/attempts", None, b.student),
        ("PUT", f"/attempts/{ids['attempt']}/answers", {"answers": []}, b.student),
        ("POST", f"/attempts/{ids['attempt']}/submit", None, b.student),
        (
            "PATCH",
            f"/attempts/{ids['attempt']}/scores",
            {"scores": [{"question_id": ids["quiz"], "points": 1}]},
            b.admin,
        ),
        (
            "PUT",
            "/grades",
            {
                "item_type": "assignment",
                "item_id": ids["assignment"],
                "entries": [{"student_id": a.student_id, "points": 1}],
            },
            b.admin,
        ),
        ("POST", "/grades/release", {"item_type": "assignment", "item_id": ids["assignment"]}, b.admin),
        ("POST", f"/course-spaces/{space}/threads", {"title": "x", "body": "y"}, b.admin),
        ("POST", f"/threads/{ids['thread']}/posts", {"body": "x"}, b.admin),
        ("POST", f"/threads/{ids['thread']}/moderation", {"action": "lock"}, b.admin),
        ("POST", f"/posts/{ids['post']}/moderation", {"action": "hide"}, b.admin),
    ]
    for method, path, body, headers in writes:
        r = client.request(method, f"{BASE}{path}", json=body, headers=headers)
        assert r.status_code == 404, (method, path, r.status_code)
    # B cannot create a space for A's offering, which B's read model does not know.
    r = client.post(f"{BASE}/course-spaces", json={"course_offering_id": a.offering, "title": "x"}, headers=b.admin)
    assert r.status_code == 422
    # Nothing of A's changed.
    assert a.get(f"/course-spaces/{space}", a.teacher)["title"] == "Programming"


def test_a_registration_event_in_one_organisation_grants_nothing_in_another(client, org, other_org):
    a = Course(client, org)
    a.material()
    b_person, b_headers = other_org.user("student")
    # The same offering id and person id, but delivered for the other organisation.
    deliver(other_org.id, cons.REGISTRATION_CONFIRMED, registration_confirmed(a.offering, b_person, a.section_a))
    assert client.get(f"{BASE}/me/course-materials", headers=b_headers).json()["items"] == []
    assert client.get(f"{BASE}/course-spaces/{a.space['id']}", headers=b_headers).status_code == 404
