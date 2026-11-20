"""Submit a record for approval to platform/workflow, in-process, without importing it.

A module imports only itself and packages/ (module standard), so it cannot call platform/workflow's service. This
module is the shared place it calls instead: `submit()` delegates to `hooks.submit`, which is None until the host
wires it. apps/backend wires it at startup to workflow's create-request use case (the one `POST /requests` runs),
so a module and workflow import nothing of each other, like identity's `hooks.user_limit` and billing.

The call runs in the caller's session and transaction: the request row and its `workflow.request.submitted` event are
written with the caller's own change and committed (or rolled back) by the caller. Nothing here commits.

Only the API process wires the hook. In a process that does not (the event-bus relay, a script), `submit()` raises
WorkflowUnavailableError instead of quietly doing nothing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# WorkflowRefusedError.code values
UNKNOWN_CHAIN = "unknown_chain"  # no active chain with that code in this organisation (its admin creates it)
CHAIN_HAS_NO_STEPS = "chain_has_no_steps"  # the chain exists but has no approval step
INVALID_REQUEST = "invalid_request"  # a field is missing, blank or too long, or entity_type is not a module's

# A module's entity types are namespaced `<module>.<type>` (e.g. `examinations.result_set`) and are RESERVED: only
# `submit()`, in-process, creates a request for one. platform/workflow's `POST /requests` refuses them (403
# `reserved_entity_type`), so a user holding `workflow:request:create` (students and faculty do) cannot make up a
# request whose approval a module would take for its own record (security review N6). An entity type without a dot
# (`leave`, `expense`) is a free-standing request people file through the API; no module acts on its outcome.
ENTITY_TYPE_SEPARATOR = "."


def is_module_entity_type(entity_type: str | None) -> bool:
    """Whether `entity_type` is reserved for a module (`<module>.<type>`): created only through `submit()`."""
    return ENTITY_TYPE_SEPARATOR in (entity_type or "")


class WorkflowError(Exception):
    """Base of the errors `submit()` raises."""


class WorkflowUnavailableError(WorkflowError):
    """The host has not wired platform/workflow into this process (`hooks.submit` is None)."""


class WorkflowRefusedError(WorkflowError):
    """platform/workflow refused the request. `code` is one of the constants above; the message says why."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class WorkflowHooks:
    """Filled by the host at startup (apps/backend wires platform/workflow). `submit` takes the same arguments as
    `submit()` below and returns the request as a dict with at least id, status and current_step_order."""

    submit: Callable[..., dict[str, Any]] | None = None


hooks = WorkflowHooks()


def submit(
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
    """Submit `entity_type`/`entity_id` for approval through the organisation's chain `chain_code`.

    `requested_by` is the user submitting it (the acting user's id): they are the requester, so they cannot approve
    it themselves, and `client_token` is idempotent per requester. Submitting again with the same token returns the
    request created the first time (`created` False) instead of a second one. `context` is stored with the request
    and shown to approvers; keep it to what they need to decide.

    `entity_type` must be the module's own namespaced type, `<module>.<type>` (e.g. `examinations.result_set`):
    those are reserved for `submit()`, and the HTTP API refuses them, so a request for one was always made by the
    module itself. Anything else is refused with INVALID_REQUEST.

    Returns {"id", "status", "current_step_order", "created"}: a new request is "pending" at its chain's first step.
    The outcome arrives later as the event workflow.request.approved or workflow.request.rejected, carrying the
    same request_id (the returned "id"), entity_type and entity_id. A consumer acts on an outcome only when its
    `request_id` is the id `submit()` returned for that record (keep it with the record).

    Raises WorkflowUnavailableError when workflow is not wired in this process, and WorkflowRefusedError (code
    UNKNOWN_CHAIN, CHAIN_HAS_NO_STEPS or INVALID_REQUEST) when workflow refuses it.
    """
    if hooks.submit is None:
        raise WorkflowUnavailableError("platform/workflow is not wired in this process (eos_core.workflow.hooks)")
    if not organisation_id:
        raise WorkflowRefusedError(INVALID_REQUEST, "organisation_id is required")
    module, _, kind = (entity_type or "").partition(ENTITY_TYPE_SEPARATOR)
    if not module.strip() or not kind.strip():
        raise WorkflowRefusedError(
            INVALID_REQUEST, f"entity_type {entity_type!r} must be the module's own, namespaced <module>.<type>"
        )
    if not requested_by:
        raise WorkflowRefusedError(INVALID_REQUEST, "requested_by is required")
    return hooks.submit(
        db,
        organisation_id,
        chain_code=chain_code,
        entity_type=entity_type,
        entity_id=entity_id,
        title=title,
        requested_by=requested_by,
        description=description,
        context=context,
        client_token=client_token,
    )
