"""#325 Q10: a module submits a record for approval through eos_core.workflow.submit, which the API's startup wires to
platform/workflow's create-request use case. End to end with the installed modules: the organisation's admin creates
the chain through POST /chains (workflow seeds none), a module-side call creates the request in its own transaction,
a replay with the same client_token returns it, and an unknown chain is refused with a code."""

import uuid

import pytest
from eos_backend import workflow_hook
from eos_core import workflow
from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_core.tenant import organisation_scope
from eos_identity.application.service import create_user
from eos_testing import register_and_login
from eos_testing.tenancy import auth
from sqlalchemy import select

CHAIN = "examinations.results"


@pytest.fixture
def org(client):
    """A registered organisation, its admin's headers, a faculty member (the requester) and the chain."""
    slug = f"wf-{uuid.uuid4().hex[:8]}"
    o = register_and_login(client, slug=slug)
    admin = auth(o["token"])
    organisation_id = o["org"]["id"]
    with organisation_scope(organisation_id), SessionLocal() as db:
        faculty = create_user(
            db,
            organisation_id=organisation_id,
            email=f"faculty@{slug}.example.com",
            name="Faculty",
            password="Passw0rd!x",
            roles=["faculty"],
        )
        db.commit()
        faculty_id = faculty.id
    r = client.post(
        "/api/v1/workflow/chains",
        json={
            "code": CHAIN,
            "title": "Result approval",
            "steps": [{"step_order": 1, "name": "Controller of examinations", "approver_role": "org-admin"}],
        },
        headers=admin,
    )
    assert r.status_code == 201, r.text
    return {"id": organisation_id, "admin": admin, "faculty": faculty_id}


def _submit(organisation_id, requested_by, *, commit=True, **overrides):
    """What a module does in its own use case: its session, its organisation scope, its commit."""
    args = {
        "chain_code": CHAIN,
        "entity_type": "examinations.result_set",
        "entity_id": "rs-1",
        "title": "Semester 1 results",
        "requested_by": requested_by,
        "context": {"students": 42},
    } | overrides
    with organisation_scope(organisation_id), SessionLocal() as db:
        out = workflow.submit(db, organisation_id, **args)
        if commit:
            db.commit()
        else:
            db.rollback()
        return out


def _submitted_events(organisation_id):
    with organisation_scope(organisation_id), SessionLocal() as db:
        return [
            e.payload
            for e in db.scalars(
                select(OutboxEvent).where(
                    OutboxEvent.name == "workflow.request.submitted", OutboxEvent.organisation_id == organisation_id
                )
            )
        ]


def test_the_api_startup_wires_the_hook_to_workflow(client):
    assert workflow.hooks.submit is workflow_hook.submit_request


