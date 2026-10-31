"""Workflow application service: chains, requests, approval advancement, delegation, and events."""

from __future__ import annotations

from datetime import UTC, timedelta

from eos_core import events
from eos_core.db import scoped, utcnow
from eos_core.tenant import organisation_scope
from eos_identity.application.service import get_user
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..domain.models import (
    ACTION_APPROVED,
    ACTION_DELEGATED,
    ACTION_REJECTED,
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
    ApprovalChain,
    ApprovalStep,
    WorkflowAction,
    WorkflowRequest,
)
from ..infrastructure import config


class WorkflowError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _scope(organisation_id: str):
    return organisation_scope(organisation_id)


def resolve_user_name(db: Session, user_id: str | None) -> str | None:
    if not user_id:
        return None
    u = get_user(db, user_id)
    return u.name if u else None


def create_chain(
    db: Session,
    organisation_id: str,
    code: str,
    title: str,
    description: str | None,
    steps_data: list[dict],
) -> ApprovalChain:
    """Configure a new approval chain with ordered steps."""
    if not code or not code.strip():
        raise WorkflowError(422, "code is required")
    if not title or not title.strip():
        raise WorkflowError(422, "title is required")
    if not steps_data:
        raise WorkflowError(422, "at least one approval step is required")
    if len(steps_data) > config.max_steps():
        raise WorkflowError(422, f"chain exceeds maximum allowed steps ({config.max_steps()})")

    with _scope(organisation_id):
        existing = db.execute(
            scoped(db, select(ApprovalChain), ApprovalChain).where(ApprovalChain.code == code)
        ).scalar_one_or_none()
        if existing:
            raise WorkflowError(409, f"Approval chain with code '{code}' already exists")

        chain = ApprovalChain(
            organisation_id=organisation_id,
            code=code.strip(),
            title=title.strip(),
            description=description.strip() if description else None,
            is_active=True,
        )
        db.add(chain)
        db.flush()

        seen_orders = set()
        for s in steps_data:
            order = s.get("step_order")
            name = s.get("name")
            role = s.get("approver_role")
            if not order or order in seen_orders:
                raise WorkflowError(422, f"Invalid or duplicate step_order: {order}")
            seen_orders.add(order)
            if not name or not str(name).strip():
                raise WorkflowError(422, "step name is required")
            if not role or not str(role).strip():
                raise WorkflowError(422, "approver_role is required")

            sla = s.get("sla_hours")
            is_final = bool(s.get("is_final", False))

            step = ApprovalStep(
                organisation_id=organisation_id,
                chain_id=chain.id,
                step_order=order,
                name=str(name).strip(),
                approver_role=str(role).strip(),
                sla_hours=int(sla) if sla is not None else None,
                is_final=is_final,
            )
            db.add(step)

        db.flush()
        return chain


def get_chain(db: Session, organisation_id: str, chain_id: str) -> ApprovalChain | None:
    with _scope(organisation_id):
        return db.execute(
            scoped(db, select(ApprovalChain), ApprovalChain).where(ApprovalChain.id == chain_id)
        ).scalar_one_or_none()


def get_chain_by_code(db: Session, organisation_id: str, code: str) -> ApprovalChain | None:
    with _scope(organisation_id):
        return db.execute(
            scoped(db, select(ApprovalChain), ApprovalChain).where(ApprovalChain.code == code)
        ).scalar_one_or_none()


def list_chains(db: Session, organisation_id: str) -> list[ApprovalChain]:
    with _scope(organisation_id):
        stmt = scoped(db, select(ApprovalChain), ApprovalChain).order_by(ApprovalChain.created_at.desc())
        return list(db.execute(stmt).scalars().all())


def find_by_token(db: Session, organisation_id: str, client_token: str | None) -> WorkflowRequest | None:
    if not client_token:
        return None
    with _scope(organisation_id):
        return db.execute(
            scoped(db, select(WorkflowRequest), WorkflowRequest).where(WorkflowRequest.client_token == client_token)
        ).scalar_one_or_none()


