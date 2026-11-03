import logging
import os
import tempfile
from pathlib import Path

os.environ.setdefault("EOS_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/workflow-test.db")
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[4]))

import pytest
from eos_core.db import SessionLocal, init_db
from eos_core.events import OutboxEvent
from eos_core.tenant import platform_scope
from eos_workflow.api.router import router
from eos_workflow.domain.models import ApprovalChain, ApprovalStep, WorkflowAction, WorkflowRequest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete
from workflow_support import PREFIX


@pytest.fixture(scope="session", autouse=True)
def _workflow_tables():
    init_db()


@pytest.fixture(autouse=True)
def _workflow_clean():
    with platform_scope(), SessionLocal() as s:
        if s.get_bind().dialect.name != "sqlite":
            return
        s.execute(delete(WorkflowAction))
        s.execute(delete(WorkflowRequest))
        s.execute(delete(ApprovalStep))
        s.execute(delete(ApprovalChain))
        s.execute(delete(OutboxEvent))
        s.commit()


@pytest.fixture(autouse=True)
def _workflow_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("WORKFLOW_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def _workflow_loggers_enabled():
    for name, logger in logging.Logger.manager.loggerDict.items():
        if name.startswith("eos") and isinstance(logger, logging.Logger):
            logger.disabled = False


@pytest.fixture
def workflow_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def workflow_client():
    app = FastAPI()
    app.include_router(router, prefix=PREFIX)
    with TestClient(app) as c:
        yield c
