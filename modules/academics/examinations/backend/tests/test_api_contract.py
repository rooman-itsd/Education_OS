"""The 15 configuration and exam-cycle operations against contracts/openapi.yaml: the routes and their permissions are the
contract's, and every response body has the fields, types and enums the contract declares, no more and no fewer."""

import uuid
from pathlib import Path

import pytest
import yaml

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BASE,
    assessment_body,
    cycle_body,
    grading_body,
    make_assessment,
    make_cycle,
    make_grading,
    ok,
    uid,
)
from eos_examinations.api.router import router  # noqa: E402

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
    "listGradingSchemes": ("get", "/grading-schemes"),
    "createGradingScheme": ("post", "/grading-schemes"),
    "getGradingScheme": ("get", "/grading-schemes/{grading_scheme_id}"),
    "replaceGradingScheme": ("put", "/grading-schemes/{grading_scheme_id}"),
    "setDefaultGradingScheme": ("post", "/grading-schemes/{grading_scheme_id}/set-default"),
    "listAssessmentSchemes": ("get", "/assessment-schemes"),
    "createAssessmentScheme": ("post", "/assessment-schemes"),
    "getAssessmentScheme": ("get", "/assessment-schemes/{assessment_scheme_id}"),
    "replaceAssessmentScheme": ("put", "/assessment-schemes/{assessment_scheme_id}"),
    "activateAssessmentScheme": ("post", "/assessment-schemes/{assessment_scheme_id}/activate"),
    "listExamCycles": ("get", "/exam-cycles"),
    "createExamCycle": ("post", "/exam-cycles"),
    "getExamCycle": ("get", "/exam-cycles/{exam_cycle_id}"),
    "updateExamCycle": ("patch", "/exam-cycles/{exam_cycle_id}"),
    "changeExamCycleStatus": ("post", "/exam-cycles/{exam_cycle_id}/status"),
}
WIDENED = {  # the contract's descriptions: write-all widens write-department
    "createAssessmentScheme",
    "replaceAssessmentScheme",
    "activateAssessmentScheme",
}
WRITE_ALL = "examinations:assessment-scheme:write-all"


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


def check(value, schema: dict, where: str = "$", *, read_only_ok: bool = True) -> None:
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
    if schema.get("format") == "date" and isinstance(value, str):
        assert len(value) == 10
    if isinstance(value, int | float) and not isinstance(value, bool):
        if "minimum" in schema:
            assert value >= schema["minimum"], where
        if "maximum" in schema:
            assert value <= schema["maximum"], where
    if isinstance(value, dict) and "properties" in schema:
        missing = set(schema.get("required", [])) - set(value)
        assert not missing, f"{where}: missing {missing}"
        # `department_id` is readOnly and "cached from the course offering": the offering read model is not filled yet,
        # so it is not served and is not required (docs/reviewer-decisions.md).
        extra = set(value) - set(schema["properties"])
        assert not extra, f"{where}: not in the contract: {extra}"
        for key, item in value.items():
            check(item, schema["properties"][key], f"{where}.{key}")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            check(item, schema["items"], f"{where}[{i}]")
    if isinstance(value, list) and "minItems" in schema:
        assert len(value) >= schema["minItems"], where


def operation(operation_id: str) -> dict:
    method, path = IMPLEMENTED[operation_id]
    return CONTRACT["paths"][path][method]


def body_schema(operation_id: str, status: int) -> dict:
    return operation(operation_id)["responses"][str(status)]["content"]["application/json"]["schema"]


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
        expected = {op["x-permission"]} | ({WRITE_ALL} if operation_id in WIDENED else set())
        assert routes[(method, path)] == expected, operation_id
        if operation_id in WIDENED:
            assert WRITE_ALL in op["description"]  # the contract itself says the wider key widens the scope


def test_the_servers_prefix_is_the_one_the_tests_mount():
    assert BASE == CONTRACT["servers"][0]["url"]


def test_every_permission_key_the_routes_use_is_in_the_catalogue():
    catalogue = {
        p["key"]
        for p in yaml.safe_load(
            (Path(__file__).resolve().parents[2] / "contracts" / "permissions.yaml").read_text(encoding="utf-8")
        )["permissions"]
    }
    for method, path in IMPLEMENTED.values():
        assert CONTRACT["paths"][path][method]["x-permission"] in catalogue


