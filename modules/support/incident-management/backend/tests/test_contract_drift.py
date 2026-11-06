"""The code's enums, keys and response shapes against the contract files themselves, so a contract change that the
code has not followed fails here instead of passing with hand-copied values."""

import dataclasses
import inspect
from pathlib import Path

import pytest
import yaml
from eos_incident_management.api import schemas
from eos_incident_management.application import service
from eos_incident_management.application.access import PERMISSION_KEYS
from eos_incident_management.application.errors import STATUS_BY_KIND
from eos_incident_management.domain import incidents, problems, stats

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


@pytest.fixture(scope="module")
def openapi():
    return yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def permissions():
    return yaml.safe_load((CONTRACTS / "permissions.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def events():
    return yaml.safe_load((CONTRACTS / "events.yaml").read_text(encoding="utf-8"))


def schema(openapi, name):
    return openapi["components"]["schemas"][name]


def properties(openapi, name) -> list[str]:
    """Properties of a schema, following allOf."""
    body = schema(openapi, name)
    out: list[str] = []
    for part in body.get("allOf", [body]):
        if "$ref" in part:
            out += properties(openapi, part["$ref"].rsplit("/", 1)[1])
        else:
            out += list(part.get("properties", {}))
    return out


def test_enums(openapi):
    assert list(incidents.SEVERITIES) == schema(openapi, "Severity")["enum"]
    assert list(incidents.INCIDENT_STATUSES) == schema(openapi, "IncidentStatus")["enum"]
    assert list(problems.PROBLEM_STATUSES) == schema(openapi, "ProblemStatus")["enum"]
    assert list(problems.RCA_STATUSES) == schema(openapi, "RcaStatus")["enum"]
    assert list(problems.ACTION_STATUSES) == schema(openapi, "ActionStatus")["enum"]
    assert list(incidents.TARGET_STATUSES) == schema(openapi, "IncidentStatusInput")["properties"]["status"]["enum"]
    assert list(problems.TARGET_STATUSES) == schema(openapi, "ProblemStatusInput")["properties"]["status"]["enum"]
    assert list(problems.ACTION_TARGETS) == schema(openapi, "ActionUpdateInput")["properties"]["status"]["enum"]
    assert list(incidents.RELATIONS) == schema(openapi, "ReferenceInput")["properties"]["relation"]["enum"]
    counted = schema(openapi, "OpenCounts")["properties"]["by_status"]["items"]["properties"]["status"]["enum"]
    assert list(incidents.ACTIVE_STATUSES) == counted


def test_request_models_have_exactly_the_contract_fields(openapi):
    pairs = {
        "IncidentInput": schemas.IncidentInput,
        "IncidentUpdateInput": schemas.IncidentUpdateInput,
        "IncidentStatusInput": schemas.IncidentStatusInput,
        "ReferenceInput": schemas.ReferenceInput,
        "ProblemInput": schemas.ProblemInput,
        "ProblemUpdateInput": schemas.ProblemUpdateInput,
        "ProblemStatusInput": schemas.ProblemStatusInput,
        "RcaInput": schemas.RcaInput,
        "ActionInput": schemas.ActionInput,
        "ActionUpdateInput": schemas.ActionUpdateInput,
    }
    for name, model in pairs.items():
        assert list(model.model_fields) == properties(openapi, name), name
        required = set(schema(openapi, name).get("required", []))
        assert {f for f, info in model.model_fields.items() if info.is_required()} == required, name
    body = openapi["paths"]["/incidents/{id}/updates"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert list(schemas.TimelineInput.model_fields) == list(body["properties"])


def test_contract_max_lengths_are_kept(openapi):
    assert schema(openapi, "ServiceLabels")["items"]["maxLength"] == 80
    assert schema(openapi, "IncidentInput")["properties"]["title"]["maxLength"] == 200


def test_open_counts_fields(openapi):
    body = schema(openapi, "OpenCounts")
    assert [f.name for f in dataclasses.fields(stats.OpenCounts)] == list(body["properties"])
    severity_row = body["properties"]["by_severity"]["items"]["properties"]
    status_row = body["properties"]["by_status"]["items"]["properties"]
    assert [f.name for f in dataclasses.fields(stats.SeverityCount)] == list(severity_row)
    assert [f.name for f in dataclasses.fields(stats.StatusCount)] == list(status_row)


@pytest.mark.parametrize(
    ("name", "fn"),
    [
        ("Incident", service.incident_dict),
        ("TimelineUpdate", service.update_dict),
        ("Reference", service.reference_dict),
        ("Problem", service.problem_dict),
        ("Rca", service.rca_dict),
        ("CorrectiveAction", service.action_dict),
    ],
)
def test_serialised_shapes_have_exactly_the_contract_fields(openapi, name, fn):
    source = inspect.getsource(fn)
    keys = [line.strip().split('"')[1] for line in source.splitlines() if line.strip().startswith('"')]
    assert keys == properties(openapi, name), name


def test_detail_shapes_add_the_contract_fields(openapi):
    source = inspect.getsource(service.get_incident) + inspect.getsource(service.get_problem)
    for name in ("IncidentDetail", "ProblemDetail"):
        extra = schema(openapi, name)["allOf"][1]["properties"]
        for field in extra:
            assert f'"{field}"' in source, (name, field)


def test_permission_keys_are_the_catalogue(permissions):
    assert list(PERMISSION_KEYS) == [p["key"] for p in permissions["permissions"]]


def test_every_role_grants_only_catalogue_keys(permissions):
    for role in permissions["roles"]:
        assert set(role["grants"]) <= set(PERMISSION_KEYS), role["name"]


def test_operations_name_the_permission_the_router_checks(openapi):
    """Each operation's summary names its permission; the router's dependency for it holds that key."""
    from eos_incident_management.api.router import router

    by_route = {}
    for route in router.routes:
        path = route.path.replace("{incident_id}", "{id}").replace("{problem_id}", "{id}")
        for dep in route.dependant.dependencies:
            closure = dep.call.__closure__ or ()
            keys = [c.cell_contents for c in closure if isinstance(c.cell_contents, tuple)]
            if keys:
                by_route[(next(iter(route.methods)).lower(), path)] = keys[0]
    for path, item in openapi["paths"].items():
        for method, operation in item.items():
            text = " ".join(str(operation.get(k, "")) for k in ("summary", "description"))
            named = [k for k in PERMISSION_KEYS if k in text]
            assert named, (method, path)
            assert set(named) == set(by_route[(method, path)]), (method, path, named, by_route[(method, path)])


def test_published_event_names_are_the_catalogue(events):
    source = inspect.getsource(service)
    names = {e["name"] for e in events["events"]}
    assert names == {
        "incident-management.incident.reported",
        "incident-management.incident.status-changed",
        "incident-management.incident.severity-changed",
        "incident-management.problem.status-changed",
        "incident-management.problem.rca-published",
        "incident-management.action.assigned",
    }
    for name in names:
        assert f'"{name.removeprefix("incident-management.")}"' in source, name


def test_mapped_statuses_are_ones_the_contract_answers(openapi):
    answered = {
        int(code)
        for path in openapi["paths"].values()
        for operation in path.values()
        for code in operation.get("responses", {})
    }
    assert set(STATUS_BY_KIND.values()) <= answered
