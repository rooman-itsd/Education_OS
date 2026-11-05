"""NUL characters never reach the database. Postgres text cannot hold them (a 500 there); SQLite can, so without these
checks the bug would only show in production."""

import pytest
from conftest import BASE, DESCRIPTION
from eos_grievance.api import schemas as s
from pydantic import ValidationError


def test_request_bodies_refuse_nul_anywhere():
    with pytest.raises(ValidationError, match="NUL"):
        s.UpdateInput(body="hello\u0000there")
    with pytest.raises(ValidationError, match="NUL"):
        s.GrievanceInput(track="ragging", category="x", description=DESCRIPTION, respondent={"description": "a\u0000b"})
    with pytest.raises(ValidationError):
        s.CommitteeInput(name="ab\u0000c", kind="icc")


def test_nul_in_a_request_is_a_422(campus):
    c = campus
    body = {"track": "ragging", "category": "x\u0000y", "description": DESCRIPTION}
    assert c.post("/me/grievances", body, c.complainant).status_code == 422
    assert c.post("/committees", {"name": "a\u0000b", "kind": "icc"}).status_code == 422


def test_nul_in_the_url_is_refused_before_the_database(campus):
    c = campus
    assert c.get("/grievances/a%00b", c.member()).status_code == 404
    assert c.get("/me/grievances/a%00b", c.complainant).status_code == 404
    refused = c.get("/grievances?status=a%00b", c.member())
    assert (refused.status_code, refused.json()["detail"]["code"]) == (422, "invalid_query")
    assert c.get("/grievances?cursor=%00", c.member()).status_code == 422
    assert BASE
