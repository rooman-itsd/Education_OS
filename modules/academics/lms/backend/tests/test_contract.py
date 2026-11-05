"""The API against contracts/openapi.yaml and contracts/permissions.yaml: every operation is served at its path with its
x-permission, every key is in the catalogue, every success body has the fields, types and enums the contract declares
(no more, no fewer), every error body is an ErrorResponse with a status the contract declares, and the enums the
code uses are the contract's."""

import uuid
from pathlib import Path

import yaml
from conftest import BASE, NOW, Course, at, set_clock
from eos_lms.api.router import router
from eos_lms.application import access
from eos_lms.domain import rules

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = yaml.safe_load((ROOT / "contracts" / "openapi.yaml").read_text(encoding="utf-8"))
CATALOGUE = yaml.safe_load((ROOT / "contracts" / "permissions.yaml").read_text(encoding="utf-8"))
SCHEMAS = CONTRACT["components"]["schemas"]
JSON = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}
OPERATIONS = {
    op["operationId"]: (method, path)
    for path, item in CONTRACT["paths"].items()
    for method, op in item.items()
    if method in ("get", "post", "put", "patch", "delete")
}

# Statuses the API answers that the contract does not declare for the operation (listed in the PR for the owner):
# - 400 for a malformed body or query parameter on operations that declare no 400;
# - 409 when the course space is archived (read-only) on unit operations, which declare no 409.
UNDECLARED = {
    ("changeCourseSpaceStatus", 400),
    ("changeCourseMaterialStatus", 400),
    ("changeAssignmentStatus", 400),
    ("changeQuizStatus", 400),
    ("releaseGrades", 400),
    ("moderateThread", 400),
    ("moderatePost", 400),
    ("listCourseSpaces", 400),
    ("createContentUnit", 409),
    ("updateContentUnit", 409),
    ("scoreQuizAttempt", 409),
}


def resolve(schema: dict) -> dict:
    """The schema with $ref followed and allOf merged."""
    if "$ref" in schema:
        return resolve(SCHEMAS[schema["$ref"].rsplit("/", 1)[1]])
    if "allOf" in schema:
        merged: dict = {"properties": {}, "required": []}
        for part in schema["allOf"]:
            part = resolve(part)
            merged["properties"].update(part.get("properties", {}))
            merged["required"] += part.get("required", [])
            merged.update({key: v for key, v in part.items() if key not in ("properties", "required")})
        return merged
    return schema


def check(value, schema: dict, where: str = "$") -> None:
    schema = resolve(schema)
    if "oneOf" in schema:
        errors = []
        for option in schema["oneOf"]:
            try:
                check(value, option, where)
                return
            except AssertionError as e:
                errors.append(str(e))
        raise AssertionError(f"{where}: {value!r} matches none of oneOf: {errors}")
    types = schema.get("type")
    if types:
        allowed = types if isinstance(types, list) else [types]
        good = any(isinstance(value, JSON[t]) for t in allowed)
        if isinstance(value, bool) and "boolean" not in allowed:
            good = False
        assert good, f"{where}: {value!r} is not {allowed}"
    if "enum" in schema:
        assert value in schema["enum"], f"{where}: {value!r} not in {schema['enum']}"
    if schema.get("format") == "uuid" and isinstance(value, str):
        uuid.UUID(value)
    if isinstance(value, dict) and "properties" in schema:
        missing = set(schema.get("required", [])) - set(value)
        assert not missing, f"{where}: missing {missing}"
        extra = set(value) - set(schema["properties"])
        assert not extra, f"{where}: not in the contract: {extra}"
        for key, item in value.items():
            check(item, schema["properties"][key], f"{where}.{key}")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            check(item, schema["items"], f"{where}[{i}]")


def operation(operation_id: str) -> dict:
    method, path = OPERATIONS[operation_id]
    return CONTRACT["paths"][path][method]


def body_schema(operation_id: str, status: int) -> dict:
    return operation(operation_id)["responses"][str(status)]["content"]["application/json"]["schema"]


# ---------------------------------------------------------------- routes and permissions


