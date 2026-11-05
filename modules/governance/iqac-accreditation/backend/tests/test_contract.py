"""The module against its contracts: routes, the permission each route is guarded by, the error statuses, enums and
bounds of the schemas, every response body, every published event, and the permission catalogue."""

import re
from pathlib import Path

import pytest
import yaml
from conftest import BASE, Desk, days, outbox
from eos_core.db import new_id

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
SPEC = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))
EVENTS = yaml.safe_load((CONTRACTS / "events.yaml").read_text(encoding="utf-8"))
PERMISSIONS = yaml.safe_load((CONTRACTS / "permissions.yaml").read_text(encoding="utf-8"))
SCHEMAS = SPEC["components"]["schemas"]
METHODS = {"get", "post", "put", "patch", "delete"}
KEY = re.compile(r"iqac-accreditation:[a-z-]+:[a-z-]+")


def operations() -> dict[tuple[str, str], dict]:
    return {(m.upper(), p): op for p, item in SPEC["paths"].items() for m, op in item.items() if m in METHODS}


# ---------------------------------------------------------------- routes and permissions


def test_routes_match_the_contract_operations():
    from eos_iqac_accreditation.api.router import router

    routes = {(m, route.path) for route in router.routes for m in route.methods}
    assert routes == set(operations())
    assert len(routes) == 23


def declared_permissions(summary: str) -> set[str]:
    """The keys of the sentence "Permission a, b or c." that ends each summary."""
    return set(KEY.findall(" ".join(summary.split()).rsplit("Permission ", 1)[1]))


def test_every_route_is_guarded_by_exactly_the_keys_its_operation_names():
    from eos_iqac_accreditation.api.router import router

    ops = operations()
    for route in router.routes:
        guards = [d.call.permissions for d in route.dependant.dependencies if hasattr(d.call, "permissions")]
        assert len(guards) == 1, route.path
        for method in route.methods:
            declared = declared_permissions(ops[(method, route.path)]["summary"])
            assert guards[0] == declared, (method, route.path, sorted(guards[0]), sorted(declared))


def test_the_catalogue_declares_the_keys_the_module_checks_and_the_roles_grant_only_those():
    from eos_iqac_accreditation.application.access import PERMISSION_KEYS

    declared = {p["key"] for p in PERMISSIONS["permissions"]}
    assert declared == set(PERMISSION_KEYS)
    assert all(key.startswith("iqac-accreditation:") for key in declared)
    used = set().union(*(declared_permissions(op["summary"]) for op in operations().values()))
    assert used <= declared
    for role in PERMISSIONS["roles"]:
        assert set(role["grants"]) <= declared, role["name"]
    assert {r["name"] for r in PERMISSIONS["roles"]} == {
        "iqac-accreditation-coordinator",
        "iqac-accreditation-contributor",
        "iqac-accreditation-viewer",
    }


def test_the_governance_dashboard_role_holds_the_widget_permission():
    from eos_core.config import permissions_for

    assert "iqac-accreditation:stats:read" in permissions_for(["governance"], False)
    assert "iqac-accreditation:stats:read" not in permissions_for(["faculty"], False)


# ---------------------------------------------------------------- error statuses


def code_of(r) -> tuple[int, str]:
    body = r.json()["detail"]
    assert set(body) >= {"code", "message"}, body
    return r.status_code, body["code"]


def declared_statuses() -> set[tuple[str, str, str]]:
    """(method, path, status) of every non-2xx answer the contract lists."""
    return {
        (m, p, status)
        for (m, p), op in operations().items()
        for status in op["responses"]
        if not status.startswith("2")
    }


