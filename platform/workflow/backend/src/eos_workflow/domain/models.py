"""Domain models for workflow: ApprovalChain, ApprovalStep, WorkflowRequest, WorkflowAction.

Every table carries organisation_id and is tenant-isolated with PostgreSQL row-level security.
"""

from __future__ import annotations

from datetime import datetime

from eos_core.db import Base, TenantMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

MAX_CODE = 64
MAX_TITLE = 255
MAX_STEP_NAME = 128
MAX_ROLE = 64
MAX_ENTITY_TYPE = 64
MAX_ENTITY_ID = 64
MAX_CLIENT_TOKEN = 120

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_CANCELLED = "cancelled"

ACTION_APPROVED = "approved"
ACTION_REJECTED = "rejected"
ACTION_DELEGATED = "delegated"

TABLE_NAMES = ["workflow_chain", "workflow_step", "workflow_request", "workflow_action"]


class ApprovalChain(Base, TenantMixin):
    """An organisation-configured template for an approval sequence (e.g. leave, purchase order)."""

    __tablename__ = "workflow_chain"
    __table_args__ = (
        UniqueConstraint("organisation_id", "code", name="uq_workflow_chain_org_code"),
        Index("ix_workflow_chain_org", "organisation_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(MAX_CODE), nullable=False)
    title: Mapped[str] = mapped_column(String(MAX_TITLE), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    steps: Mapped[list[ApprovalStep]] = relationship(
        "ApprovalStep",
        back_populates="chain",
        order_by="ApprovalStep.step_order",
        cascade="all, delete-orphan",
    )


class ApprovalStep(Base, TenantMixin):
    """A single sequential checkpoint in an ApprovalChain with required role and optional SLA."""

    __tablename__ = "workflow_step"
    __table_args__ = (
        UniqueConstraint("chain_id", "step_order", name="uq_workflow_step_chain_order"),
        Index("ix_workflow_step_chain", "chain_id"),
        Index("ix_workflow_step_org", "organisation_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    chain_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_chain.id", ondelete="CASCADE"), nullable=False
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(MAX_STEP_NAME), nullable=False)
    approver_role: Mapped[str] = mapped_column(String(MAX_ROLE), nullable=False)
    sla_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    chain: Mapped[ApprovalChain] = relationship("ApprovalChain", back_populates="steps")


class WorkflowRequest(Base, TenantMixin):
    """A concrete workflow instance submitted for sign-off by a module or user."""

    __tablename__ = "workflow_request"
    __table_args__ = (
        Index("ix_workflow_request_org_status", "organisation_id", "status"),
        Index("ix_workflow_request_org_entity", "organisation_id", "entity_type", "entity_id"),
        Index("uq_workflow_request_org_token", "organisation_id", "client_token", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    chain_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflow_chain.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(MAX_ENTITY_TYPE), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(MAX_ENTITY_ID), nullable=False)
    title: Mapped[str] = mapped_column(String(MAX_TITLE), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requester_id: Mapped[str] = mapped_column(String(36), nullable=False)
    requester_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_step_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=STATUS_PENDING, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_step_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delegated_to: Mapped[str | None] = mapped_column(String(36), nullable=True)
    client_token: Mapped[str | None] = mapped_column(String(MAX_CLIENT_TOKEN), nullable=True)
    context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    def __init__(self, **kwargs):
        kwargs.setdefault("current_step_order", 1)
        kwargs.setdefault("status", STATUS_PENDING)
        kwargs.setdefault("context", {})
        super().__init__(**kwargs)

    chain: Mapped[ApprovalChain] = relationship("ApprovalChain")
    history: Mapped[list[WorkflowAction]] = relationship(
        "WorkflowAction",
        back_populates="request",
        order_by="WorkflowAction.occurred_at",
        cascade="all, delete-orphan",
    )


class WorkflowAction(Base, TenantMixin):
    """Immutable audit trail of actions taken on a request (approved, rejected, delegated)."""

    __tablename__ = "workflow_action"
    __table_args__ = (
        Index("ix_workflow_action_req_occurred", "request_id", "occurred_at"),
        Index("ix_workflow_action_org", "organisation_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_request.id", ondelete="CASCADE"), nullable=False
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(String(MAX_STEP_NAME), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    request: Mapped[WorkflowRequest] = relationship("WorkflowRequest", back_populates="history")