def test_every_operation_is_served_at_its_path_with_its_x_permission():
    routes = {}
    for route in router.routes:
        for method in route.methods:
            keys = set()
            for dep in route.dependant.dependencies:
                keys |= set(getattr(dep.call, "permissions", ()))
            routes[(method.lower(), route.path)] = keys
    assert set(routes) == set(OPERATIONS.values())
    for operation_id, (method, path) in OPERATIONS.items():
        assert routes[(method, path)] == {operation(operation_id)["x-permission"]}, operation_id


def test_permission_keys_are_the_catalogues():
    declared = {p["key"] for p in CATALOGUE["permissions"]}
    assert set(access.PERMISSION_KEYS) == declared
    assert {
        op["x-permission"] for item in CONTRACT["paths"].values() for op in item.values() if "x-permission" in op
    } <= (declared)
    for role in CATALOGUE["roles"]:
        assert set(role["grants"]) <= declared, role["name"]
    assert set(access.MANAGE_ALL) | set(access.MANAGE_ALL.values()) <= declared


def test_the_servers_prefix_is_the_one_the_tests_mount():
    assert BASE == CONTRACT["servers"][0]["url"]


def test_enums_are_the_contracts():
    pairs = {
        "CourseSpaceStatus": rules.COURSE_SPACE_STATUSES,
        "MaterialType": rules.MATERIAL_TYPES,
        "MaterialStatus": rules.MATERIAL_STATUSES,
        "WorkStatus": rules.WORK_STATUSES,
        "SubmissionType": rules.SUBMISSION_TYPES,
        "SubmissionStatus": rules.SUBMISSION_STATUSES,
        "QuestionType": rules.QUESTION_TYPES,
        "AttemptStatus": rules.ATTEMPT_STATUSES,
        "ManualGradingState": rules.MANUAL_GRADING_STATES,
        "ItemType": rules.ITEM_TYPES,
        "GradeStatus": rules.GRADE_STATUSES,
        "ThreadState": rules.THREAD_STATES,
        "PostState": rules.POST_STATES,
    }
    for name, values in pairs.items():
        assert tuple(SCHEMAS[name]["enum"]) == values, name
    assert tuple(SCHEMAS["GradebookCell"]["properties"]["status"]["enum"]) == rules.GRADEBOOK_CELL_STATUSES
    assert tuple(SCHEMAS["QuizSettings"]["properties"]["attempt_scoring"]["enum"]) == rules.ATTEMPT_SCORING
    moderation = CONTRACT["paths"]["/threads/{thread_id}/moderation"]["post"]["requestBody"]
    assert tuple(moderation["content"]["application/json"]["schema"]["properties"]["action"]["enum"]) == (
        rules.THREAD_ACTIONS
    )
    status = CONTRACT["paths"]["/course-spaces/{course_space_id}/status"]["post"]["requestBody"]
    assert set(status["content"]["application/json"]["schema"]["properties"]["status"]["enum"]) == set(
        rules.COURSE_SPACE_TRANSITIONS
    )


# ---------------------------------------------------------------- success bodies


