"""NUL characters never reach the database. Postgres text cannot hold them (a 500 there); SQLite can, so without these
checks the bug would only show in production."""

import pytest
from conftest import BASE
from eos_amc_vendor_support.api import schemas as s
from pydantic import ValidationError


def test_request_bodies_refuse_nul_anywhere():
    with pytest.raises(ValidationError, match="NUL"):
        s.ContractUpdateInput(title="Lift\u0000AMC")
    with pytest.raises(ValidationError, match="NUL"):
        s.ContractUpdateInput(vendor_contacts=[{"name": "Desk\u0000"}])


def test_nul_in_the_url_is_refused_before_the_database(client, org):
    _, headers = org.user("amc-vendor-support-viewer")
    assert client.get(f"{BASE}/contracts/a%00b", headers=headers).status_code == 404
    refused = client.get(f"{BASE}/contracts?q=a%00b", headers=headers)
    assert (refused.status_code, refused.json()["detail"]["code"]) == (422, "invalid_query")
