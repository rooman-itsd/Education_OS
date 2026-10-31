"""Application service tests for workflow: multi-step progression, delegation, outbox events, and idempotency."""

import pytest
from eos_core.events import OutboxEvent
from eos_workflow.application import service
from eos_workflow.application.service import WorkflowError
from eos_workflow.domain.models import (
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
)
from sqlalchemy import select
from workflow_support import Org, sample_chain


def test_chain_creation_and_listing(workflow_db):
    org = Org(workflow_db)
    data = sample_chain("travel_grant")
    chain = service.create_chain(
        workflow_db,
        org.id,
        code=data["code"],
        title=data["title"],
        description=data["description"],
        steps_data=data["steps"],
    )
    workflow_db.commit()

    assert chain.id is not None
    assert len(chain.steps) == 2

    # Listing
    chains = service.list_chains(workflow_db, org.id)
    assert len(chains) == 1
    assert chains[0].code == "travel_grant"

    # Duplicate code rejected
    with pytest.raises(WorkflowError) as exc:
        service.create_chain(workflow_db, org.id, "travel_grant", "Another", None, data["steps"])
    assert exc.value.status == 409


def test_request_lifecycle_and_step_advancement(workflow_db):
    org = Org(workflow_db)
    chain_data = sample_chain("leave_req")
    service.create_chain(
        workflow_db,
        org.id,
        code=chain_data["code"],
        title=chain_data["title"],
        description=chain_data["description"],
        steps_data=chain_data["steps"],
    )
    workflow_db.commit()

    # 1. Create request
    req, created = service.create_request(
        workflow_db,
        org.id,
        chain_code="leave_req",
        entity_type="leave",
        entity_id="l-100",
        title="Leave Request for Dr. Roy",
        requester_id=org.faculty.id,
        requester_name="Dr. Roy",
        client_token="token-abc",
    )
    workflow_db.commit()
    assert created is True
    assert req.status == STATUS_PENDING
    assert req.current_step_order == 1
    assert req.current_step_deadline is not None

    # Idempotent retry returns existing
    req2, created2 = service.create_request(
        workflow_db,
        org.id,
        chain_code="leave_req",
        entity_type="leave",
        entity_id="l-100",
        title="Leave Request for Dr. Roy",
        requester_id=org.faculty.id,
        client_token="token-abc",
    )
    assert created2 is False
    assert req2.id == req.id

    # 2. Advance Step 1 (HoD Review - requires department-admin)
    # Unprivileged user fails
    with pytest.raises(WorkflowError) as exc:
        service.approve_request(
            workflow_db,
            org.id,
            req.id,
            actor_id=org.student.id,
            actor_roles=["student"],
            comments="I approve",
        )
    assert exc.value.status == 403

    # Department admin approves Step 1
    req = service.approve_request(
        workflow_db,
        org.id,
        req.id,
        actor_id=org.dept_admin.id,
        actor_roles=["department-admin"],
        comments="Recommended by HoD",
    )
    workflow_db.commit()

    assert req.status == STATUS_PENDING
    assert req.current_step_order == 2

    # Verify event published for advancement
    evs = list(
        workflow_db.execute(select(OutboxEvent).where(OutboxEvent.name == "workflow.step.advanced")).scalars().all()
    )
    assert len(evs) == 1
    assert evs[0].payload["current_step_order"] == 2

    # 3. Final Step 2 (requires org-admin)
    req = service.approve_request(
        workflow_db,
        org.id,
        req.id,
        actor_id=org.admin.id,
        actor_roles=["org-admin"],
        comments="Approved by Director",
    )
    workflow_db.commit()

    assert req.status == STATUS_APPROVED
    assert req.completed_at is not None

    # Verify final approved event published
    evs_approved = list(
        workflow_db.execute(select(OutboxEvent).where(OutboxEvent.name == "workflow.request.approved")).scalars().all()
    )
    assert len(evs_approved) == 1
    assert evs_approved[0].payload["request_id"] == req.id


def test_request_rejection(workflow_db):
    org = Org(workflow_db)
    chain_data = sample_chain("exp_req")
    service.create_chain(
        workflow_db,
        org.id,
        code=chain_data["code"],
        title=chain_data["title"],
        description=chain_data["description"],
        steps_data=chain_data["steps"],
    )
    workflow_db.commit()

    req, _ = service.create_request(
        workflow_db,
        org.id,
        chain_code="exp_req",
        entity_type="expense",
        entity_id="e-50",
        title="Laptop Expense",
        requester_id=org.faculty.id,
    )
    workflow_db.commit()

    # Reject at step 1
    req = service.reject_request(
        workflow_db,
        org.id,
        req.id,
        actor_id=org.dept_admin.id,
        actor_roles=["department-admin"],
        comments="Budget exhausted",
    )
    workflow_db.commit()

    assert req.status == STATUS_REJECTED
    assert req.completed_at is not None

    # Rejection event
    evs = list(
        workflow_db.execute(select(OutboxEvent).where(OutboxEvent.name == "workflow.request.rejected")).scalars().all()
    )
    assert len(evs) == 1

    # Cannot act on resolved request
    with pytest.raises(WorkflowError) as exc:
        service.approve_request(workflow_db, org.id, req.id, org.admin.id, ["org-admin"])
    assert exc.value.status == 409