def journey(client, org, monkeypatch) -> dict[str, list]:
    """Every operation once, as the roles that use it. operationId -> [(status, body), ...]."""
    seen: dict[str, list] = {}

    def record(operation_id, response, status):
        assert response.status_code == status, (operation_id, response.status_code, response.text)
        seen.setdefault(operation_id, []).append((status, response.json()))
        return response.json()

    c = Course(client, org)
    space = c.space["id"]
    record("listCourseSpaces", c.call("GET", "/course-spaces", headers=c.student), 200)
    record("getCourseSpace", c.call("GET", f"/course-spaces/{space}", headers=c.teacher), 200)
    record("updateCourseSpace", c.call("PATCH", f"/course-spaces/{space}", {"description": None}, c.teacher), 200)
    unit = record("createContentUnit", c.call("POST", f"/course-spaces/{space}/units", {"title": "W1"}, c.teacher), 201)
    record("updateContentUnit", c.call("PATCH", f"/units/{unit['id']}", {"published": True}, c.teacher), 200)
    record("listContentUnits", c.call("GET", f"/course-spaces/{space}/units", headers=c.student), 200)
    doc = {"material_type": "document", "title": "Slides", "document_id": str(uuid.uuid4()), "unit_id": unit["id"]}
    m = record("createCourseMaterial", c.call("POST", f"/course-spaces/{space}/materials", doc, c.teacher), 201)
    record("updateCourseMaterial", c.call("PATCH", f"/materials/{m['id']}", {"title": "Slides 1"}, c.teacher), 200)
    record(
        "changeCourseMaterialStatus",
        c.call("POST", f"/materials/{m['id']}/status", {"status": "published"}, c.teacher),
        200,
    )
    record("getCourseMaterial", c.call("GET", f"/materials/{m['id']}", headers=c.student), 200)
    record("listCourseMaterials", c.call("GET", f"/course-spaces/{space}/materials", headers=c.student), 200)
    record("getMyCourseMaterials", c.call("GET", "/me/course-materials", headers=c.student), 200)

    body = {
        "title": "Essay",
        "instructions": "Write",
        "due_at": at(days=7),
        "max_points": 10,
        "submission_type": "file_and_text",
        "late_policy": {"accept_late": True, "late_cutoff_at": at(days=9)},
        "unit_id": unit["id"],
    }
    x = record("createAssignment", c.call("POST", f"/course-spaces/{space}/assignments", body, c.teacher), 201)
    record("updateAssignment", c.call("PATCH", f"/assignments/{x['id']}", {"max_attempts": 2}, c.teacher), 200)
    record(
        "changeAssignmentStatus",
        c.call("POST", f"/assignments/{x['id']}/status", {"status": "published"}, c.teacher),
        200,
    )
    record("getAssignment", c.call("GET", f"/assignments/{x['id']}", headers=c.student), 200)
    record("listAssignments", c.call("GET", f"/course-spaces/{space}/assignments", headers=c.student), 200)
    sub = {"document_ids": [str(uuid.uuid4())], "text": "Mine"}
    record("submitAssignment", c.call("POST", f"/assignments/{x['id']}/submissions", sub, c.student), 201)
    record("listSubmissions", c.call("GET", f"/assignments/{x['id']}/submissions", headers=c.teacher), 200)
    record("listMySubmissions", c.call("GET", "/me/submissions", headers=c.student), 200)
    record("getMyGradingQueue", c.call("GET", "/me/grading-queue", headers=c.teacher), 200)

    questions = [
        {
            "question_type": "multiple_choice",
            "prompt": "Primes",
            "options": ["2", "4", "5"],
            "answer_key": [0, 2],
            "points": 2,
        },
        {"question_type": "short_answer", "prompt": "Capital of India", "answer_key": ["New Delhi"], "points": 1},
        {"question_type": "essay", "prompt": "Discuss", "points": 3},
    ]
    qbody = {
        "title": "Q",
        "opens_at": at(hours=-1),
        "closes_at": at(days=1),
        "time_limit_minutes": 30,
        "questions": questions,
    }
    qz = record("createQuiz", c.call("POST", f"/course-spaces/{space}/quizzes", qbody, c.teacher), 201)
    record("updateQuiz", c.call("PATCH", f"/quizzes/{qz['id']}", {"auto_release": True}, c.teacher), 200)
    record("changeQuizStatus", c.call("POST", f"/quizzes/{qz['id']}/status", {"status": "published"}, c.teacher), 200)
    record("getQuiz", c.call("GET", f"/quizzes/{qz['id']}", headers=c.student), 200)
    record("getQuiz", c.call("GET", f"/quizzes/{qz['id']}", headers=c.teacher), 200)
    record("listQuizzes", c.call("GET", f"/course-spaces/{space}/quizzes", headers=c.student), 200)
    t = record("startQuizAttempt", c.call("POST", f"/quizzes/{qz['id']}/attempts", None, c.student), 201)
    ids = [q["id"] for q in t["questions"]]
    answers = [
        {"question_id": ids[0], "selected_options": [0, 2]},
        {"question_id": ids[1], "text_answer": "new delhi"},
        {"question_id": ids[2], "text_answer": "Because"},
    ]
    record("saveQuizAnswers", c.call("PUT", f"/attempts/{t['id']}/answers", {"answers": answers}, c.student), 200)
    record("submitQuizAttempt", c.call("POST", f"/attempts/{t['id']}/submit", None, c.student), 200)
    record("listQuizAttempts", c.call("GET", f"/quizzes/{qz['id']}/attempts", headers=c.teacher), 200)
    scores = {"scores": [{"question_id": ids[2], "points": 2, "comment": "Good"}]}
    record("scoreQuizAttempt", c.call("PATCH", f"/attempts/{t['id']}/scores", scores, c.teacher), 200)
    record("listMyQuizAttempts", c.call("GET", "/me/quiz-attempts", headers=c.student), 200)

    entries = {"item_type": "assignment", "item_id": x["id"], "entries": [{"student_id": c.student_id, "points": 8}]}
    record("enterGrades", c.call("PUT", "/grades", entries, c.teacher), 200)
    release = {"item_type": "assignment", "item_id": x["id"]}
    record("releaseGrades", c.call("POST", "/grades/release", release, c.teacher), 200)
    again = {
        **entries,
        "entries": [{"student_id": c.student_id, "points": 9, "feedback": "Better", "reason": "Recount"}],
    }
    record("enterGrades", c.call("PUT", "/grades", again, c.teacher), 200)
    record("getGradebook", c.call("GET", f"/course-spaces/{space}/gradebook", headers=c.teacher), 200)
    record("listMyGrades", c.call("GET", "/me/grades", headers=c.student), 200)

    th = record(
        "createThread", c.call("POST", f"/course-spaces/{space}/threads", {"title": "Hi", "body": "?"}, c.student), 201
    )
    p = record("createPost", c.call("POST", f"/threads/{th['id']}/posts", {"body": "Hello"}, c.teacher), 201)
    record("moderatePost", c.call("POST", f"/posts/{p['id']}/moderation", {"action": "hide"}, c.teacher), 200)
    record("moderateThread", c.call("POST", f"/threads/{th['id']}/moderation", {"action": "lock"}, c.teacher), 200)
    record("listThreads", c.call("GET", f"/course-spaces/{space}/threads", headers=c.student), 200)
    record("getThread", c.call("GET", f"/threads/{th['id']}", headers=c.teacher), 200)
    record("getCourseworkActivityReport", c.call("GET", "/reports/coursework-activity", headers=c.viewer), 200)
    record(
        "getCourseworkActivityReport",
        c.call("GET", f"/reports/coursework-activity?department_id={c.department}", headers=c.admin),
        200,
    )

    record(
        "changeAssignmentStatus", c.call("POST", f"/assignments/{x['id']}/status", {"status": "closed"}, c.teacher), 200
    )
    record("changeQuizStatus", c.call("POST", f"/quizzes/{qz['id']}/status", {"status": "closed"}, c.teacher), 200)
    record(
        "changeCourseMaterialStatus",
        c.call("POST", f"/materials/{m['id']}/status", {"status": "unpublished"}, c.teacher),
        200,
    )

    other = Course(client, org)
    created = other.space
    seen.setdefault("createCourseSpace", []).append((201, created))
    record(
        "changeCourseSpaceStatus",
        other.call("POST", f"/course-spaces/{created['id']}/status", {"status": "archived"}),
        200,
    )
    set_clock(monkeypatch, NOW)
    return seen


