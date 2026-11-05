"""Hostile input answers 400, 404, 409 or 422, never a 500: every body field of every operation is sent values past
its column, its calendar or its type, and every list parameter is pushed past its bounds."""

import json

import pytest
from conftest import BASE, Course
from eos_lms.infrastructure.models import new_id
from test_contract import CONTRACT, OPERATIONS, resolve

ALLOWED = {200, 201, 400, 403, 404, 409, 422}
HOSTILE = [
    2**63,
    -(2**63),
    1e308,
    "x" * 200_001,
    "",
    [],
    {},
    None,
    True,
    "0001-01-01T00:00:00+01:00",
    "9999-12-31T23:59:59-05:00",
    ["not-a-uuid"],
    [2**63],
]


def fill(path: str, ids: dict) -> str:
    for name, value in ids.items():
        path = path.replace("{" + name + "}", value)
    return path


@pytest.fixture
def seeded(client, org):
    c = Course(client, org)
    m = c.material()
    unit = c.post(f"/course-spaces/{c.space['id']}/units", {"title": "W"}, 201, c.teacher)
    x = c.assignment()
    qz = c.quiz()
    attempt = c.post(f"/quizzes/{qz['id']}/attempts", None, 201, c.student)
    t = c.post(f"/course-spaces/{c.space['id']}/threads", {"title": "t", "body": "b"}, 201, c.student)
    p = c.post(f"/threads/{t['id']}/posts", {"body": "p"}, 201, c.student)
    ids = {
        "course_space_id": c.space["id"],
        "unit_id": unit["id"],
        "material_id": m["id"],
        "assignment_id": x["id"],
        "quiz_id": qz["id"],
        "attempt_id": attempt["id"],
        "thread_id": t["id"],
        "post_id": p["id"],
    }
    return c, ids


def request_properties(op: dict) -> dict:
    body = op.get("requestBody")
    if not body:
        return {}
    return resolve(body["content"]["application/json"]["schema"]).get("properties", {})


def test_no_body_field_value_causes_a_server_error(seeded):
    c, ids = seeded
    for operation_id, (method, path) in OPERATIONS.items():
        if method == "get":
            continue
        op = CONTRACT["paths"][path][method]
        url = fill(path, ids)
        headers = c.student if op["x-permission"].endswith(("-own", "submit-own", "attempt-own")) else c.admin
        for raw in ("null", "[]", '"x"', "1", "{", '{"a": NaN}'):
            r = c.client.request(
                method.upper(), f"{BASE}{url}", content=raw, headers={**headers, "Content-Type": "application/json"}
            )
            assert r.status_code in ALLOWED, (operation_id, raw, r.status_code)
        for name in request_properties(op):
            for value in HOSTILE + [float("nan"), float("inf")]:
                content = json.dumps({name: value})
                r = c.client.request(
                    method.upper(),
                    f"{BASE}{url}",
                    content=content,
                    headers={**headers, "Content-Type": "application/json"},
                )
                assert r.status_code in ALLOWED, (operation_id, name, repr(value)[:40], r.status_code, r.text[:200])


def test_no_query_parameter_causes_a_server_error(seeded):
    c, ids = seeded
    values = ["0", "-1", "201", "1000001", "99999999999999999999", "1e3", "٣", "%00", "x" * 5000, "true", "nope"]
    for operation_id, (method, path) in OPERATIONS.items():
        if method != "get":
            continue
        op = CONTRACT["paths"][path][method]
        names = [p.get("name") or p["$ref"].rsplit("/", 1)[1].lower() for p in op.get("parameters", [])]
        for name in names:
            for value in values:
                r = c.client.get(f"{BASE}{fill(path, ids)}", params={name: value}, headers=c.admin)
                assert r.status_code in ALLOWED, (operation_id, name, value, r.status_code)


def test_limits_and_offsets_are_bounded(seeded):
    c, _ = seeded
    for query in ("limit=0", "limit=201", "offset=-1", "offset=1000001", "offset=99999999999999999999", "limit=٣"):
        r = c.call("GET", f"/course-spaces?{query}")
        assert r.status_code == 400 and r.json()["detail"]["code"] == "invalid_parameter", query
    assert c.get("/course-spaces?limit=200&offset=1000000")["items"] == []


def test_malformed_path_ids_are_not_found(seeded):
    c, _ = seeded
    for bad in ("x", "1", "' or 1=1 --", new_id().upper() + "0", "%20"):
        assert c.call("GET", f"/course-spaces/{bad}").status_code == 404, bad
        assert c.call("GET", f"/quizzes/{bad}").status_code == 404, bad
        assert c.call("PUT", f"/attempts/{bad}/answers", {"answers": []}, c.student).status_code == 404, bad


def test_strings_are_bounded(seeded):
    c, ids = seeded
    space = ids["course_space_id"]
    assert c.call("PATCH", f"/course-spaces/{space}", {"title": "x" * 201}).status_code == 400
    assert c.call("PATCH", f"/course-spaces/{space}", {"title": "x" * 200}).status_code == 200
    long_url = "https://example.org/" + "a" * 2000
    body = {"material_type": "link", "title": "x", "url": long_url}
    assert c.call("POST", f"/course-spaces/{space}/materials", body, c.teacher).status_code == 400
    sections = [new_id() for _ in range(201)]
    assert c.call("PATCH", f"/course-spaces/{space}", {"visible_section_ids": sections}).status_code == 400


