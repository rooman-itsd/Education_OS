"""The classes, attendance, report and /me operations against contracts/openapi.yaml: each route is the contract's
with its x-permission, every response body has exactly the declared fields, types and enums (oneOf included), and every
status the API answers is one the contract declares."""

import uuid

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BASE,
    CLASSES_AND_ATTENDANCE,
    EXAMS,
    HEAD,
    STUDENT,
    VIEWER,
    Classroom,
    active_term,
    ok,
)
from eos_timetable_attendance.api.router import router  # noqa: E402
from test_api_contract import CONTRACT, JSON, SCHEMAS, resolve  # noqa: E402


def validate(value, schema: dict, where: str = "$") -> None:
    """test_api_contract.check, plus oneOf (exactly one branch matches)."""
    schema = resolve(schema)
    if "oneOf" in schema:
        matched = 0
        for branch in schema["oneOf"]:
            try:
                validate(value, branch, where)
                matched += 1
            except AssertionError:
                pass
        assert matched == 1, f"{where}: {value!r} matches {matched} branches of oneOf"
        return
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
            validate(item, schema["properties"][key], f"{where}.{key}")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            validate(item, schema["items"], f"{where}[{i}]")


def operation(operation_id: str) -> dict:
    method, path = CLASSES_AND_ATTENDANCE[operation_id]
    return CONTRACT["paths"][path][method]


def expect(operation_id: str, response, status: int) -> dict:
    """The response has `status`, the contract declares it, and the body is the declared schema."""
    assert response.status_code == status, (operation_id, response.status_code, response.text)
    declared = operation(operation_id)["responses"]
    assert str(status) in declared, (operation_id, status)
    body = response.json()
    if status < 300:
        validate(body, declared[str(status)]["content"]["application/json"]["schema"], operation_id)
    else:
        validate(body["detail"], SCHEMAS["ErrorResponse"], operation_id)
    return body


def test_every_route_is_the_contracts_with_its_x_permission():
    routes = {}
    for route in router.routes:
        for method in route.methods:
            keys = set()
            for dep in route.dependant.dependencies:
                keys |= set(getattr(dep.call, "permissions", ()))
            routes[(method.lower(), route.path)] = keys
    for operation_id, (method, path) in CLASSES_AND_ATTENDANCE.items():
        op = CONTRACT["paths"][path][method]
        assert op["operationId"] == operation_id
        assert routes[(method, path)] == {op["x-permission"]}, operation_id
    served = {op["operationId"] for path in CONTRACT["paths"].values() for op in path.values() if isinstance(op, dict)}
    assert set(CLASSES_AND_ATTENDANCE) <= served


