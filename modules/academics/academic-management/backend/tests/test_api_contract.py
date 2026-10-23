"""Every response body checked against contracts/openapi.yaml: required fields present, no field the contract does
not define, JSON types and enums as declared. Bodies come from the real API on a throwaway database."""

from pathlib import Path

import pytest
import yaml

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see test_api_deps.py)")

from conftest import (  # noqa: E402
    BASE,
    assign,
    make_course,
    make_offering,
    make_programme,
    make_term,
    ok,
    open_offering,
)

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


def check(value, schema, where="$"):
    if "$ref" in schema:
        schema = SCHEMAS[schema["$ref"].rsplit("/", 1)[1]]
    types = schema.get("type")
    if types:
        allowed = types if isinstance(types, list) else [types]
        good = any(isinstance(value, JSON[t]) for t in allowed)
        if isinstance(value, bool) and "boolean" not in allowed:
            good = False
        assert good, f"{where}: {value!r} is not {allowed}"
    if "enum" in schema:
        assert value in schema["enum"], f"{where}: {value!r} not in {schema['enum']}"
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


def response_schema(path: str, method: str, status: int) -> dict:
    return CONTRACT["paths"][path][method]["responses"][str(status)]["content"]["application/json"]["schema"]


@pytest.fixture
def bodies(client, org):
    """One real response of every operation that returns a body."""
    _, admin = org.user("org-admin")
    teacher, teacher_h = org.user("faculty", name="T. Teacher")
    term = make_term(client, admin)
    ok(client.post(f"{BASE}/terms/{term['id']}/activate", headers=admin))
    programme = make_programme(client, admin)
    course = make_course(client, admin)
    item = {"course_id": course["id"], "programme_term": 1, "category": "core", "credits": 4}
    curriculum = ok(
        client.post(f"{BASE}/programmes/{programme['id']}/curricula", json={"items": [item]}, headers=admin), 201
    )
    offering = make_offering(client, admin, course["id"], term["id"])
    open_offering(client, admin, offering["id"], teacher)
    co_teacher, _ = org.user("faculty", name="C. Co-teacher")
    helper = assign(client, admin, offering["id"], co_teacher, role="co_instructor", hours=2)
    o = offering["id"]
    get = lambda p, h=admin: ok(client.get(f"{BASE}{p}", headers=h))  # noqa: E731
    return [
        ("/terms", "get", 200, get("/terms")),
        ("/terms/{academic_period_id}", "get", 200, get(f"/terms/{term['id']}")),
        ("/programmes", "get", 200, get("/programmes")),
        ("/programmes/{programme_id}", "get", 200, get(f"/programmes/{programme['id']}")),
        ("/programmes/{programme_id}/curricula", "get", 200, get(f"/programmes/{programme['id']}/curricula")),
        ("/programmes/{programme_id}/curricula", "post", 201, curriculum),
        ("/curricula/{curriculum_id}", "get", 200, get(f"/curricula/{curriculum['id']}")),
        ("/courses", "get", 200, get("/courses")),
        ("/courses/{course_id}", "get", 200, get(f"/courses/{course['id']}")),
        ("/offerings", "get", 200, get("/offerings")),
        ("/offerings/{course_offering_id}", "get", 200, get(f"/offerings/{o}")),
        ("/offerings/{course_offering_id}/sections", "get", 200, get(f"/offerings/{o}/sections")),
        ("/offerings/{course_offering_id}/faculty-assignments", "get", 200, get(f"/offerings/{o}/faculty-assignments")),
        ("/offerings/{course_offering_id}/faculty-assignments", "post", 201, helper),
        ("/offerings/{course_offering_id}/roster", "get", 200, get(f"/offerings/{o}/roster", teacher_h)),
        ("/me/offerings", "get", 200, get("/me/offerings", teacher_h)),
        ("/faculty-load", "get", 200, get("/faculty-load")),
    ]


def test_every_response_matches_its_contract_schema(bodies):
    for path, method, status, body in bodies:
        check(body, response_schema(path, method, status), f"{method.upper()} {path}")


def test_the_contract_lists_every_route_this_module_serves(client):
    from eos_academic_management.api.router import router

    served = {(r.path, m.lower()) for r in router.routes for m in r.methods}
    declared = {
        (p, m) for p, item in CONTRACT["paths"].items() for m in item if m in {"get", "post", "put", "patch", "delete"}
    }
    assert served == declared


def test_every_route_is_guarded_by_exactly_the_keys_its_operation_declares(client):
    """Each route's require() guard holds the operation's x-permission, plus the keys of x-permission-any where the
    contract lists several; a guard that accepts more or less than the contract says is a drift."""
    from eos_academic_management.api.router import router

    for route in router.routes:
        guards = [d.call.permissions for d in route.dependant.dependencies if hasattr(d.call, "permissions")]
        assert len(guards) == 1, route.path
        for method in route.methods:
            op = CONTRACT["paths"][route.path][method.lower()]
            declared = {op["x-permission"], *op.get("x-permission-any", [])}
            assert op["x-permission"] in op.get("x-permission-any", [op["x-permission"]]), route.path
            assert guards[0] == declared, (method, route.path, sorted(guards[0]), sorted(declared))