def create_request(
    db: Session,
    organisation_id: str,
    chain_code: str,
    entity_type: str,
    entity_id: str,
    title: str,
    requester_id: str,
    requester_name: str | None = None,
    description: str | None = None,
    client_token: str | None = None,
    context_data: dict | None = None,
) -> tuple[WorkflowRequest, bool]:
    """Submit a new request for approval. Idempotent on client_token."""
    if client_token:
        existing = find_by_token(db, organisation_id, client_token)
        if existing:
            return existing, False

    if not title or not title.strip():
        raise WorkflowError(422, "title is required")
    if not entity_type or not entity_type.strip():
        raise WorkflowError(422, "entity_type is required")
    if not entity_id or not entity_id.strip():
        raise WorkflowError(422, "entity_id is required")

    chain = get_chain_by_code(db, organisation_id, chain_code)
    if not chain or not chain.is_active:
        raise WorkflowError(404, f"Approval chain '{chain_code}' not found or inactive")

    sorted_steps = sorted(chain.steps, key=lambda s: s.step_order)
    if not sorted_steps:
        raise WorkflowError(400, f"Approval chain '{chain_code}' has no configured steps")

    first_step = sorted_steps[0]
    now = utcnow()
    deadline = now + timedelta(hours=first_step.sla_hours) if first_step.sla_hours else None
    if not requester_name:
        requester_name = resolve_user_name(db, requester_id)

    req = WorkflowRequest(
        organisation_id=organisation_id,
        chain_id=chain.id,
        entity_type=entity_type.strip(),
        entity_id=entity_id.strip(),
        title=title.strip(),
        description=description.strip() if description else None,
        requester_id=requester_id,
        requester_name=requester_name,
        current_step_order=first_step.step_order,
        status=STATUS_PENDING,
        submitted_at=now,
        current_step_deadline=deadline,
        client_token=client_token,
        context=context_data or {},
    )
    with _scope(organisation_id):
        db.add(req)
        db.flush()

        events.publish(
            db,
            "workflow.request.submitted",
            organisation_id,
            {
                "request_id": req.id,
                "chain_id": chain.id,
                "chain_code": chain.code,
                "entity_type": req.entity_type,
                "entity_id": req.entity_id,
                "requester_id": req.requester_id,
                "step_order": first_step.step_order,
                "step_name": first_step.name,
                "approver_role": first_step.approver_role,
            },
            actor=requester_id,
        )

    return req, True


def get_request(db: Session, organisation_id: str, request_id: str) -> WorkflowRequest | None:
    with _scope(organisation_id):
        return db.execute(
            scoped(db, select(WorkflowRequest), WorkflowRequest).where(WorkflowRequest.id == request_id)
        ).scalar_one_or_none()


def list_requests(
    db: Session,
    organisation_id: str,
    status: str | None = None,
    entity_type: str | None = None,
    requester_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[WorkflowRequest], int]:
    with _scope(organisation_id):
        q = scoped(db, select(WorkflowRequest), WorkflowRequest)
        count_q = scoped(db, select(func.count(WorkflowRequest.id)), WorkflowRequest)
        if status:
            q = q.where(WorkflowRequest.status == status)
            count_q = count_q.where(WorkflowRequest.status == status)
        if entity_type:
            q = q.where(WorkflowRequest.entity_type == entity_type)
            count_q = count_q.where(WorkflowRequest.entity_type == entity_type)
        if requester_id:
            q = q.where(WorkflowRequest.requester_id == requester_id)
            count_q = count_q.where(WorkflowRequest.requester_id == requester_id)

        total = db.execute(count_q).scalar() or 0
        q = q.order_by(WorkflowRequest.submitted_at.desc()).limit(limit).offset(offset)
        items = list(db.execute(q).scalars().all())
        return items, total


def list_pending(
    db: Session,
    organisation_id: str,
    user_id: str | None = None,
    user_roles: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[WorkflowRequest], int]:
    """Requests pending approval where the user is an authorized approver, delegate, or admin."""
    roles = set(user_roles or [])
    is_admin = "org-admin" in roles or "super-admin" in roles

    with _scope(organisation_id):
        q = scoped(db, select(WorkflowRequest), WorkflowRequest).where(WorkflowRequest.status == STATUS_PENDING)
        count_q = scoped(db, select(func.count(WorkflowRequest.id)), WorkflowRequest).where(
            WorkflowRequest.status == STATUS_PENDING
        )

        if not is_admin:
            q = q.outerjoin(
                ApprovalStep,
                (ApprovalStep.chain_id == WorkflowRequest.chain_id)
                & (ApprovalStep.step_order == WorkflowRequest.current_step_order),
            )
            count_q = count_q.outerjoin(
                ApprovalStep,
                (ApprovalStep.chain_id == WorkflowRequest.chain_id)
                & (ApprovalStep.step_order == WorkflowRequest.current_step_order),
            )
            conditions = []
            if user_id:
                conditions.append(WorkflowRequest.delegated_to == user_id)
            if roles:
                conditions.append(ApprovalStep.approver_role.in_(roles))
            if conditions:
                cond = or_(*conditions)
                q = q.where(cond)
                count_q = count_q.where(cond)
            else:
                return [], 0

        total = db.execute(count_q).scalar() or 0
        q = q.order_by(WorkflowRequest.submitted_at.desc()).limit(limit).offset(offset)
        items = list(db.execute(q).scalars().all())
        return items, total


