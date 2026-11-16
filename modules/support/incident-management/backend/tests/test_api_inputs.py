"""Edge inputs are refused with 422 (or 404 for ids that name nothing), never a server error: values past what the
columns hold, date-times at the calendar ends, comma lists where the contract takes one value, and cursors this module
did not hand out."""

import pytest
from conftest import incident_body, problem_body

HUGE = "x" * 10_001
YEARS = [
    "0001-01-01T00:00:00+05:00",
    "0001-01-01T00:00:00",
    "9999-12-31T23:59:59-05:00",
    "9999-12-31T23:59:59Z",
    "1999-12-31T23:59:59Z",
    "2101-01-01T00:00:00Z",
]


@pytest.mark.parametrize("started_at", YEARS)
def test_started_at_out_of_range(desk, started_at):
    response = desk.post("/incidents", incident_body(started_at=started_at), desk.responder)
    assert response.status_code == 422, response.text


def test_long_values_are_refused(desk):
    for body in (
        incident_body(title="t" * 201),
        incident_body(description="d" * 20_001),
        incident_body(affected_services=["s" * 81]),
        incident_body(affected_services=[f"s{i}" for i in range(21)]),
        incident_body(responder_ids=["22222222-2222-4222-8222-222222222222"] * 51),
    ):
        assert desk.post("/incidents", body, desk.responder).status_code == 422
    incident = desk.incident()
    ref = {"module": "m" * 61, "entity": "ticket", "id": "1", "relation": "related_ticket"}
    assert desk.post(f"/incidents/{incident['id']}/references", ref, desk.responder).status_code == 422
    ref = {"module": "helpdesk", "entity": "ticket", "id": "1" * 101, "relation": "related_ticket"}
    assert desk.post(f"/incidents/{incident['id']}/references", ref, desk.responder).status_code == 422
    assert desk.post("/problems", problem_body(title=HUGE)).status_code == 422


@pytest.mark.parametrize("due", ["0001-01-01", "9999-12-31", "2026-02-30"])
def test_due_date_out_of_range(desk, due):
    problem = desk.problem()
    body = {"description": "Upgrade", "owner_id": desk.responder_id, "due_date": due}
    assert desk.post(f"/problems/{problem['id']}/actions", body).status_code == 422


@pytest.mark.parametrize(
    "query",
    [
        "/incidents?severity=high,low",
        "/incidents?status=open,nonsense",
        "/incidents?lead=me,someone",
        "/incidents?lead=someone",
        "/incidents?problem_id=1",
        "/incidents?q=" + "q" * 201,
        "/incidents?service=" + "s" * 81,
        "/incidents?limit=0",
        "/incidents?limit=101",
        "/incidents?limit=99999999999",
        "/incidents?limit=9223372036854775808",
        "/problems?owner=x",
        "/actions?status=open,done",
        "/actions?overdue=maybe",
    ],
)
def test_bad_query_values(desk, query):
    response = desk.get(query)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    "cursor", ["garbage!", "MTAwMDAwMQ==", "LTE=", "YWJj", "x" * 500, "OTk5OTk5OTk5OTk5OTk5OTk5OTk5"]
)
@pytest.mark.parametrize("path", ["/incidents", "/problems", "/actions"])
def test_cursors_not_handed_out_are_refused(desk, path, cursor):
    response = desk.get(f"{path}?cursor={cursor}")
    assert response.status_code == 422, response.text


def test_the_largest_cursor_is_an_empty_page(desk):
    assert desk.ok(desk.get("/incidents?cursor=MTAwMDAwMA=="))["items"] == []  # offset 10**6


@pytest.mark.parametrize("bad_id", ["1", "99999999999", "9223372036854775808", "x" * 2000])
def test_unknown_ids_are_not_found(desk, bad_id):
    assert desk.get(f"/incidents/{bad_id}").status_code == 404
    assert desk.get(f"/problems/{bad_id}").status_code == 404
    assert desk.get(f"/problems/{bad_id}/rca").status_code == 404
    assert desk.post(f"/incidents/{bad_id}/status", {"status": "investigating"}).status_code == 404
