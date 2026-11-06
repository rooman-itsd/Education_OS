"""Drift between contracts/ and the code: every operation in openapi.yaml has a route with the permissions the contract
names, and every route is in the contract; the documented error statuses are answered; request and response bodies have
the contract's fields; enums match; every published event payload carries exactly the fields events.yaml lists."""

import re
from pathlib import Path

import pytest
import yaml
from conftest import DESCRIPTION, outbox

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
SPEC = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))
METHODS = {"get", "post", "patch", "put", "delete"}
OPERATIONS = {(m.upper(), path): op for path, item in SPEC["paths"].items() for m, op in item.items() if m in METHODS}
SCHEMAS = SPEC["components"]["schemas"]
KEY = re.compile(r"grievance:(?:case|appeal|committee|stats):[a-z-]+")


def _path(route_path: str) -> str:
    return re.sub(r"\{(committee_id|case_id)\}", "{id}", route_path)


def _routes():
    from eos_grievance.api.router import router

    out = {}
    for route in router.routes:
        for method in route.methods:
            out[(method, _path(route.path))] = route
    return out


def test_routes_match_the_contract_operations():
    assert set(_routes()) == set(OPERATIONS)
    assert len(OPERATIONS) == 19


def test_each_route_demands_the_permissions_the_contract_names():
    routes = _routes()
    for key, op in OPERATIONS.items():
        named = set(KEY.findall(op["summary"]))
        assert named, key
        guards = [d.call.permissions for d in routes[key].dependant.dependencies if hasattr(d.call, "permissions")]
        assert len(guards) == 1, key
        assert set(guards[0]) == named, (key, guards[0], named)


def test_permission_keys_exist_in_the_catalogue():
    catalogue = yaml.safe_load((CONTRACTS / "permissions.yaml").read_text(encoding="utf-8"))
    declared = {p["key"] for p in catalogue["permissions"]}
    from eos_grievance.application.access import PERMISSION_KEYS

    assert declared == set(PERMISSION_KEYS)
    granted = {g for role in catalogue["roles"] for g in role["grants"]}
    assert granted == declared


def test_success_statuses_match_the_contract():
    routes = _routes()
    for key, op in OPERATIONS.items():
        success = {int(code) for code in op["responses"] if code.startswith("2")}
        assert (routes[key].status_code or 200) in success, key


def _flatten(name: str) -> tuple[set[str], set[str]]:
    """(properties, required) of a component schema, following allOf."""
    schema = SCHEMAS[name]
    props, required = set(schema.get("properties", {})), set(schema.get("required", []))
    for part in schema.get("allOf", []):
        if "$ref" in part:
            p, r = _flatten(part["$ref"].rsplit("/", 1)[1])
        else:
            p, r = set(part.get("properties", {})), set(part.get("required", []))
        props, required = props | p, required | r
    return props, required


@pytest.mark.parametrize(
    ("schema", "model"),
    [
        ("CommitteeInput", "CommitteeInput"),
        ("CommitteeUpdateInput", "CommitteeUpdateInput"),
        ("GrievanceInput", "GrievanceInput"),
        ("Respondent", "Respondent"),
        ("Member", "Member"),
        ("UpdateInput", "UpdateInput"),
        ("AppealInput", "AppealInput"),
        ("StatusInput", "StatusInput"),
        ("ProceedingInput", "ProceedingInput"),
        ("DecisionInput", "DecisionInput"),
        ("TransferInput", "TransferInput"),
        ("AppealDecisionInput", "AppealDecisionInput"),
    ],
)
def test_request_bodies_have_the_contract_fields_and_lengths(schema, model):
    from eos_grievance.api import schemas as s

    cls = getattr(s, model)
    props, required = _flatten(schema)
    assert set(cls.model_fields) == props
    assert {n for n, f in cls.model_fields.items() if f.is_required()} == required
    ours = cls.model_json_schema()["properties"]
    for name, spec in SCHEMAS[schema].get("properties", {}).items():
        if "minLength" in spec:
            assert _bound(ours[name], "minLength") == spec["minLength"], (schema, name)
        if "maxLength" in spec:
            assert _bound(ours[name], "maxLength") <= spec["maxLength"], (schema, name)


def _bound(spec: dict, key: str):
    if key in spec:
        return spec[key]
    for part in spec.get("anyOf", []):
        if key in part:
            return part[key]
    return None


def test_the_withdraw_body_is_optional_in_the_contract_and_in_the_code(campus):
    op = OPERATIONS[("POST", "/me/grievances/{id}/withdraw")]
    assert not op["requestBody"].get("required")
    c = campus
    case = c.file()
    assert c.post(f"/me/grievances/{case['id']}/withdraw", None, c.complainant).status_code == 200


