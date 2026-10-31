"""Multi-tenant database repository for selection-process."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.orm import Session, joinedload

from .models import (
    CandidateModel,
    DecisionModel,
    PanelModel,
    ProcessModel,
    ProcessTypeModel,
    SlotModel,
    StageModel,
)

# --- Process Types ---


def get_process_type(db: Session, organisation_id: str, type_id: str) -> ProcessTypeModel | None:
    return (
        db.query(ProcessTypeModel)
        .filter(
            ProcessTypeModel.organisation_id == organisation_id,
            ProcessTypeModel.id == type_id,
        )
        .first()
    )


def get_process_type_by_name(db: Session, organisation_id: str, name: str) -> ProcessTypeModel | None:
    return (
        db.query(ProcessTypeModel)
        .filter(
            ProcessTypeModel.organisation_id == organisation_id,
            ProcessTypeModel.name == name,
        )
        .first()
    )


def list_process_types(db: Session, organisation_id: str) -> list[ProcessTypeModel]:
    return (
        db.query(ProcessTypeModel)
        .filter(ProcessTypeModel.organisation_id == organisation_id)
        .order_by(ProcessTypeModel.name)
        .all()
    )


def count_processes_for_type(db: Session, organisation_id: str, type_id: str) -> int:
    return (
        db.query(sa.func.count(ProcessModel.id))
        .filter(
            ProcessModel.organisation_id == organisation_id,
            ProcessModel.type_id == type_id,
        )
        .scalar()
        or 0
    )


# --- Processes ---


def get_process(db: Session, organisation_id: str, process_id: str) -> ProcessModel | None:
    return (
        db.query(ProcessModel)
        .options(
            joinedload(ProcessModel.stages),
            joinedload(ProcessModel.panels),
        )
        .filter(
            ProcessModel.organisation_id == organisation_id,
            ProcessModel.id == process_id,
        )
        .first()
    )


def list_processes(
    db: Session,
    organisation_id: str,
    *,
    type_id: str | None = None,
    statuses: Sequence[str] | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ProcessModel], int]:
    query = (
        db.query(ProcessModel)
        .options(
            joinedload(ProcessModel.stages),
            joinedload(ProcessModel.panels),
        )
        .filter(ProcessModel.organisation_id == organisation_id)
    )
    if type_id:
        query = query.filter(ProcessModel.type_id == type_id)
    if statuses:
        query = query.filter(ProcessModel.status.in_(statuses))
    if q:
        query = query.filter(ProcessModel.title.ilike(f"%{q}%"))

    total = query.with_entities(sa.func.count(ProcessModel.id)).order_by(None).scalar() or 0
    items = query.order_by(ProcessModel.created_at.desc()).offset(offset).limit(limit).all()
    return items, total


def count_candidates_for_process(db: Session, organisation_id: str, process_id: str) -> int:
    return (
        db.query(sa.func.count(CandidateModel.id))
        .filter(
            CandidateModel.organisation_id == organisation_id,
            CandidateModel.process_id == process_id,
        )
        .scalar()
        or 0
    )


# --- Stages ---


def list_stages_for_process(db: Session, organisation_id: str, process_id: str) -> list[StageModel]:
    return (
        db.query(StageModel)
        .filter(
            StageModel.organisation_id == organisation_id,
            StageModel.process_id == process_id,
        )
        .order_by(StageModel.sequence.asc())
        .all()
    )


def get_stage(db: Session, organisation_id: str, stage_id: str) -> StageModel | None:
    return (
        db.query(StageModel)
        .filter(
            StageModel.organisation_id == organisation_id,
            StageModel.id == stage_id,
        )
        .first()
    )


# --- Panels ---


def get_panel(db: Session, organisation_id: str, panel_id: str) -> PanelModel | None:
    return (
        db.query(PanelModel)
        .filter(
            PanelModel.organisation_id == organisation_id,
            PanelModel.id == panel_id,
        )
        .first()
    )


def list_panels_for_process(db: Session, organisation_id: str, process_id: str) -> list[PanelModel]:
    return (
        db.query(PanelModel)
        .filter(
            PanelModel.organisation_id == organisation_id,
            PanelModel.process_id == process_id,
        )
        .order_by(PanelModel.name.asc())
        .all()
    )


# --- Candidates ---


def get_candidate(db: Session, organisation_id: str, candidate_id: str) -> CandidateModel | None:
    return (
        db.query(CandidateModel)
        .options(
            joinedload(CandidateModel.decisions),
        )
        .filter(
            CandidateModel.organisation_id == organisation_id,
            CandidateModel.id == candidate_id,
        )
        .first()
    )


def get_candidate_by_person(
    db: Session, organisation_id: str, process_id: str, person_id: str
) -> CandidateModel | None:
    return (
        db.query(CandidateModel)
        .filter(
            CandidateModel.organisation_id == organisation_id,
            CandidateModel.process_id == process_id,
            CandidateModel.person_id == person_id,
        )
        .first()
    )


def list_candidates(
    db: Session,
    organisation_id: str,
    *,
    process_id: str | None = None,
    person_id: str | None = None,
    statuses: Sequence[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CandidateModel], int]:
    query = (
        db.query(CandidateModel)
        .options(
            joinedload(CandidateModel.decisions),
        )
        .filter(CandidateModel.organisation_id == organisation_id)
    )
    if process_id:
        query = query.filter(CandidateModel.process_id == process_id)
    if person_id:
        query = query.filter(CandidateModel.person_id == person_id)
    if statuses:
        query = query.filter(CandidateModel.status.in_(statuses))

    total = query.with_entities(sa.func.count(CandidateModel.id)).order_by(None).scalar() or 0
    items = query.order_by(CandidateModel.registered_at.desc()).offset(offset).limit(limit).all()
    return items, total


def list_candidates_for_panelist(
    db: Session,
    organisation_id: str,
    process_id: str,
    person_id: str,
    *,
    statuses: Sequence[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CandidateModel], int]:
    """Finds candidates whose current stage is covered by a panel that person_id belongs to."""
    # First get panels for process where person_id is a member
    panels = list_panels_for_process(db, organisation_id, process_id)
    member_stage_ids: set[str | None] = set()
    has_global_panel = False
    for p in panels:
        members = p.member_person_ids or []
        if person_id in members:
            if p.stage_id is None:
                has_global_panel = True
            else:
                member_stage_ids.add(p.stage_id)

    query = (
        db.query(CandidateModel)
        .options(joinedload(CandidateModel.decisions))
        .filter(
            CandidateModel.organisation_id == organisation_id,
            CandidateModel.process_id == process_id,
        )
    )
    if not has_global_panel:
        query = query.filter(CandidateModel.current_stage_id.in_(member_stage_ids))

    if statuses:
        query = query.filter(CandidateModel.status.in_(statuses))

    total = query.with_entities(sa.func.count(CandidateModel.id)).order_by(None).scalar() or 0
    items = query.order_by(CandidateModel.registered_at.desc()).offset(offset).limit(limit).all()
    return items, total


# --- Decisions ---


def get_decision_by_panelist(
    db: Session, organisation_id: str, candidate_id: str, stage_id: str, decided_by: str
) -> DecisionModel | None:
    return (
        db.query(DecisionModel)
        .filter(
            DecisionModel.organisation_id == organisation_id,
            DecisionModel.candidate_id == candidate_id,
            DecisionModel.stage_id == stage_id,
            DecisionModel.decided_by == decided_by,
        )
        .first()
    )


def list_decisions_for_candidate(db: Session, organisation_id: str, candidate_id: str) -> list[DecisionModel]:
    return (
        db.query(DecisionModel)
        .filter(
            DecisionModel.organisation_id == organisation_id,
            DecisionModel.candidate_id == candidate_id,
        )
        .order_by(DecisionModel.decided_at.asc())
        .all()
    )


# --- Slots ---


def list_upcoming_slots(
    db: Session,
    organisation_id: str,
    *,
    candidate_id: str | None = None,
    limit: int = 10,
) -> list[SlotModel]:
    query = db.query(SlotModel).filter(
        SlotModel.organisation_id == organisation_id,
        SlotModel.status == "scheduled",
    )
    if candidate_id:
        query = query.filter(SlotModel.candidate_id == candidate_id)
    return query.order_by(SlotModel.starts_at.asc()).limit(limit).all()
