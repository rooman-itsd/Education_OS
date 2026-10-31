"""HTTP surface of selection-process, matching contracts/openapi.yaml.
Mounted under /api/v1/selection-process."""

from __future__ import annotations

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from ..application.service import (
    CANDIDATE_MANAGE,
    CANDIDATE_READ,
    DECISION_MANAGE,
    DECISION_WRITE,
    PANEL_MANAGE,
    PROCESS_MANAGE,
    PROCESS_READ,
    PROCESS_TYPE_MANAGE,
    PROCESS_TYPE_READ,
    Actor,
    SelectionProcessService,
)
from ..domain.models import DomainError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["selection-process"])


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except DomainError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"code": e.code, "message": e.message},
        ) from e


# ------------------------------------------------------------------
# Process Types
# ------------------------------------------------------------------


@router.get("/process-types")
def list_process_types(
    actor: Actor = Depends(require(PROCESS_TYPE_READ)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.list_process_types, actor)


@router.post("/process-types", status_code=status.HTTP_201_CREATED)
def create_process_type(
    body: s.ProcessTypeInput,
    actor: Actor = Depends(require(PROCESS_TYPE_MANAGE)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.create_process_type, actor, body.model_dump())


@router.patch("/process-types/{id}")
def update_process_type(
    id: str,
    body: s.ProcessTypeInput,
    actor: Actor = Depends(require(PROCESS_TYPE_MANAGE)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.update_process_type, actor, id, body.model_dump(exclude_unset=True))


@router.delete("/process-types/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_process_type(
    id: str,
    actor: Actor = Depends(require(PROCESS_TYPE_MANAGE)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    _run(svc.delete_process_type, actor, id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------
# Processes
# ------------------------------------------------------------------


@router.get("/processes")
def list_processes(
    type_id: str | None = Query(default=None),
    status: list[str] | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    actor: Actor = Depends(require(PROCESS_READ)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(
        svc.list_processes,
        actor,
        type_id=type_id,
        statuses=status,
        q=q,
        page=page,
        page_size=page_size,
    )


@router.post("/processes", status_code=status.HTTP_201_CREATED)
def create_process(
    body: s.ProcessInput,
    actor: Actor = Depends(require(PROCESS_MANAGE)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.create_process, actor, body.model_dump())


@router.get("/processes/{id}")
def get_process(
    id: str,
    actor: Actor = Depends(require(PROCESS_READ)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.get_process, actor, id)


@router.patch("/processes/{id}")
def update_process(
    id: str,
    body: s.ProcessUpdate,
    actor: Actor = Depends(require(PROCESS_MANAGE)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.update_process, actor, id, body.model_dump(exclude_unset=True))


@router.delete("/processes/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_process(
    id: str,
    actor: Actor = Depends(require(PROCESS_MANAGE)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    _run(svc.delete_process, actor, id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/processes/{id}/stages")
def replace_stages(
    id: str,
    body: list[s.StageInput],
    actor: Actor = Depends(require(PROCESS_MANAGE)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.replace_stages, actor, id, [s.model_dump() for s in body])


@router.post("/processes/{id}/open")
def open_process(
    id: str,
    actor: Actor = Depends(require(PROCESS_MANAGE)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.open_process, actor, id)


@router.post("/processes/{id}/close")
def close_process(
    id: str,
    actor: Actor = Depends(require(PROCESS_MANAGE)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.close_process, actor, id)


# ------------------------------------------------------------------
# Panels
# ------------------------------------------------------------------


@router.get("/processes/{id}/panels")
def list_panels(
    id: str,
    actor: Actor = Depends(require(PROCESS_READ)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.list_panels, actor, id)


@router.post("/processes/{id}/panels", status_code=status.HTTP_201_CREATED)
def create_panel(
    id: str,
    body: s.PanelInput,
    actor: Actor = Depends(require(PANEL_MANAGE)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.create_panel, actor, id, body.model_dump())


@router.patch("/panels/{id}")
def update_panel(
    id: str,
    body: s.PanelInput,
    actor: Actor = Depends(require(PANEL_MANAGE)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.update_panel, actor, id, body.model_dump(exclude_unset=True))


@router.delete("/panels/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_panel(
    id: str,
    actor: Actor = Depends(require(PANEL_MANAGE)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    _run(svc.delete_panel, actor, id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------
# Candidates
# ------------------------------------------------------------------


@router.get("/processes/{id}/candidates")
def list_candidates(
    id: str,
    scope: str = Query(default="mine", pattern="^(mine|managed)$"),
    status: list[str] | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    actor: Actor = Depends(require(CANDIDATE_READ)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(
        svc.list_candidates,
        actor,
        id,
        scope=scope,
        statuses=status,
        page=page,
        page_size=page_size,
    )


@router.post("/processes/{id}/candidates", status_code=status.HTTP_201_CREATED)
def register_candidate(
    id: str,
    body: s.CandidateInput,
    actor: Actor = Depends(require(CANDIDATE_MANAGE)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.register_candidate, actor, id, body.model_dump())


@router.get("/candidates/{id}")
def get_candidate(
    id: str,
    actor: Actor = Depends(require(CANDIDATE_READ)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.get_candidate, actor, id)


@router.post("/candidates/{id}/withdraw")
def withdraw_candidate(
    id: str,
    actor: Actor = Depends(require(CANDIDATE_MANAGE)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.withdraw_candidate, actor, id)


# ------------------------------------------------------------------
# Decisions & Finalize
# ------------------------------------------------------------------


@router.get("/candidates/{id}/decisions")
def list_decisions(
    id: str,
    actor: Actor = Depends(require(CANDIDATE_READ)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.list_decisions, actor, id)


@router.post("/candidates/{id}/decisions", status_code=status.HTTP_201_CREATED)
def record_decision(
    id: str,
    body: s.DecisionInput,
    actor: Actor = Depends(require(DECISION_WRITE)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.record_decision, actor, id, body.model_dump())


@router.post("/candidates/{id}/finalize")
def finalize_candidate(
    id: str,
    body: s.FinalizeInput,
    actor: Actor = Depends(require(DECISION_MANAGE)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.finalize_candidate, actor, id, body.model_dump())


# ------------------------------------------------------------------
# Slots (Upcoming Events)
# ------------------------------------------------------------------


@router.get("/slots/upcoming")
def list_upcoming_slots(
    candidate_id: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    actor: Actor = Depends(require(PROCESS_READ, CANDIDATE_READ)),
    db: Session = Depends(get_db),
):
    svc = SelectionProcessService(db)
    return _run(svc.list_upcoming_slots, actor, candidate_id=candidate_id, limit=limit)
