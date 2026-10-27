"""On Postgres, a request's queries run with the caller's organisation and no RLS bypass: the pre-auth user
lookup (platform scope) must not leave its transaction, and its bypass setting, open for the rest of the request."""

import pytest
from eos_backend.main import create_app
from eos_core.db import get_db
from eos_core.settings import settings
from eos_identity.api.deps import Principal, current_principal
from eos_testing import register_and_login
from eos_testing.tenancy import auth
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(not settings.is_postgres, reason="row-level security settings are a Postgres feature")

probe = APIRouter()


@probe.get("/scope")
def scope(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    """What the database sees for this request's queries, after authentication."""
    bypass, org = db.execute(
        text("SELECT current_setting('app.bypass_rls', true), current_setting('app.organisation_id', true)")
    ).one()
    return {"bypass": bypass, "organisation": org, "principal_org": p.organisation_id}


def test_a_request_runs_as_its_organisation_with_bypass_off():
    app = create_app(extra_routers={"lms": probe})  # lms is in the trial plan, so the gate lets the probe through
    with TestClient(app) as client:
        a = register_and_login(client, slug="scope-probe", academy_type="music-academy")
        r = client.get("/api/v1/lms/scope", headers=auth(a["token"]))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["organisation"] == a["org"]["id"] == body["principal_org"]
        assert body["bypass"] == "off"
