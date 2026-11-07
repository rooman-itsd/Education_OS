"""The code matches contracts/: every operation has a route and every route is in the contract; each operation asks
for the permission its summary names; permission keys, roles, enums and error statuses are the contract's; every
published event carries exactly the fields events.yaml lists; and every response has the fields of its schema."""

import re
from pathlib import Path

import pytest
import yaml
from conftest import BASE, days, outbox

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
SPEC = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))
PERMISSIONS = yaml.safe_load((CONTRACTS / "permissions.yaml").read_text(encoding="utf-8"))
EVENTS = yaml.safe_load((CONTRACTS / "events.yaml").read_text(encoding="utf-8"))
METHODS = ("get", "post", "patch", "put", "delete")
OPERATIONS = [(m, path) for path, item in SPEC["paths"].items() for m in METHODS if m in item]
UUID = "00000000-0000-4000-8000-000000000000"


def test_routes_match_the_contract_operations():
    from eos_rti.api.router import router

    contract = {(m.upper(), path) for m, path in OPERATIONS}
    routes = set()
    for route in router.routes:
        path = re.sub(r"\{(request|referral)_id\}", "{id}", route.path)
        routes |= {(m, path) for m in route.methods}
    assert routes == contract
    assert len(contract) == 14


def test_permission_keys_and_roles_are_the_catalogue():
    from eos_rti.application import access

    keys = {p["key"] for p in PERMISSIONS["permissions"]}
    assert keys == set(access.PERMISSION_KEYS)
    for role in PERMISSIONS["roles"]:
        assert set(role["grants"]) <= keys, role["name"]
    assert {r["name"] for r in PERMISSIONS["roles"]} == {
        "rti-officer",
        "rti-custodian",
        "rti-appellate-authority",
        "rti-viewer",
    }


def _needs(method: str, path: str) -> set[str]:
    """The permission keys the operation's summary names: `Permission rti:a:b.` or `Permission rti:a:b or rti:c:d.`"""
    text = SPEC["paths"][path][method]["summary"] + " " + SPEC["paths"][path][method].get("description", "")
    found = re.search(r"Permission (rti:\w+:\w+(?: or rti:\w+:\w+)*)\.", text)
    assert found, (method, path)
    return set(re.findall(r"rti:\w+:\w+", found.group(1)))


def test_every_operation_names_a_permission():
    for method, path in OPERATIONS:
        assert _needs(method, path) <= {p["key"] for p in PERMISSIONS["permissions"]}, (method, path)


@pytest.mark.parametrize(("method", "path"), OPERATIONS, ids=[f"{m.upper()} {p}" for m, p in OPERATIONS])
def test_each_operation_asks_for_exactly_its_permission(client, org, method, path):
    needs = _needs(method, path)
    url = BASE + path.replace("{id}", UUID)
    call = lambda headers: client.request(method.upper(), url, json={} if method != "get" else None, headers=headers)  # noqa: E731
    assert call({}).status_code == 401
    assert call({"Authorization": "Bearer not-a-token"}).status_code == 401
    for role in PERMISSIONS["roles"]:
        _, headers = org.user(role["name"])
        status = call(headers).status_code
        if needs & set(role["grants"]):
            assert status not in (401, 403), (role["name"], method, path, status)
        else:
            assert status == 403, (role["name"], method, path, status)
    _, nobody = org.user("student")
    assert call(nobody).status_code == 403


