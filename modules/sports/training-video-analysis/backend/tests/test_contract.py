"""The router and contracts/ agree: the same operations, each guarded by the permission its x-permission names, every
permission key in permissions.yaml, and every event published is declared in events.yaml with the same fields."""

from pathlib import Path

import pytest
import yaml
from conftest import outbox
from eos_training_video_analysis.api.router import router
from eos_training_video_analysis.application.consumers import CONSUMERS
from fastapi.routing import APIRoute

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
OPENAPI = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))
PERMISSIONS = yaml.safe_load((CONTRACTS / "permissions.yaml").read_text(encoding="utf-8"))
EVENTS = yaml.safe_load((CONTRACTS / "events.yaml").read_text(encoding="utf-8"))
METHODS = {"get", "put", "post", "patch", "delete"}
OPERATIONS = {
    (method.upper(), path): op
    for path, item in OPENAPI["paths"].items()
    for method, op in item.items()
    if method in METHODS
}


def _route_permissions() -> dict[tuple[str, str], str]:
    """(METHOD, path) -> the permission the route's `require` dependency checks."""
    out = {}
    for route in router.routes:
        assert isinstance(route, APIRoute)
        for method in route.methods:
            deps = [d.call for d in route.dependant.dependencies]
            perms = [
                c.__closure__[0].cell_contents for c in deps if getattr(c, "__name__", "") == "dep" and c.__closure__
            ]
            out[(method, route.path)] = perms[0] if perms else None
    return out


def test_routes_match_the_contract_operations():
    assert set(_route_permissions()) == set(OPERATIONS)


@pytest.mark.parametrize("key", sorted(OPERATIONS), ids=[f"{m} {p}" for m, p in sorted(OPERATIONS)])
def test_each_route_checks_the_contract_permission(key):
    assert _route_permissions()[key] == OPERATIONS[key]["x-permission"]
    assert OPERATIONS[key]["responses"].get("403") == {"$ref": "#/components/responses/Forbidden"}


def test_every_x_permission_is_in_the_catalogue_and_every_role_grants_known_keys():
    keys = {p["key"] for p in PERMISSIONS["permissions"]}
    assert {op["x-permission"] for op in OPERATIONS.values()} == keys
    for role in PERMISSIONS["roles"]:
        assert set(role["grants"]) <= keys, role["name"]


def test_published_events_match_events_yaml(client, org):
    plan = org.plan()
    drill = org.drill()
    s = org.session(plan_id=plan["id"], location="Main ground", drill_ids=[drill["id"]])
    assert org.patch(f"/sessions/{s['id']}", {"status": "completed"}).status_code == 200
    v = org.video(session_id=s["id"])
    org.post(f"/videos/{v['id']}/drill-tags", {"drill_id": drill["id"], "start_timestamp": 1, "end_timestamp": 9})
    org.annotation(v["id"])
    declared = {e["name"]: set(e["payload"]) for e in EVENTS["events"]}
    published = {e.name: set(e.payload) for e in outbox(org.id)}
    assert published == declared


def test_responses_carry_the_contract_fields(client, org):
    """Each response body has the fields its contract schema marks required, and no field the schema lacks."""
    schemas = OPENAPI["components"]["schemas"]
    plan = org.plan(squad_id="22222222-2222-2222-2222-222222222222", description="Base", objectives=["speed"])
    drill = org.drill(description="d", target_focus="feet", equipment_needed=["ladder"], standard_duration_minutes=15)
    s = org.session(plan_id=plan["id"], attendee_ids=[plan["squad_id"]], location="Ground")
    v = org.video(session_id=s["id"], thumbnail_url="https://files.example.com/t.jpg", resolution="1920x1080")
    tag = org.post(f"/videos/{v['id']}/drill-tags", {"drill_id": drill["id"], "start_timestamp": 1, "end_timestamp": 9})
    note = org.annotation(v["id"], end_timestamp=50, drawing_markup={"lines": []})
    for body, name in (
        (plan, "TrainingPlan"),
        (drill, "Drill"),
        (s, "TrainingSession"),
        (v, "TrainingVideo"),
        (tag, "DrillTag"),
        (note, "VideoAnnotation"),
    ):
        assert set(schemas[name]["required"]) <= set(body), name
        assert set(body) <= set(schemas[name]["properties"]), name


def test_consumed_events_are_declared_in_module_yaml():
    manifest = yaml.safe_load((CONTRACTS.parent / "module.yaml").read_text(encoding="utf-8"))
    assert set(manifest["consumes_events"]) == set(CONSUMERS)
