import os
import tempfile
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/hr_payroll_test.db"  # never a real database
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))  # every permissions.yaml

import pytest
from hp_support import NOW, Org


@pytest.fixture(scope="session")
def client():
    """The module alone: no other module is needed for its tests to pass (module standard)."""
    from eos_core.db import init_db
    from eos_hr_payroll.api.router import router
    from eos_hr_payroll.infrastructure import models  # noqa: F401  registers the tables
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    init_db()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/hr-payroll")
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    from eos_hr_payroll.application import common

    monkeypatch.setattr(common, "clock", lambda: NOW)
    for key in ("LEAVE_YEAR_START_MONTH", "PAYROLL_DUE_DAY", "CURRENCY"):
        monkeypatch.delenv(f"HR_PAYROLL_{key}", raising=False)


@pytest.fixture
def org():
    return Org()


@pytest.fixture
def other_org():
    return Org()