def triggers(d: Desk) -> list[tuple[str, str, str, object]]:
    """One request per declared error answer: (method, path, status, the request that gets it)."""
    c = d.collecting()
    sub = d.submitted_q()
    accepted = d.submitted_q()
    evidence = d.ok(
        d.post(
            f"/responses/{accepted['q']['id']}/evidence",
            {"title": "x", "kind": "link", "url": "https://e.edu"},
            d.alice,
        )
    )
    d.ok(d.post(f"/responses/{accepted['q']['id']}/review", {"decision": "accept"}))
    cid, fid = c["cycle"]["id"], c["framework"]["id"]
    metric = c["metrics"][0]["id"]
    d.framework(code="TAKEN")
    open_framework = d.framework()
    d.cycle(open_framework["id"])
    planned = d.cycle(fid)
    reviewing = d.cycle()
    d.move(reviewing["id"], "collecting")
    d.move(reviewing["id"], "under_review")
    cancelled = d.action_item()
    d.ok(d.patch(f"/action-items/{cancelled['id']}", {"status": "cancelled"}))
    ghost = new_id()
    ok_link = {"title": "x", "kind": "link", "url": "https://e.edu"}
    return [
        ("POST", "/frameworks", "409", lambda: d.post("/frameworks", {"code": "TAKEN", "name": "x"})),
        ("PATCH", "/frameworks/{id}", "409", lambda: d.patch(f"/frameworks/{open_framework['id']}", {"active": False})),
        (
            "POST",
            "/frameworks/{id}/metrics",
            "409",
            lambda: d.post(f"/frameworks/{fid}/metrics", {"code": "Q1", "title": "x", "kind": "qualitative"}),
        ),
        ("GET", "/cycles/{id}", "404", lambda: d.get(f"/cycles/{ghost}")),
        (
            "POST",
            "/cycles",
            "422",
            lambda: d.post(
                "/cycles", {"framework_id": fid, "name": "x", "period_start": "2026-01-02", "period_end": "2026-01-01"}
            ),
        ),
        ("PATCH", "/cycles/{id}", "409", lambda: d.patch(f"/cycles/{cid}", {"name": "x"})),
        ("POST", "/cycles/{id}/status", "409", lambda: d.post(f"/cycles/{planned['id']}/status", {"status": "closed"})),
        (
            "POST",
            "/cycles/{id}/status",
            "422",
            lambda: d.post(f"/cycles/{reviewing['id']}/status", {"status": "submitted"}),
        ),
        (
            "POST",
            "/cycles/{id}/assignments",
            "409",
            lambda: d.post(
                f"/cycles/{cid}/assignments",
                {"assignments": [{"metric_id": metric, "owner_id": d.alice_id, "due_on": days(5)}]},
            ),
        ),
        (
            "POST",
            "/cycles/{id}/assignments",
            "422",
            lambda: d.post(
                f"/cycles/{cid}/assignments",
                {"assignments": [{"metric_id": ghost, "owner_id": d.alice_id, "due_on": days(5)}]},
            ),
        ),
        ("GET", "/responses/{id}", "404", lambda: d.get(f"/responses/{ghost}")),
        ("PUT", "/responses/{id}", "409", lambda: d.put(f"/responses/{sub['q']['id']}", {"value": 1}, d.alice)),
        ("POST", "/responses/{id}/submit", "409", lambda: d.post(f"/responses/{sub['q']['id']}/submit", None, d.alice)),
        ("POST", "/responses/{id}/submit", "422", lambda: d.post(f"/responses/{c['q']['id']}/submit", None, d.alice)),
        (
            "POST",
            "/responses/{id}/review",
            "409",
            lambda: d.post(f"/responses/{c['n']['id']}/review", {"decision": "accept"}),
        ),
        (
            "POST",
            "/responses/{id}/review",
            "422",
            lambda: d.post(f"/responses/{sub['q']['id']}/review", {"decision": "return"}),
        ),
        (
            "POST",
            "/responses/{id}/evidence",
            "409",
            lambda: d.post(f"/responses/{accepted['q']['id']}/evidence", ok_link, d.alice),
        ),
        (
            "DELETE",
            "/responses/{id}/evidence/{evidence_id}",
            "404",
            lambda: d.delete(f"/responses/{sub['q']['id']}/evidence/{ghost}", d.alice),
        ),
        (
            "DELETE",
            "/responses/{id}/evidence/{evidence_id}",
            "409",
            lambda: d.delete(f"/responses/{accepted['q']['id']}/evidence/{evidence['id']}", d.alice),
        ),
        ("PATCH", "/action-items/{id}", "409", lambda: d.patch(f"/action-items/{cancelled['id']}", {"title": "x"})),
    ]


def test_every_error_status_the_contract_lists_is_answered_with_a_code_and_a_message(desk):
    cases = triggers(desk)
    assert {(m, p, s) for m, p, s, _ in cases} >= declared_statuses()
    for method, path, status, request in cases:
        r = request()
        assert r.status_code == int(status), (method, path, status, r.status_code, r.text[:200])
        code_of(r)