def _current_step(req: WorkflowRequest) -> ApprovalStep | None:
    if not req.chain or not req.chain.steps:
        return None
    for s in req.chain.steps:
        if s.step_order == req.current_step_order:
            return s
    return None


def _check_approver_auth(req: WorkflowRequest, actor_id: str, actor_roles: list[str] | None) -> ApprovalStep:
    if req.status != STATUS_PENDING:
        raise WorkflowError(409, f"Request is already {req.status}")

    if actor_id == req.requester_id:
        raise WorkflowError(403, "Requesters cannot approve, reject, or delegate their own requests")

    step = _current_step(req)
    if not step:
        raise WorkflowError(500, "Corrupt workflow: current step definition missing in chain")

    roles = set(actor_roles or [])
    if "org-admin" in roles or "super-admin" in roles:
        return step
    if req.delegated_to and req.delegated_to == actor_id:
        return step
    if step.approver_role in roles:
        return step

    raise WorkflowError(403, f"Action requires role '{step.approver_role}' or designated delegation")


def approve_request(
    db: Session,
    organisation_id: str,
    request_id: str,
    actor_id: str,
    actor_name: str | None = None,
    actor_roles: list[str] | None = None,
    comments: str | None = None,
) -> WorkflowRequest:
    req = get_request(db, organisation_id, request_id)
    if not req:
        raise WorkflowError(404, "Workflow request not found")

    step = _check_approver_auth(req, actor_id, actor_roles)

    if not actor_name:
        actor_name = resolve_user_name(db, actor_id)

    # Record action
    action = WorkflowAction(
        organisation_id=organisation_id,
        request_id=req.id,
        step_order=step.step_order,
        step_name=step.name,
        actor_id=actor_id,
        actor_name=actor_name,
        action=ACTION_APPROVED,
        comments=comments,
    )
    db.add(action)
    req.delegated_to = None

    # Check next steps
    all_steps = sorted(req.chain.steps, key=lambda s: s.step_order)
    subsequent_steps = [s for s in all_steps if s.step_order > step.step_order]

    now = utcnow()
    if step.is_final or not subsequent_steps:
        # Final approval reached
        req.status = STATUS_APPROVED
        req.completed_at = now
        req.current_step_deadline = None
        events.publish(
            db,
            "workflow.request.approved",
            organisation_id,
            {
                "request_id": req.id,
                "chain_id": req.chain_id,
                "chain_code": req.chain.code,
                "entity_type": req.entity_type,
                "entity_id": req.entity_id,
                "approved_by": actor_id,
                "comments": comments,
            },
            actor=actor_id,
        )
    else:
        # Advance to next step
        next_step = subsequent_steps[0]
        req.current_step_order = next_step.step_order
        req.current_step_deadline = now + timedelta(hours=next_step.sla_hours) if next_step.sla_hours else None
        events.publish(
            db,
            "workflow.step.advanced",
            organisation_id,
            {
                "request_id": req.id,
                "chain_id": req.chain_id,
                "chain_code": req.chain.code,
                "entity_type": req.entity_type,
                "entity_id": req.entity_id,
                "previous_step_order": step.step_order,
                "current_step_order": next_step.step_order,
                "current_step_name": next_step.name,
                "approver_role": next_step.approver_role,
            },
            actor=actor_id,
        )

    db.flush()
    return req


def reject_request(
    db: Session,
    organisation_id: str,
    request_id: str,
    actor_id: str,
    actor_name: str | None = None,
    actor_roles: list[str] | None = None,
    comments: str | None = None,
) -> WorkflowRequest:
    req = get_request(db, organisation_id, request_id)
    if not req:
        raise WorkflowError(404, "Workflow request not found")

    step = _check_approver_auth(req, actor_id, actor_roles)

    if not actor_name:
        actor_name = resolve_user_name(db, actor_id)

    action = WorkflowAction(
        organisation_id=organisation_id,
        request_id=req.id,
        step_order=step.step_order,
        step_name=step.name,
        actor_id=actor_id,
        actor_name=actor_name,
        action=ACTION_REJECTED,
        comments=comments,
    )
    db.add(action)

    now = utcnow()
    req.status = STATUS_REJECTED
    req.completed_at = now
    req.current_step_deadline = None
    req.delegated_to = None

    events.publish(
        db,
        "workflow.request.rejected",
        organisation_id,
        {
            "request_id": req.id,
            "chain_id": req.chain_id,
            "chain_code": req.chain.code,
            "entity_type": req.entity_type,
            "entity_id": req.entity_id,
            "rejected_by": actor_id,
            "step_order": step.step_order,
            "step_name": step.name,
            "comments": comments,
        },
        actor=actor_id,
    )

    db.flush()
    return req