def test_success_bodies_and_statuses_match_the_contract(client, org, h):
    grading = client.post(f"{BASE}/grading-schemes", json=grading_body(), headers=h)
    assert grading.status_code == 201 and "201" in operation("createGradingScheme")["responses"]
    check(grading.json(), body_schema("createGradingScheme", 201))
    g = grading.json()["id"]
    check(ok(client.get(f"{BASE}/grading-schemes/{g}", headers=h)), body_schema("getGradingScheme", 200))
    check(ok(client.get(f"{BASE}/grading-schemes", headers=h)), body_schema("listGradingSchemes", 200))
    check(
        ok(client.put(f"{BASE}/grading-schemes/{g}", json=grading_body("New"), headers=h)),
        body_schema("replaceGradingScheme", 200),
    )
    default = ok(client.post(f"{BASE}/grading-schemes/{g}/set-default", headers=h))
    check(default, body_schema("setDefaultGradingScheme", 200))
    assert default["is_default"] is True

    scheme = client.post(f"{BASE}/assessment-schemes", json=assessment_body(), headers=h)
    assert scheme.status_code == 201
    check(scheme.json(), body_schema("createAssessmentScheme", 201))
    a = scheme.json()["id"]
    check(ok(client.get(f"{BASE}/assessment-schemes/{a}", headers=h)), body_schema("getAssessmentScheme", 200))
    check(ok(client.get(f"{BASE}/assessment-schemes", headers=h)), body_schema("listAssessmentSchemes", 200))
    check(
        ok(
            client.put(
                f"{BASE}/assessment-schemes/{a}", json=assessment_body(scheme.json()["course_offering_id"]), headers=h
            )
        ),
        body_schema("replaceAssessmentScheme", 200),
    )
    activated = ok(client.post(f"{BASE}/assessment-schemes/{a}/activate", headers=h))
    check(activated, body_schema("activateAssessmentScheme", 200))
    assert activated["status"] == "active"

    full = cycle_body(eligibility_cutoff_date="2026-11-10", min_attendance_percent=75, check_dues=True)
    cycle = client.post(f"{BASE}/exam-cycles", json=full, headers=h)
    assert cycle.status_code == 201
    check(cycle.json(), body_schema("createExamCycle", 201))
    c = cycle.json()["id"]
    check(ok(client.get(f"{BASE}/exam-cycles/{c}", headers=h)), body_schema("getExamCycle", 200))
    check(ok(client.get(f"{BASE}/exam-cycles", headers=h)), body_schema("listExamCycles", 200))
    check(
        ok(client.patch(f"{BASE}/exam-cycles/{c}", json={"name": "N", "min_attendance_percent": None}, headers=h)),
        body_schema("updateExamCycle", 200),
    )
    moved = ok(client.post(f"{BASE}/exam-cycles/{c}/status", json={"status": "scheduled"}, headers=h))
    check(moved, body_schema("changeExamCycleStatus", 200))
    assert moved["status"] == "scheduled"


def test_an_empty_list_matches_the_contract(client, h):
    for operation_id, path in (
        ("listGradingSchemes", "/grading-schemes"),
        ("listAssessmentSchemes", "/assessment-schemes"),
        ("listExamCycles", "/exam-cycles"),
    ):
        body = ok(client.get(f"{BASE}{path}", headers=h))
        assert body == {"items": [], "total": 0}
        check(body, body_schema(operation_id, 200))