def test_class_and_attendance_bodies_match_the_contract(client, org):
    room = Classroom(client, org, students=2, department_id=(dept := str(uuid.uuid4())))
    active_term(org.id, room.ids["period"])
    a, b = room.students
    h, f = room.admin, room.faculty
    c = expect(
        "createScheduledClass",
        client.post(
            f"{BASE}/scheduled-classes",
            json={
                "course_offering_id": room.ids["offering"],
                "section_id": room.ids["section"],
                "instructor_assignment_id": room.ids["assignment"],
                "starts_at": "2026-11-03T09:00:00+00:00",
                "ends_at": "2026-11-03T10:00:00+00:00",
                "location_label": "R1",
            },
            headers=h,
        ),
        201,
    )
    cid = c["id"]
    expect("listScheduledClasses", client.get(f"{BASE}/scheduled-classes", headers=h), 200)
    expect("getScheduledClass", client.get(f"{BASE}/scheduled-classes/{cid}", headers=h), 200)
    expect(
        "updateScheduledClass",
        client.patch(f"{BASE}/scheduled-classes/{cid}", json={"location_label": None}, headers=h),
        200,
    )
    s = expect(
        "openAttendanceSession", client.post(f"{BASE}/scheduled-classes/{cid}/attendance-session", headers=f), 201
    )
    expect("openAttendanceSession", client.post(f"{BASE}/scheduled-classes/{cid}/attendance-session", headers=f), 200)
    sid = s["id"]
    expect(
        "getAttendanceSessionForClass", client.get(f"{BASE}/scheduled-classes/{cid}/attendance-session", headers=f), 200
    )
    expect("listAttendanceRecords", client.get(f"{BASE}/attendance-sessions/{sid}/records", headers=f), 200)
    marked = expect(
        "markAttendance",
        client.put(
            f"{BASE}/attendance-sessions/{sid}/records",
            json={"records": [{"student_id": a, "status": "absent", "remark": "no show"}]},
            headers=f,
        ),
        200,
    )
    expect("getMyAttendanceToMark", client.get(f"{BASE}/me/attendance-to-mark", headers=f), 200)
    expect("closeAttendanceSession", client.post(f"{BASE}/attendance-sessions/{sid}/close", headers=f), 200)
    expect("getAttendanceSession", client.get(f"{BASE}/attendance-sessions/{sid}", headers=f), 200)
    rid = next(r["id"] for r in marked["items"] if r["student_id"] == a)
    expect(
        "correctAttendanceRecord",
        client.patch(f"{BASE}/attendance-records/{rid}", json={"status": "present", "reason": "pass"}, headers=f),
        200,
    )
    expect("getAttendanceRecordHistory", client.get(f"{BASE}/attendance-records/{rid}/history", headers=f), 200)
    expect("getMyTeachingSchedule", client.get(f"{BASE}/me/teaching-schedule", headers=f), 200)
    _, viewer = org.user(VIEWER)
    expect(
        "getStudentAttendanceSummary",
        client.get(f"{BASE}/reports/students/{a}/attendance-summary", headers=viewer),
        200,
    )
    expect(
        "getStudentAttendanceHistory",
        client.get(f"{BASE}/reports/students/{a}/attendance-history", headers=viewer),
        200,
    )
    expect(
        "getDepartmentAttendance",
        client.get(
            f"{BASE}/reports/department-attendance?department_id={dept}&include_students_below_threshold=true",
            headers=viewer,
        ),
        200,
    )
    _, exams = org.user(EXAMS)
    expect(
        "getAttendanceForEligibility",
        client.post(
            f"{BASE}/reports/attendance-eligibility",
            json={"course_offering_id": room.ids["offering"], "cutoff_date": "2026-11-03", "student_ids": [a]},
            headers=exams,
        ),
        200,
    )
    student = org.user(STUDENT, user_id=b)[1]
    expect("getMySchedule", client.get(f"{BASE}/me/schedule", headers=student), 200)
    expect("getMyAttendanceSummary", client.get(f"{BASE}/me/attendance-summary", headers=student), 200)
    expect("getMyAttendanceHistory", client.get(f"{BASE}/me/attendance-history", headers=student), 200)
    other = room.new_class("2026-11-03T09:30:00+00:00")
    room.open(other["id"], headers=h)
    cancelled = expect(
        "cancelScheduledClass", client.post(f"{BASE}/scheduled-classes/{other['id']}/cancel", headers=h), 200
    )
    assert cancelled["attendance_session"]["status"] == "cancelled"