def delegate_request(
    db: Session,
    organisation_id: str,
    request_id: str,
    actor_id: str,
    delegate_to_user_id: str,
    actor_name: str | None = None,
    actor_roles: list[str] | None = None,
    comments: str | None = None,
) -> WorkflowRequest:
    req = get_request(db, organisation_id, request_id)
    if not req:
        raise WorkflowError(404, "Workflow request not found")

    step = _check_approver_auth(req, actor_id, actor_roles)

    if not delegate_to_user_id or delegate_to_user_id.strip() == "":
        raise WorkflowError(422, "delegate_to_user_id is required")
    if delegate_to_user_id == actor_id:
        raise WorkflowError(422, "Cannot delegate to yourself")

    target_user = get_user(db, delegate_to_user_id.strip())
    if not target_user or target_user.organisation_id != organisation_id or target_user.status != "active":
        raise WorkflowError(422, "Delegation target must be an active member of this organisation")

    if not actor_name:
        actor_name = resolve_user_name(db, actor_id)

    req.delegated_to = delegate_to_user_id.strip()

    action = WorkflowAction(
        organisation_id=organisation_id,
        request_id=req.id,
        step_order=step.step_order,
        step_name=step.name,
        actor_id=actor_id,
        actor_name=actor_name,
        action=ACTION_DELEGATED,
        comments=f"Delegated to {req.delegated_to}: {comments}" if comments else f"Delegated to {req.delegated_to}",
    )
    db.add(action)

    events.publish(
        db,
        "workflow.request.delegated",
        organisation_id,
        {
            "request_id": req.id,
            "delegated_by": actor_id,
            "delegated_to": req.delegated_to,
            "step_order": step.step_order,
            "step_name": step.name,
            "comments": comments,
        },
        actor=actor_id,
    )

    db.flush()
    return req


def is_overdue(req: WorkflowRequest) -> bool:
    if req.status != STATUS_PENDING or not req.current_step_deadline:
        return False
    deadline = req.current_step_deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)
    return utcnow() > deadline


def view_step(step: ApprovalStep) -> dict:
    return {
        "id": step.id,
        "chain_id": step.chain_id,
        "step_order": step.step_order,
        "name": step.name,
        "approver_role": step.approver_role,
        "sla_hours": step.sla_hours,
        "is_final": step.is_final,
        "created_at": step.created_at.isoformat(),
    }


def view_chain(chain: ApprovalChain) -> dict:
    return {
        "id": chain.id,
        "organisation_id": chain.organisation_id,
        "code": chain.code,
        "title": chain.title,
        "description": chain.description,
        "is_active": chain.is_active,
        "created_at": chain.created_at.isoformat(),
        "updated_at": chain.updated_at.isoformat(),
        "steps": [view_step(s) for s in sorted(chain.steps, key=lambda s: s.step_order)],
    }


def view_action(action: WorkflowAction) -> dict:
    return {
        "id": action.id,
        "request_id": action.request_id,
        "step_order": action.step_order,
        "step_name": action.step_name,
        "actor_id": action.actor_id,
        "actor_name": action.actor_name,
        "action": action.action,
        "comments": action.comments,
        "occurred_at": action.occurred_at.isoformat(),
    }


def view_request(req: WorkflowRequest) -> dict:
    return {
        "id": req.id,
        "organisation_id": req.organisation_id,
        "chain_id": req.chain_id,
        "entity_type": req.entity_type,
        "entity_id": req.entity_id,
        "title": req.title,
        "description": req.description,
        "requester_id": req.requester_id,
        "requester_name": req.requester_name,
        "current_step_order": req.current_step_order,
        "status": req.status,
        "submitted_at": req.submitted_at.isoformat(),
        "completed_at": req.completed_at.isoformat() if req.completed_at else None,
        "current_step_deadline": req.current_step_deadline.isoformat() if req.current_step_deadline else None,
        "is_overdue": is_overdue(req),
        "delegated_to": req.delegated_to,
        "client_token": req.client_token,
        "context": req.context,
    }


def view_request_detail(req: WorkflowRequest) -> dict:
    data = view_request(req)
    data["history"] = [view_action(a) for a in req.history]
    return data