# ---------------------------------------------------------------- schemas: enums, bounds, required fields


def contract_enum(name: str) -> list[str]:
    return SCHEMAS[name]["enum"]


def test_enums_match_the_domain_and_the_request_models():
    from eos_iqac_accreditation.api import schemas as s
    from eos_iqac_accreditation.domain import accreditation as rules

    assert list(rules.CYCLE_STATUSES) == contract_enum("CycleStatus")
    assert list(rules.RESPONSE_STATUSES) == contract_enum("ResponseStatus")
    assert list(rules.ACTION_STATUSES) == contract_enum("ActionStatus")
    assert list(rules.METRIC_KINDS) == contract_enum("MetricKind")
    assert list(rules.CYCLE_TARGETS) == SCHEMAS["CycleStatusInput"]["properties"]["status"]["enum"]
    assert list(rules.ACTION_TARGETS) == SCHEMAS["ActionItemUpdateInput"]["properties"]["status"]["enum"]

    def enum_of(model, field):
        prop = model.model_json_schema()["properties"][field]
        return next(p["enum"] for p in prop.get("anyOf", [prop]) if "enum" in p)

    assert enum_of(s.MetricInput, "kind") == contract_enum("MetricKind")
    assert enum_of(s.CycleStatusInput, "status") == SCHEMAS["CycleStatusInput"]["properties"]["status"]["enum"]
    assert enum_of(s.EvidenceInput, "kind") == SCHEMAS["EvidenceInput"]["properties"]["kind"]["enum"]
    assert enum_of(s.ReviewInput, "decision") == SCHEMAS["ReviewInput"]["properties"]["decision"]["enum"]
    assert (
        enum_of(s.ActionItemUpdateInput, "status") == SCHEMAS["ActionItemUpdateInput"]["properties"]["status"]["enum"]
    )


def test_the_status_filters_and_the_limit_follow_the_contract():
    from eos_iqac_accreditation.api.router import router

    limit = SPEC["components"]["parameters"]["Limit"]["schema"]
    assert (limit["minimum"], limit["maximum"], limit["default"]) == (1, 100, 20)
    by_path = {(m, r.path): r for r in router.routes for m in r.methods}
    for path in ("/responses", "/action-items"):
        params = {p.name: p for p in by_path[("GET", path)].dependant.query_params}
        meta = params["limit"].field_info.metadata
        assert {type(x).__name__: getattr(x, "ge", None) or getattr(x, "le", None) for x in meta} == {
            "Ge": 1,
            "Le": 100,
        }
        assert params["limit"].field_info.default == 20


INPUTS = {
    "FrameworkInput": "FrameworkInput",
    "MetricInput": "MetricInput",
    "MetricUpdateInput": "MetricUpdateInput",
    "CycleInput": "CycleInput",
    "CycleUpdateInput": "CycleUpdateInput",
    "CycleStatusInput": "CycleStatusInput",
    "ResponseInput": "ResponseInput",
    "EvidenceInput": "EvidenceInput",
    "ReviewInput": "ReviewInput",
    "ActionItemInput": "ActionItemInput",
    "ActionItemUpdateInput": "ActionItemUpdateInput",
}
# The contract's FrameworkInput requires code and name on PATCH too; the module's PATCH takes any of them (README,
# "Assumptions to revisit"), so the update model is checked for the same properties but no required ones.
UPDATE_MODELS = {"FrameworkInput": "FrameworkUpdateInput"}


def property_of(model, name):
    prop = model.model_json_schema()["properties"][name]
    return {k: v for alt in prop.get("anyOf", [prop]) for k, v in alt.items()}


@pytest.mark.parametrize("name", sorted(INPUTS))
def test_each_request_model_has_the_contract_properties_bounds_and_required_fields(name):
    from eos_iqac_accreditation.api import schemas as s

    spec = SCHEMAS[name]
    model = getattr(s, INPUTS[name])
    assert set(model.model_json_schema()["properties"]) == set(spec["properties"])
    assert set(model.model_json_schema().get("required", [])) == set(spec.get("required", [])), name
    for prop, definition in spec["properties"].items():
        mine = property_of(model, prop)
        if "maxLength" in definition:
            assert mine["maxLength"] == definition["maxLength"], (name, prop)
        if "minLength" in definition:
            assert mine["minLength"] >= definition["minLength"], (name, prop)
    if name in UPDATE_MODELS:
        update = getattr(s, UPDATE_MODELS[name])
        assert set(update.model_json_schema()["properties"]) == set(spec["properties"])
        assert not update.model_json_schema().get("required")