def test_every_success_body_matches_the_contract(client, org, monkeypatch):
    seen = journey(client, org, monkeypatch)
    assert set(seen) == set(OPERATIONS), set(OPERATIONS) - set(seen)
    for operation_id, responses in seen.items():
        for status, body in responses:
            check(body, body_schema(operation_id, status), operation_id)


def test_students_never_receive_an_answer_key(client, org, monkeypatch):
    seen = journey(client, org, monkeypatch)
    for operation_id in ("getQuiz", "startQuizAttempt", "listQuizzes"):
        for _, body in seen[operation_id][:1]:
            assert "answer_key" not in repr(body), operation_id
    teacher_view = seen["getQuiz"][1][1]
    assert all("answer_key" in q for q in teacher_view["questions"] if q["question_type"] != "essay")


# ---------------------------------------------------------------- error bodies


def test_error_bodies_are_error_responses_with_declared_statuses(client, org):
    c = Course(client, org)
    space, missing = c.space["id"], str(uuid.uuid4())
    x = c.assignment()
    qz = c.quiz()
    calls = {
        "createCourseSpace": [
            (400, c.call("POST", "/course-spaces", {"title": "x"})),
            (409, c.call("POST", "/course-spaces", {"course_offering_id": c.offering, "title": "Again"})),
            (422, c.call("POST", "/course-spaces", {"course_offering_id": missing, "title": "x"})),
        ],
        "getCourseSpace": [(404, c.call("GET", f"/course-spaces/{missing}"))],
        "updateCourseSpace": [(400, c.call("PATCH", f"/course-spaces/{space}", {"title": ""}))],
        "changeCourseSpaceStatus": [(409, c.call("POST", f"/course-spaces/{space}/status", {"status": "active"}))],
        "createCourseMaterial": [
            (400, c.call("POST", f"/course-spaces/{space}/materials", {"material_type": "link", "title": "x"})),
            (
                422,
                c.call(
                    "POST",
                    f"/course-spaces/{space}/materials",
                    {"material_type": "page", "title": "x", "body": "b", "unit_id": missing},
                ),
            ),
        ],
        "getCourseMaterial": [(404, c.call("GET", f"/materials/{missing}"))],
        "createAssignment": [(400, c.call("POST", f"/course-spaces/{space}/assignments", {"title": "x"}))],
        "submitAssignment": [
            (403, c.call("POST", f"/assignments/{x['id']}/submissions", {"text": "x"}, c.teacher)),
            (400, c.call("POST", f"/assignments/{x['id']}/submissions", {"document_ids": [missing]}, c.student)),
        ],
        "startQuizAttempt": [(404, c.call("POST", f"/quizzes/{missing}/attempts", None, c.student))],
        "updateQuiz": [(409, c.call("PATCH", f"/quizzes/{qz['id']}", {"questions": [qz_question()]}, c.teacher))],
        "enterGrades": [
            (
                422,
                c.call(
                    "PUT",
                    "/grades",
                    {"item_type": "assignment", "item_id": x["id"], "entries": [{"student_id": missing, "points": 1}]},
                    c.teacher,
                ),
            ),
            (
                404,
                c.call(
                    "PUT",
                    "/grades",
                    {"item_type": "quiz", "item_id": missing, "entries": [{"student_id": missing, "points": 1}]},
                    c.teacher,
                ),
            ),
        ],
        "getGradebook": [(403, c.call("GET", f"/course-spaces/{space}/gradebook", headers=c.student_b))],
        "createThread": [(400, c.call("POST", f"/course-spaces/{space}/threads", {"title": "x"}, c.student))],
        "getCourseworkActivityReport": [(403, c.call("GET", "/reports/coursework-activity", headers=c.student))],
    }
    error = SCHEMAS["ErrorResponse"]
    for operation_id, results in calls.items():
        for status, response in results:
            assert response.status_code == status, (operation_id, response.text)
            assert str(status) in operation(operation_id)["responses"] or status == 403, operation_id
            check(response.json()["detail"], error, operation_id)


def qz_question() -> dict:
    return {"question_type": "true_false", "prompt": "x", "answer_key": True, "points": 1}


def test_undeclared_statuses_are_only_the_listed_gaps():
    """Each entry is a status the API answers that the contract does not declare; this fails once the contract
    declares it, as a reminder to drop the entry."""
    for operation_id, status in UNDECLARED:
        assert str(status) not in operation(operation_id)["responses"], (operation_id, status)
