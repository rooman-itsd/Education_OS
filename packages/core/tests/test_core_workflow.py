"""eos_core.workflow: the shared place a module submits a record for approval without importing platform/workflow.
Unwired it refuses loudly; wired it hands every argument to the host's hook and returns what the hook returns."""

import pytest
from eos_core import workflow
from eos_core.workflow import (
    INVALID_REQUEST,
    UNKNOWN_CHAIN,
    WorkflowError,
    WorkflowRefusedError,
    WorkflowUnavailableError,
)

ARGS = {
    "chain_code": "examinations.results",
    "entity_type": "examinations.result_set",
    "entity_id": "rs-1",
    "title": "Semester 1 results",
    "requested_by": "user-1",
}


@pytest.fixture(autouse=True)
def _unwired(monkeypatch):
    monkeypatch.setattr(workflow.hooks, "submit", None)


def test_unwired_submit_raises_unavailable():
    assert workflow.hooks.submit is None
    with pytest.raises(WorkflowUnavailableError) as e:
        workflow.submit(object(), "org-1", **ARGS)
    assert isinstance(e.value, WorkflowError)


def test_wired_submit_passes_every_argument_and_returns_the_hooks_result(monkeypatch):
    calls = []
    db = object()

    def hook(session, organisation_id, **kwargs):
        calls.append((session, organisation_id, kwargs))
        return {"id": "req-1", "status": "pending", "current_step_order": 1, "created": True}

    monkeypatch.setattr(workflow.hooks, "submit", hook)
    out = workflow.submit(db, "org-1", **ARGS, description="d", context={"marks": 3}, client_token="t-1")

    assert out == {"id": "req-1", "status": "pending", "current_step_order": 1, "created": True}
    assert calls == [
        (db, "org-1", {**ARGS, "description": "d", "context": {"marks": 3}, "client_token": "t-1"})
    ]  # the caller's own session: the request is written in its transaction


def test_optional_arguments_default_to_none(monkeypatch):
    seen = {}
    monkeypatch.setattr(workflow.hooks, "submit", lambda db, org, **kw: seen.update(kw) or {})
    workflow.submit(None, "org-1", **ARGS)
    assert seen["description"] is None and seen["context"] is None and seen["client_token"] is None


def test_the_hooks_refusal_reaches_the_caller_with_its_code(monkeypatch):
    def refuse(db, org, **kw):
        raise WorkflowRefusedError(UNKNOWN_CHAIN, "Approval chain 'examinations.results' not found or inactive")

    monkeypatch.setattr(workflow.hooks, "submit", refuse)
    with pytest.raises(WorkflowRefusedError) as e:
        workflow.submit(None, "org-1", **ARGS)
    assert e.value.code == UNKNOWN_CHAIN and isinstance(e.value, WorkflowError)


@pytest.mark.parametrize("missing", ["organisation_id", "requested_by"])
def test_no_organisation_or_requester_is_refused_before_the_hook(monkeypatch, missing):
    monkeypatch.setattr(workflow.hooks, "submit", lambda *a, **k: pytest.fail("hook called"))
    args = {**ARGS, "requested_by": "" if missing == "requested_by" else "user-1"}
    with pytest.raises(WorkflowRefusedError) as e:
        workflow.submit(None, "" if missing == "organisation_id" else "org-1", **args)
    assert e.value.code == INVALID_REQUEST