def test_error_statuses_are_declared_and_shaped(client, org):
    room = Classroom(client, org, students=1)
    h, f = room.admin, room.faculty
    missing = str(uuid.uuid4())
    c = room.new_class()
    _, s = room.held({}, "2026-11-03T08:00:00+00:00")
    record = ok(client.get(f"{BASE}/attendance-sessions/{s['id']}/records", headers=f))["items"][0]
    _, head = org.user(HEAD)
    _, other = org.user(STUDENT)
    calls = [
        ("createScheduledClass", 400, client.post(f"{BASE}/scheduled-classes", json={}, headers=h)),
        (
            "createScheduledClass",
            422,
            client.post(
                f"{BASE}/scheduled-classes",
                json={
                    "course_offering_id": missing,
                    "section_id": missing,
                    "instructor_assignment_id": missing,
                    "starts_at": "2026-11-03T09:00:00+00:00",
                    "ends_at": "2026-11-03T10:00:00+00:00",
                },
                headers=h,
            ),
        ),
        ("getScheduledClass", 404, client.get(f"{BASE}/scheduled-classes/{missing}", headers=h)),
        ("updateScheduledClass", 400, client.patch(f"{BASE}/scheduled-classes/{c['id']}", json={"x": 1}, headers=h)),
        ("updateScheduledClass", 404, client.patch(f"{BASE}/scheduled-classes/{missing}", json={}, headers=h)),
        (
            "updateScheduledClass",
            409,
            client.patch(f"{BASE}/scheduled-classes/{s['scheduled_class_id']}", json={}, headers=h),
        ),
        (
            "updateScheduledClass",
            422,
            client.patch(f"{BASE}/scheduled-classes/{c['id']}", json={"instructor_assignment_id": missing}, headers=h),
        ),
        ("cancelScheduledClass", 404, client.post(f"{BASE}/scheduled-classes/{missing}/cancel", headers=h)),
        (
            "cancelScheduledClass",
            409,
            client.post(f"{BASE}/scheduled-classes/{s['scheduled_class_id']}/cancel", headers=h),
        ),
        (
            "getAttendanceSessionForClass",
            404,
            client.get(f"{BASE}/scheduled-classes/{c['id']}/attendance-session", headers=h),
        ),
        (
            "openAttendanceSession",
            404,
            client.post(f"{BASE}/scheduled-classes/{missing}/attendance-session", headers=f),
        ),
        (
            "openAttendanceSession",
            409,
            client.post(f"{BASE}/scheduled-classes/{s['scheduled_class_id']}/attendance-session", headers=f),
        ),
        ("getAttendanceSession", 404, client.get(f"{BASE}/attendance-sessions/{missing}", headers=f)),
        ("closeAttendanceSession", 404, client.post(f"{BASE}/attendance-sessions/{missing}/close", headers=f)),
        ("closeAttendanceSession", 409, client.post(f"{BASE}/attendance-sessions/{s['id']}/close", headers=f)),
        ("listAttendanceRecords", 404, client.get(f"{BASE}/attendance-sessions/{missing}/records", headers=f)),
        ("listAttendanceRecords", 403, client.get(f"{BASE}/attendance-sessions/{s['id']}/records", headers=head)),
        ("markAttendance", 400, client.put(f"{BASE}/attendance-sessions/{s['id']}/records", json={}, headers=f)),
        (
            "markAttendance",
            409,
            client.put(
                f"{BASE}/attendance-sessions/{s['id']}/records",
                json={"records": [{"student_id": room.students[0], "status": "late"}]},
                headers=f,
            ),
        ),
        (
            "correctAttendanceRecord",
            400,
            client.patch(f"{BASE}/attendance-records/{record['id']}", json={"status": "late"}, headers=f),
        ),
        (
            "correctAttendanceRecord",
            403,
            client.patch(
                f"{BASE}/attendance-records/{record['id']}", json={"status": "late", "reason": "x"}, headers=head
            ),
        ),
        ("getAttendanceRecordHistory", 404, client.get(f"{BASE}/attendance-records/{missing}/history", headers=f)),
        (
            "getStudentAttendanceSummary",
            403,
            client.get(f"{BASE}/reports/students/{missing}/attendance-summary", headers=head),
        ),
        (
            "getStudentAttendanceHistory",
            403,
            client.get(f"{BASE}/reports/students/{missing}/attendance-history", headers=head),
        ),
        ("getDepartmentAttendance", 404, client.get(f"{BASE}/reports/department-attendance", headers=head)),
        (
            "getDepartmentAttendance",
            400,
            client.get(f"{BASE}/reports/department-attendance?department_id=x", headers=head),
        ),
        ("getMyAttendanceSummary", 404, client.get(f"{BASE}/me/attendance-summary", headers=other)),
        (
            "getAttendanceForEligibility",
            404,
            client.post(
                f"{BASE}/reports/attendance-eligibility",
                json={"course_offering_id": missing, "cutoff_date": "2026-11-03"},
                headers=org.user(EXAMS)[1],
            ),
        ),
    ]
    for operation_id, status, response in calls:
        expect(operation_id, response, status)
    active_term(org.id, str(uuid.uuid4()))
    expect("getDepartmentAttendance", client.get(f"{BASE}/reports/department-attendance", headers=head), 403)
