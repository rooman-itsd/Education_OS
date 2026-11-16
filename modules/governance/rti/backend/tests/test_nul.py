"""NUL characters never reach the database. Postgres text cannot hold them (a 500 there); SQLite can, so without these
checks the bug would only show in production."""

import pytest
from conftest import BASE
from eos_rti.api import schemas as s
from pydantic import ValidationError


def test_request_bodies_refuse_nul_anywhere():
    with pytest.raises(ValidationError, match="NUL"):
        s.RequestUpdateInput(subject="Faculty\u0000 recruitment")
    with pytest.raises(ValidationError, match="NUL"):
        s.RequestUpdateInput(applicant={"name": "Asha\u0000"})
    with pytest.raises(ValidationError, match="NUL"):
        s.ReplyInput(reply="\u0000")


@pytest.mark.parametrize(
    "path",
    ["/requests/a%00b", "/requests/a%00b/assign", "/requests/a%00b/close", "/referrals/a%00b/reply", "/requests/%00"],
)
def test_nul_in_a_path_id_names_no_row(client, org, path):
    _, headers = org.user("rti-officer")
    _, custodian = org.user("rti-custodian")
    method = "get" if path.count("/") == 2 and "reply" not in path else "post"
    assert client.request(method, BASE + path, json={}, headers={**headers, **custodian}).status_code in (404, 403, 405)
    response = client.request(method, BASE + path, json={"officer_id": "x", "reply": "x"}, headers=headers)
    assert response.status_code in (404, 403)


@pytest.mark.parametrize(
    "query", ["q=a%00b", "status=a%00b", "officer=a%00b", "received_via=a%00b", "cursor=1%00", "limit=1%00"]
)
def test_nul_in_the_query_is_refused_before_the_database(client, org, query):
    _, headers = org.user("rti-officer")
    assert client.get(f"{BASE}/requests?{query}", headers=headers).status_code == 422


def test_the_422_for_a_nul_in_the_query_says_why(client, org):
    _, headers = org.user("rti-officer")
    refused = client.get(f"{BASE}/requests?q=a%00b", headers=headers)
    assert refused.json()["detail"]["code"] == "invalid_query"
