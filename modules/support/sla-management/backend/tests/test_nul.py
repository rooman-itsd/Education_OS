"""NUL characters never reach the database. Postgres text cannot hold them (a 500 there); SQLite can, so without these
checks the bug would only show in production."""

import pytest
from conftest import BASE
from eos_sla_management.api import schemas as s
from pydantic import ValidationError


def test_request_bodies_refuse_nul_anywhere():
    with pytest.raises(ValidationError, match="NUL"):
        s.CalendarUpdateInput(name="Office\u0000hours")


def test_nul_in_the_url_is_refused_before_the_database(client, org):
    _, headers = org.user("sla-management-admin")
    assert client.get(f"{BASE}/calendars/a%00b", headers=headers).status_code in (404, 422)
    refused = client.get(f"{BASE}/clocks?ticket_id=a%00b", headers=headers)
    assert (refused.status_code, refused.json()["detail"]["code"]) == (422, "invalid_query")
