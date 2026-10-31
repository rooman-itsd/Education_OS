"""Selection-process application services.
Enforces multi-tenancy, state transitions, duplicate candidate protection,
multi-panelist decision uniqueness, and emits events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.models import (
    FINAL_CANDIDATE_STATUSES,
    AlreadyDecidedError,
    CandidateFinalizedError,
    CandidateStatus,
    ConflictError,
    DecisionOutcome,
    DuplicateCandidateError,
    NoStagesError,
    NotFoundError,
    ProcessNotDraftError,
    ProcessNotOpenError,
    ProcessStatus,
    SlotStatus,
)
from ..infrastructure import repository as repo
from ..infrastructure.models import (
    CandidateModel,
    DecisionModel,
    PanelModel,
    ProcessModel,
    ProcessTypeModel,
    SlotModel,
    StageModel,
    iso,
)

MODULE = "selection-process"

PROCESS_TYPE_READ = f"{MODULE}:process-type:read"
PROCESS_TYPE_MANAGE = f"{MODULE}:process-type:manage"
PROCESS_READ = f"{MODULE}:process:read"
PROCESS_MANAGE = f"{MODULE}:process:manage"
PANEL_MANAGE = f"{MODULE}:panel:manage"
CANDIDATE_READ = f"{MODULE}:candidate:read"
CANDIDATE_READ_ALL = f"{MODULE}:candidate:read-all"
CANDIDATE_MANAGE = f"{MODULE}:candidate:manage"
DECISION_WRITE = f"{MODULE}:decision:write"
DECISION_MANAGE = f"{MODULE}:decision:manage"


@dataclass
class Actor:
    """Represents the calling principal."""

    user_id: str
    organisation_id: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


def _publish(db: Session, name: str, organisation_id: str, payload: dict) -> None:
    events.publish(
        db,
        f"{MODULE}.{name}",
        organisation_id,
        {"organisation_id": organisation_id, **payload},
    )


class SelectionProcessService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Process Types
    # ------------------------------------------------------------------

    def list_process_types(self, actor: Actor) -> list[dict]:
        types = repo.list_process_types(self.db, actor.organisation_id)
        result = []
        for t in types:
            count = repo.count_processes_for_type(self.db, actor.organisation_id, t.id)
            result.append(
                {
                    "id": t.id,
                    "organisation_id": t.organisation_id,
                    "name": t.name,
                    "description": t.description,
                    "process_count": count,
                    "created_at": iso(t.created_at),
                }
            )
        return result

    def create_process_type(self, actor: Actor, data: dict) -> dict:
        existing = repo.get_process_type_by_name(self.db, actor.organisation_id, data["name"])
        if existing:
            raise ConflictError("name_conflict", f"Process type '{data['name']}' already exists")

        model = ProcessTypeModel(
            organisation_id=actor.organisation_id,
            name=data["name"],
            description=data.get("description"),
            created_at=utcnow(),
        )
        self.db.add(model)
        try:
            self.db.commit()
        except IntegrityError as err:
            self.db.rollback()
            raise ConflictError("name_conflict", "Process type name already in use") from err

        self.db.refresh(model)
        return {
            "id": model.id,
            "organisation_id": model.organisation_id,
            "name": model.name,
            "description": model.description,
            "process_count": 0,
            "created_at": iso(model.created_at),
        }

    def update_process_type(self, actor: Actor, type_id: str, data: dict) -> dict:
        t = repo.get_process_type(self.db, actor.organisation_id, type_id)
        if not t:
            raise NotFoundError("Process type not found")

        if "name" in data and data["name"] is not None:
            t.name = data["name"]
        if "description" in data:
            t.description = data["description"]

        try:
            self.db.commit()
        except IntegrityError as err:
            self.db.rollback()
            raise ConflictError("name_conflict", "Process type name already in use") from err

        self.db.refresh(t)
        count = repo.count_processes_for_type(self.db, actor.organisation_id, t.id)
        return {
            "id": t.id,
            "organisation_id": t.organisation_id,
            "name": t.name,
            "description": t.description,
            "process_count": count,
            "created_at": iso(t.created_at),
        }

    def delete_process_type(self, actor: Actor, type_id: str) -> None:
        t = repo.get_process_type(self.db, actor.organisation_id, type_id)
        if not t:
            raise NotFoundError("Process type not found")

        count = repo.count_processes_for_type(self.db, actor.organisation_id, type_id)
        if count > 0:
            raise ConflictError("processes_exist", "Processes still use this type")

        self.db.delete(t)
        self.db.commit()

    # ------------------------------------------------------------------
    # Processes
    # ------------------------------------------------------------------

    def _serialize_process(self, p: ProcessModel) -> dict:
        stages = repo.list_stages_for_process(self.db, p.organisation_id, p.id)
        panels = repo.list_panels_for_process(self.db, p.organisation_id, p.id)
        candidate_count = repo.count_candidates_for_process(self.db, p.organisation_id, p.id)

        return {
            "id": p.id,
            "organisation_id": p.organisation_id,
            "type_id": p.type_id,
            "title": p.title,
            "academic_year": p.academic_year,
            "context": p.context,
            "status": p.status,
            "stages": [
                {
                    "id": s.id,
                    "process_id": s.process_id,
                    "name": s.name,
                    "sequence": s.sequence,
                    "description": s.description,
                }
                for s in stages
            ],
            "panels": [
                {
                    "id": pan.id,
                    "process_id": pan.process_id,
                    "stage_id": pan.stage_id,
                    "name": pan.name,
                    "member_person_ids": pan.member_person_ids or [],
                }
                for pan in panels
            ],
            "candidate_count": candidate_count,
            "created_at": iso(p.created_at),
            "updated_at": iso(p.updated_at),
        }

    def list_processes(
        self,
        actor: Actor,
        *,
        type_id: str | None = None,
        statuses: list[str] | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        limit = max(1, min(page_size, 200))
        offset = (max(1, page) - 1) * limit
        items, total = repo.list_processes(
            self.db,
            actor.organisation_id,
            type_id=type_id,
            statuses=statuses,
            q=q,
            limit=limit,
            offset=offset,
        )
        return {
            "items": [self._serialize_process(p) for p in items],
            "total": total,
            "page": page,
            "page_size": limit,
        }

    def create_process(self, actor: Actor, data: dict) -> dict:
        ptype = repo.get_process_type(self.db, actor.organisation_id, data["type_id"])
        if not ptype:
            raise NotFoundError("Process type not found")

        process = ProcessModel(
            organisation_id=actor.organisation_id,
            type_id=data["type_id"],
            title=data["title"],
            academic_year=data.get("academic_year"),
            context=data.get("context"),
            status=ProcessStatus.DRAFT.value,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        self.db.add(process)
        self.db.flush()

        # Add initial stages if provided
        stages_data = data.get("stages") or []
        for s in stages_data:
            stage = StageModel(
                organisation_id=actor.organisation_id,
                process_id=process.id,
                name=s["name"],
                sequence=s["sequence"],
                description=s.get("description"),
                created_at=utcnow(),
            )
            self.db.add(stage)

        self.db.commit()
        self.db.refresh(process)
        return self._serialize_process(process)

    def get_process(self, actor: Actor, process_id: str) -> dict:
        p = repo.get_process(self.db, actor.organisation_id, process_id)
        if not p:
            raise NotFoundError("Process not found")
        return self._serialize_process(p)

    def update_process(self, actor: Actor, process_id: str, data: dict) -> dict:
        p = repo.get_process(self.db, actor.organisation_id, process_id)
        if not p:
            raise NotFoundError("Process not found")

        if "title" in data and data["title"] is not None:
            p.title = data["title"]
        if "academic_year" in data:
            p.academic_year = data["academic_year"]
        p.updated_at = utcnow()

        self.db.commit()
        self.db.refresh(p)
        return self._serialize_process(p)

    def delete_process(self, actor: Actor, process_id: str) -> None:
        p = repo.get_process(self.db, actor.organisation_id, process_id)
        if not p:
            raise NotFoundError("Process not found")

        if p.status != ProcessStatus.DRAFT.value:
            raise ConflictError("process_not_draft", "Process is not a draft")

        cand_count = repo.count_candidates_for_process(self.db, actor.organisation_id, process_id)
        if cand_count > 0:
            raise ConflictError("process_has_candidates", "Process has candidates")

        self.db.delete(p)
        self.db.commit()

    def replace_stages(self, actor: Actor, process_id: str, stages_data: list[dict]) -> list[dict]:
        p = repo.get_process(self.db, actor.organisation_id, process_id)
        if not p:
            raise NotFoundError("Process not found")

        if p.status != ProcessStatus.DRAFT.value:
            raise ProcessNotDraftError()

        # Delete old stages
        old_stages = repo.list_stages_for_process(self.db, actor.organisation_id, process_id)
        for s in old_stages:
            self.db.delete(s)
        self.db.flush()

        # Add new stages
        new_stages = []
        for s in stages_data:
            stage = StageModel(
                organisation_id=actor.organisation_id,
                process_id=process_id,
                name=s["name"],
                sequence=s["sequence"],
                description=s.get("description"),
                created_at=utcnow(),
            )
            self.db.add(stage)
            new_stages.append(stage)

        p.updated_at = utcnow()
        self.db.commit()

        # Reload ordered
        stages = repo.list_stages_for_process(self.db, actor.organisation_id, process_id)
        return [
            {
                "id": s.id,
                "process_id": s.process_id,
                "name": s.name,
                "sequence": s.sequence,
                "description": s.description,
            }
            for s in stages
        ]

    def open_process(self, actor: Actor, process_id: str) -> dict:
        p = repo.get_process(self.db, actor.organisation_id, process_id)
        if not p:
            raise NotFoundError("Process not found")

        if p.status != ProcessStatus.DRAFT.value:
            raise ProcessNotDraftError("Process is not a draft")

        stages = repo.list_stages_for_process(self.db, actor.organisation_id, process_id)
        if not stages:
            raise NoStagesError("Process has no stages")

        p.status = ProcessStatus.OPEN.value
        p.updated_at = utcnow()
        self.db.commit()
        self.db.refresh(p)
        return self._serialize_process(p)

    def close_process(self, actor: Actor, process_id: str) -> dict:
        p = repo.get_process(self.db, actor.organisation_id, process_id)
        if not p:
            raise NotFoundError("Process not found")

        p.status = ProcessStatus.CLOSED.value
        p.updated_at = utcnow()
        self.db.commit()
        self.db.refresh(p)
        return self._serialize_process(p)

    # ------------------------------------------------------------------
    # Panels
    # ------------------------------------------------------------------

    def list_panels(self, actor: Actor, process_id: str) -> list[dict]:
        p = repo.get_process(self.db, actor.organisation_id, process_id)
        if not p:
            raise NotFoundError("Process not found")

        panels = repo.list_panels_for_process(self.db, actor.organisation_id, process_id)
        return [
            {
                "id": pan.id,
                "process_id": pan.process_id,
                "stage_id": pan.stage_id,
                "name": pan.name,
                "member_person_ids": pan.member_person_ids or [],
            }
            for pan in panels
        ]

    def create_panel(self, actor: Actor, process_id: str, data: dict) -> dict:
        p = repo.get_process(self.db, actor.organisation_id, process_id)
        if not p:
            raise NotFoundError("Process not found")

        stage_id = data.get("stage_id")
        if stage_id:
            stage = repo.get_stage(self.db, actor.organisation_id, stage_id)
            if not stage or stage.process_id != process_id:
                raise NotFoundError("Stage not found on process")

        panel = PanelModel(
            organisation_id=actor.organisation_id,
            process_id=process_id,
            stage_id=stage_id,
            name=data["name"],
            member_person_ids=data.get("member_person_ids") or [],
            created_at=utcnow(),
        )
        self.db.add(panel)
        self.db.commit()
        self.db.refresh(panel)
        return {
            "id": panel.id,
            "process_id": panel.process_id,
            "stage_id": panel.stage_id,
            "name": panel.name,
            "member_person_ids": panel.member_person_ids or [],
        }

    def update_panel(self, actor: Actor, panel_id: str, data: dict) -> dict:
        panel = repo.get_panel(self.db, actor.organisation_id, panel_id)
        if not panel:
            raise NotFoundError("Panel not found")

        if "name" in data and data["name"] is not None:
            panel.name = data["name"]
        if "stage_id" in data:
            panel.stage_id = data["stage_id"]
        if "member_person_ids" in data and data["member_person_ids"] is not None:
            panel.member_person_ids = data["member_person_ids"]

        self.db.commit()
        self.db.refresh(panel)
        return {
            "id": panel.id,
            "process_id": panel.process_id,
            "stage_id": panel.stage_id,
            "name": panel.name,
            "member_person_ids": panel.member_person_ids or [],
        }

    def delete_panel(self, actor: Actor, panel_id: str) -> None:
        panel = repo.get_panel(self.db, actor.organisation_id, panel_id)
        if not panel:
            raise NotFoundError("Panel not found")

        self.db.delete(panel)
        self.db.commit()

    # ------------------------------------------------------------------
    # Candidates
    # ------------------------------------------------------------------

    def _serialize_candidate(self, c: CandidateModel) -> dict:
        decisions = repo.list_decisions_for_candidate(self.db, c.organisation_id, c.id)
        return {
            "id": c.id,
            "process_id": c.process_id,
            "organisation_id": c.organisation_id,
            "person_id": c.person_id,
            "status": c.status,
            "current_stage_id": c.current_stage_id,
            "source": c.source,
            "decisions": [
                {
                    "id": d.id,
                    "candidate_id": d.candidate_id,
                    "stage_id": d.stage_id,
                    "panel_id": d.panel_id,
                    "decided_by": d.decided_by,
                    "outcome": d.outcome,
                    "score": d.score,
                    "comments": d.comments,
                    "decided_at": iso(d.decided_at),
                }
                for d in decisions
            ],
            "registered_at": iso(c.registered_at),
            "decided_at": iso(c.decided_at),
        }

    def register_candidate(self, actor: Actor, process_id: str, data: dict) -> dict:
        p = repo.get_process(self.db, actor.organisation_id, process_id)
        if not p:
            raise NotFoundError("Process not found")

        if p.status != ProcessStatus.OPEN.value:
            raise ProcessNotOpenError()

        person_id = data["person_id"]

        # Duplicate candidate check
        existing = repo.get_candidate_by_person(self.db, actor.organisation_id, process_id, person_id)
        if existing:
            raise DuplicateCandidateError()

        stages = repo.list_stages_for_process(self.db, actor.organisation_id, process_id)
        first_stage_id = stages[0].id if stages else None

        cand = CandidateModel(
            organisation_id=actor.organisation_id,
            process_id=process_id,
            person_id=person_id,
            current_stage_id=first_stage_id,
            status=CandidateStatus.REGISTERED.value,
            source=data.get("source"),
            registered_at=utcnow(),
        )
        self.db.add(cand)

        try:
            self.db.flush()
        except IntegrityError as err:
            self.db.rollback()
            raise DuplicateCandidateError() from err

        # Emit registered event
        _publish(
            self.db,
            "candidate.registered",
            actor.organisation_id,
            {
                "process_id": process_id,
                "candidate_id": cand.id,
                "person_id": person_id,
            },
        )

        self.db.commit()
        self.db.refresh(cand)
        return self._serialize_candidate(cand)

    def list_candidates(
        self,
        actor: Actor,
        process_id: str,
        *,
        scope: str = "mine",
        statuses: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        limit = max(1, min(page_size, 200))
        offset = (max(1, page) - 1) * limit

        if scope == "mine":
            items, total = repo.list_candidates(
                self.db,
                actor.organisation_id,
                process_id=process_id,
                person_id=actor.user_id,
                statuses=statuses,
                limit=limit,
                offset=offset,
            )
        else:
            # scope == "managed"
            if actor.can(CANDIDATE_READ_ALL) or actor.can(PROCESS_MANAGE):
                items, total = repo.list_candidates(
                    self.db,
                    actor.organisation_id,
                    process_id=process_id,
                    statuses=statuses,
                    limit=limit,
                    offset=offset,
                )
            else:
                items, total = repo.list_candidates_for_panelist(
                    self.db,
                    actor.organisation_id,
                    process_id,
                    actor.user_id,
                    statuses=statuses,
                    limit=limit,
                    offset=offset,
                )

        return {
            "items": [self._serialize_candidate(c) for c in items],
            "total": total,
            "page": page,
            "page_size": limit,
        }

    def get_candidate(self, actor: Actor, candidate_id: str) -> dict:
        c = repo.get_candidate(self.db, actor.organisation_id, candidate_id)
        if not c:
            raise NotFoundError("Candidate not found")
        return self._serialize_candidate(c)

    def withdraw_candidate(self, actor: Actor, candidate_id: str) -> dict:
        c = repo.get_candidate(self.db, actor.organisation_id, candidate_id)
        if not c:
            raise NotFoundError("Candidate not found")

        if c.status in FINAL_CANDIDATE_STATUSES:
            raise CandidateFinalizedError()

        c.status = CandidateStatus.WITHDRAWN.value
        c.decided_at = utcnow()

        _publish(
            self.db,
            "candidate.withdrawn",
            actor.organisation_id,
            {
                "process_id": c.process_id,
                "candidate_id": c.id,
            },
        )

        self.db.commit()
        self.db.refresh(c)
        return self._serialize_candidate(c)

    # ------------------------------------------------------------------
    # Decisions & Stage Progression
    # ------------------------------------------------------------------

    def list_decisions(self, actor: Actor, candidate_id: str) -> list[dict]:
        c = repo.get_candidate(self.db, actor.organisation_id, candidate_id)
        if not c:
            raise NotFoundError("Candidate not found")

        decisions = repo.list_decisions_for_candidate(self.db, actor.organisation_id, candidate_id)
        return [
            {
                "id": d.id,
                "candidate_id": d.candidate_id,
                "stage_id": d.stage_id,
                "panel_id": d.panel_id,
                "decided_by": d.decided_by,
                "outcome": d.outcome,
                "score": d.score,
                "comments": d.comments,
                "decided_at": iso(d.decided_at),
            }
            for d in decisions
        ]

    def record_decision(self, actor: Actor, candidate_id: str, data: dict) -> dict:
        c = repo.get_candidate(self.db, actor.organisation_id, candidate_id)
        if not c:
            raise NotFoundError("Candidate not found")

        if c.status in FINAL_CANDIDATE_STATUSES:
            raise CandidateFinalizedError()

        if not c.current_stage_id:
            raise ConflictError("no_current_stage", "Candidate has no active stage")

        stage_id = c.current_stage_id

        # Panelist decision uniqueness check
        existing = repo.get_decision_by_panelist(self.db, actor.organisation_id, candidate_id, stage_id, actor.user_id)
        if existing:
            raise AlreadyDecidedError()

        outcome = data["outcome"]
        score = data.get("score")
        comments = data.get("comments")

        # Find panel for current stage if applicable
        panels = repo.list_panels_for_process(self.db, actor.organisation_id, c.process_id)
        matching_panel_id = None
        for p in panels:
            if actor.user_id in (p.member_person_ids or []):
                if p.stage_id == stage_id or p.stage_id is None:
                    matching_panel_id = p.id
                    break

        dec_model = DecisionModel(
            organisation_id=actor.organisation_id,
            candidate_id=candidate_id,
            stage_id=stage_id,
            panel_id=matching_panel_id,
            decided_by=actor.user_id,
            outcome=outcome,
            score=score,
            comments=comments,
            decided_at=utcnow(),
        )
        self.db.add(dec_model)

        # Stage progression
        stages = repo.list_stages_for_process(self.db, actor.organisation_id, c.process_id)
        stage_ids = [s.id for s in stages]

        try:
            current_idx = stage_ids.index(stage_id)
        except ValueError:
            current_idx = -1

        if outcome == DecisionOutcome.ADVANCE.value:
            if current_idx >= 0 and current_idx == len(stage_ids) - 1:
                # Last stage -> candidate is SELECTED
                c.status = CandidateStatus.SELECTED.value
                c.decided_at = utcnow()
                _publish(
                    self.db,
                    "candidate.finalized",
                    actor.organisation_id,
                    {
                        "process_id": c.process_id,
                        "candidate_id": c.id,
                        "person_id": c.person_id,
                        "outcome": CandidateStatus.SELECTED.value,
                    },
                )
            elif current_idx >= 0:
                # Advance to next stage
                c.current_stage_id = stage_ids[current_idx + 1]
                c.status = CandidateStatus.IN_PROGRESS.value
            else:
                c.status = CandidateStatus.IN_PROGRESS.value
        elif outcome == DecisionOutcome.HOLD.value:
            c.status = CandidateStatus.IN_PROGRESS.value
        elif outcome == DecisionOutcome.REJECT.value:
            c.status = CandidateStatus.REJECTED.value
            c.decided_at = utcnow()
            _publish(
                self.db,
                "candidate.finalized",
                actor.organisation_id,
                {
                    "process_id": c.process_id,
                    "candidate_id": c.id,
                    "person_id": c.person_id,
                    "outcome": CandidateStatus.REJECTED.value,
                },
            )

        # Emit decision recorded
        _publish(
            self.db,
            "decision.recorded",
            actor.organisation_id,
            {
                "process_id": c.process_id,
                "candidate_id": c.id,
                "stage_id": stage_id,
                "outcome": outcome,
            },
        )

        try:
            self.db.commit()
        except IntegrityError as err:
            self.db.rollback()
            raise AlreadyDecidedError() from err

        self.db.refresh(dec_model)
        return {
            "id": dec_model.id,
            "candidate_id": dec_model.candidate_id,
            "stage_id": dec_model.stage_id,
            "panel_id": dec_model.panel_id,
            "decided_by": dec_model.decided_by,
            "outcome": dec_model.outcome,
            "score": dec_model.score,
            "comments": dec_model.comments,
            "decided_at": iso(dec_model.decided_at),
        }

    def finalize_candidate(self, actor: Actor, candidate_id: str, data: dict) -> dict:
        c = repo.get_candidate(self.db, actor.organisation_id, candidate_id)
        if not c:
            raise NotFoundError("Candidate not found")

        if c.status in FINAL_CANDIDATE_STATUSES:
            raise CandidateFinalizedError()

        outcome = data["outcome"]
        c.status = outcome
        c.decided_at = utcnow()

        _publish(
            self.db,
            "candidate.finalized",
            actor.organisation_id,
            {
                "process_id": c.process_id,
                "candidate_id": c.id,
                "person_id": c.person_id,
                "outcome": outcome,
            },
        )

        self.db.commit()
        self.db.refresh(c)
        return self._serialize_candidate(c)

    # ------------------------------------------------------------------
    # Slots (Upcoming Events)
    # ------------------------------------------------------------------

    def list_upcoming_slots(self, actor: Actor, candidate_id: str | None = None, limit: int = 10) -> list[dict]:
        slots = repo.list_upcoming_slots(self.db, actor.organisation_id, candidate_id=candidate_id, limit=limit)
        return [
            {
                "id": s.id,
                "process_id": s.process_id,
                "stage_id": s.stage_id,
                "candidate_id": s.candidate_id,
                "title": s.title,
                "starts_at": iso(s.starts_at),
                "ends_at": iso(s.ends_at),
                "status": s.status,
                "location": s.location,
            }
            for s in slots
        ]

    def create_slot(self, actor: Actor, process_id: str, data: dict) -> dict:
        p = repo.get_process(self.db, actor.organisation_id, process_id)
        if not p:
            raise NotFoundError("Process not found")

        slot = SlotModel(
            organisation_id=actor.organisation_id,
            process_id=process_id,
            stage_id=data.get("stage_id"),
            candidate_id=data.get("candidate_id"),
            title=data["title"],
            starts_at=datetime.fromisoformat(data["starts_at"])
            if isinstance(data["starts_at"], str)
            else data["starts_at"],
            ends_at=datetime.fromisoformat(data["ends_at"]) if isinstance(data["ends_at"], str) else data["ends_at"],
            status=data.get("status", SlotStatus.SCHEDULED.value),
            location=data.get("location"),
            created_at=utcnow(),
        )
        self.db.add(slot)
        self.db.commit()
        self.db.refresh(slot)
        return {
            "id": slot.id,
            "process_id": slot.process_id,
            "stage_id": slot.stage_id,
            "candidate_id": slot.candidate_id,
            "title": slot.title,
            "starts_at": iso(slot.starts_at),
            "ends_at": iso(slot.ends_at),
            "status": slot.status,
            "location": slot.location,
        }
