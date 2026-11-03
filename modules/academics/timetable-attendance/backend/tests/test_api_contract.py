"""The timetable operations against contracts/openapi.yaml: the routes and their permissions are the contract's, and
every response body has the fields, types and enums the contract declares, no more and no fewer."""

import uuid
from pathlib import Path

import pytest
import yaml

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import ADMIN, BASE, make_timetable, ok, slot  # noqa: E402
from eos_timetable_attendance.api.router import router  # noqa: E402

CONTRACT = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
)
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
# This batch's operations: operationId -> (method, path).
IMPLEMENTED = {
    "listTimetables": ("get", "/timetables"),
    "createTimetable": ("post", "/timetables"),
    "getTimetable": ("get", "/timetables/{timetable_id}"),
    "updateTimetable": ("patch", "/timetables/{timetable_id}"),
    "replaceTimetableSlots": ("put", "/timetables/{timetable_id}/slots"),
    "listTimetableConflicts": ("get", "/timetables/{timetable_id}/conflicts"),
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
            merged.update({k: v for k, v in part.items() if k not in ("properties", "required")})
        return merged
    return schema


def check(value, schema: dict, where: str = "$") -> None:
    schema = resolve(schema)
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


def body_schema(operation_id: str, status: int) -> dict:
    method, path = IMPLEMENTED[operation_id]
    response = CONTRACT["paths"][path][method]["responses"][str(status)]
    return response["content"]["application/json"]["schema"]


def operation(operation_id: str) -> dict:
    method, path = IMPLEMENTED[operation_id]
    return CONTRACT["paths"][path][method]


def test_every_implemented_route_is_a_contract_operation_with_its_x_permission():
    routes = {}
    for route in router.routes:
        for method in route.methods:
            keys = set()
            for dep in route.dependant.dependencies:
                keys |= set(getattr(dep.call, "permissions", ()))
            routes[(method.lower(), route.path)] = keys
    assert set(routes) == set(IMPLEMENTED.values())
    for operation_id, (method, path) in IMPLEMENTED.items():
        op = CONTRACT["paths"][path][method]
        assert op["operationId"] == operation_id
        assert routes[(method, path)] == {op["x-permission"]}, operation_id


def test_the_servers_prefix_is_the_one_the_tests_mount():
    assert BASE == CONTRACT["servers"][0]["url"]


def test_success_bodies_match_the_contract(client, org):
    _, h = org.user(ADMIN)
    ids = org.academic()
    created = make_timetable(
        client, h, ids["period"], department_id=str(uuid.uuid4()), slots=[slot(ids, location_label="R1")]
    )
    check(created, body_schema("createTimetable", 201))
    t = created["id"]
    check(ok(client.get(f"{BASE}/timetables/{t}", headers=h)), body_schema("getTimetable", 200))
    check(ok(client.get(f"{BASE}/timetables", headers=h)), body_schema("listTimetables", 200))
    check(
        ok(client.patch(f"{BASE}/timetables/{t}", json={"name": "New"}, headers=h)), body_schema("updateTimetable", 200)
    )
    both = [
        slot(ids),
        slot(ids, start="09:30:00", end="10:30:00", effective_from="2026-11-01", effective_to="2026-12-01"),
    ]
    replaced = ok(client.put(f"{BASE}/timetables/{t}/slots", json={"slots": both}, headers=h))
    check(replaced, body_schema("replaceTimetableSlots", 200))
    conflicts = ok(client.get(f"{BASE}/timetables/{t}/conflicts", headers=h))
    assert conflicts["items"]
    check(conflicts, body_schema("listTimetableConflicts", 200))


def test_an_empty_slot_replacement_and_an_empty_list_match_the_contract(client, org):
    _, h = org.user(ADMIN)
    t = make_timetable(client, h)
    check(
        ok(client.put(f"{BASE}/timetables/{t['id']}/slots", json={"slots": []}, headers=h)),
        body_schema("replaceTimetableSlots", 200),
    )
    check(
        ok(client.get(f"{BASE}/timetables/{t['id']}/conflicts", headers=h)), body_schema("listTimetableConflicts", 200)
    )
    check(ok(client.get(f"{BASE}/timetables?status=published", headers=h)), body_schema("listTimetables", 200))


def test_error_bodies_are_the_contracts_error_response_with_declared_statuses(client, org):
    _, h = org.user(ADMIN)
    ids = org.academic()
    t = make_timetable(client, h, ids["period"])
    missing = str(uuid.uuid4())
    calls = {
        "createTimetable": (400, client.post(f"{BASE}/timetables", json={"name": "x"}, headers=h)),
        "getTimetable": (404, client.get(f"{BASE}/timetables/{missing}", headers=h)),
        "updateTimetable": (400, client.patch(f"{BASE}/timetables/{t['id']}", json={"name": " "}, headers=h)),
        "replaceTimetableSlots": (
            422,
            client.put(
                f"{BASE}/timetables/{t['id']}/slots", json={"slots": [slot(ids, section_id=missing)]}, headers=h
            ),
        ),
        "listTimetableConflicts": (404, client.get(f"{BASE}/timetables/{missing}/conflicts", headers=h)),
    }
    error = SCHEMAS["ErrorResponse"]
    for operation_id, (status, response) in calls.items():
        assert response.status_code == status, (operation_id, response.text)
        assert str(status) in operation(operation_id)["responses"], operation_id  # the contract declares this status
        check(response.json()["detail"], error, operation_id)


def test_the_409_of_updating_a_published_timetable_is_declared_and_shaped(client, org):
    from eos_core.db import SessionLocal
    from eos_timetable_attendance.infrastructure.models import TimetableRow

    _, h = org.user(ADMIN)
    t = make_timetable(client, h)
    with SessionLocal() as db:
        db.get(TimetableRow, t["id"]).status = "published"
        db.commit()
    for operation_id, response in {
        "updateTimetable": client.patch(f"{BASE}/timetables/{t['id']}", json={"name": "x"}, headers=h),
        "replaceTimetableSlots": client.put(f"{BASE}/timetables/{t['id']}/slots", json={"slots": []}, headers=h),
    }.items():
        assert response.status_code == 409
        assert "409" in operation(operation_id)["responses"]
        check(response.json()["detail"], SCHEMAS["ErrorResponse"])


def test_the_contract_declares_no_401_or_403_for_these_operations_yet():
    """Known gap, recorded in docs/reviewer-decisions.md item 7: the API answers 401 and 403 (api/deps.py) but the
    contract does not declare them. This test fails when the contract gains them, as a reminder to assert them."""
    for operation_id in IMPLEMENTED:
        declared = set(operation(operation_id)["responses"])
        assert not declared & {"401", "403"}, operation_id