def test_a_module_creates_a_request_at_the_chains_first_step(client, org):
    out = _submit(org["id"], org["faculty"], client_token="results-rs-1")
    assert out["status"] == "pending" and out["current_step_order"] == 1 and out["created"] is True

    r = client.get(f"/api/v1/workflow/requests/{out['id']}", headers=org["admin"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["requester_id"] == org["faculty"] and body["requester_name"] == "Faculty"
    assert body["entity_type"] == "examinations.result_set" and body["entity_id"] == "rs-1"
    assert body["context"] == {"students": 42}
    (event,) = _submitted_events(org["id"])
    assert event["request_id"] == out["id"] and event["chain_code"] == CHAIN and event["requester_id"] == org["faculty"]

    # The admin approves through the API; the module would react to workflow.request.approved.
    a = client.post(f"/api/v1/workflow/requests/{out['id']}/approve", json={}, headers=org["admin"])
    assert a.status_code == 200 and a.json()["status"] == "approved", a.text


def test_the_same_client_token_returns_the_first_request(client, org):
    first = _submit(org["id"], org["faculty"], client_token="results-rs-1")
    again = _submit(org["id"], org["faculty"], client_token="results-rs-1", title="Retried")
    assert again["id"] == first["id"] and again["created"] is False
    assert len(_submitted_events(org["id"])) == 1


def test_an_unknown_chain_is_refused_with_its_code(client, org):
    with pytest.raises(workflow.WorkflowRefusedError) as e:
        _submit(org["id"], org["faculty"], chain_code="examinations.nope")
    assert e.value.code == workflow.UNKNOWN_CHAIN
    assert _submitted_events(org["id"]) == []


def test_a_chain_of_another_organisation_is_unknown_here(client, org):
    other = register_and_login(client, slug=f"wf-{uuid.uuid4().hex[:8]}")
    with pytest.raises(workflow.WorkflowRefusedError) as e:
        _submit(other["org"]["id"], org["faculty"])
    assert e.value.code == workflow.UNKNOWN_CHAIN


def test_the_routes_validation_applies(client, org):
    with pytest.raises(workflow.WorkflowRefusedError) as e:
        _submit(org["id"], org["faculty"], entity_id="x" * 65)
    assert e.value.code == workflow.INVALID_REQUEST and "entity_id" in str(e.value)


def test_the_request_is_part_of_the_callers_transaction(client, org):
    """A caller that rolls back its own change takes the request and its event with it."""
    out = _submit(org["id"], org["faculty"], commit=False)
    r = client.get(f"/api/v1/workflow/requests/{out['id']}", headers=org["admin"])
    assert r.status_code == 404
    assert _submitted_events(org["id"]) == []


def test_a_refusal_leaves_the_callers_transaction_usable(client, org):
    with organisation_scope(org["id"]), SessionLocal() as db:
        with pytest.raises(workflow.WorkflowRefusedError):
            workflow.submit(
                db,
                org["id"],
                chain_code="examinations.nope",
                entity_type="examinations.result_set",
                entity_id="rs-9",
                title="Results",
                requested_by=org["faculty"],
            )
        out = workflow.submit(
            db,
            org["id"],
            chain_code=CHAIN,
            entity_type="examinations.result_set",
            entity_id="rs-9",
            title="Results",
            requested_by=org["faculty"],
        )
        db.commit()
    assert client.get(f"/api/v1/workflow/requests/{out['id']}", headers=org["admin"]).status_code == 200


def test_a_lost_race_on_the_client_token_returns_the_winners_request(client, org, monkeypatch):
    """Two submissions with one token both miss the lookup; the unique index stops the second. On Postgres the insert
    ran under a savepoint, so the winner's request is returned and the caller's transaction goes on; on SQLite (no
    savepoint, see workflow_hook._savepoint) the IntegrityError reaches the caller, which rolls back."""
    from eos_workflow.application import service
    from sqlalchemy.exc import IntegrityError

    first = _submit(org["id"], org["faculty"], client_token="race")
    real, misses = service.find_by_token, []

    def miss_once(*args):
        if not misses:
            misses.append(1)
            return None
        return real(*args)

    monkeypatch.setattr(service, "find_by_token", miss_once)
    with organisation_scope(org["id"]), SessionLocal() as db:
        if db.get_bind().dialect.name == "sqlite":
            with pytest.raises(IntegrityError):
                workflow.submit(
                    db, org["id"], chain_code=CHAIN, entity_type="examinations.result_set", entity_id="rs-1",
                    title="Results", requested_by=org["faculty"], client_token="race",
                )  # fmt: skip
            return
        again = workflow.submit(
            db, org["id"], chain_code=CHAIN, entity_type="examinations.result_set", entity_id="rs-1",
            title="Results", requested_by=org["faculty"], client_token="race",
        )  # fmt: skip
        db.commit()
    assert again["id"] == first["id"] and again["created"] is False


def test_a_student_cannot_create_a_modules_request_over_http_while_submit_still_can(client, org):
    """Security review N6 (#673): the outcome events identify the record by entity_type and entity_id, and students
    hold workflow:request:create. A request a student made up for `examinations.result_set` would, once approved,
    look to examinations like its own result set's approval. A module's namespaced types are reserved for submit()."""
    slug = f"wf-st-{uuid.uuid4().hex[:6]}"
    with organisation_scope(org["id"]), SessionLocal() as db:
        create_user(
            db,
            organisation_id=org["id"],
            email=f"student@{slug}.example.com",
            name="Student",
            password="Passw0rd!x",
            roles=["student"],
        )
        db.commit()
    login = client.post(
        "/api/v1/identity/auth/login", json={"email": f"student@{slug}.example.com", "password": "Passw0rd!x"}
    )
    assert login.status_code == 200, login.text
    student = auth(login.json()["token"])
    forged = {"chain_code": CHAIN, "entity_type": "examinations.result_set", "entity_id": "rs-1", "title": "Results"}

    r = client.post("/api/v1/workflow/requests", json=forged, headers=student)
    assert r.status_code == 403 and r.json()["code"] == "reserved_entity_type", r.text
    assert client.post("/api/v1/workflow/requests", json=forged, headers=org["admin"]).status_code == 403  # anyone
    assert _submitted_events(org["id"]) == []  # nothing was created

    # a free-standing request (no module namespace) is still the student's to file
    own = client.post("/api/v1/workflow/requests", json={**forged, "entity_type": "leave"}, headers=student)
    assert own.status_code == 201, own.text

    # and the module itself still submits its record in-process
    out = _submit(org["id"], org["faculty"], client_token="results-rs-1")
    assert out["created"] is True
    assert [e["entity_type"] for e in _submitted_events(org["id"])].count("examinations.result_set") == 1


def test_submit_refuses_an_entity_type_that_is_not_a_modules_own(client, org):
    for entity_type in ("result_set", ".result_set", "examinations.", ""):
        with pytest.raises(workflow.WorkflowRefusedError) as e:
            _submit(org["id"], org["faculty"], entity_type=entity_type)
        assert e.value.code == workflow.INVALID_REQUEST