def test_the_assignment_and_reference_models_match_the_contract():
    from eos_iqac_accreditation.api import schemas as s

    item = SCHEMAS["AssignmentInput"]["properties"]["assignments"]
    assert set(s.Assignment.model_json_schema()["required"]) == set(item["items"]["required"])
    assert s.AssignmentInput.model_json_schema()["properties"]["assignments"]["minItems"] == item["minItems"] == 1
    reference = SCHEMAS["Reference"]
    assert set(s.Reference.model_json_schema()["required"]) == set(reference["required"])
    assert set(s.Reference.model_json_schema()["properties"]) == set(reference["properties"])


# ---------------------------------------------------------------- every response body against its schema

JSON = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}
FORMATS = {
    "uuid": re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"),
    "date": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "date-time": re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$"),
    "uri": re.compile(r"^https?://"),
}


def resolve(schema: dict) -> dict:
    """A schema with $ref and allOf folded into one object schema."""
    if "$ref" in schema:
        return resolve(SCHEMAS[schema["$ref"].rsplit("/", 1)[1]])
    if "allOf" in schema:
        merged: dict = {"type": "object", "properties": {}, "required": []}
        for part in map(resolve, schema["allOf"]):
            merged["properties"].update(part.get("properties", {}))
            merged["required"] += part.get("required", [])
        return merged
    return schema


def check(value, schema, where="$"):
    schema = resolve(schema)
    types = schema.get("type")
    if types:
        allowed = types if isinstance(types, list) else [types]
        good = any(isinstance(value, JSON[t]) for t in allowed)
        if isinstance(value, bool) and not {"boolean"} & set(allowed):
            good = False
        assert good, f"{where}: {value!r} is not {allowed}"
    if "enum" in schema:
        assert value in schema["enum"], f"{where}: {value!r} not in {schema['enum']}"
    if isinstance(value, str) and schema.get("format") in FORMATS:
        assert FORMATS[schema["format"]].match(value), f"{where}: {value!r} is not a {schema['format']}"
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
    return SPEC["paths"][path][method]["responses"][str(status)]["content"]["application/json"]["schema"]


@pytest.fixture
def bodies(desk):
    """One real response of every operation that returns a body, in a state that fills every optional field."""
    d = desk
    c = d.collecting()
    fid, cid, q = c["framework"]["id"], c["cycle"]["id"], c["q"]
    d.metric(fid, unit="%", guidance="Count graduates", criterion="Criterion 3")
    saved = d.ok(d.put(f"/responses/{q['id']}", {"value": 61.5, "narrative": "Up from 58"}, d.alice))
    link = d.ok(
        d.post(
            f"/responses/{q['id']}/evidence",
            {"title": "Report", "kind": "link", "url": "https://example.edu/r", "note": "p. 2"},
            d.alice,
        )
    )
    ref = d.ok(
        d.post(
            f"/responses/{q['id']}/evidence",
            {"title": "Ref", "kind": "reference", "reference": {"module": "m", "entity": "e", "id": "1"}},
            d.alice,
        )
    )
    submitted = d.ok(d.post(f"/responses/{q['id']}/submit", None, d.alice))
    reviewed = d.ok(d.post(f"/responses/{q['id']}/review", {"decision": "accept", "comment": "Good"}))
    item = d.action_item(cycle_id=cid, metric_id=q["metric_id"], description="d", source="Audit")
    started = d.ok(d.patch(f"/action-items/{item['id']}", {"status": "in_progress"}))
    fresh = d.metric(fid)
    assigned = d.assign(cid, (fresh["id"], d.bob_id, days(3)))
    detail = d.ok(d.get(f"/cycles/{cid}"))
    moved = d.move(cid, "under_review")
    other = d.cycle(fid)
    renamed = d.ok(d.patch(f"/cycles/{other['id']}", {"name": "Renamed"}))
    get = lambda p: d.ok(d.get(p))  # noqa: E731
    return [
        ("/frameworks", "get", 200, get("/frameworks")),
        ("/frameworks", "post", 201, d.framework(description="Full")),
        ("/frameworks/{id}", "patch", 200, d.ok(d.patch(f"/frameworks/{fid}", {"name": "Renamed"}))),
        ("/frameworks/{id}/metrics", "get", 200, get(f"/frameworks/{fid}/metrics")),
        ("/frameworks/{id}/metrics", "post", 201, d.metric(fid, unit="n", guidance="g", criterion="c")),
        ("/metrics/{id}", "patch", 200, d.ok(d.patch(f"/metrics/{fresh['id']}", {"title": "Renamed"}))),
        ("/cycles", "get", 200, get("/cycles")),
        ("/cycles", "post", 201, other),
        ("/cycles/{id}", "get", 200, detail),
        ("/cycles/{id}", "patch", 200, renamed),
        ("/cycles/{id}/status", "post", 200, moved),
        ("/cycles/{id}/assignments", "post", 201, assigned),
        ("/responses", "get", 200, get("/responses")),
        ("/responses/{id}", "get", 200, get(f"/responses/{q['id']}")),
        ("/responses/{id}", "put", 200, saved),
        ("/responses/{id}/submit", "post", 200, submitted),
        ("/responses/{id}/review", "post", 200, reviewed),
        ("/responses/{id}/evidence", "post", 201, link),
        ("/responses/{id}/evidence", "post", 201, ref),
        ("/action-items", "get", 200, get("/action-items")),
        ("/action-items", "post", 201, item),
        ("/action-items/{id}", "patch", 200, started),
        ("/stats/action-items", "get", 200, get("/stats/action-items")),
    ]


