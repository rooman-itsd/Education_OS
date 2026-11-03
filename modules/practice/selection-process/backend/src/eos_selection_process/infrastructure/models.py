"""SQLAlchemy models for selection-process."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from eos_core.db import Base, utcnow
from sqlalchemy.orm import relationship

from ..domain.models import CandidateStatus, ProcessStatus, SlotStatus

PREFIX = "selection_process_"


def _id() -> str:
    return str(uuid.uuid4())


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


class ProcessTypeModel(Base):
    __tablename__ = "selection_process_type"

    id = sa.Column(sa.String(36), primary_key=True, default=_id)
    organisation_id = sa.Column(sa.String(36), nullable=False, index=True)
    name = sa.Column(sa.String(120), nullable=False)
    description = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utcnow, nullable=False)

    processes = relationship("ProcessModel", back_populates="type")

    __table_args__ = (sa.UniqueConstraint("organisation_id", "name", name="uq_selection_process_type_org_name"),)


class ProcessModel(Base):
    __tablename__ = "selection_process"

    id = sa.Column(sa.String(36), primary_key=True, default=_id)
    organisation_id = sa.Column(sa.String(36), nullable=False, index=True)
    type_id = sa.Column(sa.String(36), sa.ForeignKey("selection_process_type.id"), nullable=False, index=True)
    title = sa.Column(sa.String(200), nullable=False)
    academic_year = sa.Column(sa.String(50), nullable=True)
    context = sa.Column(sa.JSON, nullable=True)
    status = sa.Column(sa.String(30), nullable=False, default=ProcessStatus.DRAFT.value, index=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = sa.Column(sa.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    type = relationship("ProcessTypeModel", back_populates="processes")
    stages = relationship(
        "StageModel", back_populates="process", cascade="all, delete-orphan", order_by="StageModel.sequence"
    )
    panels = relationship("PanelModel", back_populates="process", cascade="all, delete-orphan")
    candidates = relationship("CandidateModel", back_populates="process", cascade="all, delete-orphan")
    slots = relationship("SlotModel", back_populates="process", cascade="all, delete-orphan")


class StageModel(Base):
    __tablename__ = "selection_process_stage"

    id = sa.Column(sa.String(36), primary_key=True, default=_id)
    organisation_id = sa.Column(sa.String(36), nullable=False, index=True)
    process_id = sa.Column(
        sa.String(36), sa.ForeignKey("selection_process.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = sa.Column(sa.String(120), nullable=False)
    sequence = sa.Column(sa.Integer, nullable=False)
    description = sa.Column(sa.Text, nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utcnow, nullable=False)

    process = relationship("ProcessModel", back_populates="stages")
    panels = relationship("PanelModel", back_populates="stage")

    __table_args__ = (
        sa.UniqueConstraint("organisation_id", "process_id", "sequence", name="uq_selection_stage_process_sequence"),
    )


class PanelModel(Base):
    __tablename__ = "selection_process_panel"

    id = sa.Column(sa.String(36), primary_key=True, default=_id)
    organisation_id = sa.Column(sa.String(36), nullable=False, index=True)
    process_id = sa.Column(
        sa.String(36), sa.ForeignKey("selection_process.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage_id = sa.Column(
        sa.String(36), sa.ForeignKey("selection_process_stage.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name = sa.Column(sa.String(120), nullable=False)
    member_person_ids = sa.Column(sa.JSON, nullable=False, default=list)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utcnow, nullable=False)

    process = relationship("ProcessModel", back_populates="panels")
    stage = relationship("StageModel", back_populates="panels")


class CandidateModel(Base):
    __tablename__ = "selection_process_candidate"

    id = sa.Column(sa.String(36), primary_key=True, default=_id)
    organisation_id = sa.Column(sa.String(36), nullable=False, index=True)
    process_id = sa.Column(
        sa.String(36), sa.ForeignKey("selection_process.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id = sa.Column(sa.String(36), nullable=False, index=True)
    current_stage_id = sa.Column(
        sa.String(36), sa.ForeignKey("selection_process_stage.id", ondelete="SET NULL"), nullable=True
    )
    status = sa.Column(sa.String(30), nullable=False, default=CandidateStatus.REGISTERED.value, index=True)
    source = sa.Column(sa.JSON, nullable=True)
    registered_at = sa.Column(sa.DateTime(timezone=True), default=utcnow, nullable=False)
    decided_at = sa.Column(sa.DateTime(timezone=True), nullable=True)

    process = relationship("ProcessModel", back_populates="candidates")
    decisions = relationship(
        "DecisionModel", back_populates="candidate", cascade="all, delete-orphan", order_by="DecisionModel.decided_at"
    )
    slots = relationship("SlotModel", back_populates="candidate")

    __table_args__ = (
        sa.UniqueConstraint("organisation_id", "process_id", "person_id", name="uq_selection_candidate_process_person"),
    )


class DecisionModel(Base):
    __tablename__ = "selection_process_decision"

    id = sa.Column(sa.String(36), primary_key=True, default=_id)
    organisation_id = sa.Column(sa.String(36), nullable=False, index=True)
    candidate_id = sa.Column(
        sa.String(36), sa.ForeignKey("selection_process_candidate.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage_id = sa.Column(
        sa.String(36), sa.ForeignKey("selection_process_stage.id", ondelete="CASCADE"), nullable=False, index=True
    )
    panel_id = sa.Column(sa.String(36), sa.ForeignKey("selection_process_panel.id", ondelete="SET NULL"), nullable=True)
    decided_by = sa.Column(sa.String(36), nullable=False, index=True)
    outcome = sa.Column(sa.String(30), nullable=False)
    score = sa.Column(sa.Float, nullable=True)
    comments = sa.Column(sa.Text, nullable=True)
    decided_at = sa.Column(sa.DateTime(timezone=True), default=utcnow, nullable=False)

    candidate = relationship("CandidateModel", back_populates="decisions")

    __table_args__ = (
        sa.UniqueConstraint(
            "organisation_id", "candidate_id", "stage_id", "decided_by", name="uq_selection_decision_panelist"
        ),
    )


class SlotModel(Base):
    __tablename__ = "selection_process_slot"

    id = sa.Column(sa.String(36), primary_key=True, default=_id)
    organisation_id = sa.Column(sa.String(36), nullable=False, index=True)
    process_id = sa.Column(
        sa.String(36), sa.ForeignKey("selection_process.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage_id = sa.Column(sa.String(36), sa.ForeignKey("selection_process_stage.id", ondelete="CASCADE"), nullable=True)
    candidate_id = sa.Column(
        sa.String(36), sa.ForeignKey("selection_process_candidate.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title = sa.Column(sa.String(200), nullable=False)
    starts_at = sa.Column(sa.DateTime(timezone=True), nullable=False, index=True)
    ends_at = sa.Column(sa.DateTime(timezone=True), nullable=False)
    status = sa.Column(sa.String(30), nullable=False, default=SlotStatus.SCHEDULED.value)
    location = sa.Column(sa.String(200), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utcnow, nullable=False)

    process = relationship("ProcessModel", back_populates="slots")
    candidate = relationship("CandidateModel", back_populates="slots")


TABLES = [
    ProcessTypeModel,
    ProcessModel,
    StageModel,
    PanelModel,
    CandidateModel,
    DecisionModel,
    SlotModel,
]