def test_enums_match_the_contract():
    from eos_grievance.domain import cases as d

    assert tuple(SCHEMAS["Track"]["enum"]) == d.TRACKS
    assert tuple(SCHEMAS["CommitteeKind"]["enum"]) == d.COMMITTEE_KINDS
    assert tuple(SCHEMAS["MemberRole"]["enum"]) == d.MEMBER_ROLES
    assert tuple(SCHEMAS["CaseStatus"]["enum"]) == d.STATUSES
    assert tuple(SCHEMAS["Closure"]["enum"]) == d.CLOSURES
    assert tuple(SCHEMAS["DecisionOutcome"]["enum"]) == d.DECISION_OUTCOMES
    assert tuple(SCHEMAS["AppealOutcome"]["enum"]) == d.APPEAL_OUTCOMES
    assert tuple(SCHEMAS["ProceedingInput"]["properties"]["kind"]["enum"]) == d.PROCEEDING_KINDS
    moves = {to for _, to in d.STATUS_MOVES}
    assert set(SCHEMAS["StatusInput"]["properties"]["status"]["enum"]) == moves
    from eos_grievance.api import schemas as s

    assert s.GrievanceInput.model_json_schema()["properties"]["track"]["enum"] == list(d.TRACKS)
    assert s.CommitteeInput.model_json_schema()["properties"]["kind"]["enum"] == list(d.COMMITTEE_KINDS)
    assert (
        s.StatusInput.model_json_schema()["properties"]["status"]["enum"]
        == SCHEMAS["StatusInput"]["properties"]["status"]["enum"]
    )


def _check_shape(name: str, body: dict) -> None:
    props, required = _flatten(name)
    assert required <= set(body), (name, required - set(body))
    assert set(body) <= props, (name, set(body) - props)


def test_response_bodies_have_the_contract_fields(campus, monkeypatch):
    c = campus
    monkeypatch.setenv("GRIEVANCE_APPEAL_WINDOW_DAYS", "7")
    monkeypatch.setenv("GRIEVANCE_STUDENT_GRIEVANCE_ACKNOWLEDGE_DAYS", "2")
    _check_shape("Committee", c.committees["sgrc"])
    _check_shape("Committee", c.ok(c.get("/committees", c.complainant))[0])
    mine = c.file(incident_date="2026-11-01", respondent={"description": "A name"})
    _check_shape("MyGrievance", mine)
    page = c.ok(c.get("/me/grievances", c.complainant))
    _check_shape("MyGrievancePage", page)
    _check_shape("MyGrievance", page["items"][0])
    c.move(mine["id"], "acknowledged")
    proceeding = {"kind": "hearing", "held_on": "2026-11-04", "summary": "Summary."}
    _check_shape("Proceeding", c.ok(c.post(f"/grievances/{mine['id']}/proceedings", proceeding, c.member())))
    _check_shape("Update", c.ok(c.post(f"/grievances/{mine['id']}/updates", {"body": "Hello."}, c.member())))
    c.move(mine["id"], "under_inquiry")
    decided = c.ok(
        c.post(f"/grievances/{mine['id']}/decision", {"outcome": "upheld", "findings": "Found."}, c.member())
    )
    _check_shape("GrievanceDetail", decided)
    _check_shape("Decision", decided["decision"])
    listed = c.ok(c.get("/grievances", c.member()))
    _check_shape("GrievancePage", listed)
    _check_shape("Grievance", listed["items"][0])
    assert listed["items"][0]["respondent"] == {"description": "A name"}
    _check_shape("MyGrievanceDetail", c.ok(c.get(f"/me/grievances/{mine['id']}", c.complainant)))
    appealed = c.ok(c.post(f"/me/grievances/{mine['id']}/appeal", {"reason": "I disagree with it."}, c.complainant))
    _check_shape("MyGrievance", appealed)
    body = {"outcome": "dismissed", "outcome_note": "No grounds."}
    detail = c.ok(c.post(f"/grievances/{mine['id']}/appeal-decision", body, c.member("ombudsperson")))
    _check_shape("GrievanceDetail", detail)
    _check_shape("Appeal", detail["appeal"])
    _check_shape("GrievanceDetail", c.ok(c.get(f"/grievances/{mine['id']}", c.member())))
    _check_shape(
        "Grievance", c.ok(c.post(f"/grievances/{mine['id']}/status", {"status": "closed"}, c.member("ombudsperson")))
    )
    other = c.file()
    target = c.committees["icc"]["id"]
    _check_shape(
        "Grievance",
        c.ok(c.post(f"/grievances/{other['id']}/transfer", {"committee_id": target, "reason": "Wrong"}, c.member())),
    )
    stats = c.ok(c.get("/stats/open-by-committee", c.coordinator))
    _check_shape("OpenByCommittee", stats)
    row_props = SCHEMAS["OpenByCommittee"]["properties"]["committees"]["items"]
    assert set(row_props["required"]) <= set(stats["committees"][0]) <= set(row_props["properties"])
    by_status = row_props["properties"]["by_status"]["items"]
    busy = next(x for x in stats["committees"] if x["by_status"])
    assert set(busy["by_status"][0]) == set(by_status["properties"])
    tracks = c.ok(c.get("/stats/open", c.viewer))
    _check_shape("OpenByTrack", tracks)
    track_props = SCHEMAS["OpenByTrack"]["properties"]["tracks"]["items"]
    assert set(tracks["tracks"][0]) == set(track_props["properties"])