def test_every_response_matches_its_contract_schema(bodies):
    for path, method, status, body in bodies:
        check(body, response_schema(path, method, status), f"{method.upper()} {path}")
    # Every operation that returns a body was checked, and the one with a second shape (evidence) in both of them.
    answered = {(p, m) for p, m, _, _ in bodies}
    returning = {
        (p, m)
        for (m_, p), op in operations().items()
        for m in [m_.lower()]
        if any("content" in r for r in op["responses"].values())
    }
    assert answered == returning


# ---------------------------------------------------------------- events


def test_events_are_version_1_and_carry_no_content():
    assert EVENTS["version"] == 1
    for event in EVENTS["events"]:
        assert event["name"].startswith("iqac-accreditation.")
        assert "organisation_id" in event["payload"]
        assert not {"value", "narrative", "comment", "review_comment", "evidence", "url"} & set(event["payload"])


def test_every_published_event_carries_exactly_the_declared_fields(desk):
    d = desk
    c = d.submitted_q()
    d.ok(d.post(f"/responses/{c['q']['id']}/review", {"decision": "accept"}))
    d.ok(d.put(f"/responses/{c['n']['id']}", {"narrative": "x"}, d.bob))
    d.ok(d.post(f"/responses/{c['n']['id']}/submit", None, d.bob))
    d.ok(d.post(f"/responses/{c['n']['id']}/review", {"decision": "accept"}))
    for status, extra in (("under_review", {}), ("submitted", {"submitted_on": "2026-06-01"}), ("closed", {})):
        d.move(c["cycle"]["id"], status, **extra)
    for event in EVENTS["events"]:
        payloads = outbox(event["name"], d.org.id)
        assert payloads, event["name"]
        for payload in payloads:
            assert set(payload) == set(event["payload"]), event["name"]
    assert {e["name"] for e in EVENTS["events"]} == {
        "iqac-accreditation.cycle.status-changed",
        "iqac-accreditation.response.accepted",
    }


def test_the_published_event_carries_the_actor_and_the_tenant(desk):
    from eos_core.db import SessionLocal
    from eos_core.events import OutboxEvent
    from sqlalchemy import select

    d = desk
    c = d.cycle()
    d.move(c["id"], "collecting")
    with SessionLocal() as db:
        row = db.scalars(
            select(OutboxEvent).where(
                OutboxEvent.name == "iqac-accreditation.cycle.status-changed", OutboxEvent.organisation_id == d.org.id
            )
        ).one()
    assert (row.actor, row.organisation_id, row.version) == (d.coordinator_id, d.org.id, 1)


def test_the_module_reads_nothing_the_contract_does_not_declare():
    manifest = yaml.safe_load((CONTRACTS.parent / "module.yaml").read_text(encoding="utf-8"))
    assert manifest["consumes_events"] == []
    assert BASE == "/api/v1/" + manifest["name"]
