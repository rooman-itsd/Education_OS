"""Unit tests for workflow domain models and SLA calculations."""

from datetime import UTC, datetime, timedelta

from eos_workflow.application.service import is_overdue
from eos_workflow.domain.models import (
    ACTION_APPROVED,
    ACTION_DELEGATED,
    ACTION_REJECTED,
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
    TABLE_NAMES,
    ApprovalChain,
    ApprovalStep,
    WorkflowAction,
    WorkflowRequest,
)


def test_table_names_declared():
    assert set(TABLE_NAMES) == {"workflow_chain", "workflow_step", "workflow_request", "workflow_action"}


def test_approval_chain_creation():
    chain = ApprovalChain(
        organisation_id="org-1",
        code="procurement",
        title="Purchase Order Approval",
        description="For supplies over 10k",
        is_active=True,
    )
    assert chain.code == "procurement"
    assert chain.is_active is True
    assert chain.organisation_id == "org-1"


def test_approval_step_attributes():
    step = ApprovalStep(
        organisation_id="org-1",
        chain_id="chain-1",
        step_order=1,
        name="Dean Approval",
        approver_role="department-admin",
        sla_hours=48,
        is_final=False,
    )
    assert step.step_order == 1
    assert step.approver_role == "department-admin"
    assert step.sla_hours == 48
    assert step.is_final is False


def test_workflow_request_lifecycle_states():
    now = datetime.now(UTC)
    req = WorkflowRequest(
        organisation_id="org-1",
        chain_id="chain-1",
        entity_type="leave",
        entity_id="leave-101",
        title="Casual Leave",
        requester_id="user-1",
        status=STATUS_PENDING,
        submitted_at=now,
        current_step_deadline=now + timedelta(hours=24),
    )
    assert req.status == STATUS_PENDING
    assert req.current_step_order == 1
    assert is_overdue(req) is False

    # Simulate past deadline
    req.current_step_deadline = now - timedelta(hours=1)
    assert is_overdue(req) is True

    # Once approved or rejected, is_overdue is false
    req.status = STATUS_APPROVED
    assert is_overdue(req) is False
    req.status = STATUS_REJECTED
    assert is_overdue(req) is False


def test_workflow_action_record():
    action = WorkflowAction(
        organisation_id="org-1",
        request_id="req-1",
        step_order=1,
        step_name="HoD Review",
        actor_id="user-2",
        actor_name="Dr. Mehta",
        action=ACTION_APPROVED,
        comments="Approved as per policy",
    )
    assert action.action == ACTION_APPROVED
    assert action.actor_id == "user-2"

    action_rej = WorkflowAction(
        organisation_id="org-1",
        request_id="req-1",
        step_order=1,
        step_name="HoD Review",
        actor_id="user-2",
        action=ACTION_REJECTED,
    )
    assert action_rej.action == ACTION_REJECTED

    action_del = WorkflowAction(
        organisation_id="org-1",
        request_id="req-1",
        step_order=1,
        step_name="HoD Review",
        actor_id="user-2",
        action=ACTION_DELEGATED,
    )
    assert action_del.action == ACTION_DELEGATED
