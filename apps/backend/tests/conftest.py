import os
import secrets
import tempfile
from pathlib import Path

os.environ.setdefault("EOS_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")
os.environ.setdefault("EOS_DEV_MODE", "true")
# A random key per run, never the built-in development one: tests that build the app with dev mode off (test_gateway,
# test_jwt_secret) would otherwise be refused at start-up (Settings.check_secrets, security review N21).
os.environ.setdefault("EOS_JWT_SECRET", secrets.token_hex(32))
os.environ.setdefault("EOS_SUPER_ADMIN_EMAIL", "root@platform.example.com")
os.environ.setdefault("EOS_SUPER_ADMIN_PASSWORD", "RootPassw0rd!")
os.environ.setdefault("BILLING_PAYMENT_ADAPTER", "none")
os.environ.setdefault("TENANCY_AUTO_APPROVE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[3]))
# The shared client below makes every request from one address; the limiter would start refusing them part way
# through the suite. test_gateway.py builds its own app with the limiter on and small limits.
os.environ.setdefault("EOS_RATE_LIMIT_ENABLED", "false")

import pytest
from eos_backend.main import create_app
from fastapi import APIRouter
from fastapi.testclient import TestClient

# A stand-in feature module so the entitlement gate can be tested before any real module ships.
fees = APIRouter()


@fees.get("/ping")
def fees_ping():
    return {"module": "fees-accounts"}


lms = APIRouter()


@lms.get("/ping")
def lms_ping():
    return {"module": "lms"}


@pytest.fixture(scope="session")
def client():
    app = create_app(extra_routers={"fees-accounts": fees, "lms": lms})
    with TestClient(app) as c:
        yield c