def test_a_token_without_an_organisation_is_refused(client):
    from eos_core.security import create_token

    token = create_token(user_id=UUID, organisation_id=None, roles=["rti-officer"])
    assert client.get(f"{BASE}/requests", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def _enum(name: str) -> tuple:
    return tuple(SPEC["components"]["schemas"][name]["enum"])


def test_enums_are_the_contracts():
    from eos_rti.domain import requests as r

    assert r.REQUEST_STATUSES == _enum("RequestStatus")
    assert r.CLOSURES == _enum("Closure")
    assert r.CHANNELS == _enum("Channel")
    assert r.RESPONSE_TYPES == _enum("ResponseType")
    assert r.APPEAL_OUTCOMES == _enum("AppealOutcome")
    schemas = SPEC["components"]["schemas"]
    assert r.FEE_STATUSES == tuple(schemas["Fee"]["properties"]["status"]["enum"])
    assert r.REFERRAL_STATUSES == tuple(schemas["Referral"]["properties"]["status"]["enum"])
    assert r.REFERRAL_STATUSES == tuple(schemas["CustodianReferral"]["properties"]["status"]["enum"])


def test_error_statuses_are_the_ones_the_contract_documents():
    """Each non-2xx answer the contract lists. Every one of them is produced by a test in test_api_requests.py and
    test_api_flow.py; 401 and 403 are checked for every operation above, 422 for every body and parameter."""
    documented = {
        (m.upper(), p): sorted(int(s) for s in SPEC["paths"][p][m]["responses"] if int(s) >= 400) for m, p in OPERATIONS
    }
    assert {k: v for k, v in documented.items() if v} == {
        ("GET", "/requests/{id}"): [404],
        ("PATCH", "/requests/{id}"): [409],
        ("POST", "/requests/{id}/assign"): [409],
        ("POST", "/requests/{id}/referrals"): [409],
        ("POST", "/referrals/{id}/reply"): [404, 409],
        ("POST", "/requests/{id}/respond"): [409, 422],
        ("POST", "/requests/{id}/transfer"): [409],
        ("POST", "/requests/{id}/appeal"): [409],
        ("POST", "/requests/{id}/appeal-decision"): [409],
        ("POST", "/requests/{id}/close"): [409],
    }


def test_the_contract_statuses_come_out(desk):
    """404, 409 and 422 as the contract describes them, for one operation each."""
    r = desk.request()
    respond = {"type": "refused", "summary": "No.", "dispatched_on": days(0), "dispatch_mode": "post"}
    assert desk.get(f"/requests/{UUID}").status_code == 404
    assert desk.post(f"/requests/{r['id']}/close").status_code == 409
    assert desk.post(f"/requests/{r['id']}/respond", respond).status_code == 409  # not assigned
    desk.ok(desk.post(f"/requests/{r['id']}/assign", {"officer_id": desk.officer_id}))
    assert desk.post(f"/requests/{r['id']}/respond", respond).status_code == 422  # grounds missing


def test_event_names_and_payloads_match_events_yaml(desk, org):
    assert EVENTS["version"] == 1
    assert [e["name"] for e in EVENTS["events"]] == ["rti.request.received", "rti.request.closed"]
    done = desk.responded()
    desk.ok(
        desk.post(f"/requests/{done['id']}/appeal", {"filed_on": days(0), "grounds": "Incomplete."}, desk.appellate)
    )
    desk.ok(
        desk.post(
            f"/requests/{done['id']}/appeal-decision",
            {"outcome": "dismissed", "decision_note": "No merit.", "decided_on": days(0)},
            desk.appellate,
        )
    )
    desk.ok(desk.post(f"/requests/{done['id']}/close"))
    for event in EVENTS["events"]:
        payloads = outbox(event["name"], org.id)
        assert payloads, event["name"]
        assert set(payloads[-1]) == set(event["payload"]), event["name"]


# ---------------------------------------------------------------- response shapes


def _resolve(schema: dict) -> dict:
    """The schema with $ref followed and allOf merged."""
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[1]
        return _resolve(SPEC["components"]["schemas"][name])
    if "allOf" in schema:
        merged: dict = {"type": "object", "properties": {}, "required": []}
        for part in map(_resolve, schema["allOf"]):
            merged["properties"].update(part.get("properties", {}))
            merged["required"] += part.get("required", [])
        return merged
    return schema


PATTERNS = {
    "date": r"^\d{4}-\d{2}-\d{2}$",
    "date-time": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$",
    "uuid": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
}


def conforms(schema: dict, value, path: str = "$") -> list[str]:
    """Why `value` does not fit `schema` (empty when it does). Checks types, enums, formats, required fields and
    fields the schema does not list."""
    schema = _resolve(schema)
    if "oneOf" in schema:
        tries = [conforms(option, value, path) for option in schema["oneOf"]]
        return [] if any(not t for t in tries) else [f"{path}: no oneOf option fits: {tries}"]
    types = schema.get("type", "object" if "properties" in schema else None)
    types = types if isinstance(types, list) else [types]
    if value is None:
        return [] if "null" in types else [f"{path}: null is not allowed"]
    problems: list[str] = []
    if "object" in types and isinstance(value, dict):
        props = schema.get("properties", {})
        problems += [f"{path}.{k}: missing" for k in schema.get("required", []) if k not in value]
        problems += [f"{path}.{k}: not in the contract" for k in value if k not in props]
        for k, v in value.items():
            if k in props:
                problems += conforms(props[k], v, f"{path}.{k}")
    elif "array" in types and isinstance(value, list):
        for i, v in enumerate(value):
            problems += conforms(schema["items"], v, f"{path}[{i}]")
    elif "string" in types and isinstance(value, str):
        if "enum" in schema and value not in schema["enum"]:
            problems.append(f"{path}: {value!r} is not one of {schema['enum']}")
        if schema.get("format") in PATTERNS and not re.match(PATTERNS[schema["format"]], value):
            problems.append(f"{path}: {value!r} is not a {schema['format']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            problems.append(f"{path}: {value!r} does not match {schema['pattern']}")
    elif "integer" in types and isinstance(value, int) and not isinstance(value, bool):
        pass
    elif "boolean" in types and isinstance(value, bool):
        pass
    else:
        problems.append(f"{path}: {value!r} is not a {types}")
    return problems


def check(method: str, path: str, response, status: int) -> None:
    assert response.status_code == status, (method, path, response.status_code, response.text)
    schema = SPEC["paths"][path][method]["responses"][str(status)]["content"]["application/json"]["schema"]
    assert conforms(schema, response.json()) == [], (method, path)


def test_every_response_has_the_fields_of_its_schema(desk, org):
    check(
        "post",
        "/requests",
        desk.post(
            "/requests",
            {
                "received_via": "email",
                "received_on": days(-1),
                "applicant": {"name": "Asha Verma", "person_id": UUID},
                "subject": "Records",
                "information_sought": "All of them.",
                "fee": {"status": "paid", "amount": {"amount": "10"}, "mode": "cash", "receipt_reference": "R-1"},
            },
        ),
        201,
    )
    r = desk.request()
    check("get", "/requests", desk.get("/requests"), 200)
    check("get", "/requests/{id}", desk.get(f"/requests/{r['id']}"), 200)
    check("patch", "/requests/{id}", desk.patch(f"/requests/{r['id']}", {"subject": "A new subject"}), 200)
    check(
        "post", "/requests/{id}/assign", desk.post(f"/requests/{r['id']}/assign", {"officer_id": desk.officer_id}), 200
    )
    f = desk.post(
        f"/requests/{r['id']}/referrals",
        {"custodian_id": desk.custodian_id, "question": "A question?", "due_on": days(5)},
    )
    check("post", "/requests/{id}/referrals", f, 201)
    check("get", "/referrals", desk.get("/referrals"), 200)  # Referral items
    check("get", "/referrals", desk.get("/referrals", desk.custodian), 200)  # CustodianReferral items
    check(
        "post",
        "/referrals/{id}/reply",
        desk.post(f"/referrals/{f.json()['id']}/reply", {"reply": "Answer."}, desk.custodian),
        200,
    )
    check(
        "post",
        "/requests/{id}/respond",
        desk.post(
            f"/requests/{r['id']}/respond",
            {
                "type": "partly_provided",
                "summary": "Some.",
                "grounds": "Others.",
                "dispatched_on": days(0),
                "dispatch_mode": "post",
            },
        ),
        200,
    )
    check(
        "post",
        "/requests/{id}/appeal",
        desk.post(f"/requests/{r['id']}/appeal", {"filed_on": days(0), "grounds": "Incomplete."}, desk.appellate),
        200,
    )
    check(
        "post",
        "/requests/{id}/appeal-decision",
        desk.post(
            f"/requests/{r['id']}/appeal-decision",
            {"outcome": "upheld", "decision_note": "Release more.", "decided_on": days(0)},
            desk.appellate,
        ),
        200,
    )
    check("post", "/requests/{id}/close", desk.post(f"/requests/{r['id']}/close"), 200)
    t = desk.request()
    transferred = desk.post(
        f"/requests/{t['id']}/transfer",
        {"authority_name": "Council", "authority_address": "Delhi", "transferred_on": days(0), "reason": "Wrong body."},
    )
    check("post", "/requests/{id}/transfer", transferred, 200)
    desk.request(received_on=days(-40))
    check("get", "/stats/nearing-deadline", desk.get("/stats/nearing-deadline", desk.viewer), 200)
    assert conforms({"$ref": "#/components/schemas/NearingDeadline"}, {"within_days": 7})  # the checker does notice


def test_the_checker_notices_a_field_that_is_not_in_the_contract(desk):
    r = desk.request()
    bad = {**r, "extra": 1}
    assert conforms({"$ref": "#/components/schemas/Request"}, bad) == ["$.extra: not in the contract"]
    assert conforms({"$ref": "#/components/schemas/Request"}, {k: v for k, v in r.items() if k != "number"})