def _scenarios():
    """One request per documented error status: (method, path) -> {status: callable(campus) -> response}."""

    def final_case(c):
        case = c.file()
        c.ok(c.post(f"/me/grievances/{case['id']}/withdraw", None, c.complainant))
        return case["id"]

    def decided(c):
        case = c.file()
        c.decide(case["id"])
        return case["id"]

    def fresh(c):
        return c.file()["id"]

    ok_proceeding = {"kind": "note", "held_on": "2026-11-04", "summary": "A note."}
    return {
        ("POST", "/committees"): {409: lambda c: c.post("/committees", {"name": "sgrc committee", "kind": "sgrc"})},
        ("PATCH", "/committees/{id}"): {
            409: lambda c: (fresh(c), c.patch(f"/committees/{c.committees['sgrc']['id']}", {"active": False}))[1]
        },
        ("POST", "/me/grievances"): {
            422: lambda c: (
                c.ok(c.patch(f"/committees/{c.committees['icc']['id']}", {"active": False})),
                c.post(
                    "/me/grievances",
                    {"track": "sexual_harassment", "category": "x", "description": DESCRIPTION},
                    c.complainant,
                ),
            )[1]
        },
        ("GET", "/me/grievances/{id}"): {404: lambda c: c.get(f"/me/grievances/{fresh(c)}", c.other)},
        ("POST", "/me/grievances/{id}/updates"): {
            409: lambda c: c.post(f"/me/grievances/{final_case(c)}/updates", {"body": "late"}, c.complainant)
        },
        ("POST", "/me/grievances/{id}/withdraw"): {
            409: lambda c: c.post(f"/me/grievances/{decided(c)}/withdraw", None, c.complainant)
        },
        ("POST", "/me/grievances/{id}/appeal"): {
            409: lambda c: c.post(
                f"/me/grievances/{decided(c)}/appeal", {"reason": "I disagree strongly."}, c.complainant
            )
        },
        ("GET", "/grievances/{id}"): {404: lambda c: c.get(f"/grievances/{fresh(c)}", c.member("icc"))},
        ("POST", "/grievances/{id}/status"): {
            409: lambda c: c.post(f"/grievances/{fresh(c)}/status", {"status": "closed"}, c.member()),
            422: lambda c: c.post(f"/grievances/{fresh(c)}/status", {"status": "not_admitted"}, c.member()),
        },
        ("POST", "/grievances/{id}/updates"): {
            409: lambda c: c.post(f"/grievances/{final_case(c)}/updates", {"body": "late"}, c.member())
        },
        ("POST", "/grievances/{id}/proceedings"): {
            409: lambda c: c.post(f"/grievances/{fresh(c)}/proceedings", ok_proceeding, c.member())
        },
        ("POST", "/grievances/{id}/decision"): {
            409: lambda c: c.post(
                f"/grievances/{fresh(c)}/decision", {"outcome": "upheld", "findings": "abc"}, c.member()
            )
        },
        ("POST", "/grievances/{id}/transfer"): {
            409: lambda c: c.post(
                f"/grievances/{decided(c)}/transfer",
                {"committee_id": c.committees["icc"]["id"], "reason": "abc"},
                c.member(),
            )
        },
        ("POST", "/grievances/{id}/appeal-decision"): {
            409: lambda c: c.post(
                f"/grievances/{fresh(c)}/appeal-decision",
                {"outcome": "upheld", "outcome_note": "abc"},
                c.member("sgrc"),
            )
        },
    }


def test_every_documented_error_status_is_covered_and_answered(campus):
    scenarios = _scenarios()
    documented = {
        key: {int(code) for code in op["responses"] if code[0] == "4"}
        for key, op in OPERATIONS.items()
        if any(code[0] == "4" for code in op["responses"])
    }
    assert {k: set(v) for k, v in scenarios.items()} == documented
    for key, by_status in scenarios.items():
        for status, request in by_status.items():
            response = request(campus)
            assert response.status_code == status, (key, status, response.text)


def test_events_payloads_match_events_yaml(campus):
    c = campus
    spec = yaml.safe_load((CONTRACTS / "events.yaml").read_text(encoding="utf-8"))
    case = c.file()
    c.ok(c.post(f"/me/grievances/{case['id']}/withdraw", None, c.complainant))
    assert {e["name"] for e in spec["events"]} == {"grievance.case.filed", "grievance.case.closed"}
    for event in spec["events"]:
        payloads = outbox(event["name"], c.org.id)
        assert payloads, event["name"]
        assert set(payloads[-1]) == set(event["payload"]), event["name"]
    closures = SCHEMAS["Closure"]["enum"]
    assert outbox("grievance.case.closed", c.org.id)[-1]["closure"] in closures