def test_duplicates_that_slip_past_the_check_are_a_conflict(seeded, monkeypatch):
    """Two requests at once both pass the lookup; the unique constraint catches the second one."""
    from eos_lms.infrastructure import repository

    c, _ = seeded
    monkeypatch.setattr(repository, "space_by_offering", lambda db, offering_id: None)
    r = c.call("POST", "/course-spaces", {"course_offering_id": c.offering, "title": "Again"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "course_space_exists"
    # The organisation is still usable after the refused write.
    assert c.get(f"/course-spaces/{c.space['id']}")["id"] == c.space["id"]


def valid_bodies(c, ids: dict) -> dict[str, tuple[dict, dict]]:
    """A valid body per write operation, and who sends it. Each field is then replaced, one at a time."""
    question = {"question_type": "single_choice", "prompt": "p", "options": ["a", "b"], "answer_key": [0], "points": 1}
    attempt_question = c.get(f"/quizzes/{ids['quiz_id']}", c.teacher)["questions"][0]["id"]
    return {
        "createCourseSpace": ({"course_offering_id": c.offering, "title": "t", "description": "d"}, c.admin),
        "updateCourseSpace": ({"title": "t", "description": "d", "visible_section_ids": []}, c.teacher),
        "changeCourseSpaceStatus": ({"status": "active"}, c.teacher),
        "createContentUnit": ({"title": "t", "position": 0, "published": True}, c.teacher),
        "updateContentUnit": ({"title": "t", "position": 1, "published": False}, c.teacher),
        "createCourseMaterial": (
            {"material_type": "page", "title": "t", "body": "b", "unit_id": ids["unit_id"], "visible_section_ids": []},
            c.teacher,
        ),
        "updateCourseMaterial": (
            {"title": "t", "body": "b", "unit_id": None, "scheduled_class_id": new_id()},
            c.teacher,
        ),
        "changeCourseMaterialStatus": ({"status": "unpublished"}, c.teacher),
        "createAssignment": (
            {
                "title": "t",
                "due_at": "2026-12-01T00:00:00+00:00",
                "max_points": 5,
                "submission_type": "text",
                "max_attempts": 2,
                "late_policy": {"accept_late": True, "late_cutoff_at": "2026-12-02T00:00:00+00:00"},
                "target_section_ids": [],
            },
            c.teacher,
        ),
        "updateAssignment": ({"title": "t", "due_at": "2026-12-01T00:00:00+00:00", "max_points": 12}, c.teacher),
        "changeAssignmentStatus": ({"status": "published"}, c.teacher),
        "submitAssignment": ({"text": "x", "document_ids": []}, c.student),
        "createQuiz": (
            {
                "title": "t",
                "opens_at": "2026-11-05T00:00:00Z",
                "closes_at": "2026-11-06T00:00:00Z",
                "questions": [question],
            },
            c.teacher,
        ),
        "updateQuiz": ({"title": "t", "attempts_allowed": 3, "time_limit_minutes": 20}, c.teacher),
        "changeQuizStatus": ({"status": "published"}, c.teacher),
        "saveQuizAnswers": ({"answers": [{"question_id": attempt_question, "selected_options": [1]}]}, c.student),
        "scoreQuizAttempt": ({"scores": [{"question_id": attempt_question, "points": 1}]}, c.teacher),
        "enterGrades": (
            {
                "item_type": "assignment",
                "item_id": ids["assignment_id"],
                "entries": [{"student_id": c.student_id, "points": 1}],
            },
            c.teacher,
        ),
        "releaseGrades": (
            {"item_type": "assignment", "item_id": ids["assignment_id"], "student_ids": [c.student_id]},
            c.teacher,
        ),
        "createThread": ({"title": "t", "body": "b"}, c.student),
        "createPost": ({"body": "b"}, c.student),
        "moderateThread": ({"action": "lock", "reason": "r"}, c.teacher),
        "moderatePost": ({"action": "hide", "reason": "r"}, c.teacher),
    }


def test_no_single_bad_field_in_a_valid_body_causes_a_server_error(seeded):
    c, ids = seeded
    bodies = valid_bodies(c, ids)
    for operation_id, (body, headers) in bodies.items():
        method, path = OPERATIONS[operation_id]
        url = f"{BASE}{fill(path, ids)}"
        assert c.client.request(method.upper(), url, json=body, headers=headers).status_code in ALLOWED, operation_id
        for name in body:
            for value in HOSTILE:
                r = c.client.request(
                    method.upper(),
                    url,
                    content=json.dumps({**body, name: value}),
                    headers={**headers, "Content-Type": "application/json"},
                )
                assert r.status_code in ALLOWED, (operation_id, name, repr(value)[:40], r.status_code, r.text[:200])