def test_error_bodies_are_the_contracts_error_response_with_declared_statuses(client, org, h):
    g = make_grading(client, h)["id"]
    a = make_assessment(client, h)
    c = make_cycle(client, h, g)["id"]
    missing = uid()
    bad_assessment = assessment_body(a["course_offering_id"], [])
    draft_weight = make_assessment(
        client, h, components=[{**assessment_body()["components"][0], "weightage_percent": 50}]
    )
    calls = {
        "createGradingScheme": [(400, client.post(f"{BASE}/grading-schemes", json={"name": "x"}, headers=h))],
        "getGradingScheme": [(404, client.get(f"{BASE}/grading-schemes/{missing}", headers=h))],
        "replaceGradingScheme": [
            (400, client.put(f"{BASE}/grading-schemes/{g}", json={"name": "x", "bands": []}, headers=h)),
            (404, client.put(f"{BASE}/grading-schemes/{missing}", json=grading_body(), headers=h)),
        ],
        "setDefaultGradingScheme": [(404, client.post(f"{BASE}/grading-schemes/{missing}/set-default", headers=h))],
        "createAssessmentScheme": [(400, client.post(f"{BASE}/assessment-schemes", json={}, headers=h))],
        "getAssessmentScheme": [(404, client.get(f"{BASE}/assessment-schemes/{missing}", headers=h))],
        "replaceAssessmentScheme": [
            (400, client.put(f"{BASE}/assessment-schemes/{a['id']}", json=bad_assessment, headers=h)),
            (404, client.put(f"{BASE}/assessment-schemes/{missing}", json=assessment_body(), headers=h)),
        ],
        "activateAssessmentScheme": [
            (404, client.post(f"{BASE}/assessment-schemes/{missing}/activate", headers=h)),
            (422, client.post(f"{BASE}/assessment-schemes/{draft_weight['id']}/activate", headers=h)),
        ],
        "createExamCycle": [
            (400, client.post(f"{BASE}/exam-cycles", json=cycle_body(ends_on="2026-01-01"), headers=h)),
            (422, client.post(f"{BASE}/exam-cycles", json=cycle_body(grading_scheme_id=missing), headers=h)),
        ],
        "getExamCycle": [(404, client.get(f"{BASE}/exam-cycles/{missing}", headers=h))],
        "updateExamCycle": [
            (400, client.patch(f"{BASE}/exam-cycles/{c}", json={"name": " "}, headers=h)),
            (404, client.patch(f"{BASE}/exam-cycles/{missing}", json={"name": "x"}, headers=h)),
        ],
        "changeExamCycleStatus": [
            (404, client.post(f"{BASE}/exam-cycles/{missing}/status", json={"status": "scheduled"}, headers=h)),
            (409, client.post(f"{BASE}/exam-cycles/{c}/status", json={"status": "closed"}, headers=h)),
        ],
    }
    ok(client.post(f"{BASE}/assessment-schemes/{a['id']}/activate", headers=h))
    calls["replaceAssessmentScheme"].append(
        (
            409,
            client.put(
                f"{BASE}/assessment-schemes/{a['id']}", json=assessment_body(a["course_offering_id"]), headers=h
            ),
        )
    )
    error = SCHEMAS["ErrorResponse"]
    for operation_id, results in calls.items():
        for status, response in results:
            assert response.status_code == status, (operation_id, response.text)
            assert str(status) in operation(operation_id)["responses"], (operation_id, status)  # declared
            check(response.json()["detail"], error, operation_id)


def test_a_409_of_updating_a_cycle_and_replacing_a_grading_scheme_is_declared_and_shaped(client, org, h):
    g = make_grading(client, h)["id"]
    c = make_cycle(client, h, g)["id"]
    ok(client.post(f"{BASE}/exam-cycles/{c}/status", json={"status": "scheduled"}, headers=h))
    ok(client.post(f"{BASE}/exam-cycles/{c}/status", json={"status": "in_progress"}, headers=h))
    r = client.patch(f"{BASE}/exam-cycles/{c}", json={"name": "late"}, headers=h)
    assert r.status_code == 409 and "409" in operation("updateExamCycle")["responses"]
    check(r.json()["detail"], SCHEMAS["ErrorResponse"])
    assert r.json()["detail"]["details"]["status"] == "in_progress"  # `details` is the contract's free object


def test_the_contract_gaps_this_batch_records():
    """Known gaps, recorded in docs/reviewer-decisions.md and the PR notes: none is worked around. The API answers 401
    and 403 (api/deps.py) but the contract declares no 401, and a 403 only on the three assessment-scheme writes; a bad
    filter value answers 400 on both listings and an unknown status value answers 400 on changeExamCycleStatus, where
    the contract declares neither. This test fails when the contract changes, as a reminder to assert the new answers."""
    for operation_id in IMPLEMENTED:
        declared = set(operation(operation_id)["responses"])
        assert "401" not in declared, operation_id
        assert ("403" in declared) == (operation_id in WIDENED), operation_id
    for operation_id in ("listExamCycles", "listAssessmentSchemes", "changeExamCycleStatus"):
        assert "400" not in operation(operation_id)["responses"], operation_id
    assert "422" not in operation("updateExamCycle")["responses"]  # an unknown grading scheme there is a 400