def test_delegation_flow(workflow_db):
    org = Org(workflow_db)
    chain_data = sample_chain("leave_del")
    service.create_chain(
        workflow_db,
        org.id,
        code=chain_data["code"],
        title=chain_data["title"],
        description=chain_data["description"],
        steps_data=chain_data["steps"],
    )
    workflow_db.commit()

    req, _ = service.create_request(
        workflow_db,
        org.id,
        chain_code="leave_del",
        entity_type="leave",
        entity_id="l-200",
        title="Leave for delegation",
        requester_id=org.faculty.id,
    )
    workflow_db.commit()

    # Dept admin delegates to faculty member
    req = service.delegate_request(
        workflow_db,
        org.id,
        req.id,
        actor_id=org.dept_admin.id,
        delegate_to_user_id=org.faculty.id,
        actor_roles=["department-admin"],
        comments="Please cover review while I am away",
    )
    workflow_db.commit()

    assert req.delegated_to == org.faculty.id

    # The delegate can now approve despite not having department-admin role
    req = service.approve_request(
        workflow_db,
        org.id,
        req.id,
        actor_id=org.faculty.id,
        actor_roles=["faculty"],
        comments="Covering for HoD",
    )
    workflow_db.commit()
    assert req.current_step_order == 2


def test_missing_and_inactive_chain_validation(workflow_db):
    org = Org(workflow_db)
    # 1. Non-existent chain
    with pytest.raises(WorkflowError) as exc:
        service.create_request(
            workflow_db,
            org.id,
            chain_code="non_existent",
            entity_type="purchase",
            entity_id="p-1",
            title="Supplies",
            requester_id=org.faculty.id,
        )
    assert exc.value.status == 404

    # 2. Inactive chain
    chain_data = sample_chain("inactive_chain")
    chain = service.create_chain(
        workflow_db,
        org.id,
        code=chain_data["code"],
        title=chain_data["title"],
        description="Disabled chain",
        steps_data=chain_data["steps"],
    )
    chain.is_active = False
    workflow_db.commit()

    with pytest.raises(WorkflowError) as exc:
        service.create_request(
            workflow_db,
            org.id,
            chain_code="inactive_chain",
            entity_type="purchase",
            entity_id="p-2",
            title="Supplies",
            requester_id=org.faculty.id,
        )
    assert exc.value.status == 404


def test_unauthorized_delegation_refused(workflow_db):
    org = Org(workflow_db)
    chain_data = sample_chain("del_check")
    service.create_chain(
        workflow_db,
        org.id,
        code=chain_data["code"],
        title=chain_data["title"],
        description=chain_data["description"],
        steps_data=chain_data["steps"],
    )
    workflow_db.commit()

    req, _ = service.create_request(
        workflow_db,
        org.id,
        chain_code="del_check",
        entity_type="leave",
        entity_id="l-300",
        title="Leave Request",
        requester_id=org.faculty.id,
    )
    workflow_db.commit()

    # Student cannot delegate HoD review step
    with pytest.raises(WorkflowError) as exc:
        service.delegate_request(
            workflow_db,
            org.id,
            req.id,
            actor_id=org.student.id,
            delegate_to_user_id=org.faculty.id,
            actor_roles=["student"],
        )
    assert exc.value.status == 403


def test_action_on_resolved_requests_refused(workflow_db):
    org = Org(workflow_db)
    chain_data = sample_chain("resolved_check")
    service.create_chain(
        workflow_db,
        org.id,
        code=chain_data["code"],
        title=chain_data["title"],
        description=chain_data["description"],
        steps_data=[chain_data["steps"][0]],  # Single step chain
    )
    workflow_db.commit()

    req, _ = service.create_request(
        workflow_db,
        org.id,
        chain_code="resolved_check",
        entity_type="leave",
        entity_id="l-400",
        title="Quick Leave",
        requester_id=org.faculty.id,
    )
    workflow_db.commit()

    # HoD rejects request
    service.reject_request(
        workflow_db,
        org.id,
        req.id,
        actor_id=org.dept_admin.id,
        actor_roles=["department-admin"],
    )
    workflow_db.commit()

    # Cannot reject again
    with pytest.raises(WorkflowError) as exc:
        service.reject_request(
            workflow_db,
            org.id,
            req.id,
            actor_id=org.dept_admin.id,
            actor_roles=["department-admin"],
        )
    assert exc.value.status == 409

    # Cannot approve a rejected request
    with pytest.raises(WorkflowError) as exc:
        service.approve_request(
            workflow_db,
            org.id,
            req.id,
            actor_id=org.dept_admin.id,
            actor_roles=["department-admin"],
        )
    assert exc.value.status == 409


def test_event_publishing_and_transactional_rollback(workflow_db):
    org = Org(workflow_db)
    chain_data = sample_chain("tx_check")
    service.create_chain(
        workflow_db,
        org.id,
        code=chain_data["code"],
        title=chain_data["title"],
        description=chain_data["description"],
        steps_data=[chain_data["steps"][0]],
    )
    workflow_db.commit()

    req, _ = service.create_request(
        workflow_db,
        org.id,
        chain_code="tx_check",
        entity_type="leave",
        entity_id="l-500",
        title="Tx Rollback Test",
        requester_id=org.faculty.id,
    )
    workflow_db.commit()

    # Count outbox events before approval
    initial_events = len(list(workflow_db.execute(select(OutboxEvent)).scalars().all()))

    # Approve request but do not commit, then rollback
    service.approve_request(
        workflow_db,
        org.id,
        req.id,
        actor_id=org.dept_admin.id,
        actor_roles=["department-admin"],
    )
    # Check that the event was added in the session
    events_in_session = len(list(workflow_db.execute(select(OutboxEvent)).scalars().all()))
    assert events_in_session == initial_events + 1

    # Roll back transaction
    workflow_db.rollback()

    # Event must be gone after rollback
    events_after_rollback = len(list(workflow_db.execute(select(OutboxEvent)).scalars().all()))
    assert events_after_rollback == initial_events
