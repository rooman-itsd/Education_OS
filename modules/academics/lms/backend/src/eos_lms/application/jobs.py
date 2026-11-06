"""The job for the scheduler platform service (FR-9): submit, as the system, every quiz attempt still running past its
deadline (the earlier of its time limit and the quiz's closing time). It runs across organisations in platform scope;
each event still carries its own organisation_id. Attempts are also settled whenever a request looks at them
(application/scoring.py), so the job only makes the submission prompt. Until platform/scheduler exists, a host app may
call submit_overdue_attempts() on a timer."""

from __future__ import annotations

from eos_core.tenant import platform_scope
from sqlalchemy.orm import Session

from ..infrastructure import repository as repo
from . import common as c
from . import scoring


def submit_overdue_attempts(db: Session) -> int:
    """Returns how many attempts were submitted."""
    with platform_scope():
        overdue = repo.overdue_attempts(db, c.clock())
        scoring.settle(db, overdue)
        db.commit()
    return len(overdue)
