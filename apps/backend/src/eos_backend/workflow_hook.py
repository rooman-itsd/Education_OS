"""platform/workflow's create-request use case behind eos_core.workflow.hooks.submit (wired in main.lifespan).

The same validation, chain lookup, idempotency and event as `POST /api/v1/workflow/requests`: the body is checked by
the route's own input model, then `service.create_request` runs in the caller's session. A refusal is raised before
anything is written, so the caller's transaction stays usable; on Postgres the insert runs under a savepoint, so a
lost race on the client_token does too. Nothing here commits.
"""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any

from eos_core.workflow import CHAIN_HAS_NO_STEPS, INVALID_REQUEST, UNKNOWN_CHAIN, WorkflowRefusedError
from eos_workflow.api.router import NewRequestInput
from eos_workflow.application import service
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

# service.WorkflowError statuses create_request raises, as the codes eos_core.workflow promises its callers
_CODES = {404: UNKNOWN_CHAIN, 400: CHAIN_HAS_NO_STEPS, 422: INVALID_REQUEST}


def _sqlite(db) -> bool:
    return db.get_bind().dialect.name == "sqlite"


def _savepoint(db):
    """SQLite's driver sends no BEGIN before a SAVEPOINT, so releasing one would commit the caller's work with it.
    There (tests, local dev) a lost token race is left as the IntegrityError, and the caller rolls back."""
    return nullcontext() if _sqlite(db) else db.begin_nested()


def submit_request(
    db,
    organisation_id: str,
    *,
    chain_code: str,
    entity_type: str,
    entity_id: str,
    title: str,
    requested_by: str,
    description: str | None = None,
    context: dict | None = None,
    client_token: str | None = None,
) -> dict[str, Any]:
    try:
        body = NewRequestInput(
            chain_code=chain_code,
            entity_type=entity_type,
            entity_id=entity_id,
            title=title,
            description=description,
            client_token=client_token,
            context=context,
        )
    except ValidationError as e:
        fields = ", ".join(".".join(str(p) for p in err["loc"]) for err in e.errors())
        raise WorkflowRefusedError(INVALID_REQUEST, f"invalid workflow request: {fields}") from e
    try:
        with _savepoint(db):
            req, created = service.create_request(
                db,
                organisation_id,
                chain_code=body.chain_code,
                entity_type=body.entity_type,
                entity_id=body.entity_id,
                title=body.title,
                requester_id=requested_by,
                requester_name=None,
                description=body.description,
                client_token=body.client_token,
                context_data=body.context,
            )
    except service.WorkflowError as e:
        raise WorkflowRefusedError(_CODES.get(e.status, INVALID_REQUEST), str(e)) from e
    except IntegrityError:
        # Another submission with this token won the race (unique per requester): return it, as the route does.
        req = None if _sqlite(db) else service.find_by_token(db, organisation_id, requested_by, body.client_token)
        if req is None:
            raise
        created = False
    return {"id": req.id, "status": req.status, "current_step_order": req.current_step_order, "created": created}
